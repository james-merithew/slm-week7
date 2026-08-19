# Requirements Ledger — Week 7 SLM

Statuses: **MET** (with evidence file:line) / **PARTIAL** / **MISSING** / **OWED** (blocked on owner action).
Source of truth: [docs/brief.md](brief.md) — re-read the PDF before any closure claim.

Last updated: 2026-08-18 ~3:00 PM (MVP day — API-credit wall standing; see OWED register).

## Checkpoint 1 — Architecture Defense (T+4hrs)

| # | Requirement | Status | Evidence / blocker |
| --- | --- | --- | --- |
| AD1 | Falsifiable Behavior Spec (1–2 sentences, stranger-scoreable) | MET | v2.1 spec — [DECISIONS.md](DECISIONS.md), defense page beat 02; panel-vetted |
| AD2 | Prompt-Ceiling Ablation: ≥2 frontier models, different families | MET | Claude + Mistral, 96 convs each ([combined table](../evidence/2026-08-18/ablation-combined/results.md)) |
| AD3 | Prompt-Ceiling Ablation: ≥3 strategies (zero-shot, few-shot, structured/CoT) | MET | All 3 strategies × 32 scenarios run on Claude: zero_shot 6%, few_shot 16%, structured_cot 16% strict pass |
| AD4 | ≥30 scenarios per model × strategy, LLM-as-judge scored | MET | 32/cell, all 6 cells; judge audit 15% deterministic sample |
| AD5 | Results table: mean Spec-adherence + Robustness per model × strategy | MET | All 6 rows ([ablation-combined/results.md](../evidence/2026-08-18/ablation-combined/results.md)) |
| AD6 | Paragraph naming the failure mode that survives best prompting | MET | Mechanical fidelity, confirmed in BOTH families ([ablation-report.md](ablation-report.md)): unearned_word + fabricated_quote dominate; ceiling 16%/6% |
| AD7 | Architecture plan to defend (data gen → filter → train → eval) | MET | [defense-week7.html](defense/defense-week7.html) beat 03 + [presentation.md](defense/presentation.md) |

## Checkpoint 2 — MVP (Tuesday midnight)

| # | Requirement | Status |
| --- | --- | --- |
| M1 | Finalized Behavior Spec | MET — v3 ([prompts/behavior_spec.md](../src/ablation/prompts/behavior_spec.md), decision logged, tests green) |
| M2 | Full Prompt-Ceiling Ablation report submitted | MET — 192/192 convs, 2 families × 3 strategies × 32; report [docs/ablation-report.md](ablation-report.md), table [ablation-combined/results.md](../evidence/2026-08-18/ablation-combined/results.md); ceiling: 16% (Claude few_shot), 6% (all Mistral) |
| M3 | Eval harness committed: LLM-judge + behavioral check + base-vs-tuned mechanism | MET — [eval.py](../eval.py) one-command evaluator: deterministic checker headline + sampled judge audit + `--baseline` base-vs-tuned side-by-side; hf:/claude:/google:/openai: subjects |
| M4 | Full loop generate → train → eval runs end-to-end (smoke batch) | MET — generate ([v2](../data/dataset/v2/DATASET.md), 28 real dialogs) → train (real data, masking verified, loss 1.25→0.95, `runs/20260818-200031-N28-seed3407/`) → eval ([loop-smoke/results.md](../evidence/2026-08-18/loop-smoke/results.md), checker-scored via eval.py; judge leg owed pending credits) |
| M5 | First real dataset generated and filtered | MET — v3: 123 checker-filtered dialogs, Sonnet 5 teacher, provenance + filter hashes in [v3/STATS.json](../data/dataset/v3/STATS.json) (budget decision logged in DECISIONS.md) |
| M6 | First real QLoRA run completed | MET — Qwen3-4B QLoRA on Modal L4 (Unsloth path, CUDA): N=123, 3 epochs, loss 1.38→0.79, 19 min ([runs/20260818-220624-N123-seed3407/](../runs/20260818-220624-N123-seed3407/RUN.json) — config copy, loss CSV, dataset SHA, adapter) |
| M7 | First base-vs-tuned numbers in verification format (raw judge JSONL) | MET — base 0% vs tuned **20%** strict pass (N=10 first pass; viol/100w 0.87→0.51), transcripts + judge_verdicts.jsonl in [m7-base-vs-tuned/](../evidence/2026-08-18/m7-base-vs-tuned/results.md); tuned exceeds both frontier ceilings (16%/6%) |

## Checkpoint 3 — Early Submission (Thursday midnight)

| # | Requirement | Status |
| --- | --- | --- |
| E1 | ≥1 failure mode diagnosed from MVP eval, fixed via data change (v2 dataset) | MISSING |
| E2 | Updated base-vs-tuned numbers + raw judge transcripts | MISSING |
| E3 | ≥2 points on Data-Efficiency curve (or documented reason behind) | MISSING |
| E4 | Draft final artifacts: dataset shape, checkpoint, in-progress Brainlift | MISSING |

## Checkpoint 4 — Final (Sunday noon)

| # | Requirement | Status |
| --- | --- | --- |
| F1 | Dataset published | MISSING |
| F2 | Model public on HF Hub + running inference demo | MISSING |
| F3 | Results table: base vs tuned, own eval set AND staff held-out set | MISSING |
| F4 | Full Data-Efficiency curve + justified minimum viable N | MISSING |
| F5 | Brainlift with evidence | MISSING |
| F6 | 3–5 min demo video incl. live grader-supplied prompt | MISSING |

## Cross-cutting verification requirements (MVP onward)

| # | Requirement | Status |
| --- | --- | --- |
| V1 | Public HF checkpoint w/ exact commit hash | MISSING |
| V2 | One-command eval: `eval.py --model <hf-repo-id> --eval-set <path>` | MISSING |
| V3 | Raw per-example judge transcripts as JSONL | MISSING |
| V4 | Harness runnable against staff held-out set (no hardcoded scenarios) | MISSING |
| V5 | Pinned versions: HF model commit hash + eval-code commit hash | MISSING |
| V6 | Demo shows grader-supplied prompt live, base vs tuned | MISSING |
| V7 | Ablation reproducibility: prompt-ceiling script + training logs shipped | MISSING |

## OWED register (blocked on owner)

| Item | Needed for | Since |
| --- | --- | --- |
| **Anthropic credit top-up (~$30–50)** — platform.claude.com → Plans & Billing (verified still empty 2026-08-18 2:57 PM) | M2 (70 remaining Claude convs), M5 (272 remaining dialogs), all judge audits | 2026-08-18 |
| **`MISTRAL_API_KEY`** — free, no card: console.mistral.ai → API Keys; set as user env var | M2/AD2 — second family (96 convs, ready to fire) | 2026-08-18 |
| **`modal setup`** — one command in a terminal, browser auth | M6 — real QLoRA run (no local NVIDIA GPU) | 2026-08-18 |

Resolved from this register: Gemini key (obtained, then ruled out — free tier is 20 req/day/model, structurally insufficient; superseded by Mistral per [DECISIONS.md](DECISIONS.md)). OpenAI key (optional upgrade, never provided — 2-family floor met via Mistral instead).

## DROPPED register (deliberate scope calls)

*(empty)*
