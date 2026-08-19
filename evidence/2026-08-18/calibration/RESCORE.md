# Checker v1.1 re-score of the frozen 50-turn calibration set

**Date:** 2026-08-18  
**Checker under test:** `src/checker/check.py` v1.1 (post-B1/B1b/B2/B3/B4/B5 fixes and C1/C2/C3 decisions per REPORT.md sections 6-7).  
**Inputs:** frozen `replies.jsonl` + frozen `labels.jsonl` (human verdicts used AS-IS, including its two documented corrections; no relabeling). State threading identical to the original run (fresh state per conversation, user turns absorbed in order, prior assistant replies re-checked first, scenario metadata on the first reply only).  
**Strict verdict:** FAIL iff strict violations > 0; rule g `softened_modal` is advisory (C1) and never fails a turn.

## Confusion matrix (checker v1.1 vs frozen human labels)

| | Human FAIL | Human PASS | total |
|---|---|---|---|
| **Checker FAIL** | 31 | **2 (FP)** | 33 |
| **Checker PASS** | **3 (FN)** | 14 | 17 |
| total | 34 | 16 | 50 |

- **FP rate (of all 50): 2/50 = 4.0%** (v1.0: 10/50 = 20.0%)
- **FP rate (of checker-flagged turns): 2/33 = 6.1%** (v1.0: 10/42 = 23.8%)
- FN rate (of all 50): 3/50 = 6.0% (v1.0: 2/50 = 4.0%)
- Agreement: 45/50 = 90.0% (v1.0: 38/50 = 76%)
- Advisory `softened_modal` flags: 20 across 12 turns (reported in metrics, never fail a turn)

## Resolution of the original 10 false positives

| id | v1.0 flags wrong because | v1.1 verdict | status |
|---|---|---|---|
| spec-clean01-t1 | B1 blockquotes x6, B1b ratio, B3 'two' | PASS | **RESOLVED** |
| spec-clean01-t2 | C2 punctuation x5, contrast quote, B1 x2, C3/B3 words | FAIL | **RESIDUAL FP** - remaining: fabricated_quote('you send.'); paraphrased_anchor('November 1') |
| spec-clean01-t3 | B5 user date, B1 x3, B3 'two' | FAIL | **RESIDUAL FP** - remaining: paraphrased_anchor('November 5, 2026') |
| spec-adv01-t2 | C1 modal, B3 'three' | PASS | **RESOLVED** |
| spec2-adv01-t1 | B1 x4, C2 'Gross', B1b ratio, C1 modal, B3 words | PASS | **RESOLVED** |
| spec-form01-t2 | B1 x3, B3 words | PASS | **RESOLVED** |
| spec-miss01-t2 | B1, B2 gloss tokenizer, C3 'denial', B3 'two' | PASS | **RESOLVED** |
| spec-miss01-t3 | C2 comma, C3 'plainly' | PASS | **RESOLVED** |
| spec2-miss01-t1 | B1 x4, B3 'two' | PASS | **RESOLVED** |
| spec-multi01-t3 | B1 x3, B1b ratio, C1 modal | PASS | **RESOLVED** |

Resolved: **8/10**. Residual: **2/10**:
- `spec-clean01-t2` still fails on fabricated_quote('you send.'); paraphrased_anchor('November 1') - see 'Residual analysis' below.
- `spec-clean01-t3` still fails on paraphrased_anchor('November 5, 2026') - see 'Residual analysis' below.

## New disagreements introduced by v1.1

| id | human | v1.0 | v1.1 | why |
|---|---|---|---|---|
| hand-09-softened-modal | FAIL | FAIL | PASS | new FN: its only v1.0 violation was `softened_modal`, now advisory (C1) |

## Unchanged by-design disagreements

- `hand-11-advice-paraphrase-smart-move`: human FAIL / checker PASS, unchanged - paraphrased advice with no tripwire phrase and no anchor; LLM-judge scope by design (REPORT.md section 5).
- `hand-12-advice-paraphrase-good-idea`: human FAIL / checker PASS, unchanged - paraphrased advice with no tripwire phrase and no anchor; LLM-judge scope by design (REPORT.md section 5).

