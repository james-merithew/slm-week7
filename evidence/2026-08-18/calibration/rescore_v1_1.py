"""Re-score the frozen 50-turn calibration set against checker v1.1.

Protocol (mirrors REPORT.md section 1 exactly):
  - replies.jsonl and labels.jsonl are FROZEN; the human labels are used
    as-is, including the two documented corrections already applied there.
  - State threading is identical to the original run (and to
    tests/test_checker.py::test_end_to_end): fresh ConversationState per
    conversation; scripted user turns absorbed in order; the row's
    prior_assistant replies run through check_reply first so taught terms
    persist and first_reply flips; scenario metadata (adverse_action,
    operative_deadline) is passed on the FIRST reply only.
  - Checker verdict = FAIL iff strict violations are non-empty. Advisory
    flags (rule g softened_modal, demoted per C1) never fail a turn; they
    are tallied separately.

Emits RESCORE.md next to this script.

Run from the repo root:  python evidence/2026-08-18/calibration/rescore_v1_1.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.checker.check import (  # noqa: E402
    ConversationState, absorb_user_turn, check_reply,
)

SCENARIOS_PATH = ROOT / "data" / "ablation" / "scenarios.jsonl"
GATE_BAR = 0.05  # pre-registered: <5% false positives on the 50 labeled turns


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def run_row(row: dict, scenario: dict) -> dict:
    notice = scenario["notice_text"]
    md = scenario.get("metadata") or {}
    first_meta = {"adverse_action": md.get("adverse_action"),
                  "operative_deadline": md.get("operative_deadline")}
    users = scenario["turns"]
    t = row["turn_index"]
    prior = row.get("prior_assistant") or []
    assert len(prior) == t - 1, f"{row['id']}: prior count != turn_index-1"

    state = ConversationState()
    for i in range(t - 1):
        absorb_user_turn(state, users[i])
        check_reply(prior[i], notice, state, first_meta if i == 0 else {})
    absorb_user_turn(state, users[t - 1])
    verdict = check_reply(row["reply"], notice, state,
                          first_meta if t == 1 else {})
    return {
        "verdict": "PASS" if verdict.passed else "FAIL",
        "violations": [{"rule": v.rule, "detail": v.detail}
                       for v in verdict.violations],
        "advisory": [{"rule": v.rule, "detail": v.detail}
                     for v in verdict.advisory_flags],
    }


def main() -> int:
    replies = load_jsonl(HERE / "replies.jsonl")
    labels = {d["id"]: d for d in load_jsonl(HERE / "labels.jsonl")}
    scenarios = {s["id"]: s for s in load_jsonl(SCENARIOS_PATH)}
    assert len(replies) == 50 and len(labels) == 50

    rows = []
    for r in replies:
        res = run_row(r, scenarios[r["scenario_id"]])
        lab = labels[r["id"]]
        rows.append({
            "id": r["id"],
            "condition": r["condition"],
            "human": lab["human_verdict"],
            "v10": lab["checker_verdict"],
            "v10_class": lab.get("disagreement_class"),
            "v11": res["verdict"],
            "violations": res["violations"],
            "advisory": res["advisory"],
        })

    # Confusion matrix (checker v1.1 vs frozen human labels).
    cf = Counter((x["v11"], x["human"]) for x in rows)
    fail_fail = cf[("FAIL", "FAIL")]
    fail_pass = cf[("FAIL", "PASS")]   # FP
    pass_fail = cf[("PASS", "FAIL")]   # FN
    pass_pass = cf[("PASS", "PASS")]
    n = len(rows)
    flagged = fail_fail + fail_pass
    fp_of_50 = fail_pass / n
    fp_of_flagged = fail_pass / flagged if flagged else 0.0
    agree = fail_fail + pass_pass

    orig_fp_ids = [x["id"] for x in rows if x["v10_class"] == "FP"]
    resolved, residual = [], []
    for x in rows:
        if x["v10_class"] == "FP":
            if x["v11"] == "PASS":
                resolved.append(x)
            else:
                residual.append(x)

    # New disagreements: turns that agreed under v1.0 but disagree under v1.1.
    new_dis = [x for x in rows
               if x["v10"] == x["human"] and x["v11"] != x["human"]]
    # Also: v1.0 disagreements (other than the FPs) that changed class.
    still_fn = [x for x in rows
                if x["v10_class"] == "FN" and x["v11"] == "PASS"]

    advisory_total = sum(len(x["advisory"]) for x in rows)
    advisory_turns = sum(1 for x in rows if x["advisory"])

    gate_pass = fp_of_50 < GATE_BAR

    def viol_str(v):
        return "; ".join(f"{d['rule']}({d['detail']!r})" for d in v) or "none"

    lines = []
    a = lines.append
    a("# Checker v1.1 re-score of the frozen 50-turn calibration set")
    a("")
    a("**Date:** 2026-08-18  ")
    a("**Checker under test:** `src/checker/check.py` v1.1 (post-B1/B1b/B2/B3/B4/B5 "
      "fixes and C1/C2/C3 decisions per REPORT.md sections 6-7).  ")
    a("**Inputs:** frozen `replies.jsonl` + frozen `labels.jsonl` (human verdicts "
      "used AS-IS, including its two documented corrections; no relabeling). "
      "State threading identical to the original run (fresh state per "
      "conversation, user turns absorbed in order, prior assistant replies "
      "re-checked first, scenario metadata on the first reply only).  ")
    a("**Strict verdict:** FAIL iff strict violations > 0; rule g "
      "`softened_modal` is advisory (C1) and never fails a turn.")
    a("")
    a("## Confusion matrix (checker v1.1 vs frozen human labels)")
    a("")
    a("| | Human FAIL | Human PASS | total |")
    a("|---|---|---|---|")
    a(f"| **Checker FAIL** | {fail_fail} | **{fail_pass} (FP)** | {flagged} |")
    a(f"| **Checker PASS** | **{pass_fail} (FN)** | {pass_pass} | {pass_fail + pass_pass} |")
    a(f"| total | {fail_fail + pass_fail} | {fail_pass + pass_pass} | {n} |")
    a("")
    a(f"- **FP rate (of all {n}): {fail_pass}/{n} = {fp_of_50:.1%}** "
      f"(v1.0: 10/50 = 20.0%)")
    a(f"- **FP rate (of checker-flagged turns): {fail_pass}/{flagged} = "
      f"{fp_of_flagged:.1%}** (v1.0: 10/42 = 23.8%)")
    a(f"- FN rate (of all {n}): {pass_fail}/{n} = {pass_fail / n:.1%} "
      f"(v1.0: 2/50 = 4.0%)")
    a(f"- Agreement: {agree}/{n} = {agree / n:.1%} (v1.0: 38/50 = 76%)")
    a(f"- Advisory `softened_modal` flags: {advisory_total} across "
      f"{advisory_turns} turns (reported in metrics, never fail a turn)")
    a("")
    a("## Resolution of the original 10 false positives")
    a("")
    a("| id | v1.0 flags wrong because | v1.1 verdict | status |")
    a("|---|---|---|---|")
    cause = {
        "spec-clean01-t1": "B1 blockquotes x6, B1b ratio, B3 'two'",
        "spec-clean01-t2": "C2 punctuation x5, contrast quote, B1 x2, C3/B3 words",
        "spec-clean01-t3": "B5 user date, B1 x3, B3 'two'",
        "spec-adv01-t2": "C1 modal, B3 'three'",
        "spec2-adv01-t1": "B1 x4, C2 'Gross', B1b ratio, C1 modal, B3 words",
        "spec-form01-t2": "B1 x3, B3 words",
        "spec-miss01-t2": "B1, B2 gloss tokenizer, C3 'denial', B3 'two'",
        "spec-miss01-t3": "C2 comma, C3 'plainly'",
        "spec2-miss01-t1": "B1 x4, B3 'two'",
        "spec-multi01-t3": "B1 x3, B1b ratio, C1 modal",
    }
    for x in rows:
        if x["id"] not in orig_fp_ids:
            continue
        if x["v11"] == "PASS":
            status = "**RESOLVED**"
        else:
            status = f"**RESIDUAL FP** - remaining: {viol_str(x['violations'])}"
        a(f"| {x['id']} | {cause.get(x['id'], '-')} | {x['v11']} | {status} |")
    a("")
    a(f"Resolved: **{len(resolved)}/10**. Residual: **{len(residual)}/10**"
      + (":" if residual else "."))
    for x in residual:
        a(f"- `{x['id']}` still fails on {viol_str(x['violations'])} - see "
          "'Residual analysis' below.")
    a("")
    a("## New disagreements introduced by v1.1")
    a("")
    if new_dis:
        a("| id | human | v1.0 | v1.1 | why |")
        a("|---|---|---|---|---|")
        for x in new_dis:
            if x["v11"] == "PASS":
                why = ("its only v1.0 violation was `softened_modal`, now "
                       "advisory (C1)" if x["id"].startswith("hand-09")
                       else "all v1.0 violations were in channels v1.1 changed")
                kind = "new FN"
            else:
                why = f"new flags: {viol_str(x['violations'])}"
                kind = "new FP"
            a(f"| {x['id']} | {x['human']} | {x['v10']} | {x['v11']} | "
              f"{kind}: {why} |")
    else:
        a("None.")
    a("")
    a("## Unchanged by-design disagreements")
    a("")
    for x in still_fn:
        a(f"- `{x['id']}`: human FAIL / checker PASS, unchanged - paraphrased "
          "advice with no tripwire phrase and no anchor; LLM-judge scope by "
          "design (REPORT.md section 5).")
    a("")
    a("## Gate verdict")
    a("")
    verdict_word = "GATE PASSED" if gate_pass else "GATE FAILED"
    a(f"**{verdict_word}: FP = {fail_pass}/{n} = {fp_of_50:.1%} "
      f"{'<' if gate_pass else '>='} 5% pre-registered bar** "
      f"(FP of flagged = {fail_pass}/{flagged} = {fp_of_flagged:.1%}; "
      f"v1.0 was 10/50 = 20.0%).")
    a("")

    a("## Residual analysis")
    a("")
    a("- **`spec-clean01-t2`** (residual FP, 2 flags). "
      "(1) `fabricated_quote('you send.')`: an explicit CONTRAST quote - the "
      "reply says the letter reads \"we receive,\" *not* \"you send.\" "
      "REPORT.md C2 listed contrast-framing recognition as an option; the "
      "decided C2 normalization covers only trailing punctuation and "
      "single-word case, so this span still compares against the source and "
      "flags. Documented crudeness, not a bug. "
      "(2) `paraphrased_anchor('November 1')`: the reply writes \"It does "
      "not stop on November 1.\" - a truncation of the letter's "
      "\"November 1, 2026\". v1.0's substring containment silently accepted "
      "truncations (the B4 false-negative channel); v1.1's set-membership "
      "flags them by design. The frozen human label (PASS) predates the B4 "
      "exactness doctrine, so against the frozen labels this scores as an "
      "FP; under the v1.1 rule document it is a true (if harsh) flag.")
    a("- **`spec-clean01-t3`** (residual FP, 1 flag). "
      "`paraphrased_anchor('November 5, 2026')`: the user asked about "
      "\"November 5\" (no year); the reply's heading completes it to "
      "\"November 5, 2026\". The B5 exemption is exact-match against the "
      "anchors extracted from the user's turns, so the year-completed form "
      "is not exempt (RULES.md documents this residual crudeness). The "
      "bare \"November 5\" echo is exempt and no longer flags.")
    a("- **`hand-09-softened-modal`** (new FN, priced in by C1). This "
      "hand-constructed probe was the single true `softened_modal` flag in "
      "the calibration (rule g precision 1/20 = 5%). Demoting rule g to "
      "advisory (the decided C1 resolution) necessarily gives up this one "
      "true catch: the turn now passes strictly while carrying a "
      "softened_modal advisory flag. Softened obligations without tripwire "
      "phrases join paraphrased advice in the LLM judge's assigned scope.")
    a("")
    a("## Per-turn results (v1.1)")
    a("")
    a("| id | cond | human | v1.0 | v1.1 | agree | strict flags | advisory |")
    a("|---|---|---|---|---|---|---|---|")
    for x in rows:
        ag = "yes" if x["v11"] == x["human"] else ("FP" if x["v11"] == "FAIL"
                                                   else "FN")
        rules = Counter(d["rule"] for d in x["violations"])
        rule_s = ", ".join(f"{k} x{v}" if v > 1 else k
                           for k, v in sorted(rules.items())) or "-"
        adv_s = str(len(x["advisory"])) if x["advisory"] else "-"
        a(f"| {x['id']} | {x['condition']} | {x['human']} | {x['v10']} | "
          f"{x['v11']} | {ag} | {rule_s} | {adv_s} |")
    a("")

    out = HERE / "RESCORE.md"
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"wrote {out}")
    print(f"FP {fail_pass}/{n} = {fp_of_50:.1%} | FN {pass_fail}/{n} | "
          f"agree {agree}/{n} | {verdict_word}")
    for x in residual:
        print("residual FP:", x["id"], viol_str(x["violations"]))
    for x in new_dis:
        print("new disagreement:", x["id"], x["human"], "->", x["v11"],
              viol_str(x["violations"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
