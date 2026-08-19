"""Teacher calls + THE FILTER.

Every assistant turn is produced by the teacher model conditioned on the
behavior spec (system message) and the dialog so far, then run through the
deterministic checker (src.checker.check_reply) with proper cross-turn state
threading. A failing turn gets exactly ONE repair round (re-prompt with the
violation list); if the repair also fails, the whole dialog is discarded.

State-threading details that matter:
  * check_reply MUTATES its state (taught terms persist, first_reply flips),
    so each attempt is checked against a deep copy of the pre-turn state;
    the copy is adopted only when the attempt passes.
  * The repair prompt is a transient exchange - it is NOT absorbed into the
    checker state (it is not a real student turn) and is NOT stored in the
    final dialog.

Per-turn metadata policy (documented in DATASET.md):
  * turn 0: full metadata (operative_deadline, adverse_action) - the first
    reply must state the operative deadline verbatim, scaffold, and banner.
  * follow-ups: adverse_action only, EXCEPT deadline_collapse turns, which
    also carry operative_deadline (restating the earliest clock verbatim is
    the deadline-fidelity behavior those turns exist to teach).
"""
from __future__ import annotations

import copy
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from src.checker.check import ConversationState, absorb_user_turn, check_reply

from .notices import Notice
from .students import DialogScript

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "src" / "ablation" / "prompts" / "behavior_spec.md"
FEWSHOT_PATH = ROOT / "src" / "ablation" / "prompts" / "few_shot_examples.md"
BANNER_PATH = ROOT / "src" / "checker" / "data" / "banner.txt"

TEACHER_MODEL = "claude-opus-5"
MAX_TOKENS = 4096
# claude-opus-5 deprecates the temperature parameter; None = omit it.
TEMPERATURE = None
API_ATTEMPTS = 6

# spaCy pipelines are not thread-safe; serialize checker calls.
_CHECK_LOCK = threading.Lock()

_SYSTEM_CACHE: str | None = None


def build_system_prompt() -> str:
    """behavior_spec.md + few-shot examples + exact-string harness notes.

    The harness notes exist because the checker matches exact strings: the
    banner must be one single line (the spec file wraps it), quoted spans
    must be single-line verbatim substrings of the letter, and scaffold
    markers are matched character-for-character.
    """
    global _SYSTEM_CACHE
    if _SYSTEM_CACHE is not None:
        return _SYSTEM_CACHE
    spec = SPEC_PATH.read_text(encoding="utf-8")
    fewshot = FEWSHOT_PATH.read_text(encoding="utf-8")
    banner = BANNER_PATH.read_text(encoding="utf-8").strip()
    notes = f"""

---

# Worked examples

{fewshot}

---

# Output format notes (exact strings - follow these to the letter)

1. Use quotation marks ONLY around text copied character-for-character from
   the reader's letter or form. Never put quotation marks around your own
   words or paraphrases. Keep each quoted span on a single line and copy it
   exactly - capitalization, punctuation, and spacing included. To quote
   more than one line of the letter, quote each line separately.
2. Copy every date, dollar amount, and phone number character for character
   exactly as printed in the letter. Never round, shorten, or re-format
   them, and never introduce a date or amount that the letter does not
   print.
3. When the letter denies, reduces, or stops benefits, your first reply
   must contain the banner below as ONE single line, character for
   character, with no line break inside it:

{banner}

4. The three section headings of your first reply must appear character for
   character: "What this letter says", "What it asks you to do", "By when"
   (bold markers around them are fine; the heading text itself must be
   exact).
5. When your sentence mentions a date or amount that the letter ties to
   "must" / "required" / "have to", keep the word "must" (or "need to" /
   "required") in that same sentence of yours.
"""
    _SYSTEM_CACHE = spec + notes
    return _SYSTEM_CACHE


def repair_prompt(violations: list) -> str:
    """violations: list of dicts {rule, detail, message} (Verdict.to_dict form)."""
    lines = "\n".join(
        f"- {v['rule']}: {v['message']} (detail: {v['detail']})"
        for v in violations)
    return (
        "Your reply broke these rules:\n"
        f"{lines}\n\n"
        "Rewrite your entire previous reply so it is fully compliant with "
        "your instructions. Fix every violation listed above, keep everything "
        "that was already correct, and output ONLY the rewritten reply."
    )


def metadata_for_turn(notice: Notice, turn_index: int, intent: str) -> dict:
    md = notice.metadata
    if turn_index == 0:
        return {
            "operative_deadline": md.get("operative_deadline"),
            "adverse_action": md.get("adverse_action", False),
        }
    out = {"adverse_action": md.get("adverse_action", False)}
    if intent == "deadline_collapse" and md.get("operative_deadline"):
        out["operative_deadline"] = md["operative_deadline"]
    return out


@dataclass
class DialogResult:
    script: DialogScript
    accepted: bool
    messages: list = field(default_factory=list)  # user/assistant only
    repairs: int = 0
    rejected: list = field(default_factory=list)  # rejected-pair records
    discard_reason: str | None = None
    first_pass_verdicts: list = field(default_factory=list)  # per-turn dicts
    api_calls: int = 0


