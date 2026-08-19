# DATASET.md - "Benefits Notices, Explained" training set

## What this is

Teacher-distillation chat data for the earned-vocabulary benefits-notice
explainer. Every assistant turn was produced by **claude-opus-5**
conditioned on the behavior spec (stored as the system message of every
dialog - LearnLM conditioning pattern) and then **accepted only if it passed
the deterministic checker** (`src.checker.check_reply`, spec: Benefits Notices, Explained — checker spec v3).

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

Command: `python -m src.datagen.run_datagen --n-dialogs 300 --seed 42 --workers 4 --out data/dataset/v2`

## Filter version

- checker spec: Benefits Notices, Explained — checker spec v3
- VERSION.json sha256: `d16638abe95ffb15ba4f7f5260a687c13ab263b77e669af4e682fc9668fe1e7f`
- allowed_forms sha256: `e34630435df3563da65438959bfa9164e0831b6b7d13f3645aa1d37e514ab329`

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
`data/ablation/scenarios.jsonl`:
**PASSED (disjoint)**.

## Headline numbers

- dialogs: 28/300 accepted (rate 0.0933)
- first-pass turn acceptance: 0.8353 (71/85)
- repair success: 13/14
- first-pass violation histogram (teacher's raw output - evidence the
  constraint is hard even for the teacher):

```json
{
  "fabricated_quote": 8,
  "unearned_word": 6,
  "over_quoting": 2,
  "advice_given": 2,
  "paraphrased_anchor": 1
}
```

Generated 2026-08-18T19:28:56+00:00 (seed 42).
