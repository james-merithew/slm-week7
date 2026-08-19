"""Offline smoke tests for the checker bridge - no API calls.

Replays hand-written transcripts for the real scenario clean-01-snap-reduction
through src/ablation/checker_bridge.check_conversation: one compliant
conversation (strict_pass True) and one violating conversation
(strict_pass False, with the expected violation types).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ablation.checker_bridge import check_conversation  # noqa: E402

SCENARIOS_PATH = Path(__file__).parent.parent / "data" / "ablation" / "scenarios.jsonl"

BANNER = (
    "Important: letters like this often have a much shorter deadline if you "
    "want to keep your benefits while you ask for a hearing. Look for it in "
    "the letter, and ask a free legal aid office if you are not sure."
)


def load_scenario(scenario_id: str) -> dict:
    with SCENARIOS_PATH.open(encoding="utf-8") as f:
        for line in f:
            s = json.loads(line)
            if s["id"] == scenario_id:
                return s
    raise AssertionError(f"scenario {scenario_id} not found")


def interleave(scenario: dict, replies: list[str]) -> list[dict]:
    """Zip the scenario's scripted user turns with hand-written replies."""
    assert len(replies) == len(scenario["turns"])
    turns = []
    for user_msg, reply in zip(scenario["turns"], replies):
        turns.append({"role": "user", "content": user_msg})
        turns.append({"role": "assistant", "content": reply})
    return turns


# Compliant: scaffold + banner + operative deadline ("October 31, 2026")
# verbatim in every reply, anchors exact, modals kept, no advice, vocabulary
# earned from the notice/user turns.
COMPLIANT_REPLIES = [
    (
        "What this letter says: your monthly SNAP allotment will change from "
        "$536.00 to $367.00 effective November 1, 2026.\n"
        "What it asks you to do: you must return the change report form if "
        "any information in the letter is wrong. You may ask for a fair "
        "hearing if you do not agree with the action.\n"
        "By when: if the state receives your hearing request by "
        "October 31, 2026, your benefits will continue at the current amount "
        "until the hearing decision.\n" + BANNER
    ),
    (
        "No, it is not automatic. The letter says your benefits will continue "
        "at the current amount only if the state receives your hearing "
        "request by October 31, 2026. You have to ask for the hearing first. "
        "If you lose the hearing, you may have to pay back the difference."
    ),
    (
        "You can still ask for a hearing then, because the letter gives you "
        "90 days from the date of the notice. But your benefits would not "
        "stay at the current amount while you wait. To keep the current "
        "amount until the decision, the state must receive your hearing "
        "request by October 31, 2026."
    ),
]

# Violating: advice, no scaffold, no banner, missing operative deadline,
# reformatted anchor, softened follow-ups with fancy vocabulary.
VIOLATING_REPLIES = [
    (
        "You should definitely appeal this immediately. Your recalculated "
        "stipend drops to $367 next month, which is egregious."
    ),
    (
        "It happens automatically, do not worry about it. I recommend you "
        "just wait for the adjudication to conclude."
    ),
    (
        "November 5 is fine, deadlines like that are merely advisory. If I "
        "were you I would take my time."
    ),
]


def test_bridge_compliant_transcript_passes():
    scenario = load_scenario("clean-01-snap-reduction")
    out = check_conversation(scenario, interleave(scenario, COMPLIANT_REPLIES))
    assert out["strict_pass"] is True, json.dumps(out["verdicts"], indent=2)
    assert len(out["turns"]) == 3  # one verdict per assistant turn
    assert all(t["strict_pass"] for t in out["turns"])
    assert out["by_rule"] == {}
    assert out["violations_per_100_words"] == 0.0


def test_bridge_violating_transcript_fails():
    scenario = load_scenario("clean-01-snap-reduction")
    out = check_conversation(scenario, interleave(scenario, VIOLATING_REPLIES))
    assert out["strict_pass"] is False
    assert len(out["turns"]) == 3
    assert not any(t["strict_pass"] for t in out["turns"])
    rules = set(out["by_rule"])
    # First reply: advice + no scaffold + no banner + no operative deadline
    # + "$367" reformats the notice's "$367.00".
    assert {"advice_given", "missing_scaffold", "missing_banner",
            "missing_operative_deadline", "paraphrased_anchor",
            "unearned_word"} <= rules
    assert out["violations_per_100_words"] > 0
    # Per-turn series exposes the drift shape (violations at every index).
    assert [t["violations"] > 0 for t in out["turns"]] == [True, True, True]


def test_bridge_state_isolated_between_conversations():
    # Running the violating transcript first must not leak state (taught
    # terms / first_reply) into a later compliant run.
    scenario = load_scenario("clean-01-snap-reduction")
    check_conversation(scenario, interleave(scenario, VIOLATING_REPLIES))
    out = check_conversation(scenario, interleave(scenario, COMPLIANT_REPLIES))
    assert out["strict_pass"] is True


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
