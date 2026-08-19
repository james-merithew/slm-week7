# Context Discovery — Where Should Earned Words Live?

> 2026-08-17. Stage 1 of the deployment-context pipeline (behavior is locked;
> this decides the subject/domain). Two independent discovery agents.

## The headline conflict (for the Delphi/SME round to settle)

**Patient discharge/medication documents:**
- Brainstormer: **KILL** — held-out set will contain a dosing scenario;
  vocabulary-constrained paraphrase of "warfarin 5mg alternating days" is
  uninsurable; most cohort-saturated idea.
- Researcher: **#1** — strongest numbers in the space: ~88% of discharge
  instructions unreadable to their patients (JGIM); low health literacy costs
  $106–238B/yr (Georgetown HPI); readable discharge summaries **halved 30-day
  readmissions** in one program (StatPearls); >1M adverse drug events/yr from
  label misuse; hospitals pay via CMS readmission penalties (up to 3% of
  Medicare revenue); ACA §1557 language-access rules.

## Convergent leader: government benefits notices (SNAP/Medicaid)

Brainstormer #1, researcher #2:
- RCT-grade: simplified mailings ~doubled enrollment (NBER w31239); CalFresh
  recipients ~6x more likely to exit in paperwork month; 55–75% of leavers
  still eligible (CBPP).
- **Plain Writing Act of 2010** is binding and agencies average a **C** grade
  (Center for Plain Language 2022) — a standing compliance gap our published
  deterministic checker addresses independently of the model.
- Lowest liability of any high-impact domain: no advice line; worst case is a
  wrong deadline (mitigation: quote dates verbatim — a spec rule candidate).
- Ledger story: recurring letters → user learns the vocabulary of a system
  they're stuck inside for years (strongest honest teaching claim).
- Weakness: slow government sales; entry via civic-tech intermediaries.

## New entrant from research: informed-consent simplification (B2B)

- Consent forms average 12th-grade reading level vs ~8th-grade standard (NEJM);
  80.5% of trial ICFs "difficult to read" (PMC).
- **Checker maps 1:1 onto an existing paid workflow:** IRBs already enforce
  grade-level ceilings and bounce forms; sponsors eat trial delays.
- Human IRB reviews every output → liability structurally contained despite
  medical content. B2B document transformation, not consumer chat.

## Rest of the researcher's field (see agent output for full table)

4. Employee benefits/insurance choice — best pure-commercial fallback (employers
   buy; 86% of employees confused; SBC mandate) — advice line if unguarded.
5. Medical bills/EOBs — 72% confused; up to 80% of bills contain errors.
6. Pro-se courts — real need, **high UPL liability** (DoNotPay precedent) — avoid.
7. ESL workplace safety — OSHA "language and vocabulary" rule; fatality-rate
   evidence; matches the NGSL lexicon exactly.
8. Consumer finance disclosures — CFPB TRID redesign +29% comprehension.
9. Tenant/housing — great shape, weak buyer.
10. Immigration — highest liability; avoid.

## Brainstormer's independent top 3 (before owner candidates)

1. Gov benefits notices (33) · 2. Insurance EOBs/denials (33) · 3. IRS notices
(33; most citable harm via Taxpayer Advocate, best single demo document, low
frequency). Dev-docs-for-career-switchers scored highest raw (34) but fails the
documented-harm criterion.

**Cross-cutting design rule (adopt regardless of winner):** the scariest shared
failure is lossy paraphrase of load-bearing verbs (may/must, proposed/final,
request/require) — training data must over-represent those distinctions; the
held-out set will probe exactly there.

## Pending

Brainstormer scoring of owner candidates: (A) fitness/nutrition vocabulary
coach, (B) banking/finance jargon coach ("your money mail, explained" merge),
(C) "official mail, explained" umbrella vs the one-target-one-context rule.
Then: SME weak-spot round → lenses + red team → 3-lens adjudication.