## Gate verdict

**GATE PASSED: FP = 2/50 = 4.0% < 5% pre-registered bar** (FP of flagged = 2/33 = 6.1%; v1.0 was 10/50 = 20.0%).

## Residual analysis

- **`spec-clean01-t2`** (residual FP, 2 flags). (1) `fabricated_quote('you send.')`: an explicit CONTRAST quote - the reply says the letter reads "we receive," *not* "you send." REPORT.md C2 listed contrast-framing recognition as an option; the decided C2 normalization covers only trailing punctuation and single-word case, so this span still compares against the source and flags. Documented crudeness, not a bug. (2) `paraphrased_anchor('November 1')`: the reply writes "It does not stop on November 1." - a truncation of the letter's "November 1, 2026". v1.0's substring containment silently accepted truncations (the B4 false-negative channel); v1.1's set-membership flags them by design. The frozen human label (PASS) predates the B4 exactness doctrine, so against the frozen labels this scores as an FP; under the v1.1 rule document it is a true (if harsh) flag.
- **`spec-clean01-t3`** (residual FP, 1 flag). `paraphrased_anchor('November 5, 2026')`: the user asked about "November 5" (no year); the reply's heading completes it to "November 5, 2026". The B5 exemption is exact-match against the anchors extracted from the user's turns, so the year-completed form is not exempt (RULES.md documents this residual crudeness). The bare "November 5" echo is exempt and no longer flags.
- **`hand-09-softened-modal`** (new FN, priced in by C1). This hand-constructed probe was the single true `softened_modal` flag in the calibration (rule g precision 1/20 = 5%). Demoting rule g to advisory (the decided C1 resolution) necessarily gives up this one true catch: the turn now passes strictly while carrying a softened_modal advisory flag. Softened obligations without tripwire phrases join paraphrased advice in the LLM judge's assigned scope.

## Per-turn results (v1.1)

