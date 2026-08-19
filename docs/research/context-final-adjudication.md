# Deployment Context — Final Adjudication (condensed)

> 2026-08-18. Closes the context pipeline (2 discovery agents → umbrella ruling
> → 2 domain SMEs → red-team round 3 → this 3-lens adjudication).

## Ruling: BENEFITS-ALONE — wins under ALL THREE owner weightings

- **Spiky-first:** benefits (the RLHF-vs-modal gate story is the spike;
  dev-docs is the cohort's median project).
- **Usable-first:** benefits, narrowly (owner dogfoods his own insurance/IRS
  mail; dev-docs' daily-use ceiling undercut by certified-fluent-wrongness).
- **Harm-first:** benefits, not close (RCT-grade vs vibes).
- Dev-docs wins only under an "owner's affection" weighting that isn't a
  criterion → roadmap slide. Government-mail 2-family: killed this week →
  roadmap slide.

## Lens summaries

- **Economics:** benefits' repairs are deterministic code (~300–600 LOC
  composing with the v2.2 checker; each testable in an afternoon) and the spend
  is offensive (becomes the demo). Dev-docs' repairs are human curation +
  judge calibration — defensive spend to reach parity. "Benefits fits the week;
  dev-docs fits a different, longer week."
- **Psychology:** the authenticity attack ("you've never struggled to read an
  EOB") has a better-than-lived-experience answer: "Correct — that's why I
  anchored to RCT evidence instead of my own anecdote; what I have lived is the
  mechanism (DS→SWE vocabulary gap). I chose documented harm over felt harm
  because the criterion says documented." Applying your own criteria against
  your own preference is the strongest defense-room posture available.
- **Technology:** gate 20–50% frontier pass and the *reason* is the spike
  (modal preservation fights RLHF softening). Checker fully deterministic, no
  LLM in the pass/fail path. Still LIMA-class: quote-then-explain = format,
  anchors = selective copy-through, deflection = canned register. Data-gen
  unblocked (synthetic notices, no PII, rejection-sampled; watch template
  diversity; staff held-out from real redacted letters).

## Spec delta (behavior v2.2 unchanged; context wrapper)

> "A benefits-notice reading companion for adult English readers: given typed
> benefits/insurance/IRS notice text, it quotes the operative passage exactly,
> then explains it within the earned-words vocabulary — dates, amounts, and
> contacts reproduced verbatim, modals preserved, no advice, fixed
> aid-paid-pending banner, honest about missing elements."

## Ablation scenario changes

Per-scenario operative-deadline/amount metadata; ≥1 load-bearing modal trap
each; advice-bait turns; a missing-element notice; quoted spans validated as
exact source substrings; **first-pass metric pinned** (frontier gets the full
spec in-prompt, identical deterministic conjunction, no regeneration credit).

## Residual risk register

1. **Misbinding** (right date, wrong obligation — checker-blind): operative-
   deadline metadata + sampled audit judge + named voluntarily at the defense.
2. **Frontier passes the gate** (top of band): staff-reject is gate two; if
   both fail, pivot the claim to the data-efficiency curve honestly.
3. **Quote-exemption loophole** (over-quoting to smuggle vocabulary): exact-
   substring check + quote-length ratio cap (trivial checker addition).
4. **Synthetic-notice distribution shift:** seed from varied real formats;
   staff held-out from real redacted letters.
5. **Advice leakage under paraphrase:** canned deflection + tripwire trained
   in; rehearse the top paraphrases on pinned demo paths.

## Spiky POV (defense one-liner)

> "Everyone fine-tunes a small model to add fluency; I fine-tuned a 4B to
> refuse it — holding a ~2,800-word earned-vocabulary ceiling while explaining
> benefits notices with verbatim deadlines and unsoftened 'must's — a
> conjunction frontier models fail precisely because RLHF taught them to be
> gentle with the one word that keeps your benefits alive."
