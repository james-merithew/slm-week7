# Resume runbook — fire these the moment each blocker clears

Written 2026-08-18 ~3:05 PM. Three independent blockers; each unblocks its own
lane. Lanes can run concurrently. MVP deadline: tonight midnight.

## Blocker 1 — Anthropic credits (platform.claude.com → Plans & Billing, ~$30–50)

**Verify the wall is gone** (expect a JSON reply, not a credit error):

```bash
curl -s -X POST https://api.anthropic.com/v1/messages -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" -d '{"model":"claude-haiku-4-5-20251001","max_tokens":5,"messages":[{"role":"user","content":"hi"}]}'
```

**BUDGET PLAN (revised 2026-08-18 ~3:45 PM after owner cost constraint):
~$10 total.** Prompt caching now wired into all three Anthropic call sites
(subject, teacher, judge) — the ~30k-token spec+word-list prefix re-reads at
0.1x, which is what collapsed the old $30–50 estimate.

**Lane A — finish the Claude half of the ablation (~$6–7 incl. judge).**
Two missing strategies, full 32 scenarios each, judge trimmed to 15%:

```bash
python -m src.ablation.run_ablation --scenarios data/ablation/scenarios.jsonl --out evidence/2026-08-18/ablation-claude-r2 --models claude:claude-opus-5 --strategies few_shot structured_cot --workers 8 --judge-sample 0.15
```

Then ONLY the 6 zero_shot scenarios the credit wall killed (pre-filtered
file already written — merges with the existing 26-conv artifact):

```bash
python -m src.ablation.run_ablation --scenarios data/ablation/scenarios_zeroshot_topup.jsonl --out evidence/2026-08-18/ablation-claude-zeroshot-topup --models claude:claude-opus-5 --strategies zero_shot --workers 8 --judge-sample 0.15
```

**Lane B — dataset: 150 dialogs, Sonnet 5 teacher (~$3).** Sonnet at intro
pricing; the deterministic checker filter and judge audit hold the quality
bar, and Thursday's E1 regenerates the dataset with data fixes anyway, so
tonight's set only needs to train the first model. Log the teacher switch in
DECISIONS.md when run:

```bash
python -m src.datagen.run_datagen --n-dialogs 150 --seed 42 --workers 4 --out data/dataset/v3 --teacher-model claude-sonnet-5
```

(The --teacher-model flag is wired through to the Teacher client and to
provenance in train.jsonl / STATS.json, so the dataset self-documents the
Sonnet teacher.)

## Blocker 2 — `MISTRAL_API_KEY` (free, no card: console.mistral.ai → API Keys)

Set it (new terminals only pick up User-scope vars — set both):

```powershell
[Environment]::SetEnvironmentVariable('MISTRAL_API_KEY','<key>','User'); $env:MISTRAL_API_KEY='<key>'
```

Smoke one completion first (model alias check), then the full second family —
throttling is already pinned to concurrency 1 for mistral in the runner:

```bash
python -m src.ablation.run_ablation --scenarios data/ablation/scenarios.jsonl --out evidence/2026-08-18/ablation-mistral --models mistral:mistral-large-latest --strategies zero_shot few_shot structured_cot --workers 4
```

NOTE: the judge audit inside this run also needs Anthropic credits. If
mistral unblocks first, run with `--judge-sample 0` and re-run the judge
lane after top-up.

## Blocker 3 — `modal setup` (one command, browser auth; Modal grants free monthly credits)

```bash
pip install modal
```

```bash
modal setup
```

Then the real QLoRA run (Qwen3-4B, the frozen config) on whatever dataset
exists at that moment — for the MVP that is the 28-dialog v2 (documented as
N=28 first run; the sweep re-runs at scale later):

```bash
modal volume put slm-week7-runs data/dataset/v2/train.jsonl data/v2_train.jsonl
```

```bash
modal run src/train/modal_app.py::main --config src/train/config.yaml --n 28 --seed 3407 --extra "data.path=/vol/data/v2_train.jsonl"
```

Fetch the run dir back with `modal volume get slm-week7-runs <run-name>
runs/<run-name>`, export/merge, then M7 base-vs-tuned:

```bash
python eval.py --model hf:runs/<run-name>/export/merged --baseline hf:Qwen/Qwen3-4B-Instruct-2507 --eval-set data/ablation/scenarios.jsonl --out evidence/2026-08-18/m7-base-vs-tuned
```

(Judge sample inside eval.py defaults to 25% — needs credits; use
`--judge-sample 0` + re-judge later if running before top-up. Local CPU
inference of 4B over 32 scenarios is slow — hours; consider running the eval
on Modal or overnight if the checkpoint lands late.)

## Already done today (no action)

- Checker v1.1 gate PASSED (4.0% FP), pivot decisively rejected — target locked.
- 28-dialog checker-filtered dataset (`data/dataset/v2/`).
- Loop smoke on REAL data: masking verified at seq 4096; train+eval smoke in
  progress (`evidence/2026-08-18/loop-smoke/` when done).
- Ledger current as of 3:00 PM (`docs/requirements.md`).
