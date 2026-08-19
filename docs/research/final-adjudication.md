# Final 3-Lens Adjudication — Closing Verdict

> 2026-08-17. Final step of the two-stage, three-round panel
> (5 lenses → 2 SMEs → Delphi discussion → this adjudication).

## Ruling

**Primary: Vocab Lock v2.1** (all seven red-team conditions adopted wholesale).
**Fallback: hardened Self-Explanation Gate** (explicit-verdict regex scoring).

**Pre-committed pivot trigger, evaluated at day-1 pilot close — pivot to
hardened-C if EITHER:**
- (i) frontier best-of-3-strategies strict-pass **≥85%** on the 30-scenario pilot
  (prompt ceiling clears the bar), OR
- (ii) the gloss-grammar checker cannot pass its unit suite with **<5% false
  positives on 50 hand-labeled turns** by end of day 1.

Below 85% frontier and checker green → A locked, no re-litigation.

## Lens verdicts

- **Economics:** A-v2.1 still dominates; margin narrowed from decisive to clear.
  Metric stays deterministic (judge = audit-only on ~100 sampled glosses).
  The day-1 pilot is "the cheapest information purchase of the week."
- **Psychology:** resolved. Gloss-unlock converts a word-ban into a pedagogical
  protocol (kills "gimmick"); the ablation answers "why fine-tune"; publishing
  the checker to staff is "an act of confidence no fuzzy-judge project can
  perform." Discipline: communication-behavior claims only.
- **Technology:** v2.1 in-budget (~200–300 LOC; four gloss frames over spaCy
  spans; lemminflect scope lookup) and in-class (monotone, append-only,
  in-context state = attention-learnable; not C's covert state machine).
  Plot the efficiency curve per violation type — richer deliverable.

## The spec (as presented)

> "The tutor never uses a technical term the student hasn't seen until the tutor
> has defined it in plain language — the definition, in one of four published
> gloss forms in the same sentence as first use, at most two new terms per turn,
> unlocks the term for the rest of the conversation. Compliance is scored by a
> published deterministic checker; a stranger can run it on any transcript."

## Claims the defense MAY make

1. Baseline violation rate per 100 words, measured before training (anchor).
2. The metric is deterministic and published; staff had the checker before the held-out set.
3. Prompting 2 frontier models × 3 strategies could not reach the bar; fine-tuning did (only if the numbers show it).
4. Pedagogical grounding: never-undefined-jargon + invite-term-use is a recognized plain-language teaching protocol.
5. Compliance degrades over conversation length at this measured rate (concede before asked).

## Claims it must NOT make

1. Any learning-outcome claim (fluency illusion is uncloseable) — communication behavior only.
2. Any Krashen/i+1 grounding (inverted on the record).
3. "Can't be gamed / glosses always adequate" — claim the audit rate, not perfection.

## Residual risk register

| # | Risk | Owner-mitigation |
|---|---|---|
| 1 | Gloss-laundering survives training | Filter enforces cap+grammar at generation; ship gloss-exploit frequency as headline co-metric |
| 2 | Frontier clears bar at pilot | Pre-committed pivot to hardened-C, day 1, before training spend |
| 3 | Long-conversation drift worse than curve | Frozen harness; stratify by turn index; concede curve proactively |
| 4 | Checker false positives on staff set | 50-transcript hand-label calibration before publishing |
| 5 | Presenter drifts into outcome claims in Q&A | Written claim/no-claim card in defense notes; dashboard keeps answers anchored |
