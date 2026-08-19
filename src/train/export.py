"""Merge a trained LoRA adapter into the base model and save both forms.

Outputs, inside the run directory:
  <run>/export/merged/    full merged model (safetensors) + tokenizer
  <run>/export/adapter/   adapter-only copy (small, portable)

HF Hub push: STUB ONLY. This script never handles tokens — the project owner
pushes manually (see the printed commands / README).

Usage:
  python src/train/export.py --run runs/20260818-...-N300-seed3407
  python src/train/export.py --run <run_dir> --base Qwen/Qwen3-4B-Instruct-2507
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common

# Placeholder repo id for the eventual Hub push (owner fills in and pushes).
HUB_REPO_ID_PLACEHOLDER = "YOUR-ORG/qwen3-4b-benefits-notice-qlora"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True, help="run directory containing adapter/")
    ap.add_argument("--base", default=None,
                    help="base model id (default: model_id recorded in RUN.json)")
    ap.add_argument("--skip-merge", action="store_true",
                    help="only copy the adapter (no merged full model)")
    args = ap.parse_args(argv)

    run_dir = common.resolve_path(args.run)
    adapter_src = run_dir / "adapter"
    if not adapter_src.is_dir():
        raise SystemExit(f"No adapter/ in {run_dir}")

    base_id = args.base
    run_json = run_dir / "RUN.json"
    if base_id is None and run_json.exists():
        base_id = json.loads(run_json.read_text(encoding="utf-8"))["model_id"]
    if base_id is None:
        raise SystemExit("Pass --base (no RUN.json to read model_id from)")

    export_dir = run_dir / "export"
    export_dir.mkdir(exist_ok=True)

    # 1) adapter-only copy (always)
    adapter_dst = export_dir / "adapter"
    if adapter_dst.exists():
        shutil.rmtree(adapter_dst)
    shutil.copytree(adapter_src, adapter_dst)
    print(f"[export] adapter-only copy -> {adapter_dst}")

    # 2) merged model
    if not args.skip_merge:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        print(f"[export] loading base {base_id} (fp16/bf16, NOT 4-bit — merging "
              "into a quantized base bakes in quantization error)")
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        base = AutoModelForCausalLM.from_pretrained(base_id, dtype=dtype)
        model = PeftModel.from_pretrained(base, str(adapter_src))
        model = model.merge_and_unload()
        merged_dir = export_dir / "merged"
        model.save_pretrained(str(merged_dir), safe_serialization=True)
        AutoTokenizer.from_pretrained(base_id).save_pretrained(str(merged_dir))
        print(f"[export] merged model -> {merged_dir}")

    # 3) Hub push stub — owner runs this manually with their own auth.
    print(f"""
[export] HF Hub push (STUB — no tokens handled here; owner pushes):
    hf auth login                          # once, interactive
    hf upload {HUB_REPO_ID_PLACEHOLDER} {export_dir / 'adapter'} --repo-type model
    # or for the merged model:
    hf upload {HUB_REPO_ID_PLACEHOLDER} {export_dir / 'merged'} --repo-type model
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
