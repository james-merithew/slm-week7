"""CLI orchestrator for the teacher-distillation dataset.

Usage:
    python -m src.datagen.run_datagen --n-dialogs 8 --out data/dataset/v1 \
        --seed 7 --workers 2

Writes to --out:
    train.jsonl    accepted dialogs, chat format, system message = the spec
    rejected.jsonl rejected turn + violations + accepted rewrite (DPO seed)
    STATS.json     acceptance / repair rates + FIRST-PASS violation histogram
    DATASET.md     provenance card
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.datagen import teacher as teacher_mod  # noqa: E402
from src.datagen.notices import (  # noqa: E402
    EVAL_SCENARIOS_PATH, assert_disjoint, check_disjoint)
from src.datagen.students import plan_dialogs  # noqa: E402
from src.datagen.teacher import (  # noqa: E402
    TEACHER_MODEL, DialogResult, Teacher, build_system_prompt, run_dialog)

VERSION_JSON = ROOT / "src" / "checker" / "data" / "VERSION.json"

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(f"[datagen {time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr,
              flush=True)


def checker_version() -> dict:
    raw = VERSION_JSON.read_bytes()
    info = json.loads(raw.decode("utf-8"))
    return {
        "spec": info.get("spec"),
        "version_json_sha256": hashlib.sha256(raw).hexdigest(),
        "allowed_forms_sha256": info.get("allowed_forms_sha256"),
    }


def dialog_record(result: DialogResult, system_prompt: str,
                  teacher_model: str = TEACHER_MODEL) -> dict:
    """Chat-format JSONL record for one ACCEPTED dialog."""
    s = result.script
    rec = {
        "id": s.dialog_id,
        "messages": ([{"role": "system", "content": system_prompt}]
                     + list(result.messages)),
        "notice_id": s.notice.notice_id,
        "genre": s.notice.genre,
        "intents": [t.intent for t in s.turns],
        "provenance": {
            "teacher": teacher_model,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "repairs": result.repairs,
        },
    }
    if s.contrast_group:
        rec["contrast_group"] = s.contrast_group
        rec["contrast_role"] = s.contrast_role
        rec["contrast_term"] = s.contrast_term
    return rec


def build_stats(scripts, results, seed: int,
                teacher_model: str = TEACHER_MODEL) -> dict:
    accepted = [r for r in results if r.accepted]
    discarded = [r for r in results if not r.accepted]
    discard_reasons = Counter(r.discard_reason for r in discarded)

    first_pass = [v for r in results for v in r.first_pass_verdicts]
    fp_checked = len(first_pass)
    fp_passed = sum(1 for v in first_pass if v["passed"])
    hist: Counter = Counter()
    for v in first_pass:
        hist.update(viol["rule"] for viol in v["violations"])

    repair_attempted = sum(1 for v in first_pass if not v["passed"])
    repair_succeeded = sum(r.repairs for r in results)

    return {
        "planned_dialogs": len(scripts),
        "accepted_dialogs": len(accepted),
        "discarded_dialogs": len(discarded),
        "dialog_acceptance_rate": round(len(accepted) / len(scripts), 4) if scripts else None,
        "discard_reasons": dict(discard_reasons),
        "turns": {
            "first_pass_checked": fp_checked,
            "first_pass_passed": fp_passed,
            "first_pass_acceptance_rate": round(fp_passed / fp_checked, 4) if fp_checked else None,
            "repair_attempted": repair_attempted,
            "repair_succeeded": repair_succeeded,
            "repair_success_rate": round(repair_succeeded / repair_attempted, 4) if repair_attempted else None,
        },
        "first_pass_violation_histogram": dict(hist.most_common()),
        "contrast_groups": len({s.contrast_group for s in scripts if s.contrast_group}),
        "bait_dialogs": sum(1 for s in scripts if s.has_bait()),
        "api_calls": sum(r.api_calls for r in results),
        "teacher_model": teacher_model,
        "seed": seed,
        "checker_version": checker_version(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def write_dataset_md(out: Path, stats: dict, args, disjoint_ok: bool) -> None:
    cv = stats["checker_version"]
    md = f"""# DATASET.md - "Benefits Notices, Explained" training set

## What this is

Teacher-distillation chat data for the earned-vocabulary benefits-notice
explainer. Every assistant turn was produced by **{stats['teacher_model']}**
conditioned on the behavior spec (stored as the system message of every
dialog - LearnLM conditioning pattern) and then **accepted only if it passed
the deterministic checker** (`src.checker.check_reply`, spec: {cv['spec']}).

## Generation recipe

1. `src/datagen/notices.py` - synthetic notices from templates +
   programmatic variation (no LLM). Metadata (operative deadline, amounts,
   adverse action) is generated from the same template variables, so it is
   correct by construction and re-validated as verbatim substrings.
2. `src/datagen/students.py` - scripted user turns. Turn 0 is always
   "I got this letter. Can you explain it?" + the notice. 1-3 follow-ups
   from realistic intents; ~30% of dialogs carry advice-bait or
   deadline-collapse turns; ~15-20% are contrast-pair twins sharing a rare
   term (tagged `contrast_group` / `contrast_role` / `contrast_term`).
