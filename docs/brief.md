# Week 7 Brief — Train Your Own Small Learning Model

> Source: `Train_Your_Own_Small_Learning_Model.pdf` (ingested 2026-08-17).
> This is a faithful extraction; the PDF is the authority.

**Tagline:** Instill one falsifiable behavior into a small open model — and prove it, end to end.

## Before You Start

- Not about beating a frontier model. Prove you can make a small model reliably do ONE narrow thing — by controlling its training data, not by writing a cleverer prompt.
- **The dataset is the deliverable.** Training is a downstream button-press. ~80% of the outcome is decided by the data you generate and filter, not the fine-tuning run.
- **The one hard test:** a well-prompted base model can't already do it reliably. If a good prompt already nails the target, fine-tuning is pointless. Pick a behavior where *reliability* — every time, in-character, without drifting — is the hard part.

## Background

- 1B–4B model, trained on a few hundred to a few thousand well-filtered examples, can reliably hold a narrow behavioral constraint that a prompted frontier model drifts off of over a long conversation.
- Two things carry the project (neither is the training loop):
  - **Data generation** — distill from a frontier teacher, then filter hard for quality. Craft is in the generation prompt and the quality gate, not raw volume.
  - **Evaluation, built before you train** — without it, "we fine-tuned a model" is unfalsifiable.

## The Gate: Behavior Spec

First deliverable, before any code: a falsifiable Behavior Spec — one or two sentences a stranger could use to mark any model output pass/fail. It is simultaneously the data-generation rubric, the eval criterion, and the project's spiky POV.

Example specs given in the brief:
- **Tutor:** never states the final answer; every response is a scaffolding question or hint calibrated to the student's most recent message; only confirms an answer once the student produces it themselves.
- **Structured output:** always returns a single valid JSON object matching the given schema, no prose before/after, even when input is incomplete or adversarial.

## Core Challenge

Choose a specific **learning or teaching behavior**. Research it, generate a distilled dataset that embodies it, fine-tune a small open base model (QLoRA) to hold it, and prove — with numbers, not claims — that the tuned model beats the base model at the target behavior.

Rules that keep it honest:
- One target, one context. No broad domains — diffuse data makes a mushy model.
- **No training before the eval exists.**
- A disappointing model is almost always a data problem. Don't tune hyperparameters to fix bad data.
- Don't chase capability benchmarks. Measure the target behavior.

## Required Ablations

### Ablation 1 — Prompt-Ceiling Ablation

Before any fine-tuning code, prove (with numbers) that prompting has a real ceiling below the reliability bar. **Presented live at the Architecture Defense.**

- ≥ 2 frontier models from **different model families**.
- ≥ 3 prompting strategies per model: zero-shot, few-shot with in-context examples, and a structured/chain-of-thought system prompt.
- **Minimum 30 scenarios per model × strategy combination**, scored against the Behavior Spec using the same LLM-as-judge rubric used later for base-vs-tuned.
- A results table (mean Spec-adherence and Robustness per model × strategy) plus a short paragraph naming the specific failure mode that survives the best prompting attempt.

**Why this is the gate:** if the numbers don't show a real plateau, you haven't found an edge — staff sends you back to pick a harder target before you're cleared for MVP.

### Ablation 2 — Data-Efficiency Curve

Determine the minimum dataset size at which the tuned model reliably holds the behavior.

- Train ≥ 4 checkpoints at different dataset sizes (e.g. log-spaced N, N/2, N/4, N/8 — choose and justify spacing).
- Evaluate every checkpoint on the same eval set (own + staff held-out) with the existing harness.
- Report performance-vs-N curve for at least Spec adherence and Robustness.
- Identify and justify the smallest N that holds the behavior — the stated "minimum viable dataset size" in the Brainlift.
- Partial curve (2+ points) expected by Early Submission; full curve with justified minimum N due at Final.

## Verification Requirements (MVP onward — must be independently re-runnable)

| Requirement | Meaning |
| --- | --- |
| Public model checkpoint | Pushed to Hugging Face Hub (public), exact commit hash referenced in submission. Graders pull and run it. |
| One-command eval script | `eval.py --model <hf-repo-id> --eval-set <path>` regenerates the full results table from nothing. |
| Raw judge transcripts | Full per-example LLM-as-judge output (score + reasoning) as JSONL — not just aggregates. |
| Staff held-out eval set | Harness will be run against scenarios you never saw. Graded — primary overfitting check. |
| Pinned versions | Exact HF model commit hash and eval-code commit hash in submission. |
| Live comparison in demo | Demo video must show a grader-supplied prompt run live against base vs. tuned. |
| Ablation reproducibility | Prompt-Ceiling script and Data-Efficiency training logs included; grader can rerun ≥1 sample point of each. |

## Submission Timeline

| Checkpoint | Due |
| --- | --- |
| **Architecture Defense** | Tuesday, 4 hrs after assignment |
| **MVP** | Tuesday midnight |
| **Early Submission** | Thursday midnight |
| **Final Submission** | Sunday noon |

### MVP (Tuesday midnight) — all required to pass
- Finalized Behavior Spec (falsifiable, 1–2 sentences).
- Completed Prompt-Ceiling Ablation report — presented at Architecture Defense, submitted in full here.
- Eval harness built and committed: LLM-as-judge scoring, a behavioral check for the spec's specific failure mode, base-vs-tuned comparison mechanism.
- Full loop — generate → train → eval — runs end to end on a small smoke-test batch.
- First real dataset generated and filtered; first real QLoRA run completed.
- First base-vs-tuned eval numbers, in the Verification Requirements format.

### Early Submission (Thursday midnight)
- ≥1 failure mode diagnosed from MVP eval, resolved via a **data change** (v2 dataset) — not a training-config change.
- Updated base-vs-tuned numbers showing the delta, with raw judge transcripts.
- ≥2 points on the Data-Efficiency curve, or a documented reason you're behind.
- Draft final artifacts: dataset shape, model checkpoint, in-progress Brainlift.

### Final Submission (Sunday noon) — all required to pass
- The dataset, published — the real artifact.
- The model on HF Hub, public, plus a running inference demo.
- Eval harness and results table — base vs. tuned, on own eval set AND staff held-out set.
- Full Data-Efficiency curve with justified minimum viable N.
- Brainlift — behavior thesis, and whether data → behavior held, with evidence.
- 3–5 minute demo video: tuned model doing what base fails at, including one live grader-supplied prompt.

## Stretch Ladder (in order)
1. DPO / preference tuning on top of SFT; measure delta over SFT alone.
2. Adversarial/robustness eval built to break the behavior; report robustness, not just clean-input performance.
3. Composed behavior — a second, potentially competing constraint held simultaneously.

## Stack Suggestions
- **Base model:** small Qwen3 (0.6B / 1.7B / 4B) is the current default. Alternates: Llama 3.2 1B/3B, Gemma 3 small, SmolLM3. Start from the Instruct variant.
- **Framework:** Unsloth for QLoRA (~2× faster, ~70% less VRAM). TRL/PEFT or Axolotl for more control.
- **Compute:** one A100/H100 via Modal / RunPod / Colab. Models ≤1.7B fit a 24GB consumer card.
- **Teacher model:** any frontier model — costs covered.
