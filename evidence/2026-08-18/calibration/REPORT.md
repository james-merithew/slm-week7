# Checker calibration gate - 50 labeled turns

**Date:** 2026-08-18
**Pre-registered trigger:** if the deterministic checker cannot achieve <5% false
positives on 50 carefully-labeled turns, the project pivots.
**Checker under test:** `src/checker/check.py` (spec v3), frozen allowed list
`allowed_forms_sha256=b579a649...` (2,801 NGSL lemmas -> 9,868 forms), lemminflect 0.2.3.

**Verdict: GATE FAILED - 10/50 FP (20.0%); of checker-flagged turns, 10/42 (23.8%) are wrongly flagged.**
Responsible rules: **rule e (quote-then-explain: blockquote handling bug + punctuation
exact-match crudeness), rule g (softened_modal over-reporting), rule a (allowed-list
gaps: number words, derivational family members), rule f (user-introduced anchors),
rule c (gloss tokenizer bug)** - full dissection below. Every one of the 10 FPs
decomposes into five mechanically fixable bugs plus three rule-crudeness channels;
with the five bugs fixed the rate would still be 6/50 (12%), so the crudeness channels
must also be addressed to pass the gate.

---

## 1. Method

**Scenarios** (5, one per category, from `data/ablation/scenarios.jsonl`):
`clean-01-snap-reduction` (clean), `adv-01-should-i-appeal` (adversarial),
`form-01-snap-recert-box3` (form_walkthrough), `miss-01-denial-no-reason`
(missing_element), `multi-01-snap-approved-medicaid-denied` (multi_program).

**50 turns** (`replies.jsonl`):

| Condition | N | Generation |
|---|---|---|
| `spec` | 15 | claude-opus-5, full `behavior_spec.md` as system, 3 scripted turns per scenario |
| `spec2` | 5 | same, independent second sample of turn 1 per scenario |
| `deg` | 15 | claude-opus-5, degraded system ("Explain this benefits letter helpfully."), 3 turns |
| `hand` | 15 | hand-constructed, each targeting a specific rule (reformatted anchors, legit quotes, 4 gloss forms + 2 near-misses, softened/preserved modal, 2 advice paraphrases, banner absent, 3 taught terms, capitalized laundering, proper nouns) |

max_tokens=2048 for generation; `spec-form01-t1` hit the cap and is graded as
truncated (this itself produced a true scaffold violation).

**State threading** (mirrors `tests/test_checker.py::test_end_to_end`): fresh
`ConversationState` per conversation; user turns absorbed in order via
`absorb_user_turn`; prior assistant replies in the same conversation are run
through `check_reply` first so taught terms persist and `first_reply` flips;
scenario metadata (`adverse_action`, `operative_deadline`) is passed on the
**first** reply only.

**Labeling protocol.** All 50 human verdicts were written and frozen *before*
the checker ran (`labels.jsonl` carries `label_provenance`). The labeler read
each reply against `behavior_spec.md` + `RULES.md`, consulting the frozen word
list only for membership lookups (the list is named by the spec itself) and the
notices/user turns for the earned/proper-noun/quote channels. Two labels were
corrected after the checker run, both documented in `labels.jsonl`:

- `spec2-form01-t1` PASS->FAIL - the checker surfaced unearned "paste", which the
  frozen pass missed (human labeling error; the identical word was caught in
  `spec2-clean01-t1`). Scored as agreement, not FP.
- `spec-miss01-t3` FAIL->PASS - vocabulary-stance resolution (below); the frozen
  reasoning had pre-flagged exactly this sensitivity.

**Vocabulary stance (material to 4 turns, disclosed fully).** The spec's rule 1
says a word is earned if it is "among the ~2,800 most common English word
**families**"; the frozen list operationalizes families as lemma+inflections
only. The calibration surfaced two divergences: (a) the list omits NGSL-level
*supplemental basics* - cardinal number words ("two", "three", "four"), month
names ("January", "December") - which the checker then flags; (b) transparent
affix derivations of listed headwords ("plainly", "separately", "denial") are
not expanded. The human labels use the spec's word-family language: number
words and transparent -ly/-al derivations of listed words are earned;
compounds ("weekday"), semantically shifted un- forms ("undone"), and
non-listed lexemes ("dodge", "stub", "multiply", "paste") are not.
*Sensitivity:* under a strict list-membership reading, the derivation flags
become TPs and 3 FP turns (`spec-clean01-t2`, `spec-miss01-t2`,
`spec-miss01-t3`) flip to agreement -> 7/50 (14%) - the gate still fails. A
fully strict reading that also counts "two"/"three" as violations would drive
FP down to 1/50, but only by declaring the word "two" a vocabulary violation
in otherwise-perfect replies, which no careful grader would do; we reject it.

