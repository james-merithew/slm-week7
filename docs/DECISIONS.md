# Decision Log — Week 7 SLM

Newest at top. Every entry ends with an explicit **Rejected:** clause.

---

## 2026-08-18 — Harness v2: max_seq_len 2048 → 4096 (silent no-op training averted)

Reading the frozen config before the first real run surfaced that
`max_seq_len: 2048` truncates every v3 dialog past its assistant turns — the
behavior-spec system prompt alone is ~2100 tokens. Verified empirically with
`--verify-masking` on all 123 dialogs: **zero trainable tokens at 2048**. The
Modal 4B run would have exited 0 with a flat loss on nothing. Harness bumped
to v2 with 4096 (covers the observed ~3.7k p99); data.path pinned to v3.
**Rejected:** trimming the system prompt out of training rows to fit 2048
(the deployed model must be conditioned exactly as the teacher was — LearnLM
conditioning pattern is part of the spec).

## 2026-08-18 — Budget plan: $10 ceiling — Sonnet 5 teacher, 150-dialog v3, trimmed judge

Owner set a hard funds constraint ("I don't have that much"; loaded $10).
Enabling prompt caching (spec+word-list prefix re-reads at 0.1x) collapsed
the input side; the remaining cuts: teacher switched claude-opus-5 →
**claude-sonnet-5** (intro pricing) for dataset v3, planned N 300 → 150,
judge audit 25% → 15%, zero_shot re-run limited to the 6 credit-wall
casualties. Quality bar held by the deterministic checker filter (unchanged,
hash-pinned) + judge audit. Outcome: v3 = 123 accepted dialogs at 82%
dialog acceptance; Sonnet needed repairs more often (47% first-pass turn
acceptance vs Opus's 84%) but repairs succeeded at 88%. The ablation SUBJECT
stayed Opus — the ceiling claim and gate-pilot evidence are Opus-based, and
weakening the subject to save ~$3 would soften the headline result.
**Rejected:** Sonnet as ablation subject (undermines "prompting plateaus on
the strongest model"); Batch API (50% off but beaten by caching on our
input-dominated calls, and adds multi-round batch orchestration on deadline
day); shipping without the dataset (M5 is a graded MVP item).

## 2026-08-18 — Both pre-registered gates resolved: target LOCKED

Gate 1 (checker feasibility): v1.1 re-score on the frozen 50-turn set =
**4.0% FP < 5% bar — PASSED** (evidence/2026-08-18/calibration/RESCORE.md).
Gate 2 (prompt ceiling): pilot, claude-opus-5 × 3 strategies × 5 clean
scenarios, checker v1.1, first-pass — best strategy (few_shot) = **20% strict
pass**, zero_shot and structured_cot = **0%** — far below the 85% pivot
trigger, on the easiest stratum (evidence/2026-08-18/gate-pilot/). Judge audit
confirms the failure mode is mechanical fidelity, not substance. The
Self-Explanation-Gate fallback is retired to the record; Benefits Notices +
earned-words v3 is the confirmed week target.
**Rejected:** firing the pivot (trigger condition decisively unmet).

## 2026-08-18 — Checker v1.1: calibration-driven fixes + crudeness resolutions

Calibration gate FAILED at v1.0 (10/50 FP = 20% vs the pre-registered <5% bar;
full audit in evidence/2026-08-18/calibration/REPORT.md). Per the audit's
counterfactual (bugs fixed → 12%; + crudeness resolved → 0% on the frozen set),
v1.1 implements: B1/B1b blockquote + double-count fixes, B2 gloss tokenizer
unification, B3 NGSL supplemental basics (number words, months, days — new
frozen-list hash), B4 anchor set-membership (kills truncation evasion, an
FN-side hardening), B5 user-introduced-anchor exemption. Crudeness decisions
(data-driven): C1 softened_modal DEMOTED to advisory (measured 5% precision —
RULES.md's "under-reports" claim falsified and corrected); C2 quote comparison
normalizes one trailing comma/period and compares single-word quotes
case-insensitively; C3 transparent derivational families of listed headwords
earned via curated affix rules. Pivot decision deferred to the re-score of the
SAME frozen 50 turns (labels frozen; no relabeling) — pre-registration intent
is "is deterministic checking feasible," and the audit shows the FP mass is
mechanically specified code, not concept failure.
**Rejected:** pivoting to the fallback behavior on the v1.0 number alone
(audit shows fixable mechanics, not infeasibility); relabeling the calibration
set (would contaminate the re-score); keeping softened_modal in strict-pass
(5% precision indefensible before staff).

## 2026-08-18 — Ablation second family: Mistral free tier (supersedes Gemini free tier)

The wire-smoke surfaced a hard fact that invalidated the Gemini-free-tier
decision's premise: free-tier Gemini allows **20 requests/day/model**
(`GenerateRequestsPerDayPerProjectPerModel-FreeTier, quotaValue: 20`), vs ~270
requests needed for the ablation's second-family half — structurally
impossible, not merely slow. Owner constraint: free/no-card. Chosen:
**Mistral La Plateforme free tier, mistral-large-latest** — a genuine frontier
family satisfying the brief's 2-family floor, OpenAI-compatible endpoint (one
provider-map line), ~1 RPS free limits workable with existing throttling
(mistral concurrency pinned to 1).
**Rejected:** Google billing (strongest baseline + would unlock 3.1-pro, but
requires a card — owner declined); OpenAI (card); OpenRouter (~$5 purchase +
router-defensibility caveat); Groq free tier (Llama — open-weights "frontier"
claim is softer than Mistral's); waiting out the Gemini quota (~14 days);
rotating Gemini models across days (invalidates model consistency).

## 2026-08-18 — Deployment context: Benefits Notices, Explained (spec v3)

Owner signed off ("lets start and do the mvp") after a full context pipeline
(2 discovery agents → umbrella ruling → 2 domain SMEs → red-team round 3 →
3-lens adjudication; record in docs/research/context-*.md). Winner under all
three owner criteria (spiky / usable / documented harm). Behavior v2.2
unchanged; context wrapper adds: fixed three-part scaffold (what it says / what
it asks / by when), mandatory quote-then-explain (quoted spans must be exact
source substrings), verbatim anchors (dates/amounts/contacts/doc names),
conservative modal-preservation rule, no-invention rule + fixed aid-paid-pending
banner, canned advice-deflection + deterministic tripwire, form-field
walkthrough as a scenario category (explain fields, never compose answers),
typed/clean-text v1, English/intermediate-ESL scoping stated upfront,
"harm-bounded by design" liability posture, first-pass metric pinned.
**Rejected:** dev-docs for career-switchers (owner's personal favorite — lost
under all three of his own criteria; 40–50% gate-failure risk; gloss-ledger
certifies fluent wrongness; cohort-median project) → roadmap. Government-mail
2-family incl. IRS (red-team kill: doubles held-out surface for one headline)
→ roadmap. Fitness, banking/money-mail, patient-health, generic tutor context —
killed on the record.

## 2026-08-17 — Primary learner + base vocabulary (spec v2.2)

Owner locked: **primary learner = adult ESL / career-switcher (~18–45)**;
middle-schoolers demoted to secondary market. Base vocabulary ceiling moves from
the 1,000-word toy list to a **~3,000-word-family learner list — NGSL shipped
(CC BY, redistributable), Oxford 3000 cited as the recognizable equivalent**.
Rationale: owner caught that 1,000-list violations ("particular", "determine")
are trivially easy for adults — the checker would flag words that lose no one,
gutting the educational claim. At B1-learner level the leaks that remain are the
meaningful ones (academic vocabulary: "utilize", "facilitate", "coefficient").
Also keeps the graders' live prompt in-distribution (adults type like adults)
and avoids the minors thread in Q&A. Known trade-off, accepted: larger allowance
→ higher frontier compliance → gate risk up; the pre-registered day-1 pilot and
pivot trigger already cover it.
**Rejected:** middle-school primary (live-demo out-of-distribution, minors
questions); keeping the 1,000 list for mechanical difficulty (measures a word
game, not teaching); shipping Oxford 3000 verbatim (OUP copyright vs
publish-the-checker requirement).

## 2026-08-17 — Target behavior: Vocab Lock v2.1 (earned-words tutor)

Chosen via a three-round panel (5 lenses → 2 SMEs → Delphi discussion → 3-lens
adjudication → product robustness check; full record in docs/research/). Spec:
tutor never uses a technical term the student hasn't seen until glossed in plain
language (4 published gloss forms, ≤2 unlocks/turn, permanent conversation-wide
unlock); deterministic checker is the headline metric, LLM judge audit-only.
Pre-registered pivot: day-1 pilot frontier strict-pass ≥85% OR checker >5% FP on
50 hand-labeled turns → fallback to hardened Self-Explanation Gate
(explicit-verdict regex scoring) before any training spend.
**Rejected:** No-Praise tutor (red-team: gate near-certain to fail — frontier
models with a system prompt already comply; invisible demo); Self-Explanation
Gate as primary (judge-dependent core metric, degenerate never-verdict policy,
mushiest curve — retained as fallback); Vocab Lock v1/v2 as specced (v1:
Krashen grounding inverted, pedagogy attackable; v2: gloss-unlock unconstrained
dissolves the spec via gloss-laundering).

## 2026-08-17 — Ablation baselines: three families, first-party APIs (supersedes OpenRouter)

Owner set the decision rule: **merit first; price is only a tiebreaker when two
options are otherwise level.** On merit: direct OpenAI + Google APIs (plus
Anthropic) — first-party serving removes the "was the baseline really
full-precision?" attack a router invites, and running THREE families
(3×3×30 = 270 conversations, checker-scored for free) turns the gate result
into "prompting plateaus across every major family," exceeding the brief's
2-family floor. Runner supports openai/google/openrouter providers via one
OpenAI-compatible client map; guards tested offline.
**Rejected:** OpenRouter as the access path (routing/provider variability =
defensibility hole; price advantage irrelevant under the merit-first rule —
superseded same day); two families only (weaker evidence for one fewer key).

## 2026-08-17 — Judge model: Sonnet (price as tiebreaker, correctly applied)

Judge role is audit-only (sampled gloss quality + substance score; the
deterministic checker is the headline metric). On merit Opus and Sonnet both
clear that bar — a genuine tie — so price broke it per the owner's rule.
**Rejected:** Opus judge (no merit gain for the audit role).

## 2026-08-17 — Compute: Modal for training runs, local 24GB card for smoke tests

Modal gives scriptable, reproducible A100 runs — the strongest "grader can re-run it" story — while the local card covers fast iteration and models ≤1.7B. Data-efficiency sweep (4+ checkpoints) runs on Modal so configs/logs are captured per run.
**Rejected:** Colab (weak reproducibility, session evictions mid-sweep); RunPod (manual environment = weaker pinning story).

## 2026-08-17 — Judge model: Claude (Anthropic API), same rubric across all evals

The brief requires the SAME LLM-as-judge rubric for the prompt-ceiling ablation and base-vs-tuned comparison. Claude as judge with a fixed rubric prompt, temperature 0, structured verdict output, raw transcripts persisted as JSONL from day one.
**Rejected:** using a judge from the same family as an ablation subject only — Claude also appears as an ablation subject, which is a known self-preference bias risk; mitigated by (a) pass/fail criteria being near-deterministic per the spec, (b) behavioral (regex/deterministic) checks alongside the judge, (c) spot-audit of judge transcripts. A cross-family judge ensemble was rejected for cost/time this week; revisit if judge disagreement shows up in spot-audits.
