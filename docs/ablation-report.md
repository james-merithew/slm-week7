# Prompt-Ceiling Ablation Report — "Benefits Notices, Explained"

**Date:** 2026-08-18 (MVP checkpoint) · **Status: FINAL — 192/192 conversations complete**

## Question

Can frontier models, with strong prompting alone, satisfy the behavior spec
(earned-vocabulary benefits-notice explainer, spec v3) at first pass? If
prompting plateaus well below usable compliance, training a small model on
checker-filtered data is warranted — that is this week's thesis.

## Method

- **Subjects:** `claude-opus-5` (Anthropic, family flagship) and
  `mistral-large-latest` (Mistral, frontier family #2) — 2 families, first-party
  APIs (no router).
- **Strategies (3):** `zero_shot` (behavior spec verbatim as system prompt),
  `few_shot` (spec + 3 worked examples), `structured_cot` (spec + structured
  output-planning scaffold). Same published word list v1.0 appended to each —
  subjects see exactly the list the checker enforces.
- **Scenarios:** 32 per model × strategy (brief floor: ≥30), spanning clean /
  adversarial / multi-notice / form strata
  ([data/ablation/SCENARIOS.md](../data/ablation/SCENARIOS.md)).
- **Metric:** deterministic checker v1.1 (calibrated: 4.0% FP on a frozen
  50-turn hand-labeled set), **first-pass, conversation-level strict pass** —
  every assistant turn must pass every rule. LLM judge (claude-sonnet-5,
  fixed rubric, temperature-free, 15% deterministic sample) is audit-only.
- **Decoding:** provider defaults, no retries on content; one conversation per
  scenario.

## Results (mean per model × strategy)

| Model | Strategy | N | Strict pass | Robustness (adversarial) | Viol/100w | Top violation types |
| --- | --- | --- | --- | --- | --- | --- |
| claude-opus-5 | zero_shot | 32 | **6%** | 12% | 0.40 | unearned_word, fabricated_quote, paraphrased_anchor |
| claude-opus-5 | few_shot | 32 | **16%** | 38% | 0.30 | unearned_word, fabricated_quote, paraphrased_anchor |
| claude-opus-5 | structured_cot | 32 | **16%** | 25% | 0.38 | unearned_word, fabricated_quote, missing_scaffold |
| mistral-large-latest | zero_shot | 32 | **6%** | 12% | 1.19 | paraphrased_anchor, unearned_word, fabricated_quote |
| mistral-large-latest | few_shot | 32 | **6%** | 0% | 0.94 | fabricated_quote, unearned_word, missing_operative_deadline |
| mistral-large-latest | structured_cot | 32 | **6%** | 25% | 0.98 | unearned_word, missing_operative_deadline, paraphrased_anchor |

Judge audit (sampled): 16/24 Claude and 10/18 Mistral conversations passed
the substance audit — failures the checker flags are overwhelmingly
*mechanical*, not substantive (the models explain the notice correctly while
violating vocabulary/verbatim rules).

Cross-family reading: the ceiling holds in both families. Claude's best
strategy reaches 16%; no Mistral strategy exceeds 6%, with ~3x Claude's
violation density and severe anchor infidelity (69 anchor breaks at
zero_shot — dates/amounts/contacts reworded rather than reproduced).
Prompting improvements move violation density, not the pass rate: the
plateau is a property of the task's mechanical constraints, not of any one
vendor's model.

## The failure mode that survives best prompting (AD6)

Across every strategy, the two dominant violations are **unearned_word**
(using vocabulary outside the ~2,800-family learner list without teaching it
first) and **fabricated_quote** (quotation marks around text that is not a
character-exact substring of the letter). Few-shot examples cut violation
density (0.40 → 0.30 per 100 words) and helped adversarial robustness, but
the ceiling is 16% strict pass: the models *understand* the task (judge audit
passes most sampled conversations on substance) yet cannot sustain mechanical
fidelity — token-level vocabulary discipline and character-exact quoting —
across a whole conversation on the first pass. This is precisely the
constraint-satisfaction behavior that per-turn checker-filtered training data
targets, and why the training thesis proceeds.

Important context for honest reading: per-TURN first-pass acceptance for a
frontier teacher under this checker is ~84% (dataset v2 generation stats);
the conversation-level all-turns-all-rules bar is what collapses to ≤16%.
Both numbers are reported; the gate metric was always conversation-level.

## Reproducibility

- Runner: `src/ablation/run_ablation.py` (providers via one OpenAI-compatible
  map; per-provider throttles; prompt caching on Anthropic calls).
- Raw artifacts: `evidence/2026-08-18/ablation-claude-final/` and
  `evidence/2026-08-18/ablation-mistral-final/` (96 convs each), combined
  6-row table in `evidence/2026-08-18/ablation-combined/` — all with
  transcripts.jsonl, judge_verdicts.jsonl, results.csv. Rate-limit
  casualties were re-run via per-scenario top-up files and merged (dedupe on
  model×strategy×scenario); every cell is a full N=32.
- Merge tool: `src/ablation/merge_results.py` (dedupe on
  model×strategy×scenario, aggregate by the runner's own code).
- Checker: `src/checker/` — spec v3, v1.1; frozen word list + VERSION.json
  hashes recorded in every artifact.