class Teacher:
    """Thin wrapper over the Anthropic messages API with retry/backoff."""

    def __init__(self, model: str = TEACHER_MODEL, client=None,
                 temperature: float | None = TEMPERATURE):
        self.model = model
        self.temperature = temperature
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import anthropic

            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RuntimeError("ANTHROPIC_API_KEY is not set")
            self._client = anthropic.Anthropic()
        return self._client

    def complete(self, system: str, messages: list) -> tuple[str, str]:
        """Returns (text, stop_reason). Retries transient API errors."""
        import anthropic

        last = None
        for attempt in range(API_ATTEMPTS):
            try:
                kwargs = dict(
                    model=self.model,
                    # Same system prompt every call — cached re-reads bill at
                    # ~0.1x input price.
                    system=[{"type": "text", "text": system,
                             "cache_control": {"type": "ephemeral"}}],
                    messages=messages,
                    max_tokens=MAX_TOKENS,
                )
                # claude-opus-5 rejects the temperature parameter
                # ("`temperature` is deprecated for this model").
                if self.temperature is not None:
                    kwargs["temperature"] = self.temperature
                resp = self.client.messages.create(**kwargs)
                text = "".join(
                    b.text for b in resp.content if b.type == "text")
                return text, resp.stop_reason
            except (anthropic.RateLimitError, anthropic.APIConnectionError,
                    anthropic.InternalServerError) as e:
                last = e
                time.sleep(min(2 ** attempt * 2, 60))
        raise RuntimeError(f"API retries exhausted: {last}")


def _checked(reply: str, notice_text: str, state: ConversationState,
             metadata: dict):
    """check_reply against a deep copy of state; returns (verdict, new_state)."""
    trial = copy.deepcopy(state)
    with _CHECK_LOCK:
        verdict = check_reply(reply, notice_text, trial, metadata)
    return verdict, trial


def run_dialog(teacher: Teacher, script: DialogScript,
               log=lambda msg: None) -> DialogResult:
    """Run one dialog sequentially (teacher sees prior turns), filtering every
    assistant turn through the checker with one repair round."""
    system = build_system_prompt()
    notice_text = script.notice.notice_text
    res = DialogResult(script=script, accepted=False)
    state = ConversationState()
    messages: list = []

    for ti, turn in enumerate(script.turns):
        absorb_user_turn(state, turn.text)
        messages.append({"role": "user", "content": turn.text})
        metadata = metadata_for_turn(script.notice, ti, turn.intent)

        reply, stop = teacher.complete(system, messages)
        res.api_calls += 1
        if stop == "refusal":
            res.discard_reason = "refusal"
            log(f"{script.dialog_id} t{ti}: teacher refusal -> discard")
            return res
        if stop == "max_tokens":
            res.discard_reason = "max_tokens"
            log(f"{script.dialog_id} t{ti}: truncated (max_tokens) -> discard")
            return res

        verdict, new_state = _checked(reply, notice_text, state, metadata)
        res.first_pass_verdicts.append({
            "turn_index": ti,
            "intent": turn.intent,
            **verdict.to_dict(),
        })

        if verdict.passed:
            state = new_state
            messages.append({"role": "assistant", "content": reply})
            continue

        # One repair round. The repair exchange is transient.
        log(f"{script.dialog_id} t{ti}: {len(verdict.violations)} violations,"
            " repairing")
        repair_msgs = messages + [
            {"role": "assistant", "content": reply},
            {"role": "user", "content": repair_prompt(
                [v.to_dict() for v in verdict.violations])},
        ]
        reply2, stop2 = teacher.complete(system, repair_msgs)
        res.api_calls += 1
        if stop2 == "refusal":
            res.discard_reason = "refusal"
            log(f"{script.dialog_id} t{ti}: refusal on repair -> discard")
            return res
        if stop2 == "max_tokens":
            res.discard_reason = "max_tokens"
            return res

        verdict2, new_state2 = _checked(reply2, notice_text, state, metadata)
        record = {
            "dialog_id": script.dialog_id,
            "notice_id": script.notice.notice_id,
            "turn_index": ti,
            "intent": turn.intent,
            "context_messages": list(messages),
            "rejected_reply": reply,
            "violations": [v.to_dict() for v in verdict.violations],
            "accepted_rewrite": None,
            "rewrite_violations": None,
        }
        if verdict2.passed:
            record["accepted_rewrite"] = reply2
            res.rejected.append(record)
            res.repairs += 1
            state = new_state2
            messages.append({"role": "assistant", "content": reply2})
            continue

        record["rewrite_violations"] = [v.to_dict() for v in verdict2.violations]
        record["rejected_rewrite"] = reply2
        res.rejected.append(record)
        res.discard_reason = "repair_failed"
        log(f"{script.dialog_id} t{ti}: repair failed "
            f"({len(verdict2.violations)} violations) -> discard dialog")
        return res

    res.accepted = True
    res.messages = messages
    return res
