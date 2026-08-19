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

Command: `python -m src.datagen.run_datagen --n-dialogs 8 --seed 7 --workers 2 --out data/dataset/v1`

## Filter version

- checker spec: Benefits Notices, Explained — checker spec v3
- VERSION.json sha256: `578030bb845cfbe7a9a77004c19ab92af23db9a248927e4dccfd2b47eb78c0be`
- allowed_forms sha256: `b579a64922d73bcd3498eab8fd28d7f171a633e84dda0794c619f025d7b3d020`

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

- dialogs: 7/8 accepted (rate 0.875)
- first-pass turn acceptance: 0.2143 (6/28)
- repair success: 21/22
- first-pass violation histogram (teacher's raw output - evidence the
  constraint is hard even for the teacher):

```json
{
  "unearned_word": 24,
  "softened_modal": 10,
  "fabricated_quote": 8
}
```

Generated 2026-08-18T18:34:47+00:00 (seed 7).
