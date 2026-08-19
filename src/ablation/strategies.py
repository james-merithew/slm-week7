"""Prompting strategies for the Prompt-Ceiling Ablation (spec v2.2, earned words).

Each strategy builds the system prompt handed to a frontier subject model.
Spec-specific content lives in prompts/:

  prompts/behavior_spec.md      - the operational spec (persona + rule + limits)
  prompts/few_shot_examples.md  - in-context examples for the few_shot strategy
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _read(name: str) -> str:
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing - write the behavior spec / examples before running."
        )
    return path.read_text(encoding="utf-8").strip()


def zero_shot() -> str:
    return _read("behavior_spec.md")


def few_shot() -> str:
    return (
        _read("behavior_spec.md")
        + "\n\nHere are examples of correct behavior:\n\n"
        + _read("few_shot_examples.md")
    )


def structured_cot() -> str:
    return (
        _read("behavior_spec.md")
        + "\n\nBefore sending any reply, silently work through this checklist:\n"
        "1. Vocabulary: is every word OUTSIDE direct quotes earned - common"
        " learner-level vocabulary, a word the reader has used, or a term I"
        " have already taught in this conversation?\n"
        "2. Accuracy: is every quote from the letter exact, character for"
        " character? Is every date, dollar amount, phone number, and document"
        " name reproduced exactly as printed? Is the operative deadline"
        " present?\n"
        "3. Obligations and advice: did I soften any 'must'? Did I give advice"
        " anywhere - any 'you should', recommendation, or judgment call? If"
        " this is my first reply about a letter, is the three-part scaffold"
        " present (What this letter says / What it asks you to do / By when)?"
        " Am I teaching at most two new terms, each glossed in an approved"
        " form?\n"
        "Only send a reply that passes all three checks. Never mention this "
        "checklist to the reader."
    )


STRATEGIES = {
    "zero_shot": zero_shot,
    "few_shot": few_shot,
    "structured_cot": structured_cot,
}
