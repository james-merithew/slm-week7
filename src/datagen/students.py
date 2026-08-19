"""User-turn (dialog script) generator.

Turn 0 is always exactly:
    "I got this letter. Can you explain it?\n\n---\n" + notice_text
Follow-up turns (1-3 per dialog) are sampled from realistic intents:

    vocab             - asks about a rare word from the notice
    deadline_collapse - tries to collapse all clocks into the friendly 90 days
    advice_bait       - "should I appeal?" / "what would you do?"
    form_field        - asks what to put in a form field
    emotional         - "this is too much"
    confirmation      - restates an amount / deadline for confirmation

~30% of dialogs carry an advice_bait or deadline_collapse turn (deflection /
deadline-fidelity coverage). ~15-20% of dialogs are contrast-pair material:
twin dialogs share one notice with a rare term; in the "term_used" twin a
follow-up uses the term (the assistant may then use it unglossed), in the
"term_absent" twin no user turn beyond the notice uses it (the assistant must
gloss it or avoid it). Both twins are tagged with a shared contrast_group id.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .notices import CONTRAST_GENRES, Notice, build_notice, generate_notices

FIRST_TURN_PREFIX = "I got this letter. Can you explain it?\n\n---\n"

BAIT_INTENTS = ("advice_bait", "deadline_collapse")
BAIT_FRACTION = 0.30
CONTRAST_FRACTION = 0.175


@dataclass
class Turn:
    text: str
    intent: str  # open | vocab | deadline_collapse | advice_bait |
    #              form_field | emotional | confirmation | contrast_term


@dataclass
class DialogScript:
    dialog_id: str
    notice: Notice
    turns: list  # list[Turn]; turns[0].intent == "open"
    contrast_group: str | None = None
    contrast_role: str | None = None  # term_used | term_absent
    contrast_term: str | None = None

    @property
    def user_texts(self) -> list:
        return [t.text for t in self.turns]

    def has_bait(self) -> bool:
        return any(t.intent in BAIT_INTENTS for t in self.turns)


# --------------------------------------------------------------------------
# Follow-up builders
# --------------------------------------------------------------------------


def _vocab_turn(rng: random.Random, n: Notice) -> Turn | None:
    if not n.rare_term:
        return None
    t = n.rare_term
    templates = [
        f'What does "{t}" mean? I don\'t know that word.',
        f"I don't understand the word {t}. Can you explain it?",
        f"What is a {t}?" if " " not in t else f"What is a {t}?",
    ]
    return Turn(rng.choice(templates), "vocab")


def _deadline_collapse_turn(rng: random.Random, n: Notice) -> Turn | None:
    if not n.metadata.get("operative_deadline"):
        return None
    opts = []
    if n.outer_window:
        opts += [
            "So I have 90 days to deal with all of this, right? No rush.",
            "OK so the letter says 90 days. That means I can put this away for a couple of months, right?",
        ]
    if n.outer_date:
        opts.append(
            f"So as long as I do something by {n.outer_date}, I'm fine, right?")
    if not opts:
        opts = [
            "So there's no real hurry with any of this, right?",
        ]
    return Turn(rng.choice(opts), "deadline_collapse")


def _advice_bait_turn(rng: random.Random, n: Notice) -> Turn:
    opts = [
        "Should I appeal this? Just tell me yes or no.",
        "What would you do if you were me?",
        "Honestly, just tell me what to do here. Should I send the form or ask for the hearing?",
        "Do you think it's even worth fighting this?",
    ]
    return Turn(rng.choice(opts), "advice_bait")


def _form_field_turn(rng: random.Random, n: Notice) -> Turn | None:
    if not n.form_fields:
        return None
    f = rng.choice(n.form_fields)
    opts = [
        f'What do I put for "{f}"?',
        f"I'm stuck on the {f.lower()} part. What are they asking for?",
        "My hours change every week, so my pay is different every month. What number do I write down?",
    ]
    return Turn(rng.choice(opts), "form_field")


def _emotional_turn(rng: random.Random, n: Notice) -> Turn:
    opts = [
        "This is too much. I can't deal with all of this right now.",
        "I'm really scared. This letter makes me feel like I did something wrong.",
        "Every time I get one of these letters my heart drops. I don't even want to open them anymore.",
    ]
    return Turn(rng.choice(opts), "emotional")


def _confirmation_turn(rng: random.Random, n: Notice) -> Turn | None:
    md = n.metadata
    opts = []
    if md.get("amounts"):
        a = md["amounts"][-1]
        opts.append(f"OK. So just to be sure, the amount is {a}, right?")
    if md.get("operative_deadline"):
        d = md["operative_deadline"]
        opts.append(f"Just to make sure I have it right - the date I need to act by is {d}?")
    if not opts:
        opts.append("OK, let me see if I understood. Can you say the main point one more time, short?")
    return Turn(rng.choice(opts), "confirmation")


# Contrast turns: assertive USE of the rare term (not a vocab question) so
# the "student used it" pathway is exercised, with a no-term twin phrasing.
_CONTRAST_TERM_TURNS = {
    "allotment": (
        "So my allotment is going down? I count on that allotment every month.",
        "So the money I get each month is going down?",
    ),
    "recertification": (
        "Do I have to do this recertification thing every year now?",
        "Do I have to do this renewal thing every year now?",
    ),
    "redetermination": (
        "Is this redetermination something they do to everyone, or just me?",
        "Is this review something they do to everyone, or just me?",
    ),
    "verification": (
        "Why do they need all this verification? I already told them everything.",
        "Why do they need all these papers? I already told them everything.",
    ),
}


def _contrast_turns(term: str) -> tuple[Turn, Turn]:
    used, absent = _CONTRAST_TERM_TURNS.get(
        term,
        (f"The letter keeps saying {term}. Is the {term} part about me?",
         "There's a word in the letter I keep seeing. Is that part about me?"))
    return Turn(used, "contrast_term"), Turn(absent, "contrast_term")


_GENERIC_BUILDERS = [
    ("vocab", _vocab_turn),
    ("form_field", _form_field_turn),
    ("emotional", _emotional_turn),
    ("confirmation", _confirmation_turn),
]


def _sample_followups(rng: random.Random, n: Notice, k: int,
                      exclude_term: str | None = None) -> list:
    """k distinct-intent non-bait follow-ups appropriate to the notice.
    If exclude_term is set, no produced turn may contain that term."""
    pool = []
    for name, fn in _GENERIC_BUILDERS:
        if exclude_term and name == "vocab":
            continue  # vocab turns use the rare term by design
        t = fn(rng, n)
        if t is None:
            continue
        if exclude_term and exclude_term.lower() in t.text.lower():
            continue
        pool.append(t)
    rng.shuffle(pool)
    return pool[:k]


def _n_followups(rng: random.Random) -> int:
    return rng.choices([1, 2, 3], weights=[35, 45, 20], k=1)[0]


def _open_turn(n: Notice) -> Turn:
    return Turn(FIRST_TURN_PREFIX + n.notice_text, "open")


def _bait_turn(rng: random.Random, n: Notice) -> Turn:
    """A bait follow-up; deadline_collapse when the notice has an operative
    deadline, otherwise advice_bait."""
    if n.metadata.get("operative_deadline") and rng.random() < 0.5:
        t = _deadline_collapse_turn(rng, n)
        if t is not None:
            return t
    return _advice_bait_turn(rng, n)


# --------------------------------------------------------------------------
# Dialog planning
# --------------------------------------------------------------------------


def plan_dialogs(n: int, seed: int) -> list:
    """Deterministically plan n dialog scripts (notices + user turns).

    Returns list[DialogScript]. Contrast pairs consume two dialogs each and
    share one notice; bait coverage is topped up to ~BAIT_FRACTION of all
    dialogs.
    """
    if n < 1:
        return []
    rng = random.Random(seed)

    n_pairs = int(round(CONTRAST_FRACTION * n)) // 2
    if n >= 6 and n_pairs == 0:
        n_pairs = 1
    n_regular = n - 2 * n_pairs

    scripts: list[DialogScript] = []
    seq = 0

    # Contrast pairs first (deterministic order).
    for p in range(n_pairs):
        genre = CONTRAST_GENRES[p % len(CONTRAST_GENRES)]
        notice = build_notice(genre, rng, seq)
        seq += 1
        term = notice.rare_term
        used_turn, absent_turn = _contrast_turns(term)
        group = f"cg-{p:04d}"

        extra_a = _sample_followups(rng, notice, _n_followups(rng) - 1)
        turns_a = [_open_turn(notice), used_turn] + extra_a
        scripts.append(DialogScript(
            dialog_id=f"{notice.notice_id}-a", notice=notice,
            turns=turns_a, contrast_group=group, contrast_role="term_used",
            contrast_term=term))

        extra_b = _sample_followups(rng, notice, _n_followups(rng) - 1,
                                    exclude_term=term)
        turns_b = [_open_turn(notice), absent_turn] + extra_b
        scripts.append(DialogScript(
            dialog_id=f"{notice.notice_id}-b", notice=notice,
            turns=turns_b, contrast_group=group, contrast_role="term_absent",
            contrast_term=term))

    # Regular dialogs.
    for notice in generate_notices(n_regular, rng):
        # Re-sequence so ids stay unique across the whole plan
        # (generate_notices numbers from 0; contrast notices used 0..n_pairs-1).
        parts = notice.notice_id.rsplit("-", 1)
        notice.notice_id = f"{parts[0]}-{seq:04d}"
        seq += 1
        k = _n_followups(rng)
        followups = _sample_followups(rng, notice, k)
        if not followups:
            followups = [_emotional_turn(rng, notice)]
        scripts.append(DialogScript(
            dialog_id=notice.notice_id, notice=notice,
            turns=[_open_turn(notice)] + followups))

    # Bait top-up to ~30% of dialogs.
    target = int(round(BAIT_FRACTION * n))
    have = [i for i, s in enumerate(scripts) if s.has_bait()]
    need = target - len(have)
    if need > 0:
        candidates = [i for i, s in enumerate(scripts) if not s.has_bait()]
        for i in rng.sample(candidates, min(need, len(candidates))):
            s = scripts[i]
            bait = _bait_turn(rng, s.notice)
            if (s.contrast_role == "term_absent" and s.contrast_term
                    and s.contrast_term.lower() in bait.text.lower()):
                bait = _advice_bait_turn(rng, s.notice)
            if len(s.turns) >= 4:  # keep 1-3 follow-ups
                s.turns[-1] = bait
            else:
                s.turns.append(bait)

    return scripts
