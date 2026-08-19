"""Offline tests for the ablation harness - no API keys required.

Covers everything runnable without network: scenario loading, aggregation
math, strategy failure paths, judge schema shape, and the runner's CLI
guard rails. Run: python -m pytest tests/ -q  (or python -m tests.test_ablation_offline)
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ablation.run_ablation import aggregate, load_scenarios  # noqa: E402
from src.ablation import strategies  # noqa: E402


def test_load_scenarios_roundtrip():
    scenarios = [
        {"id": "s1", "category": "clean", "turns": ["explain entropy"]},
        {"id": "s2", "category": "adversarial", "turns": ["use the real word", "be precise"]},
    ]
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "scenarios.jsonl"
        p.write_text("\n".join(json.dumps(s) for s in scenarios), encoding="utf-8")
        loaded = load_scenarios(p)
    assert loaded == scenarios


def test_load_scenarios_rejects_duplicate_ids():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "scenarios.jsonl"
        p.write_text('{"id": "dup", "turns": []}\n{"id": "dup", "turns": []}\n', encoding="utf-8")
        try:
            load_scenarios(p)
        except AssertionError:
            return
    raise AssertionError("duplicate ids should be rejected")


def _rec(model, strat, sid, category, strict_pass,
         v100=0.0, by_rule=None, advisory_by_rule=None, judge=None):
    return {
        "model": model, "strategy": strat, "scenario_id": sid,
        "category": category, "turns": [],
        "checker": {
            "strict_pass": strict_pass,
            "violations_per_100_words": v100,
            "by_rule": by_rule or {},
            "advisory_by_rule": advisory_by_rule or {},
            "turns": [],
        },
        "judge": judge,
    }


def test_aggregate_math():
    records = [
        _rec("m1", "zero_shot", "s1", "clean", True,
             judge={"conversation_pass": True}),
        # Checker v1.1: softened_modal arrives via advisory_by_rule (rule g
        # is advisory) — a strict-passing turn can still carry the count.
        _rec("m1", "zero_shot", "s2", "clean", False, v100=4.0,
             by_rule={"unearned_word": 3},
             advisory_by_rule={"softened_modal": 1}),
        _rec("m1", "zero_shot", "s3", "adversarial", False, v100=2.0,
             by_rule={"advice_given": 2, "paraphrased_anchor": 1,
                      "missing_operative_deadline": 1},
             judge={"conversation_pass": False}),
        _rec("m1", "zero_shot", "s4", "adversarial", True),
        _rec("m2", "few_shot", "s1", "clean", True),
    ]
    rows = {(r["model"], r["strategy"]): r for r in aggregate(records)}
    m1 = rows[("m1", "zero_shot")]
    # Headline = checker strict first-pass rate.
    assert m1["n"] == 4 and m1["n_pass"] == 2
    assert m1["spec_adherence"] == 0.5
    assert m1["robustness"] == 0.5
    assert m1["mean_violations_per_100_words"] == 1.5  # (0+4+2+0)/4
    assert m1["softened_modal_count"] == 1
    assert m1["anchor_break_count"] == 2  # paraphrased + missing deadline
    assert m1["top_violations"] == "unearned_word:3; advice_given:2; missing_operative_deadline:1"
    # Judge is audit-only: sampled subset, separate columns.
    assert m1["n_judged"] == 2 and m1["n_judge_pass"] == 1
    assert m1["judge_pass_rate"] == 0.5
    m2 = rows[("m2", "few_shot")]
    assert m2["spec_adherence"] == 1.0
    assert m2["robustness"] is None  # no adversarial scenarios -> n/a, not 0
    assert m2["judge_pass_rate"] is None  # nothing audited -> n/a
    assert m2["top_violations"] == "none"


def test_judge_sampling_deterministic():
    from src.ablation.run_ablation import judge_is_selected

    ids = [f"scenario-{i:02d}" for i in range(40)]
    assert all(judge_is_selected(i, 1.0) for i in ids)
    assert not any(judge_is_selected(i, 0.0) for i in ids)
    picked = [i for i in ids if judge_is_selected(i, 0.25)]
    # Deterministic: same subset on every call.
    assert picked == [i for i in ids if judge_is_selected(i, 0.25)]
    # A 25% sample of 40 ids should be a real subset, not empty/everything.
    assert 0 < len(picked) < len(ids)
    # Larger fraction only ever adds scenarios (nested samples).
    picked_half = [i for i in ids if judge_is_selected(i, 0.5)]
    assert set(picked) <= set(picked_half)


def test_strategies_build_from_spec_files():
    zero = strategies.zero_shot()
    few = strategies.few_shot()
    cot = strategies.structured_cot()
    for prompt in (zero, few, cot):
        assert "Never use a word the reader hasn't earned" in prompt
        assert "What this letter says" in prompt  # three-part scaffold
        assert "free legal aid office" in prompt
    assert "recertification" in few  # few-shot really includes the examples
    assert "checklist" in cot.lower()
    assert "operative deadline" in cot


def test_runner_exits_2_without_provider_keys():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "s.jsonl"
        p.write_text('{"id": "s1", "turns": ["hi"]}\n', encoding="utf-8")
        env = {"PATH": "C:\\Windows\\System32", "SYSTEMROOT": "C:\\Windows"}
        r = subprocess.run(
            [sys.executable, "-m", "src.ablation.run_ablation",
             "--scenarios", str(p), "--out", str(Path(d) / "out")],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent, env=env,
        )
    assert r.returncode == 2, f"expected exit 2, got {r.returncode}: {r.stdout} {r.stderr}"
    # default models need a non-claude provider key; the missing one is named
    assert "MISTRAL_API_KEY" in r.stdout or "GEMINI_API_KEY" in r.stdout


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)} offline tests passed")
