# src/train — QLoRA SFT harness (Qwen3-4B-Instruct, benefits-notice explainer)

Reproducible supervised fine-tuning of **Qwen/Qwen3-4B-Instruct-2507**
(fallback: `meta-llama/Llama-3.2-3B-Instruct`) with QLoRA. One frozen harness:
every knob lives in [`config.yaml`](config.yaml); every run writes an immutable
config copy + `RUN.json` provenance.

> **THINKING MODE IS OFF END-TO-END.** `<think>...</think>` blocks are
> stripped from all dataset messages at load time (`data.py`, hard-fails on
> stray tags), and `enable_thinking=False` is passed to **every**
> `apply_chat_template` call — training, masking verification, and inference.
> The `-2507` Instruct checkpoint has no thinking branch (kwarg ignored,
> harmless); on hybrid Qwen3 checkpoints (e.g. the 0.6B smoke model) it
> actively disables thinking. `infer.py` additionally strips any stray
> `<think>` block from generations, defensively.

## Files

| File | What |
|---|---|
| `config.yaml` | THE frozen harness: model, seq len, LoRA, batch/LR/epochs, seed, dataset path + N. Commented with the *why* for every default. |
| `config.smoke.yaml` | Overrides for the 10-step exit-0 loop proof (Qwen3-0.6B, seq 256, CPU-safe). |
| `smoke_data.jsonl` | 4 tiny synthetic benefits-notice conversations (system + multi-turn) — placeholder until the real dataset exists. |
| `train.py` | Primary trainer: **Unsloth** QLoRA + `train_on_responses_only` (QWEN3 markers). Auto-falls back to `train_peft.py` if unsloth won't import (native Windows). |
| `train_peft.py` | Fallback trainer: transformers + peft (+ bitsandbytes on CUDA). Same config, same masking semantics, same outputs. Works CPU-only for smoke. |
| `data.py` | JSONL loading, `<think>` stripping, deterministic subsampling, chat templating, assistant-only masking, masked-batch decoder. |
| `common.py` | Config/overrides, hashes, run dirs, `RUN.json`, CSV loss logger. |
| `export.py` | Merge LoRA → merged model + adapter-only copy; HF Hub push stub (owner pushes). |
| `infer.py` | Chat loop / `--eval-file` batch mode with the **frozen decoding config** (greedy, `max_new_tokens=1024`). |
| `modal_app.py` | Same `train.py` on a Modal A100; runs land on volume `slm-week7-runs`. |

## Run outputs

Each run creates `runs/<UTC-timestamp>-N<size>-seed<seed>/` containing:

- `config.yaml` — the *effective* config (after CLI overrides), immutable copy
- `loss_log.csv` — step, epoch, loss, LR, grad-norm, elapsed seconds
- `adapter/` — final LoRA adapter + tokenizer
- `RUN.json` — git-less provenance: config hash, dataset SHA-256, N, seed,
  wall time, library versions, argv, trainer path (`unsloth` / `peft-fallback`)

## Local smoke test (exit-0 loop proof)

```powershell
python src\train\train.py --config src\train\config.smoke.yaml
```

Tiny model (Qwen3-0.6B), N=4 synthetic conversations, 10 steps, seq len 256.
On this Windows box (no NVIDIA GPU, no triton) `train.py` prints the fallback
banner and delegates to `train_peft.py` on CPU with 4-bit auto-disabled —
that's expected. On a CUDA box it does the same thing 4-bit, or runs Unsloth
if it imports.

## Masking verification (protocol rule: decode one masked batch)

```powershell
python src\train\train.py --config src\train\config.smoke.yaml --verify-masking
```

Prints one collated batch decoded into `····[MASKED]····` vs
`▶▶▶TRAINED▶▶▶ ... ◀◀◀` segments. **Eyeball that every system/user turn is
MASKED and only assistant replies (plus their `<|im_end|>` end-of-turn token)
are TRAINED.** Run it once per new dataset and once per model change. The
Unsloth path uses `unsloth.chat_templates.train_on_responses_only` with the
QWEN3 markers (`"<|im_start|>user\n"` / `"<|im_start|>assistant\n"`); the
fallback path implements identical span masking in `data.py` (`MARKERS` —
keep in sync).

## Full local run (needs an NVIDIA GPU)

```powershell
# point config.yaml data.path at the real dataset first, then e.g.:
python src\train\train.py --config src\train\config.yaml --set data.n=300 --set train.seed=3407
```

Any config key is overridable with repeated `--set key=value` — overrides are
recorded in the run's config copy and `RUN.json`.

## Modal (A100) — the intended path for real runs and the sweep

```bash
pip install modal && modal setup          # once
# smoke on the A100:
modal run src/train/modal_app.py::main --config src/train/config.smoke.yaml
# masking verification remotely:
modal run src/train/modal_app.py::main --config src/train/config.smoke.yaml --verify-masking
# one full run:
modal run src/train/modal_app.py::main --config src/train/config.yaml --n 300 --seed 3407
# upload the real dataset once it exists (kept out of the image):
modal volume put slm-week7-runs data/benefits_notices.jsonl data/benefits_notices.jsonl
modal run src/train/modal_app.py::main --n 300 --extra "data.path=/vol/data/benefits_notices.jsonl"
```

Gated fallback model only: `modal secret create huggingface HF_TOKEN=...`
(Qwen models are ungated). Version pins live in `PINNED_PACKAGES` in
`modal_app.py`.

## The data-efficiency sweep (N ∈ {75, 150, 300, 600, 1200})

```bash
modal run src/train/modal_app.py::sweep --config src/train/config.yaml --seed 3407
```

Five sequential runs, one per N, fixed seed. Subsampling is deterministic
(shuffle full dataset with `RNG(seed)`, take first N), so for a fixed seed the
subsets are **nested**: N=75 ⊂ 150 ⊂ 300 ⊂ 600 ⊂ 1200 — the sweep measures
data quantity, not data luck. Fetch results:

```bash
modal volume ls slm-week7-runs
modal volume get slm-week7-runs <run-name> runs/<run-name>
```

## Export & inference

```powershell
python src\train\export.py --run runs\<run-dir>              # merged/ + adapter/ under <run>\export\
python src\train\infer.py --model runs\<run-dir>\export\merged                 # chat loop
python src\train\infer.py --model runs\<run-dir>\adapter --eval-file eval.jsonl  # batch: JSONL in -> .preds.jsonl out
```

Decoding is frozen at greedy / `max_new_tokens=1024` (defined once as
`DECODING` in `infer.py`) — do not add sampling flags; comparability across the
sweep depends on it. HF Hub pushing is a stub: `export.py` prints the `hf
upload` commands with a placeholder repo id; the owner authenticates and pushes.

## Windows notes

- No NVIDIA GPU was present on the dev box at scaffold time (`nvidia-smi`
  absent, Intel iGPU only) — local smoke runs CPU fp32 via the fallback path.
- Unsloth/triton/xformers are not installed locally on purpose; they are
  pinned in the Modal image only.
- bitsandbytes engages automatically in `train_peft.py` when CUDA exists;
  on CPU it is skipped and 4-bit is disabled with a printed warning.
- `train_peft.py` uses `transformers.Trainer` over pre-masked features instead
  of TRL's `SFTTrainer` (TRL's completion-masking API has churned across
  releases; pre-masked labels + plain Trainer computes the identical loss and
  is verifiable with `--verify-masking`).
