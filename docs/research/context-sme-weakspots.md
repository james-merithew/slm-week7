# Context Finalists — SME Weak-Spot Inventories (condensed)

> 2026-08-18. Stage 2 of the deployment-context pipeline. Full texts in the
> agents' outputs; this records what the red team and adjudicator consume.

## Dev-docs for career-switchers — SWE-onboarding SME: VIABLE-WITH-CHANGES

Weak spots:
1. **Term-density arithmetic fails the 2/turn cap** (README paragraph = 6–12 terms → 3–7 turns/paragraph). Only honest fix: multi-turn "guided doc walkthrough" IS the product.
2. **Proper-noun laundering seam** — tech names/acronyms (Docker, CI/CD, K8s) carry the meaning; checker validates strings; an SFT'd model will exploit the exemption. Fix: three-tier policy (products exempt-but-must-gloss / concepts capped / acronyms expanded+glossed).
3. **Expertise reversal + false-friend hazard** — ledger has no concept of word *sense* ("environment": conda vs deploy); onboarding vocab self-calibration patches infantilization, nothing patches sense-blindness.
4. **Fixes the smaller half of the pain** — word-level jargon ≈ 25–35% of doc confusion; the rest is missing conceptual scaffolding. Honest positioning: "readability governor," not doc-confusion cure.
5. **Gloss hallucination institutionalized** — glosses are parametric generation (4B's weakest spot); wrong-sense glosses score 100% on the checker and persist in the user's ledger as permanent wrong mental models. Strongest fix: curated gloss bank (~300 terms, retrieval not generation) + doc-grounded glossing.
6. Teaching claim defensible but must shrink to "controlled-vocabulary reading companion that introduces terminology at a governed rate."
7. Demo exists ONLY as live-checker split-screen (frontier explains READMEs well; the delta is the constraint). Held-out landmines: dense paragraphs, stack traces, overloaded-term docs, fluent-user infantilization, acronym policy, turn-30 ledger tracking.

**Killer question:** "What proves the definitions it taught me are TRUE? A wrong
gloss passes your checker and enters my permanent ledger — how is certified
fluent wrongness a teaching product?" Honest answer requires the curated gloss
bank + separately-scored gloss-accuracy audit.

## Benefits notices, explained — benefits-navigation SME: VIABLE-WITH-CHANGES

Weak spots → repairs (most are deterministic and strengthen the project):
1. **Deadline/action fidelity** — the killer risk (90-day hearing vs buried
   10–15-day aid-paid-pending clock; may/must; proposed/final; multi-program
   letters). Repairs: **verbatim-anchor rule** (every date/amount/contact/doc
   name must be an exact substring of the source; deterministic; regenerate on
   failure); **quote-then-explain mandatory format** (quoted text exempt from
   vocab constraint); conservative **modal-preservation check**; **no-invention
   rule** + fixed human-written aid-paid-pending/legal-aid banner.
2. **Notice reality** — 4–12 pages, multi-program, defective notices common,
   OCR corrupts load-bearing tokens. Repairs: v1 scoped to typed/pasted/clean
   PDF; critical-token confirmation for photos; missing-element honesty rule
   ("this letter does not say why — letters are supposed to; legal aid can
   help"); never narrate worksheet arithmetic.
3. **Population fit** — NGSL ceiling matches actual reading levels (strength);
   **English-only is the biggest scoping attack** — survivable if named
   upfront (intermediate-ESL readers, navigators, family helpers are real
   users; architecture is language-portable), fatal if discovered.
4. **Advice line** — printed options + printed consequences = explanation;
   recommending/predicting = advice. Canned "what should I do" template
   (teachable BECAUSE canned) + deterministic tripwire (banned phrase list).
5. **Liability** — reframe to **"harm-bounded by design"**: low mean, fat left
   tail; counterfactual baseline is the unread letter.
6. **Teaching claim is provable**: vocabulary genuinely recurs across letters;
   taught terms must be reused unglossed (retrieval) and the allowed-vocabulary
   set measurably grows — a checkable learning curve.
7. Held-out landmines enumerated: wrong-deadline paraphrase probes,
   should-I-appeal pressure, may/must flips, aid-paid-pending trap,
   multi-program cross-contamination, non-English photo (scripted refusal),
   defective notice, OCR-corrupted date, scam letter.

**Killer question:** "Notice says benefits stop Sept 1, hearing deadline Nov 15;
user asks 'so I have until November?'" Honest answer: quote both dates, refuse
to collapse them, show the fixed banner — and claim harm-bounded, not harmless.

## Status

Next: red-team pass over both repaired candidates + narrowed "Government Mail,
Explained" (benefits + IRS closed list), then 3-lens adjudication under the
owner's criteria: spiky, usable, solves documented problems.
