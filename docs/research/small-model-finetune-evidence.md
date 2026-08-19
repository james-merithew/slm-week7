# Research: Small-Model Behavioral SFT — Evidence Base

> Produced 2026-08-17 by a research agent. Purpose: feasibility evidence for the
> data-gen → QLoRA plan, dataset sizing, base-model choice, and anti-patterns.

## Documented successes closest to our shape

| Behavior | Model | Dataset | Result |
|---|---|---|---|
| **GuideLM** — Socratic guidance, "economy of words" | GPT-4o/4o-mini method | **528** curated pairs | +8–25% Socratic guidance, +57–59% economy of words; raters preferred it 30–44% more. **Trade-off: accuracy −9–20%** ([arXiv:2502.20527](https://arxiv.org/html/2502.20527v1)) |
| **MathDial** — withholding solutions, scaffolding via hints | small open models | **~3,000** semi-synthetic dialogues | Fine-tuned small models reduced "telling" below prompted ChatGPT; rated more pedagogically effective ([arXiv:2305.14536](https://arxiv.org/abs/2305.14536)) |
| **SocraticLM** (NeurIPS 2024) | fine-tuned | Socratic dialogues | Outperformed GPT-4-prompted teaching |
| Socratic question gen (EULER, socratic-llm) | Llama 3.1 8B | small SFT + DPO | **SFT alone drifts back to answering; SFT+DPO holds it** |

Key pattern: successful instilled behaviors are **format/style/register constraints**
(what the model says and how) — exactly the LIMA thesis ("alignment teaches which
subdistribution of formats to use"). Not knowledge or reasoning upgrades.

## Sample efficiency (for the Data-Efficiency Curve design)

- LIMA: 1,000 curated examples; **30 hand-crafted dialogue chains dramatically improved multi-turn behavior** ([arXiv:2305.11206](https://arxiv.org/abs/2305.11206))
- Practitioner consensus: style/format 100–200; robust behavioral change 500–5,000; **200 curated > 5,000 noisy**
- **Sweet spot for us: ~500–1,500 curated multi-turn examples** → suggests a sweep like N=1200, 600, 300, 150, 75 (log-spaced)
- SFT hyperparams for 3–7B ([arXiv:2412.13337](https://arxiv.org/abs/2412.13337)): larger batch + lower LR; mixed training beats phased

## Dataset shape (from LearnLM)

Training examples = **system instruction describing the pedagogy + compliant
response** ([arXiv:2412.16429](https://arxiv.org/html/2412.16429v1)) — behavior is
conditioned, not hard-baked. MathDial's generation recipe (strong LLM plays a
confused student; teacher turns follow a taxonomy of moves: probe, hint, focus,
telling) is directly reusable for our teacher-distillation pipeline.

**MathTutorBench** ([arXiv:2502.18940](https://arxiv.org/pdf/2502.18940)) — ready-made
"pedagogical ability vs telling" eval; candidate supplement to our own eval set.

## Anti-patterns (design around these)

1. **Don't require knowledge the base model lacks** — pick problem domains a 4B can solve (middle-school math, not proofs). GuideLM's −20% accuracy is the warning.
2. **Multi-turn persistence is the hard mode** — include many multi-turn training examples; plan a small DPO pass as the stretch (matches brief's stretch ladder).
3. **Adversarial robustness after SFT is unproven** — set expectations: tuned model evaluated on cooperative + mildly-pushy students; hard jailbreaks are the stretch adversarial eval.
4. **Catastrophic forgetting** — LoRA not full FT, low LR, few epochs, mix ~10–20% general instruction data.
5. **Qwen3 thinking-mode trap** — SFT on non-reasoning data breaks hybrid thinking; strip/standardize think tags, train AND eval with thinking disabled ([QwenLM#1429](https://github.com/QwenLM/Qwen3/discussions/1429)).

## Base model recommendation

**Qwen3 4B (thinking disabled, Unsloth QLoRA)** — best-in-tier for fine-tuning in
2026 comparisons ([distil labs](https://www.distillabs.ai/learn/best-small-language-model-for-fine-tuning-2025/)),
Apache 2.0, strongest instruction-following base. Fallback: **Llama 3.2 3B** (zero
template risk, most documented). Either trains on a 24GB card with 500–1,500
examples in under an hour.
