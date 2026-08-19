"""Deterministic compliance checker for "Benefits Notices, Explained" (spec v3).

Public API:
    check_reply(reply, source_notice, state, metadata) -> Verdict
    absorb_user_turn(state, text)

Every rule lives in its own function named after the expert panel's rule name.
See RULES.md for the publishable rule document.

CLI:
    python -m src.checker.check --reply r.txt --source n.txt --state s.json
                                [--metadata m.json] [--save-state]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .build_allowed import BANNER_PATH, load_allowed
from .wordforms import expand_contractions, family

# --------------------------------------------------------------------------
# Configuration constants
# --------------------------------------------------------------------------

DEFAULT_SCAFFOLD_MARKERS = (
    "What this letter says",
    "What it asks you to do",
    "By when",
)

ADVICE_PHRASES = (
    "you should",
    "i recommend",
    "i suggest",
    "your best option",
    "if i were you",
    "i think you should",
    "you ought to",
)

QUOTE_RATIO_CAP = 0.40
MAX_NEW_TAUGHT_TERMS = 2

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"<think>.*\Z", re.DOTALL | re.IGNORECASE)

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_ORDINAL_RE = re.compile(r"^\d+(st|nd|rd|th)$", re.IGNORECASE)

# Anchor regexes (dates, dollar amounts, phone numbers) — shared by rules f/g.
_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)"
)
ANCHOR_RES = {
    "date": re.compile(
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"
        r"|\b\d{4}-\d{2}-\d{2}\b"
        rf"|\b{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b"
    ),
    # v1.1 (calibration B4): must END on a digit so "$367," never captures the
    # trailing comma (which then spuriously failed the source comparison).
    "amount": re.compile(r"\$\s?\d(?:[\d,]*\d)?(?:\.\d+)?"),
    "phone": re.compile(
        r"\b(?:1[-. ])?(?:\(\d{3}\)\s?|\d{3}[-. ])\d{3}[-. ]\d{4}\b"
    ),
}

_MODAL_SOURCE_RE = re.compile(r"\b(?:must|required|have to|has to)\b", re.IGNORECASE)
_MODAL_REPLY_RE = re.compile(
    r"\b(?:must|need to|needs to|required?|have to|has to)\b", re.IGNORECASE
)

# Gloss grammar (rule c). Detected per sentence span.
_APOSW = r"[\w'’-]+"
_GLOSS_FORMS = [
    # X — that is, GLOSS
    ("dash_that_is",
     re.compile(r"^(?P<pre>.*?)\s*[—–-]\s*that is,\s*(?P<gloss>.+?)[.?!]?$",
                re.IGNORECASE | re.DOTALL)),
    # X, which means GLOSS
    ("which_means",
     re.compile(r"^(?P<pre>.*?),\s*which means\s+(?P<gloss>.+?)[.?!]?$",
                re.IGNORECASE | re.DOTALL)),
    # X (in other words, GLOSS)
    ("in_other_words",
     re.compile(r"^(?P<pre>.*?)\s*\(\s*in other words,\s*(?P<gloss>[^)]+)\)",
                re.IGNORECASE | re.DOTALL)),
    # DESCRIPTION. This is called X.
    ("this_is_called",
     re.compile(rf"^[\"“]?This is called\s+[\"“]?(?P<term>{_APOSW}(?:\s+{_APOSW}){{0,3}})[\"”]?\s*[.?!]?[\"”]?$",
                re.IGNORECASE)),
]

# --------------------------------------------------------------------------
# spaCy (lazy singleton)
# --------------------------------------------------------------------------

_NLP = None


def get_nlp():
    global _NLP
    if _NLP is None:
        import spacy

        _NLP = spacy.load("en_core_web_sm")
    return _NLP


_ALLOWED = None


def get_allowed() -> set[str]:
    global _ALLOWED
    if _ALLOWED is None:
        _ALLOWED = load_allowed()
    return _ALLOWED


# --------------------------------------------------------------------------
# State / verdict types
# --------------------------------------------------------------------------


@dataclass
class ConversationState:
    """Cross-turn conversation state.

    user_words       expanded earned surface forms (lemma families) from user turns
    user_turn_texts  raw user turn texts (for the proper-noun verbatim rule)
    taught_terms     canonical taught terms (lowercase; multi-word kept as phrase)
    first_reply      True until the first assistant reply has been checked
    """

    user_words: set = field(default_factory=set)
    user_turn_texts: list = field(default_factory=list)
    taught_terms: list = field(default_factory=list)
    first_reply: bool = True

    # -- derived taught-term matchers ------------------------------------
    def taught_single_forms(self) -> set:
        out = set()
        for t in self.taught_terms:
            if " " not in t:
                out |= family(t)
        return out

    def taught_phrases(self) -> set:
        return {t for t in self.taught_terms if " " in t}

    # -- (de)serialization ----------------------------------------------
    @classmethod
    def from_dict(cls, d: dict) -> "ConversationState":
        st = cls(
            taught_terms=list(d.get("taught_terms", [])),
            first_reply=bool(d.get("first_reply", True)),
        )
        for turn in d.get("user_turns", []):
            absorb_user_turn(st, turn)
        return st

    def to_dict(self) -> dict:
        return {
            "user_turns": list(self.user_turn_texts),
            "taught_terms": list(self.taught_terms),
            "first_reply": self.first_reply,
        }


def absorb_user_turn(state: ConversationState, text: str) -> None:
    """Record a user turn: its raw text (proper-noun rule) and the lemma
    families of every word in it (student-word allowance, rule b)."""
    state.user_turn_texts.append(text)
    for w in _WORD_RE.findall(expand_contractions(text)):
        state.user_words |= family(w)


@dataclass
class Violation:
    rule: str
    detail: str
    message: str

    def to_dict(self) -> dict:
        return {"rule": self.rule, "detail": self.detail, "message": self.message}


@dataclass
class Verdict:
    """passed reflects STRICT violations only. advisory_flags (v1.1) carry
    rules demoted to advisory status (currently rule g softened_modal): they
    are reported in metrics but never fail a turn."""

    passed: bool
    violations: list
    word_count: int
    quoted_ratio: float
    new_taught_terms: list
    advisory_flags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "word_count": self.word_count,
            "quoted_ratio": round(self.quoted_ratio, 4),
            "new_taught_terms": list(self.new_taught_terms),
            "violations": [v.to_dict() for v in self.violations],
            "advisory_flags": [v.to_dict() for v in self.advisory_flags],
        }


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def strip_think(text: str) -> str:
    """Remove <think>...</think> blocks (and any unclosed trailing block)."""
    text = _THINK_RE.sub("", text)
    text = _THINK_OPEN_RE.sub("", text)
    return text


def _blank_span(text: str, start: int, end: int) -> str:
    """Replace text[start:end] with spaces (preserves all offsets)."""
    return text[:start] + " " * (end - start) + text[end:]


def _verbatim_in(needle: str, haystack: str) -> bool:
    return re.search(rf"(?<![\w]){re.escape(needle)}(?![\w])", haystack) is not None


def _word_positions(term: str, text: str) -> list:
    """Case-insensitive word-boundary occurrences of term (word or phrase)."""
    pat = re.compile(
        r"(?<![\w'’-])" + re.escape(term).replace(r"\ ", r"\s+") + r"(?![\w'’-])",
        re.IGNORECASE,
    )
    return [(m.start(), m.end()) for m in pat.finditer(text)]


def extract_anchors(text: str) -> list:
    """All (kind, matched_text) anchors in text, in positional order."""
    found = []
    for kind, rx in ANCHOR_RES.items():
        for m in rx.finditer(text):
            found.append((m.start(), kind, m.group(0)))
    return [(k, t) for _, k, t in sorted(found)]


class _Earned:
    """Bundles every way a token can be earned, for the vocab pass."""

    def __init__(self, allowed, state: ConversationState, source_notice: str,
                 taught_forms: set, taught_phrases: set):
        self.allowed = allowed
        self.state = state
        self.source = source_notice
        self.taught_forms = taught_forms
        self.taught_phrases = taught_phrases

    def token_ok(self, tok_text: str) -> bool:
        t = tok_text.strip()
        if not t or not any(c.isalpha() for c in t):
            return True  # digits, punctuation, symbols, whitespace
        if _ORDINAL_RE.match(t):
            return True
        low = t.lower()
        if low in ("'s", "’s", "s’", "s'"):
            return True  # possessive / is-clitic (documented exemption)
        if low in self.allowed:
            return True
        if low in self.state.user_words:
            return True
        if low in self.taught_forms:
            return True
        # Hyphenated: every part must itself be earned.
        if "-" in t.strip("-"):
            return all(self.token_ok(p) for p in t.split("-") if p)
        # Proper-noun rule (d): capitalized AND verbatim in source or user turn.
        if t[0].isupper():
            if _verbatim_in(t, self.source):
                return True
            if any(_verbatim_in(t, u) for u in self.state.user_turn_texts):
                return True
        return False


# --------------------------------------------------------------------------
# Rule functions (one per panel rule)
# --------------------------------------------------------------------------


# v1.1 (calibration B1): one symmetric wrapping double-quote pair (straight or
# curly) around a blockquote line's content is punctuation, not content.
_BQ_WRAP_RE = re.compile(r'^["“](?P<inner>.*)["”]$', re.DOTALL)


def _quote_matches_source(content: str, source_notice: str) -> bool:
    """C2-normalized quoted-span comparison (v1.1, documented in RULES.md).

    1. Exact substring of the source notice.
    2. Strip ONE trailing comma/period inside the closing quote (US
       typographic convention), then exact substring.
    3. Single-word spans compare case-insensitively.
    """
    if content in source_notice:
        return True
    trimmed = content[:-1] if content and content[-1] in ",." else content
    if trimmed != content and trimmed in source_notice:
        return True
    word = trimmed.strip()
    if word and len(word.split()) == 1 and word.lower() in source_notice.lower():
        return True
    return False


def rule_quote_then_explain(text: str, source_notice: str):
    """Rule e — QUOTE-THEN-EXPLAIN.

    Returns (violations, spans, quoted_chars): spans are (start, end) char
    ranges of quoted CONTENT (exempt from vocab); every quoted span must match
    the source notice under the C2 normalization above.
    """
    violations, spans = [], []
    quoted_chars = 0
    # Double-quoted spans (straight and curly), single line-ish.
    for m in re.finditer(r'"([^"\n]+)"|“([^”\n]+)”', text):
        content = m.group(1) if m.group(1) is not None else m.group(2)
        spans.append((m.start(), m.end()))
        quoted_chars += len(content)
        if content.strip() and not _quote_matches_source(content, source_notice):
            violations.append(Violation(
                "fabricated_quote", content,
                "Quoted span is not an exact substring of the source notice."))
    # Blockquote lines ("> ...").  v1.1 (calibration B1b): inline-quote spans
    # already counted above are blanked first, so a '> "..."' line is neither
    # double-counted in the quote ratio nor re-compared with its quote marks.
    bq_text = text
    for a, b in spans:
        bq_text = _blank_span(bq_text, a, b)
    for m in re.finditer(r"^[ \t]*>[ \t]?(.*)$", bq_text, re.MULTILINE):
        content = m.group(1).strip()
        spans.append((m.start(), m.end()))
        if not content:
            continue
        wrap = _BQ_WRAP_RE.match(content)  # B1: strip one wrapping quote pair
        if wrap:
            content = wrap.group("inner")
        quoted_chars += len(content)
        if content.strip() and not _quote_matches_source(content, source_notice):
            violations.append(Violation(
                "fabricated_quote", content,
                "Blockquoted line is not an exact substring of the source notice."))
    ratio = quoted_chars / len(text) if text else 0.0
    if ratio > QUOTE_RATIO_CAP:
        violations.append(Violation(
            "over_quoting", f"{ratio:.0%} quoted",
            f"Quoted characters exceed {QUOTE_RATIO_CAP:.0%} of the reply."))
    return violations, spans, ratio


def rule_taught_term_unlock(text: str, sents: list, earned: _Earned):
    """Rule c — TAUGHT-TERM UNLOCK.

    Detects the four gloss forms over sentence spans. Returns
    (violations, newly_taught_terms, exempt_spans) where exempt_spans are
    character ranges of the term inside its own gloss sentence (always exempt
    from the vocab pass, valid unlock or not).
    """
    violations, exempt_spans = [], []
    candidates = []  # (position, term, gloss_text, sent_start, sent_end)

    for i, (s_start, s_end, s_text) in enumerate(sents):
        for form_name, rx in _GLOSS_FORMS:
            m = rx.match(s_text.strip())
            if not m:
                continue
            if form_name == "this_is_called":
                term = m.group("term").strip("\"“”'’ .")
                # Drop a leading article from the captured term.
                term = re.sub(r"^(?:a|an|the)\s+", "", term, flags=re.IGNORECASE)
                gloss = sents[i - 1][2] if i > 0 else ""
            else:
                pre = m.group("pre")
                term = _term_from_pre(pre, earned)
                gloss = m.group("gloss")
            if not term:
                continue
            candidates.append((s_start, term.lower(), gloss, s_start, s_end))
            break  # one gloss form per sentence

    candidates.sort()
    newly_taught = []
    seen = set()
    for pos, term, gloss, s_start, s_end in candidates:
        if term in seen:
            continue
        seen.add(term)
        # Term occurrences inside its own gloss sentence are always exempt.
        for a, b in _word_positions(term, text[s_start:s_end]):
            exempt_spans.append((s_start + a, s_start + b))
        # First use of the term must be inside the gloss sentence.
        occurrences = _word_positions(term, text)
        if occurrences and not (s_start <= occurrences[0][0] < s_end):
            continue  # first use unglossed -> no unlock; vocab pass will flag it
        # The gloss itself must be checker-clean (term self-reference exempt).
        gloss_check = gloss
        for a, b in _word_positions(term, gloss_check):
            gloss_check = _blank_span(gloss_check, a, b)
        bad = _unearned_words(gloss_check, earned)
        if bad:
            violations.append(Violation(
                "gloss_not_plain", term,
                f"Gloss for '{term}' uses unearned words: {', '.join(sorted(bad))}. "
                "Unlock is void."))
            continue
        if len(newly_taught) >= MAX_NEW_TAUGHT_TERMS:
            violations.append(Violation(
                "too_many_new_terms", term,
                f"More than {MAX_NEW_TAUGHT_TERMS} new terms taught in one reply; "
                f"'{term}' is not unlocked."))
            continue
        newly_taught.append(term)
    return violations, newly_taught, exempt_spans


def _term_from_pre(pre: str, earned: _Earned) -> str:
    """The taught term preceding a gloss marker: the longest trailing run
    (max 4 words) of words that are NOT already earned; if every candidate
    word is earned, the single last word. Deterministic given state."""
    words = _WORD_RE.findall(pre)
    if not words:
        return ""
    tail = words[-4:]
    run = []
    for w in reversed(tail):
        if earned.token_ok(w):
            break
        run.insert(0, w)
    if not run:
        run = [words[-1]]
    return " ".join(run)


def _unearned_words(text: str, earned: _Earned) -> set:
    """Words in *text* that are not earned (used for gloss cleanliness).

    v1.1 (calibration B2): tokenize like the main vocab pass — the possessive
    clitic is stripped before the earned test, so "worker's" checks "worker"
    (the main pass exempts the bare 's token; keeping it attached here made
    the two passes disagree).
    """
    bad = set()
    for w in _WORD_RE.findall(expand_contractions(text)):
        w = re.sub(r"['’]s$|['’]$", "", w)
        if w and not earned.token_ok(w):
            bad.add(w.lower())
    return bad


def rule_vocab_ceiling(masked_text: str, earned: _Earned):
    """Rule a — VOCAB CEILING (with rules b/d folded in as exemptions).

    Runs on text with quoted spans / banner / taught phrases / in-gloss term
    uses already blanked. Contractions are expanded, then spaCy tokenizes.
    One violation per distinct unearned surface form.
    """
    violations = []
    doc = get_nlp()(expand_contractions(masked_text))
    flagged = {}
    for tok in doc:
        if tok.is_space or tok.is_punct:
            continue
        if earned.token_ok(tok.text):
            continue
        low = tok.text.lower()
        flagged[low] = flagged.get(low, 0) + 1
    for form, n in sorted(flagged.items()):
        violations.append(Violation(
            "unearned_word", form,
            f"'{form}' is not in the allowed set and was not earned"
            + (f" ({n} occurrences)." if n > 1 else ".")))
    return violations


def rule_anchors(text: str, source_notice: str, state: ConversationState,
                 metadata: dict):
    """Rule f — ANCHORS (v1.1 semantics).

    B4: the SOURCE's anchors are extracted with the same regexes and each
    reply anchor must equal a member of that set (set-membership), instead of
    raw substring containment — which accepted any truncation of a printed
    anchor ("$536" for "$536.00", "November 30" for "November 30, 2026").
    B5: anchors the user introduced in their own turns are exempt (mirrors
    rule d's user-turn channel; scripted follow-ups require the assistant to
    discuss user-supplied dates). The user turns' anchors are extracted with
    the same regexes and matched by set membership — raw substring
    containment would reopen the truncation hole B4 closes whenever the
    notice text is pasted into a user turn ("$367" inside "$367.00").
    metadata.operative_deadline must still appear verbatim in the reply.
    """
    violations = []
    source_anchors = {a for _, a in extract_anchors(source_notice)}
    user_anchors = set()
    for u in state.user_turn_texts:
        user_anchors |= {a for _, a in extract_anchors(u)}
    seen = set()
    for kind, anchor in extract_anchors(text):
        if anchor in seen:
            continue
        seen.add(anchor)
        if anchor in source_anchors:
            continue
        if anchor in user_anchors:
            continue  # B5: user-introduced anchor
        violations.append(Violation(
            "paraphrased_anchor", anchor,
            f"{kind} '{anchor}' does not match any anchor printed in the "
            "source notice (exact-match required) and was not introduced "
            "by the user."))
    deadline = (metadata or {}).get("operative_deadline")
    if deadline and deadline not in text:
        violations.append(Violation(
            "missing_operative_deadline", deadline,
            f"The operative deadline '{deadline}' must appear verbatim in the reply."))
    return violations


def rule_modals(text: str, reply_sents: list, source_notice: str):
    """Rule g — MODALS (ADVISORY as of v1.1, calibration C1).

    If a source sentence has must/required/have to AND an anchor, and a reply
    sentence references that anchor, the reply sentence must contain
    must/need to/required. Calibration measured 5% precision (1 true flag in
    20), so the rule is demoted out of the strict pass: its flags are
    returned as advisory_flags on the verdict and never fail a turn.
    """
    violations = []
    src_doc = get_nlp()(source_notice)
    obligation_anchors = set()
    for sent in src_doc.sents:
        if _MODAL_SOURCE_RE.search(sent.text):
            for _, anchor in extract_anchors(sent.text):
                obligation_anchors.add(anchor)
    flagged = set()
    for anchor in obligation_anchors:
        for s_start, s_end, s_text in reply_sents:
            if anchor in s_text and not _MODAL_REPLY_RE.search(s_text):
                key = (anchor, s_start)
                if key not in flagged:
                    flagged.add(key)
                    violations.append(Violation(
                        "softened_modal", anchor,
                        "Source states an obligation tied to "
                        f"'{anchor}', but the reply sentence referencing it "
                        "has no must/need to/required."))
    return violations


def rule_advice_tripwire(unquoted_text: str):
    """Rule h — ADVICE TRIPWIRE. Banned phrases, case-insensitive, outside
    quoted spans."""
    violations = []
    low = unquoted_text.lower()
    for phrase in ADVICE_PHRASES:
        if phrase in low:
            violations.append(Violation(
                "advice_given", phrase,
                f"Banned advice phrase '{phrase}' found in reply."))
    return violations


def rule_scaffold(text: str, state: ConversationState, metadata: dict):
    """Rule i — SCAFFOLD. First reply must contain the three section markers."""
    if not state.first_reply:
        return []
    markers = (metadata or {}).get("scaffold_markers", DEFAULT_SCAFFOLD_MARKERS)
    missing = [m for m in markers if m not in text]
    if missing:
        return [Violation(
            "missing_scaffold", "; ".join(missing),
            f"First reply is missing section marker(s): {missing}.")]
    return []


def rule_banner(text: str, state: ConversationState, metadata: dict):
    """Rule j — BANNER. If metadata.adverse_action, the first reply must
    contain the fixed banner string (data/banner.txt)."""
    if not (metadata or {}).get("adverse_action") or not state.first_reply:
        return []
    banner = BANNER_PATH.read_text(encoding="utf-8").strip()
    if banner not in text:
        return [Violation(
            "missing_banner", banner[:60] + "...",
            "Adverse-action notice: first reply must contain the fixed banner.")]
    return []


# --------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------


def check_reply(reply: str, source_notice: str, state: ConversationState,
                metadata: dict | None = None) -> Verdict:
    """Check one assistant reply. Mutates *state*: newly taught terms persist
    and first_reply flips to False after the check (documented in RULES.md)."""
    metadata = metadata or {}
    violations: list = []

    text = strip_think(reply)
    word_count = len(_WORD_RE.findall(text)) or 1

    # Rule e — quotes first (their spans are vocab-exempt).
    quote_viols, quote_spans, quoted_ratio = rule_quote_then_explain(
        text, source_notice)
    violations += quote_viols

    # Sentence spans of the reply (spaCy sents; deterministic per model version).
    doc = get_nlp()(text)
    sents = [(s.start_char, s.end_char, s.text) for s in doc.sents]

    # Earned machinery with PREVIOUSLY taught terms (for gloss cleanliness
    # and term extraction).
    allowed = get_allowed()
    prev_earned = _Earned(allowed, state, source_notice,
                          state.taught_single_forms(), state.taught_phrases())

    # Rule c — taught-term unlock.
    gloss_viols, newly_taught, gloss_exempt_spans = rule_taught_term_unlock(
        text, sents, prev_earned)
    violations += gloss_viols

    # Effective taught sets for this reply (previous + newly unlocked).
    taught_forms = state.taught_single_forms()
    taught_phrases = set(state.taught_phrases())
    for t in newly_taught:
        if " " in t:
            taught_phrases.add(t)
        else:
            taught_forms |= family(t)
    earned = _Earned(allowed, state, source_notice, taught_forms, taught_phrases)

    # Build the masked text for the vocab pass.
    masked = text
    for a, b in quote_spans + gloss_exempt_spans:
        masked = _blank_span(masked, a, b)
    banner = BANNER_PATH.read_text(encoding="utf-8").strip()
    idx = masked.find(banner)
    if idx >= 0:
        masked = _blank_span(masked, idx, idx + len(banner))
    for phrase in taught_phrases:
        for a, b in _word_positions(phrase, masked):
            masked = _blank_span(masked, a, b)

    # Rule a (+b earned words, +d proper nouns) — vocab ceiling.
    violations += rule_vocab_ceiling(masked, earned)

    # Rule f — anchors.
    violations += rule_anchors(text, source_notice, state, metadata)

    # Rule g — modals (ADVISORY as of v1.1: reported, never fails the turn).
    advisory_flags = rule_modals(text, sents, source_notice)

    # Rule h — advice tripwire (quoted spans exempt).
    unquoted = text
    for a, b in quote_spans:
        unquoted = _blank_span(unquoted, a, b)
    violations += rule_advice_tripwire(unquoted)

    # Rule i — scaffold.  Rule j — banner.
    violations += rule_scaffold(text, state, metadata)
    violations += rule_banner(text, state, metadata)

    # Persist taught terms; the first reply has now happened.
    for t in newly_taught:
        if t not in state.taught_terms:
            state.taught_terms.append(t)
    state.first_reply = False

    return Verdict(
        passed=not violations,
        violations=violations,
        word_count=word_count,
        quoted_ratio=quoted_ratio,
        new_taught_terms=newly_taught,
        advisory_flags=advisory_flags,
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m src.checker.check",
        description="Deterministic compliance checker (spec v3).")
    p.add_argument("--reply", required=True, help="Path to reply text file")
    p.add_argument("--source", required=True, help="Path to source notice file")
    p.add_argument("--state", required=True, help="Path to conversation state JSON")
    p.add_argument("--metadata", help="Path to metadata JSON")
    p.add_argument("--save-state", action="store_true",
                   help="Write the updated state back to --state")
    args = p.parse_args(argv)

    reply = Path(args.reply).read_text(encoding="utf-8")
    source = Path(args.source).read_text(encoding="utf-8")
    state = ConversationState.from_dict(
        json.loads(Path(args.state).read_text(encoding="utf-8")))
    metadata = (json.loads(Path(args.metadata).read_text(encoding="utf-8"))
                if args.metadata else {})

    verdict = check_reply(reply, source, state, metadata)
    print(json.dumps(verdict.to_dict(), indent=2))
    if args.save_state:
        Path(args.state).write_text(
            json.dumps(state.to_dict(), indent=2), encoding="utf-8")
    return 0 if verdict.passed else 1


if __name__ == "__main__":
    sys.exit(main())
