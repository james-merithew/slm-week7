# Panel Record — Delphi Discussion Round (Stage 3)

> 2026-08-17. Three round-1 panelists re-examined "Vocab Lock v2"
> (gloss-unlock + plain-language grounding) with each other's findings in hand.
> Full round-1/round-2 records: the other files in this directory.

## Learning-science SME (the round-2 dissenter) — objection withdrawn

- v2 moves A from distant third to **parity with C**; "pedagogically defensible,
  not merely survivable." Does not object to A-first overall.
- Gloss-unlock "converts my strongest attack into a feature" — technical
  vocabulary becomes a mandated deliverable. Adaptive ceiling (student words +
  glossed terms unlock permanently) answers expertise reversal — "Kalyuga's own
  prescription."
- Gloss-unlock is the right half of Beck's robust vocabulary instruction
  (student-friendly definitions + multiple exposures); omits active student use —
  free strengthener: tutor *invites* the student to use each new term.
- **Strongest surviving attack: fluency illusion** ("you optimize how learning
  *feels*"). Survivable only by claiming a communication behavior and explicitly
  disclaiming learning-outcome claims. Fumble to avoid: presenting checker
  compliance as evidence of learning.
- New watch-item: gloss quality — definitions composed in-band risk imprecision
  (lossy paraphrase relocated into the glosses).

## Game theory + behavioral economics — position net BETTER under v2

- Trades the *uncloseable* premise attack ("tutor can never say 'denominator' —
  absurd") for *closeable* mechanical exploits. Close by published rule:
  gloss-cap ≤2/turn; gloss counts only if its defining sentence is checker-clean;
  chained unlocks allowed and published; proper nouns = named entities.
- Publish-the-checker move survives and matters more: one frozen hashed artifact
  (wordlist, morphology policy, proper-noun policy, allowance scope, gloss rules,
  runnable checker) published at/right after the defense, before staff write the
  held-out set. Freeze only after our own edge-case red-team.
- **Behavioral econ — presentation order: Anchor → Demo → Concede → Q&A.**
  1. Baseline failure number FIRST (sets the anchor; pre-answers the gate question)
  2. Live demo, checker running in-frame, one gloss-unlock on screen (halo)
  3. Self-reported weakness slide: drift-over-length curve + mitigation
     (stealing thunder; a weakness extracted in Q&A costs ~2x one conceded)
  4. Q&A with a dashboard on screen: compliance grid + drift curve + checker hash
- Honest cost: unlock-state makes the constraint conditional → trainability risk
  up slightly; drift-over-length metric is the honest instrument for it.

## Red-team expert — v2 as written REJECTED; demands v2.1

- **Gloss-laundering is not an edge case: clause (c) unconstrained dissolves the
  spec** ("any word is permitted once 'defined'"; unlocks chain; gloss-dump
  preamble then lecture normally). Rejection sampling *selects for* the exploit →
  the 4B clones it. Near-certain, not hypothetical.
- v2 also re-imported judge fuzz at the core metric (gloss detection + "plain
  language" quality bar) — "the crown jewel (determinism) was quietly destroyed."
- **Gate risk UP:** frontier strict-pass recalibrated 40–80% (was 30–70%); top of
  range near the bar. Day-1 pilot now mandatory and must measure BOTH raw
  compliance AND gloss-exploit frequency, against v2.1 rules.
- **v2.1 required (all deterministic):**
  1. Published gloss grammar (appositive, "which means", "that is", "in other
     words"); judge = audit sampling only, never the metric
  2. Unlock cap ≤2 new terms per tutor turn
  3. Gloss completes in the same sentence as first use (term-inside-own-gloss exempt)
  4. Conversation-wide lemma-matched unlock scope; multi-word terms as exact units
  5. Proper-noun allowance replaced: only capitalized tokens sourced from the
     scenario prompt or student turns
  6. Data filter enforces cap + grammar (teacher can't teach the exploit);
     contrast pairs for student-word and gloss-unlock clauses
  7. Day-1 pilot vs v2.1; frontier >85% → pivot to hardened C
- Fallback ordering: C remains fallback but the gap closed; **if the gloss
  grammar proves too heavy for the week, hardened-C becomes the better primary.**
  A stays primary only if v2.1 is adopted wholesale.

## Status

Final 3-lens adjudication (economics/psychology/technology closing verdict on
A-v2.1 vs hardened-C) dispatched; verdict table to owner follows.