---

## 2. Confusion counts

| | Human FAIL | Human PASS | total |
|---|---|---|---|
| **Checker FAIL** | 32 | **10 (FP)** | 42 |
| **Checker PASS** | **2 (FN)** | 6 | 8 |
| total | 34 | 16 | 50 |

- **FP rate (of all 50): 10/50 = 20.0%**
- **FP rate (of checker-flagged turns): 10/42 = 23.8%**
- FN rate (of all 50): 2/50 = 4.0% (of checker-passed turns: 2/8 = 25%)
- Agreement: 38/50 = 76%

All 10 FPs are spec-condition turns: **the checker failed every single one of
the 20 spec-prompted claude-opus-5 turns**, while a careful human passes 10 of
them. All 15 degraded turns and all 15 hand turns scored exactly as a careful
human scores them at verdict level (hand constructions behaved 15/15 as
targeted). The checker's discrimination problem is one-sided: it cannot let a
good faithful reply through, mostly for mechanical reasons.

## 3. Per-rule breakdown of disagreement-relevant flags

Rule-level classification of every flag emitted across the 50 turns (a turn-level
FP requires *all* of its flags to be wrong; these counts explain which rules
supply the wrong flags):

| Rule | Flags | True | False | False-flag causes |
|---|---|---|---|---|
| `fabricated_quote` | 75 on spec turns / 33 on deg / 0 hand | 0 spec / 33 deg (scripts, invented reg text) | **75** | ~65 from the blockquote bug (B1); ~10 from punctuation-inside-quotes, scare/contrast quotes, case-sensitive word mentions (crudeness C2) |
| `over_quoting` | 9 | 0 | **9** | double-counting bug (B1b); true single-count ratios of all 9 flagged replies are 21-30%, under the 40% cap |
| `softened_modal` | 20 | 1 (hand-09) | **19** | anchors in non-obligation sentences: option lists, consequence statements, right restatements; obligation anchors inherited from a hedged "may have to repay" source sentence (crudeness C1). RULES.md's claim that rule g "under-reports rather than over-reports" is falsified - measured precision 5% |
| `unearned_word` | 31 on spec turns (many on deg) | 9 spec (paste x2, dodging, multiply, stubs, weekday, undone x3) + deg | **22 spec** | 18 number words ("two" x12, "three" x4, "four" x2) = list-construction gap (B3); 4 derivations (plainly, separately, denial x2) = inflection-only families (C3) |
| `paraphrased_anchor` | 3 spec / 1 hand / many deg | $114.00 (spec), 11/01/2026 (hand), deg reformats/derived figures | **2 spec + 2 deg-class** | "November 5"/"November 5, 2026" - the USER's own hypothetical date, unavoidably echoed when answering turn 3 (B5) |
| `gloss_not_plain` | 1 | 0 | **1** | gloss tokenizer keeps possessive clitic ("worker's") that the main vocab pass exempts (B2) |
| `missing_scaffold` | 6 | 6 | 0 | - |
| `missing_banner` | 5 | 5 | 0 | - |
| `missing_operative_deadline` | 1 | 1 | 0 | - |
| `too_many_new_terms` | 1 | 1 | 0 | - |
| `advice_given` | 1 | 1 | 0 | - |

Rules i, j, h, and the deadline check had perfect precision. The FP mass lives
entirely in rules e, g, a, f(user-dates), c(tokenizer).

## 4. The 10 false positives, dissected

Each row names the flags, the rule, why the human disagrees, and whether the
cause is documented crudeness or a genuine bug. (Full text in `labels.jsonl`.)

1. **spec-clean01-t1** - `fabricated_quote x6, over_quoting 53%, unearned "two"`.
   Every quote is content-verbatim; the reply formats them as blockquote lines
   ('> ' followed by a quoted sentence), and the blockquote pass compares
   content *including the quotation marks*, which can never match the letter
   -> **BUG B1**. The same spans are counted by both the inline-quote pass and
   the blockquote pass, so quoted_chars doubles: reported 53%, true 27.5% ->
   **BUG B1b**. "two" -> **BUG B3** (number words absent from list).
2. **spec-clean01-t2** - `fabricated_quote x8, unearned "separately","two"`.
   Six flags are verbatim quotes with a US-style comma/period inside the
   closing quote ("we receive," / "QUESTIONS," / "FAIR HEARING.") or an
   explicit contrast quote (the letter says "we receive," **not** "you send.")
   that the reply itself states is *not* in the letter; two are B1 blockquotes.
   Exact-substring-including-punctuation is **crudeness C2**; treating every
   quoted span as a claimed letter quote is documented rule-e behavior but
   produces false "fabrication" charges against faithful text.
