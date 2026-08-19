"""Inference for trained checkpoints: interactive chat or batch eval.

ONE FROZEN HARNESS — FIXED DECODING CONFIG (do not add sampling flags):
  greedy decoding (do_sample=False), max_new_tokens=1024.
Every evaluation in this project uses exactly these settings so numbers are
comparable across the sweep.

THINKING MODE OFF: enable_thinking=False on every apply_chat_template call,
and any <think> block a model still emits is stripped from the output
defensively.

Model loading (--model accepts any ONE of):
  * a merged-model directory        (runs/<run>/export/merged)
  * an adapter directory            (runs/<run>/adapter) — base is read from
                                    the adapter's config / RUN.json
  * a plain HF model id             (baseline comparisons)

Usage:
  python src/train/infer.py --model runs/<run>/export/merged            # chat loop
  python src/train/infer.py --model runs/<run>/adapter --eval-file data/eval.jsonl --out preds.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from data import strip_thinking

# ---- FROZEN DECODING CONFIG (project harness rule) ------------------------
DECODING = dict(do_sample=False, max_new_tokens=1024)
# ---------------------------------------------------------------------------

DEFAULT_SYSTEM = "You are a benefits-notice explainer. Explain notices in plain language."


def load_model(model_path: str):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    device_map = "auto" if torch.cuda.is_available() else None
    p = common.resolve_path(model_path)
    is_dir = p.is_dir()
    ref = str(p) if is_dir else model_path

    if is_dir and (p / "adapter_config.json").exists():
        # Adapter dir: find base model id from adapter config.
        from peft import PeftModel
        acfg = json.loads((p / "adapter_config.json").read_text(encoding="utf-8"))
        base_id = acfg.get("base_model_name_or_path")
        print(f"[infer] adapter {p} on base {base_id}")
        tokenizer = AutoTokenizer.from_pretrained(ref)
        base = AutoModelForCausalLM.from_pretrained(base_id, dtype=dtype,
                                                    device_map=device_map)
        model = PeftModel.from_pretrained(base, ref)
    else:
        print(f"[infer] loading {ref}")
        tokenizer = AutoTokenizer.from_pretrained(ref)
        model = AutoModelForCausalLM.from_pretrained(ref, dtype=dtype,
                                                     device_map=device_map)
    model.eval()
    return model, tokenizer


def generate(model, tokenizer, messages: list[dict]) -> str:
    import torch
    enc = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        enable_thinking=False,       # REQUIRED: thinking OFF end-to-end
        return_tensors="pt",
        return_dict=True,
    ).to(model.device)
    with torch.no_grad():
        out = model.generate(**enc, **DECODING,
                             pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id)
    text = tokenizer.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
    return strip_thinking(text)  # defensive: drop any stray <think> block


def chat_loop(model, tokenizer, system: str) -> None:
    print("[infer] chat loop — empty line or 'exit' to quit, '/reset' to clear history")
    messages = [{"role": "system", "content": system}]
    while True:
        try:
            user = input("\nuser> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user or user.lower() == "exit":
            break
        if user == "/reset":
            messages = [{"role": "system", "content": system}]
            print("[infer] history cleared")
            continue
        messages.append({"role": "user", "content": user})
        reply = generate(model, tokenizer, messages)
        messages.append({"role": "assistant", "content": reply})
        print(f"\nassistant> {reply}")


def eval_file(model, tokenizer, in_path: Path, out_path: Path, system: str) -> None:
    """JSONL in -> completions out.

    Input rows: {"messages": [...]} (last user turn is the prompt) or
                {"prompt": "..."} (wrapped with the default system message).
    Output rows: input row + {"completion": "..."}.
    """
    n = 0
    with open(in_path, "r", encoding="utf-8") as fin, \
         open(out_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "messages" in row:
                # Use the conversation up to (excluding) any trailing
                # assistant turn — that turn is the reference, not the prompt.
                msgs = row["messages"]
                if msgs and msgs[-1]["role"] == "assistant":
                    msgs = msgs[:-1]
            else:
                msgs = [{"role": "system", "content": system},
                        {"role": "user", "content": row["prompt"]}]
            row["completion"] = generate(model, tokenizer, msgs)
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
            print(f"[infer] {n} done", end="\r")
    print(f"\n[infer] wrote {n} completions -> {out_path} "
          f"(decoding: greedy, max_new_tokens={DECODING['max_new_tokens']})")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True,
                    help="merged dir, adapter dir, or HF model id")
    ap.add_argument("--eval-file", default=None, help="JSONL in -> completions out")
    ap.add_argument("--out", default=None, help="output JSONL (default: <eval-file>.preds.jsonl)")
    ap.add_argument("--system", default=DEFAULT_SYSTEM)
    args = ap.parse_args(argv)

    model, tokenizer = load_model(args.model)
    if args.eval_file:
        in_path = common.resolve_path(args.eval_file)
        out_path = common.resolve_path(args.out) if args.out else \
            in_path.with_suffix(in_path.suffix + ".preds.jsonl")
        eval_file(model, tokenizer, in_path, out_path, args.system)
    else:
        chat_loop(model, tokenizer, args.system)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
