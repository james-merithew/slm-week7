"""Primary QLoRA SFT trainer — Unsloth path (Linux/Modal, or Windows+WSL).

Qwen3-4B-Instruct-2507 (fallback Llama-3.2-3B-Instruct), 4-bit NF4 base +
LoRA, assistant-only loss via unsloth.chat_templates.train_on_responses_only
with the QWEN3 marker strings:

    instruction_part = "<|im_start|>user\\n"
    response_part    = "<|im_start|>assistant\\n"

THINKING MODE IS OFF END-TO-END: <think> blocks are stripped from data at load
(data.py) and enable_thinking=False is passed to apply_chat_template.

WINDOWS FALLBACK: if `import unsloth` fails (triton/xformers are Linux-first;
native-Windows installs are unreliable), this script automatically delegates to
train_peft.py, which produces identical outputs (same config, same masking
semantics, same runs/ layout) via transformers+peft. Unsloth stays the
GPU/Modal path.

Usage:
  python src/train/train.py --config src/train/config.yaml --set data.n=300 --set train.seed=42
  python src/train/train.py --config src/train/config.smoke.yaml --verify-masking
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def unsloth_available() -> bool:
    try:
        import unsloth  # noqa: F401
        return True
    except Exception as e:  # ImportError, OSError (missing triton dlls), etc.
        print(f"[train] Unsloth unavailable on this machine ({type(e).__name__}: {e})")
        return False


def main(argv=None) -> int:
    if not unsloth_available():
        print("=" * 72)
        print("[train] FALLING BACK to the PEFT+transformers trainer "
              "(src/train/train_peft.py) — same config, same masking, same outputs.")
        print("=" * 72)
        import train_peft
        return train_peft.main(argv)

    # ---- Unsloth path -----------------------------------------------------
    # NOTE: unsloth must be imported before transformers/trl for its patches.
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import train_on_responses_only

    import common
    import data as data_mod
    import train_peft  # reuse the arg parser so both paths take identical CLIs

    args = train_peft.parse_args(argv)
    cfg = common.load_config(args.config, args.overrides)
    tcfg = cfg["train"]
    common.set_all_seeds(tcfg["seed"])

    ds_path = common.resolve_path(cfg["data"]["path"])
    convs = data_mod.load_conversations(ds_path)  # strips <think> blocks
    convs = data_mod.subsample(convs, cfg["data"].get("n"), tcfg["seed"],
                               cfg["data"].get("shuffle_before_subsample", True))
    n_eff = len(convs)
    print(f"[train] {n_eff} conversations from {ds_path} "
          f"(seed={tcfg['seed']}, thinking-mode stripped+disabled)")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=cfg["model"]["id"],
        max_seq_length=cfg["model"]["max_seq_len"],
        load_in_4bit=bool(cfg["model"].get("load_in_4bit", True)),
        dtype=None,  # auto: bf16 on Ampere+
    )
    lcfg = cfg["lora"]
    model = FastLanguageModel.get_peft_model(
        model,
        r=lcfg["r"],
        lora_alpha=lcfg["alpha"],
        lora_dropout=lcfg["dropout"],
        target_modules=list(lcfg["target_modules"]),
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=tcfg["seed"],
    )

    # Render full conversations with thinking OFF; Unsloth masks by markers.
    from datasets import Dataset
    texts = [data_mod.render_conversation(tokenizer, c) for c in convs]
    train_ds = Dataset.from_dict({"text": texts})

    from trl import SFTConfig, SFTTrainer

    run_dir = None
    if not args.verify_masking:
        run_dir = common.make_run_dir(cfg, n_eff)
        print(f"[train] run dir: {run_dir}")
    out_dir = str(run_dir / "hf_out") if run_dir else "unsloth_tmp_out"

    sft_args = SFTConfig(
        output_dir=out_dir,
        dataset_text_field="text",
        max_length=cfg["model"]["max_seq_len"],
        packing=bool(tcfg.get("packing", False)),
        per_device_train_batch_size=tcfg["per_device_batch_size"],
        gradient_accumulation_steps=tcfg["grad_accum_steps"],
        learning_rate=float(tcfg["learning_rate"]),
        lr_scheduler_type=tcfg["lr_scheduler"],
        warmup_ratio=float(tcfg["warmup_ratio"]),
        num_train_epochs=tcfg["epochs"],
        max_steps=tcfg.get("max_steps", -1),
        weight_decay=float(tcfg["weight_decay"]),
        max_grad_norm=float(tcfg["max_grad_norm"]),
        optim=tcfg["optim"],
        logging_steps=tcfg["logging_steps"],
        save_strategy=tcfg["save_strategy"],
        seed=tcfg["seed"],
        data_seed=tcfg["seed"],
        report_to=[],
    )
    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=train_ds,
        args=sft_args,
    )

    # Assistant-only loss: QWEN3 marker strings (see data.MARKERS — keep in sync).
    marks = data_mod.markers_for(cfg["model"]["id"])
    trainer = train_on_responses_only(
        trainer,
        instruction_part=marks["instruction_part"],
        response_part=marks["response_part"],
    )

    if args.verify_masking:
        # "Decode one masked batch" protocol rule: show exactly what gets loss.
        batch = next(iter(trainer.get_train_dataloader()))
        data_mod.print_masked_batch(tokenizer, batch)
        return 0

    trainer.add_callback(common.make_csv_logger_callback(run_dir))
    t0 = time.time()
    stats = trainer.train()
    wall = time.time() - t0

    adapter_dir = run_dir / "adapter"
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))
    common.write_run_json(run_dir, cfg, ds_path, n_eff, wall,
                          trainer_path="unsloth",
                          extra={"final_loss": getattr(stats, "training_loss", None)})
    print(f"[train] DONE in {wall:.1f}s -> {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
