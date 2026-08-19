"""Run the LLM judge audit locally over an existing transcripts.jsonl.

    python -m src.ablation.judge_transcripts --dir EVAL_DIR [--judge-sample 0.15]

For eval runs whose generation happened remotely (no API key in the
container): loads EVAL_DIR/transcripts.jsonl, judges the deterministic sample
(same selection function as the runner, so the sample is reproducible),
rewrites judge_verdicts.jsonl and regenerates results.csv / results.md with
the judge columns filled in.
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import anthropic  # noqa: E402

from src.ablation.judge import judge_conversation  # noqa: E402
from src.ablation.run_ablation import (  # noqa: E402
    aggregate, judge_is_selected, write_outputs)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m src.ablation.judge_transcripts",
        description="Judge-audit an existing eval/ablation transcript dir.")
    p.add_argument("--dir", required=True, type=Path)
    p.add_argument("--judge-sample", type=float, default=0.15)
    args = p.parse_args(argv)

    path = args.dir / "transcripts.jsonl"
    records = [json.loads(line) for line in open(path, encoding="utf-8")]
    client = anthropic.Anthropic()

    scenarios = {}  # judge needs category/judge_note; reload from the eval set
    for line in open(REPO_ROOT / "data" / "ablation" / "scenarios.jsonl",
                     encoding="utf-8"):
        s = json.loads(line)
        scenarios[s["id"]] = s

    n_judged = 0
    for rec in records:
        if rec.get("judge") is not None:
            continue  # already judged (idempotent re-runs)
        if not judge_is_selected(rec["scenario_id"], args.judge_sample):
            continue
        sc = scenarios.get(rec["scenario_id"], {"id": rec["scenario_id"]})
        rec["judge"] = judge_conversation(client, rec["turns"], sc)
        n_judged += 1
        print(f"judged {rec['model']} {rec['scenario_id']}")

    write_outputs(args.dir, records, aggregate(records))
    print(f"\n{n_judged} conversations judged; outputs rewritten in {args.dir}")
    print((args.dir / "results.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