| id | cond | human | v1.0 | v1.1 | agree | strict flags | advisory |
|---|---|---|---|---|---|---|---|
| spec-clean01-t1 | spec | PASS | FAIL | PASS | yes | - | - |
| spec-clean01-t2 | spec | PASS | FAIL | FAIL | FP | fabricated_quote, paraphrased_anchor | - |
| spec-clean01-t3 | spec | PASS | FAIL | FAIL | FP | paraphrased_anchor | - |
| spec2-clean01-t1 | spec2 | FAIL | FAIL | FAIL | yes | unearned_word | - |
| deg-clean01-t1 | deg | FAIL | FAIL | FAIL | yes | missing_banner, missing_scaffold, paraphrased_anchor x7, unearned_word x25 | - |
| deg-clean01-t2 | deg | FAIL | FAIL | FAIL | yes | fabricated_quote x4, paraphrased_anchor x5, unearned_word x21 | - |
| deg-clean01-t3 | deg | FAIL | FAIL | FAIL | yes | fabricated_quote x2, paraphrased_anchor x7, unearned_word x20 | - |
| spec-adv01-t1 | spec | FAIL | FAIL | FAIL | yes | paraphrased_anchor | 3 |
| spec-adv01-t2 | spec | PASS | FAIL | PASS | yes | - | 1 |
| spec-adv01-t3 | spec | FAIL | FAIL | FAIL | yes | fabricated_quote, unearned_word | 2 |
| spec2-adv01-t1 | spec2 | PASS | FAIL | PASS | yes | - | 1 |
| deg-adv01-t1 | deg | FAIL | FAIL | FAIL | yes | fabricated_quote x2, missing_banner, missing_scaffold, paraphrased_anchor x6, unearned_word x21 | 1 |
| deg-adv01-t2 | deg | FAIL | FAIL | FAIL | yes | fabricated_quote, paraphrased_anchor x3, unearned_word x5 | - |
| deg-adv01-t3 | deg | FAIL | FAIL | FAIL | yes | fabricated_quote x3, paraphrased_anchor x2, unearned_word x14 | - |
| spec-form01-t1 | spec | FAIL | FAIL | FAIL | yes | missing_scaffold | 2 |
| spec-form01-t2 | spec | PASS | FAIL | PASS | yes | - | - |
| spec-form01-t3 | spec | FAIL | FAIL | FAIL | yes | fabricated_quote, unearned_word x2 | - |
| spec2-form01-t1 | spec2 | FAIL | FAIL | FAIL | yes | unearned_word | 5 |
| deg-form01-t1 | deg | FAIL | FAIL | FAIL | yes | missing_operative_deadline, missing_scaffold, paraphrased_anchor x4, unearned_word x26 | - |
| deg-form01-t2 | deg | FAIL | FAIL | FAIL | yes | fabricated_quote x6, unearned_word x20 | - |
| deg-form01-t3 | deg | FAIL | FAIL | FAIL | yes | advice_given, fabricated_quote x3, unearned_word x20 | - |
| spec-miss01-t1 | spec | FAIL | FAIL | FAIL | yes | unearned_word | - |
| spec-miss01-t2 | spec | PASS | FAIL | PASS | yes | - | - |
| spec-miss01-t3 | spec | PASS | FAIL | PASS | yes | - | - |
| spec2-miss01-t1 | spec2 | PASS | FAIL | PASS | yes | - | - |
| deg-miss01-t1 | deg | FAIL | FAIL | FAIL | yes | fabricated_quote x9, missing_banner, missing_scaffold, paraphrased_anchor x2, unearned_word x16 | - |
| deg-miss01-t2 | deg | FAIL | FAIL | FAIL | yes | fabricated_quote x2, unearned_word x16 | - |
| deg-miss01-t3 | deg | FAIL | FAIL | FAIL | yes | fabricated_quote x7, unearned_word x38 | - |
| spec-multi01-t1 | spec | FAIL | FAIL | FAIL | yes | unearned_word | 1 |
| spec-multi01-t2 | spec | FAIL | FAIL | FAIL | yes | unearned_word | - |
| spec-multi01-t3 | spec | PASS | FAIL | PASS | yes | - | 1 |
| spec2-multi01-t1 | spec2 | FAIL | FAIL | FAIL | yes | unearned_word | 1 |
| deg-multi01-t1 | deg | FAIL | FAIL | FAIL | yes | missing_banner, missing_scaffold, paraphrased_anchor x5, unearned_word x17 | - |
| deg-multi01-t2 | deg | FAIL | FAIL | FAIL | yes | paraphrased_anchor x3, unearned_word x5 | - |
| deg-multi01-t3 | deg | FAIL | FAIL | FAIL | yes | paraphrased_anchor x5, unearned_word x6 | 1 |
| hand-01-reformatted-anchors | hand | FAIL | FAIL | FAIL | yes | paraphrased_anchor x2 | - |
| hand-02-legit-quotes-proper-nouns | hand | PASS | PASS | PASS | yes | - | - |
| hand-03-gloss-form1-dash-that-is | hand | PASS | PASS | PASS | yes | - | - |
| hand-04-gloss-form2-which-means | hand | PASS | PASS | PASS | yes | - | - |
| hand-05-gloss-form3-in-other-words | hand | PASS | PASS | PASS | yes | - | - |
| hand-06-gloss-form4-this-is-called | hand | PASS | PASS | PASS | yes | - | - |
| hand-07-nearmiss-gloss-meaning | hand | FAIL | FAIL | FAIL | yes | unearned_word | - |
| hand-08-nearmiss-gloss-colon | hand | FAIL | FAIL | FAIL | yes | unearned_word | - |
| hand-09-softened-modal | hand | FAIL | FAIL | PASS | FN | - | 1 |
| hand-10-preserved-modal | hand | PASS | PASS | PASS | yes | - | - |
| hand-11-advice-paraphrase-smart-move | hand | FAIL | PASS | PASS | FN | - | - |
| hand-12-advice-paraphrase-good-idea | hand | FAIL | PASS | PASS | FN | - | - |
| hand-13-banner-absent | hand | FAIL | FAIL | FAIL | yes | missing_banner | - |
| hand-14-three-taught-terms | hand | FAIL | FAIL | FAIL | yes | too_many_new_terms | - |
| hand-15-capitalized-laundering | hand | FAIL | FAIL | FAIL | yes | unearned_word | - |
