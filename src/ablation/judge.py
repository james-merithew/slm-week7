"""LLM-as-judge for the Behavior Spec.

Single judge used for BOTH the prompt-ceiling ablation and later base-vs-tuned
comparison (the brief requires the same rubric throughout). Judge model is
Claude (claude-opus-5) via the Anthropic API, structured output enforced with
output_config json_schema, raw verdicts persisted by the caller as JSONL.

The rubric text lives in prompts/judge_rubric.md so the judge code stays
behavior-agnostic.
"""

import json
from pathlib import Path

import anthropic

# Sonnet is sufficient here: the deterministic checker is the headline metric;
# the LLM judge only audits substance/gloss quality. Owner call 2026-08-17 (cost).
JUDGE_MODEL = "claude-sonnet-5"
PROMPTS_DIR = Path(__file__).parent / "prompts"

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "turn_verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "turn_index": {"type": "integer"},
                    "pass": {"type": "boolean"},
                    "violation": {
                        "type": "string",
                        "enum": [
                            "none",
                            "vacuous_explanation",
                            "incorrect_gloss",
                            "misbound_obligation",
                            "advice_leak",
                            "other",
                        ],
                    },
                    "reasoning": {"type": "string"},
                },
                "required": ["turn_index", "pass", "violation", "reasoning"],
                "additionalProperties": False,
            },
        },
        "conversation_pass": {"type": "boolean"},
        "summary": {"type": "string"},
    },
    "required": ["turn_verdicts", "conversation_pass", "summary"],
    "additionalProperties": False,
}


def load_rubric() -> str:
    path = PROMPTS_DIR / "judge_rubric.md"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing - write the judge rubric first.")
    return path.read_text(encoding="utf-8").strip()


def format_transcript(turns: list[dict]) -> str:
    lines = []
    assistant_i = 0
    for t in turns:
        if t["role"] == "assistant":
            lines.append(f"[ASSISTANT TURN {assistant_i}]\n{t['content']}")
            assistant_i += 1
        else:
            lines.append(f"[STUDENT]\n{t['content']}")
    return "\n\n".join(lines)


def judge_conversation(
    client: anthropic.Anthropic, turns: list[dict], scenario: dict
) -> dict:
    """Judge every assistant turn in a conversation against the rubric.

    Returns the parsed verdict dict (matches VERDICT_SCHEMA). The caller is
    responsible for persisting the raw verdict + reasoning as JSONL.
    """
    rubric = load_rubric()
    transcript = format_transcript(turns)
    scenario_note = scenario.get("judge_note", "")

    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=4096,
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": VERDICT_SCHEMA},
        },
        system=[{
            "type": "text",
            "text": (
                "You are a strict, impartial AUDIT judge for 'Benefits Notices, "
                "Explained'. A deterministic checker is the final authority on the "
                "mechanical rules (vocabulary, verbatim quotes, exact dates/amounts, "
                "scaffold, banner, softening and literal-advice tripwires) - do not "
                "re-check those. You audit only what the checker cannot see: "
                "substance, gloss correctness in context, quote-to-obligation "
                "binding, and advice-leak paraphrases. Judge ONLY against the "
                "rubric given. Every ASSISTANT turn gets its own verdict; the "
                "conversation passes only if every assistant turn passes.\n\n" + rubric
            ),
            # Identical across all judge calls; cached re-reads bill at ~0.1x.
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Scenario category: {scenario.get('category', 'clean')}\n"
                    + (f"Scenario note: {scenario_note}\n" if scenario_note else "")
                    + f"\nTranscript to judge:\n\n{transcript}"
                ),
            }
        ],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Judge refused: {response.stop_details}")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)
