# SME Weak-Spot Inventory — LLM Post-Training

> Produced 2026-08-17 by the LLM fine-tuning SME agent (stage 1 of the two-stage
> panel). Ranking by P(train + honest eval just works): **A > B > C**.

## Candidate A — Vocab Lock (top-ranked)

**Token mechanics:**
- Word-level constraint vs subword generation: violations are decided one token before the checker can see them; per-token violation probability compounds with reply length. SFT handles it (whole-register shift).
- Compliant text is *lower-perplexity* for a small model — "secretly easy" in the KL sense. The honest signal is therefore **drift over length/turns**: base+prompt drifts back to normal register; report violation rate by position-in-reply and turn index.
- Temperature inflates rare-word mass — **fix one decoding config for everything**.
- Checker and data filter must share one word-segmentation function (contractions, hyphens, unicode apostrophes).
- **Proper-noun laundering:** teacher will capitalize rare words to sneak them past a capitalization-based allowance; SFT clones the exploit. Audit teacher data for this.

**Conditioning (the student-word clause):**
- Verbatim echo is easy (induction heads); the *boundary* is not: near-synonyms/inflections of student words, and the negative case. Naive data → model learns static-1k + "mirror the student" and ignores scope.
- **Required: contrast pairs** (~15–20% of data): same rare word allowed in one dialog (student said it) and a violation in a matched dialog (they didn't). Plus long dialogs exercising an allowance granted many turns earlier.

**Eval validity:**
- Violations-per-100-words normalizes rate not opportunity — degenerate policy is short vague replies. Report length distributions; pool tokens across turns; substance judge is mandatory beside every compliance number.
- Substance judge should use **paired judging** (constrained vs unconstrained reference: "does A convey the key facts of B?") or factual probe questions.
- **Prompt parity decision:** same constraint-bearing system prompt on both (claim: tuning beats prompting at equal prompt) or tuned without prompt (claim: internalization). Never mix.

**Template bites:**
- Qwen3 thinking mode: strip/disable identically in training data, base eval, tuned eval; Unsloth inserts empty think blocks; pin `enable_thinking=False` end-to-end.
- Diff rendered bytes: training template vs serving template. Decode one masked batch to verify assistant-only loss (marker strings differ Qwen3 vs Llama 3.2).

**Curve:** best of the three — continuous metric, near-monotone 75→600, may flatten by 1200. Dynamic-clause sub-metric will lag; report separately.

**Frontier fairness:** include the 1k list in the frontier prompt (~2k tokens) and give the tuned model the identical prompt, or document the asymmetry as the point. Same scripted dialogs, same checker, same temp.

## Candidate B — No-Praise

- Praise is turn-initial; SFT nails position-0 fast; residual is diffuse mid-reply valence → score plateaus.
- Data trap: deleting praise sentences deletes co-occurring verdicts → accidentally trains the never-verdict policy. Data must show replacement behavior ("Correct. The next step is…").
- Collateral register damage (coldness) — measure a side-effect metric or staff will see it.
- Base-rate trap: score praise-per-opportunity, stratified correct/partial/wrong.
- Judge calibration: ~50 hand-labeled turns, report judge–human agreement.
- **Curve saturates by N=150–300 → mushy minimum-viable-N claim.**
- Ablation likely erases most of the delta under fair prompting → "worked but proved little."

## Candidate C — Self-Explanation Gate

- Implicit verdict leakage via hedging asymmetry is invisible to regex; teacher does it too → filter passes it → SFT trains the leak in; eval is blind in exactly the direction the model errs.
- Two-state machine: SFT learns "withhold" and undertrains "fire verdict after reason" → Socratic doom loop. Needs balanced gate-closed/gate-opened data.
- Episode-binary metric → wide CIs, noisy curve, mushiest minimum-N.
- Multi-turn loss masking must be exactly right (max damage from Unsloth marker bug).
- Qwen3 thinking mode riskiest here (verdict stated inside think block).

## Protocol rules (adopt regardless of candidate)

1. **One frozen harness, byte-verified** — single decoding config; one template rendering path for base/tuned/frontier; thinking off everywhere; decode a masked batch to prove assistant-only loss.
2. **Every compliance metric ships with its degenerate-policy co-metric** in the same table (substance score, verdict-delivery rate, length distribution).
3. **Pre-registered, held-out, stratified eval set** built before training, disjoint from distillation prompts; scripted multi-turn dialogs incl. pressure turns; per-stratum results with bootstrap CIs.
