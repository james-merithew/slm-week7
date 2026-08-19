"""Merge ablation run directories into one combined results artifact.

    python -m src.ablation.merge_results --dirs DIR1 DIR2 ... --out MERGED_DIR

Concatenates transcripts.jsonl (the full per-conversation records) from each
input dir, de-duplicates on (model, strategy, scenario_id) keeping the LAST
occurrence (so a re-run supersedes an earlier partial), and regenerates
results.csv / results.md / judge_verdicts.jsonl via the runner's own
aggregate() + write_outputs() — the merged table is computed by the same code
as any single run.
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.ablation.run_ablation import aggregate, write_outputs  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m src.ablation.merge_results",
        description="Merge ablation run dirs into one combined artifact.")
    p.add_argument("--dirs", nargs="+", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)

    records: dict[tuple, dict] = {}
    for d in args.dirs:
        path = d / "transcripts.jsonl"
        if not path.exists():
            print(f"ERROR: {path} not found", file=sys.stderr)
            return 2
        n = 0
        with open(path, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                records[(rec["model"], rec["strategy"], rec["scenario_id"])] = rec
                n += 1
        print(f"{d}: {n} conversations")

    merged = list(records.values())
    print(f"merged: {len(merged)} unique (model, strategy, scenario) records")
    write_outputs(args.out, merged, aggregate(merged))
    print((args.out / "results.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
