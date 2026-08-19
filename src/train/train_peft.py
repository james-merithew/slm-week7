"""PEFT + bitsandbytes fallback QLoRA trainer (Windows-local path).

WHY THIS FILE EXISTS: Unsloth on native Windows is unreliable (triton is
Linux-first; xformers/triton wheels for Windows lag or fail at import). This
trainer reproduces train.py's behavior — same config file, same thinking-off
chat templating, same assistant-only masking semantics, same runs/ outputs —
using only transformers + peft (+ bitsandbytes when CUDA exists), so the LOCAL
smoke test works on any Windows box. Unsloth remains the Modal/Linux path.

Substitution note: masking is done manually in data.py (offset-mapping over the
QWEN3 marker strings) and training uses transformers.Trainer on the
pre-tokenized dataset rather than TRL's SFTTrainer. TRL's SFTTrainer API has
churned repeatedly across releases (DataCollatorForCompletionOnlyLM removal,
1.x reshuffle); pre-masked features + plain Trainer is byte-for-byte the same
loss computation and is stable across versions. The masking itself is
verifiable with --verify-masking on either path.

CPU degradation (no NVIDIA GPU present): load_in_4bit is auto-disabled (bnb
needs CUDA), optimizer downgrades to adamw_torch, fp32. Good enough for the
exit-0 smoke proof; NOT for real training.

Usage:
  python src/train/train_peft.py --config src/train/config.smoke.yaml
  python src/train/train_peft.py --config src/train/config.yaml --set data.n=300 --set train.seed=42
  python src/train/train_peft.py --config src/train/config.smoke.yaml --verify-masking
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common
import data as data_mod


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=str(common.DEFAULT_CONFIG))
    ap.add_argument("--set", dest="overrides", action="append", default=[],
                    metavar="KEY=VALUE", help="dotted config override, e.g. data.n=300")
    ap.add_argument("--verify-masking", action="store_true",
                    help="decode one masked batch, print it, and exit (no training)")
    return ap.parse_args(argv)


def load_model_and_tokenizer(cfg: dict):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_id = cfg["model"]["id"]
    use_cuda = torch.cuda.is_available()
    want_4bit = bool(cfg["model"].get("load_in_4bit", True))
    quant_cfg = None
    if want_4bit and use_cuda:
        from transformers import BitsAndBytesConfig
        quant_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
    elif want_4bit:
        print("[train_peft] No CUDA device: disabling 4-bit quantization "
              "(bitsandbytes requires CUDA). Running full-precision on CPU — "
              "smoke-test mode only.")

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=quant_cfg,
        dtype=(torch.bfloat16 if use_cuda else torch.float32),
        device_map=("auto" if use_cuda else None),
    )
    model.config.use_cache = False  # incompatible with grad checkpointing/training

    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    if quant_cfg is not None:
        model = prepare_model_for_kbit_training(model)
    lcfg = cfg["lora"]
    lora = LoraConfig(
        r=lcfg["r"], lora_alpha=lcfg["alpha"], lora_dropout=lcfg["dropout"],
        target_modules=list(lcfg["target_modules"]),
        bias="none", task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()
    return model, tokenizer


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = common.load_config(args.config, args.overrides)
    tcfg = cfg["train"]
    common.set_all_seeds(tcfg["seed"])

    # ---- data -------------------------------------------------------------
    ds_path = common.resolve_path(cfg["data"]["path"])
    convs = data_mod.load_conversations(ds_path)
    convs = data_mod.subsample(convs, cfg["data"].get("n"), tcfg["seed"],
                               cfg["data"].get("shuffle_before_subsample", True))
    n_eff = len(convs)
    print(f"[train_peft] {n_eff} conversations from {ds_path} "
          f"(seed={tcfg['seed']}, thinking-mode stripped+disabled)")

    # ---- model ------------------------------------------------------------
    model, tokenizer = load_model_and_tokenizer(cfg)
    tokenized = data_mod.build_tokenized_dataset(
        tokenizer, convs, cfg["model"]["max_seq_len"], cfg["model"]["id"])
    collator = data_mod.PadCollator(tokenizer)

    if args.verify_masking:
        import torch
        batch = collator([tokenized[i] for i in range(min(2, len(tokenized)))])
        data_mod.print_masked_batch(tokenizer, batch)
        return 0

    # ---- trainer ----------------------------------------------------------
    import torch
    from transformers import Trainer, TrainingArguments

    run_dir = common.make_run_dir(cfg, n_eff)
    print(f"[train_peft] run dir: {run_dir}")
    use_cuda = torch.cuda.is_available()
    optim = tcfg["optim"]
    if not use_cuda and "8bit" in optim:
        optim = "adamw_torch"

    targs = TrainingArguments(
        output_dir=str(run_dir / "hf_out"),
        per_device_train_batch_size=tcfg["per_device_batch_size"],
        gradient_accumulation_steps=tcfg["grad_accum_steps"],
        learning_rate=float(tcfg["learning_rate"]),
        lr_scheduler_type=tcfg["lr_scheduler"],
        warmup_ratio=float(tcfg["warmup_ratio"]),
        num_train_epochs=tcfg["epochs"],
        max_steps=tcfg.get("max_steps", -1),
        weight_decay=float(tcfg["weight_decay"]),
        max_grad_norm=float(tcfg["max_grad_norm"]),
        optim=optim,
        logging_steps=tcfg["logging_steps"],
        save_strategy=tcfg["save_strategy"],
        seed=tcfg["seed"],
        data_seed=tcfg["seed"],
        bf16=use_cuda,
        report_to=[],
        remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model,
        args=targs,
        train_dataset=tokenized,
        data_collator=collator,
        callbacks=[common.make_csv_logger_callback(run_dir)],
    )

    t0 = time.time()
    trainer.train()
    wall = time.time() - t0

    adapter_dir = run_dir / "adapter"
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))
    common.write_run_json(run_dir, cfg, ds_path, n_eff, wall,
                          trainer_path="peft-fallback",
                          extra={"final_loss": (trainer.state.log_history[-1].get("train_loss")
                                                if trainer.state.log_history else None)})
    print(f"[train_peft] DONE in {wall:.1f}s -> {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
