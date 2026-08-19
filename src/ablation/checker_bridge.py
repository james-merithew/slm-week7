"""Bridge between conversation transcripts and the deterministic checker.

`check_conversation(scenario, turns)` replays a finished conversation through
`src.checker.check.check_reply` exactly the way the checker expects:

  - a FRESH ConversationState per conversation (check_reply mutates state:
    taught terms persist and `first_reply` flips after the first check);
  - every user turn is absorbed (student-word allowance, rule b) BEFORE the
    assistant turn that follows it is checked;
  - source_notice = scenario["notice_text"], metadata = scenario["metadata"].

Returns per-assistant-turn verdicts plus the aggregates the ablation runner
reports (strict_pass, violations/100 words overall and per turn index,
violation-type counts).

The checker's spaCy pipeline is a shared singleton that is not guaranteed
thread-safe, so the replay is serialized behind a module lock. The checker is
cheap relative to API calls; this does not bottleneck the runners.
"""
from __future__ import annotations

import threading

from src.checker.check import ConversationState, absorb_user_turn, check_reply
from src.checker.metrics import conversation_series

_CHECKER_LOCK = threading.Lock()


def check_conversation(scenario: dict, turns: list[dict]) -> dict:
    """Run the deterministic checker over every assistant turn of *turns*.

    *scenario* is one scenarios.jsonl object (needs `notice_text`, `metadata`).
    *turns* is the transcript: [{"role": "user"|"assistant", "content": str}].

    Returns a JSON-safe dict:
      turns                     per-assistant-turn metrics, in turn order
                                (index i = i-th assistant turn): word_count,
                                violations, violations_per_100_words, by_rule,
                                advisory, advisory_by_rule, quoted_ratio,
                                new_taught_terms, strict_pass
      verdicts                  full checker verdicts (violation details), same order
      strict_pass               True iff every assistant turn has zero STRICT
                                violations (advisory flags — rule g
                                softened_modal as of checker v1.1 — never
                                fail a turn; they report via advisory_by_rule)
      violations_per_100_words  conversation-level (total viols / total words)
      by_rule                   violation-type counts summed over all turns
      total_words / total_violations
    """
    source_notice = scenario["notice_text"]
    metadata = scenario.get("metadata") or {}

    with _CHECKER_LOCK:
        state = ConversationState()
        verdicts = []
        for turn in turns:
            if turn["role"] == "user":
                absorb_user_turn(state, turn["content"])
            elif turn["role"] == "assistant":
                verdicts.append(
                    check_reply(turn["content"], source_notice, state, metadata)
                )

    out = conversation_series(verdicts)
    out["verdicts"] = [v.to_dict() for v in verdicts]
    return out
