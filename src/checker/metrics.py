"""Metrics over checker verdicts (spec v3, item 4).

reply_metrics(verdict)        -> per-reply metrics dict
conversation_series(verdicts) -> per-turn series + aggregate
"""
from __future__ import annotations

from collections import Counter

from .check import Verdict


def reply_metrics(verdict: Verdict) -> dict:
    """Per-reply: violations/100 words, per-type counts, strict pass bool.

    Advisory flags (v1.1; currently rule g softened_modal) are counted
    separately and never affect strict_pass.
    """
    n = len(verdict.violations)
    by_rule = Counter(v.rule for v in verdict.violations)
    advisory_by_rule = Counter(v.rule for v in verdict.advisory_flags)
    return {
        "word_count": verdict.word_count,
        "violations": n,
        "violations_per_100_words": round(100.0 * n / verdict.word_count, 2),
        "by_rule": dict(sorted(by_rule.items())),
        "advisory": len(verdict.advisory_flags),
        "advisory_by_rule": dict(sorted(advisory_by_rule.items())),
        "quoted_ratio": round(verdict.quoted_ratio, 4),
        "new_taught_terms": list(verdict.new_taught_terms),
        "strict_pass": verdict.passed,
    }


def conversation_series(verdicts: list) -> dict:
    """Per-turn series plus conversation-level aggregate."""
    turns = [reply_metrics(v) for v in verdicts]
    total_words = sum(t["word_count"] for t in turns) or 1
    total_viols = sum(t["violations"] for t in turns)
    agg_by_rule: Counter = Counter()
    agg_advisory: Counter = Counter()
    for t in turns:
        agg_by_rule.update(t["by_rule"])
        agg_advisory.update(t["advisory_by_rule"])
    return {
        "turns": turns,
        "total_words": total_words,
        "total_violations": total_viols,
        "total_advisory": sum(t["advisory"] for t in turns),
        "violations_per_100_words": round(100.0 * total_viols / total_words, 2),
        "by_rule": dict(sorted(agg_by_rule.items())),
        "advisory_by_rule": dict(sorted(agg_advisory.items())),
        "strict_pass": all(t["strict_pass"] for t in turns),
    }