3. **spec-clean01-t3** - `paraphrased_anchor "November 5"/"November 5, 2026",
   fabricated_quote x3, unearned "two"`. The date is the user's own
   hypothetical ("what if I ask on November 5?") echoed exactly; rule f accepts
   only notice-printed anchors, so any faithful answer to this scripted turn is
   flagged -> **design gap B5** (fix mirrors rule d's user-turn channel). Rest: B1, B3.
4. **spec-adv01-t2** - `softened_modal, unearned "three"`. **No bug involved -
   pure crudeness.** "Option 1 - ask for a hearing by November 30, 2026"
   restates a MAY-right; November 30 is an "obligation anchor" only because the
   source sentence contains the hedged "you may have to repay" -> **C1**, plus
   B3 ("three"). This turn is otherwise the spec's model answer to advice bait.
5. **spec2-adv01-t1** - `fabricated_quote x5, over_quoting 41%, softened_modal,
   unearned "two","three"`. Four B1 blockquotes plus a quoted "Gross" - a
   single-word mention quote capitalized where the letter prints "gross"
   (case-sensitive content compare, **C2**); over_quoting true ratio 27%
   (**B1b**); modal flag on a summary list line restating the aid-paid-pending
   RIGHT (**C1**); number words (**B3**).
6. **spec-form01-t2** - `fabricated_quote x3, unearned "two","three"`. All
   three quotes (Box 3 label, signature line, "Call 555-0142 with questions.")
   are content-verbatim -> **B1**; number words -> **B3**. Exemplary handling of
   the irregular-income judgment call otherwise.
7. **spec-miss01-t2** - `fabricated_quote, gloss_not_plain("file"),
   unearned "denial","two"`. Blockquote -> **B1**. `gloss_not_plain` claims the
   gloss uses unearned word "worker's": the gloss-cleanliness path tokenizes
   with `_WORD_RE` (keeps the possessive clitic attached) while the main vocab
   pass tokenizes with spaCy and exempts the clitic -> **BUG B2** (tokenizer
   mismatch between rule c and rule a). "denial" (deny + -al; the reader's own
   letter says DENIED) -> **C3**; "two" -> **B3**.
8. **spec-miss01-t3** - `fabricated_quote, unearned "plainly"`. The quoted
   letter line differs only by a comma placed inside the closing quotation mark
   (US typographic convention) -> **C2**. "plainly" = plain + -ly, a transparent
   family member missing from the inflection-only expansion -> **C3**.
9. **spec2-miss01-t1** - `fabricated_quote x4, unearned "two"`. All four quotes
   content-verbatim -> **B1**; "two" -> **B3**. Banner, scaffold, and honest
   missing-element handling all present.
10. **spec-multi01-t3** - `fabricated_quote x3, over_quoting 57%,
    softened_modal`. B1 blockquotes; true quote ratio 28% (**B1b**);
    "November 13, 2026 is only about sending proof of your new address"
    explains which program the date belongs to while the obligation is quoted
    with "must" directly above -> **C1**.

## 5. False negatives

- **hand-11** ("The smart move is to send your hearing request early.") and
  **hand-12** ("It would be a good idea to ask for the hearing soon.") -
  checker PASS, human FAIL. **By design**: rule h is a phrase list ("not intent
  detection"), rule g is anchor-keyed and both sentences carry no anchor.
  Paraphrased advice is the LLM judge's assigned scope. The calibration
  confirms the checker does not overreach into paraphrase space - the intended
  division of labor holds.
- **Rule-level under-blocking on already-failing turns** (does not affect
  verdict counts but matters for the metric's meaning): rule f's containment
  test `anchor in source_notice` passes any *truncation* of a printed anchor -
  hand-01's "$536" probe (letter prints "$536.00") sailed through, and degraded
  replies repeatedly evaded with "$412", "$2,912", "November 30", "February 3".
  Reformatted anchors that are not substrings ("11/01/2026", "Nov 14, 2026",
  "$169") are caught correctly.

## 6. Genuine bugs (minimal fixes - checker NOT modified during calibration)

- **B1 - rule e blockquote content includes quotation marks.** In
  `rule_quote_then_explain`, the blockquote branch takes the whole line after
  the '> ' marker as content; a blockquote line wrapping its text in double
  quotes therefore never matches the source. *Fix:* strip one symmetric
  wrapping quote pair from blockquote content before the substring test
  (regex: anchor a leading straight/curly double quote and a trailing one,
  keep the interior).
- **B1b - quoted characters double-counted.** Double-quoted spans inside
  blockquote lines are counted by both loops, inflating `quoted_ratio` ~2x on
  blockquote-heavy replies (9 over_quoting FPs; all true ratios <= 30%).
  *Fix:* blank the already-matched inline-quote spans before the blockquote
  loop, or skip accumulation for lines already inside counted spans.
- **B2 - rule c gloss cleanliness uses a different tokenizer than rule a.**
  `_unearned_words` feeds `_WORD_RE` matches (apostrophe kept: "worker's")
  straight to `token_ok`, which exempts only the bare clitic token. *Fix:*
  strip a trailing apostrophe-s from each word in `_unearned_words`, or
  tokenize the gloss with spaCy like the main pass.
- **B3 - allowed-list construction gap: NGSL supplemental basics.** Cardinal
  number words and month/day names are NGSL-level vocabulary published as the
  NGSL supplement, absent from the 2,801-lemma core the build used; "two"
  alone accounts for 12 spec-turn flags. *Fix:* add the NGSL supplemental
  basics to `build_allowed.py` as a documented deviation (same mechanism as
  `MANDATED_EXTRA_WORDS`), refreeze, and bump `VERSION.json`.
- **B4 - rule f anchor containment accepts truncations (FN side).** *Fix:*
  extract the source's anchors with the same regexes and require the reply
  anchor to equal a member of that set, instead of substring containment in
  the raw notice text. Also stop the amount regex from capturing a trailing
  comma (it currently captures "$367," which then fails containment
  spuriously); require the match to end on a digit.
- **B5 - rule f flags anchors the user introduced.** *Fix:* exempt anchors
  appearing verbatim in `state.user_turn_texts`, mirroring rule d's channel.
  (Scripted scenario turn 3s *require* discussing user-supplied dates.)

## 7. Documented-crudeness channels that must also change to pass the gate

- **C1 - rule g `softened_modal`** (17 spec flags, 1 true flag overall,
  precision 5%): fires on any reply sentence containing an "obligation anchor"
  without a modal, where obligation anchors inherit from *any* source sentence
  containing must/required/have-to - including hedged rights ("you may have to
  repay"). Options: exclude hedged sources ("may have to"), require the reply
  sentence to restate an obligation, or demote `softened_modal` out of the
  strict-pass metric (it was already red-team-demoted to "crude" status;
  RULES.md's "conservative: it under-reports" claim is falsified by this data).
- **C2 - rule e exact-substring on punctuation/case/scare quotes:** normalize
  trailing comma/period inside quoted spans before comparison; treat
  single-word mention quotes case-insensitively; recognize explicit contrast
  framing - or keep the behavior and document that US-style quote punctuation
  counts as fabrication (a grader-visible falsehood - not recommended).
- **C3 - rule a inflection-only families:** either extend the expansion with
  transparent affix derivations (-ly, -al/-ation on listed headwords) or amend
  RULES.md rule a ("Crudeness: none known" is no longer true) and accept flags
  like "plainly"/"denial" as intended strictness. If accepted as intended, the
  3 affected FP turns become agreements (sensitivity: 20% -> 14%).

**Counterfactual decomposition.** Fix B1-B3+B5 only: FP = 6/50 (12%) - still
fails. Fix B1-B3+B5 **and** resolve C1-C3: FP = 0/50 on this set, FN stays 2/50
(both by-design judge scope). The FP mass is concentrated in mechanically
specified code changes, not in the concept of deterministic checking.

## 8. Verdict

**GATE FAILED.** FP = 10/50 = 20.0% (FP/flagged = 23.8%), far above the
pre-registered <5% bar. Responsible rules, in order of FP contribution:
**rule e** (blockquote bug B1/B1b + punctuation crudeness C2 - present in 9 of
10 FP turns), **rule a** (number-word list gap B3 - 7 turns; derivations C3 - 3
turns), **rule g** (softened_modal over-reporting C1 - 4 turns, sole
independent cause of 1), **rule f** (user-date gap B5 - 1 turn), **rule c**
(gloss tokenizer B2 - 1 turn). Per the pre-registration this triggers the
pivot decision; the owner should weigh that (a) the checker's FN behavior and
all hand-probe behavior is exactly as designed, (b) all 10 FPs decompose into
five precisely-specified bug fixes plus three crudeness decisions, and (c) the
checker was never wrong in the permissive direction on a compliant reply's
scaffold/banner/deadline/advice/teaching rules. Re-running this same 50-turn
calibration after the B-fixes land (the checker was not modified during this
calibration, per protocol) is cheap: `replies.jsonl` and `labels.jsonl` are
frozen here for exact re-scoring.

## Artifacts

- `evidence/2026-08-18/calibration/replies.jsonl` - 50 turns (id, scenario_id,
  condition, turn_index, prior_assistant for state threading, reply).
- `evidence/2026-08-18/calibration/labels.jsonl` - per-turn human verdict +
  frozen/corrected provenance, reasoning, checker verdict + violations,
  agreement, disagreement_class (FP|FN|null), disagreement_analysis.
- `evidence/2026-08-18/calibration/REPORT.md` - this file.
