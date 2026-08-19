# Context Finalists — Red-Team Round 3 (condensed)

> 2026-08-18. Attacks on the SME-repaired finalists. Feeds the final adjudication.

## Verdicts

- **Benefits-alone: VIABLE-WITH-CHANGES — the red team's pick under BOTH the
  owner's criteria and its own judgment** ("not close" on spiky + documented harm).
- **Government-mail 2-family (benefits + IRS): KILL for this week** — doubles
  held-out/format surface, adds the fattest tail (IRS levy deadlines,
  "do I owe this?" advice-bait) for one headline. Roadmap slide, not scope.
- **Dev-docs: ranked last** — 40–50% gate-failure probability, low cohort
  spikiness, demo reads as RAG-with-a-style-guide. "I would not spend the week."

## Key findings

**Gate:** benefits' conjunction (vocab + quote-then-explain + verbatim anchors +
modal fidelity) is where frontier models mechanically leak — they normalize
dates, reformat amounts, paraphrase document names, and **chronically soften
modals ("you must" → "you'll want to") — RLHF politeness working against them**.
Estimated frontier strict-pass: **20–50%**, on cheap short scenarios. Dev-docs:
NGSL-2,800 is loose (~92% coverage of general English) on frontier home turf →
**60–85% strict-pass**; plateau only reappears on ≥8-turn walkthroughs, which is
also where the 4B is weakest (symmetric risk).

**Checker scope:** benefits fits the week IF the modal-preservation check is
demoted to a crude global deterministic rule (no softeners on anchored
obligations; "may" in output only if "may" in source) with judge as audit only.
Anchor substring checks = regex; quote-span exemption trivial once format is
mandated.

**Held-out:** benefits' disputes are pin-able in spec text: (a) anchor direction
= any-anchor-in-output-must-match-source + one designated operative deadline per
scenario in eval metadata that MUST appear; (b) **quote-exemption hole: quoted
spans must be exact source substrings** or paraphrase-in-quote-marks defeats
both vocab and anchor checks; (c) elided quotes ("…") that distort meaning.
Dev-docs' disputes are about *meaning* (gloss correctness off-bank) — you lose those.

**Demo:** benefits = best of the entire process (notice left, explanation right,
anchors highlighted with match-lines to source, advice-bait deflection fires
live). Script the paste-text moment (v1 is typed-text); rehearse top-10
advice-bait paraphrases against the tripwire.

**Residual risks compared:** benefits' fat tail = **misbinding** (right date
quoted, attached to the wrong obligation — checker passes, harm maximal): name
it voluntarily, judge-audit a sample, bound with operative-deadline metadata.
Dev-docs' = chronic uncorrectness in the core deliverable. For a graded week,
dev-docs' risk is worse (a hole in the thesis); for a deployed user, benefits'
is worse (a hole in someone's rent) — say both aloud.

**Required changes for benefits (adopt all):** modal-check demotion stated in
spec; quoted-spans-exact rule; anchor direction + operative-deadline metadata;
misbinding named in writeup before staff find it; first-pass metric pinned under
any regeneration loop; demo paths scripted.

**Posture line:** "The project's strongest defense-day posture is that its
limitations file reads like this review."