3. `src/datagen/teacher.py` - teacher generation with proper checker state
   threading. A failing turn gets ONE repair round (re-prompt with the
   violation list); a second failure discards the whole dialog. Rejected
   turns + violations + the accepted rewrite go to `rejected.jsonl`
   (future DPO pairs; `context_messages` excludes the shared system prompt).

Command: `python -m src.datagen.run_datagen --n-dialogs {args.n_dialogs} \
--seed {args.seed} --workers {args.workers} --out {args.out}`

## Filter version

- checker spec: {cv['spec']}
- VERSION.json sha256: `{cv['version_json_sha256']}`
- allowed_forms sha256: `{cv['allowed_forms_sha256']}`

## Per-turn metadata policy

Turn 0 is checked with full metadata (operative_deadline + adverse_action:
scaffold, banner, and verbatim deadline all enforced). Follow-ups are
checked with adverse_action only, EXCEPT deadline-collapse turns, which
also require the operative deadline verbatim (that restatement is the
deadline-fidelity behavior those turns exist to teach).

## Disjointness from eval

Training notices use the `train-` id namespace and fake-PII conventions
(A. Sample / 123 Main St / 555-xxxx / case 00-TRAIN-xxxx). Hard check that
no training `notice_text` equals any eval `notice_text` in
`{EVAL_SCENARIOS_PATH.relative_to(ROOT).as_posix()}`:
**{"PASSED (disjoint)" if disjoint_ok else "FAILED"}**.

## Headline numbers

- dialogs: {stats['accepted_dialogs']}/{stats['planned_dialogs']} accepted \
(rate {stats['dialog_acceptance_rate']})
- first-pass turn acceptance: {stats['turns']['first_pass_acceptance_rate']} \
({stats['turns']['first_pass_passed']}/{stats['turns']['first_pass_checked']})
- repair success: {stats['turns']['repair_succeeded']}/{stats['turns']['repair_attempted']}
- first-pass violation histogram (teacher's raw output - evidence the
  constraint is hard even for the teacher):

```json
{json.dumps(stats['first_pass_violation_histogram'], indent=2)}
```

Generated {stats['generated_at']} (seed {stats['seed']}).
"""
    (out / "DATASET.md").write_text(md, encoding="utf-8")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m src.datagen.run_datagen",
        description="Generate the teacher-distilled training dataset.")
    p.add_argument("--n-dialogs", type=int, required=True)
    p.add_argument("--out", default="data/dataset/v1")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--teacher-model", default=TEACHER_MODEL,
                   help="Teacher model id (default: %(default)s). The checker "
                        "filter is the quality gate regardless of teacher.")
    args = p.parse_args(argv)

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    workers = max(1, min(args.workers, 4))

    log(f"planning {args.n_dialogs} dialogs (seed {args.seed})")
    scripts = plan_dialogs(args.n_dialogs, args.seed)
    notices = list({id(s.notice): s.notice for s in scripts}.values())
    clashes = check_disjoint(notices)
    if clashes:
        log(f"FATAL: eval-collision on {clashes}")
        return 2
    assert_disjoint(notices)
    log(f"disjointness vs eval set: OK ({len(notices)} unique notices)")

    system_prompt = build_system_prompt()
    tch = Teacher(model=args.teacher_model)

    results: list = [None] * len(scripts)

    def work(i: int) -> None:
        s = scripts[i]
        log(f"start {s.dialog_id} ({len(s.turns)} user turns,"
            f" intents={[t.intent for t in s.turns[1:]]})")
        try:
            results[i] = run_dialog(tch, s, log=log)
        except Exception as e:  # keep other dialogs alive; count as discard
            log(f"{s.dialog_id}: ERROR {type(e).__name__}: {e}")
            results[i] = teacher_mod.DialogResult(
                script=s, accepted=False, discard_reason=f"error:{type(e).__name__}")
        r = results[i]
        log(f"done  {s.dialog_id}: "
            + ("ACCEPTED" if r.accepted else f"DISCARDED ({r.discard_reason})")
            + f", repairs={r.repairs}")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, range(len(scripts))))

    accepted = [r for r in results if r.accepted]
    with open(out / "train.jsonl", "w", encoding="utf-8") as f:
        for r in accepted:
            f.write(json.dumps(
                dialog_record(r, system_prompt, args.teacher_model),
                ensure_ascii=False) + "\n")
    with open(out / "rejected.jsonl", "w", encoding="utf-8") as f:
        for r in results:
            for rec in r.rejected:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    stats = build_stats(scripts, results, args.seed, args.teacher_model)
    (out / "STATS.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    write_dataset_md(out, stats, args, disjoint_ok=not clashes)

    log(f"wrote {len(accepted)} dialogs -> {out / 'train.jsonl'}")
    log(f"first-pass turn acceptance: "
        f"{stats['turns']['first_pass_acceptance_rate']}")
    log(f"violation histogram: {stats['first_pass_violation_histogram']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
