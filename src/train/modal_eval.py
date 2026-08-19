"""Modal app: run eval.py (base-vs-tuned, checker-scored) on the L4.

Local CPU inference of the 4B is impractical (hours per model), so generation
runs remotely; the checker (deterministic, pure python) runs there too. The
LLM judge does NOT run remotely — no API key enters the container. Run the
judge locally afterwards over the downloaded transcripts with
src/ablation/judge_transcripts.py.

  modal run src/train/modal_eval.py::main \
      --model hf:/vol/runs/<run>/adapter \
      --baseline hf:Qwen/Qwen3-4B-Instruct-2507 \
      --limit 10 --out-name m7-base-vs-tuned

  modal volume get slm-week7-runs eval/m7-base-vs-tuned evidence/2026-08-18/m7-base-vs-tuned
"""

from __future__ import annotations

from pathlib import Path

import modal

APP_NAME = "slm-week7-eval"
GPU = "L4"
TIMEOUT_S = 2 * 60 * 60

PINNED_PACKAGES = [
    "unsloth==2026.8.18",   # same image stack as training: torch/transformers/peft
    "datasets>=3.2",
    "pyyaml>=6.0",
    "anthropic",            # imported by eval.py's judge module (unused: judge-sample 0)
    "openai",               # imported by run_ablation's provider map (unused remotely)
    # Checker determinism pins (mirror requirements.txt — checker runs remotely):
    "spacy==3.8.15",
    "lemminflect==0.2.3",
    "en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl",
]

# In the container this file sits at /root/modal_eval.py, where parents[2]
# does not exist — guard so remote import doesn't IndexError (the value is
# only meaningful locally, for the add_local_dir calls at image build).
_here = Path(__file__).resolve()
REPO_ROOT = _here.parents[2] if len(_here.parents) > 2 else _here.parent
REMOTE_ROOT = "/root/project"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*PINNED_PACKAGES)
    .env({"HF_HOME": "/hf_cache"})
    .add_local_dir(str(REPO_ROOT / "src"), f"{REMOTE_ROOT}/src")
    .add_local_dir(str(REPO_ROOT / "data" / "ablation"), f"{REMOTE_ROOT}/data/ablation")
    .add_local_file(str(REPO_ROOT / "eval.py"), f"{REMOTE_ROOT}/eval.py")
)

app = modal.App(APP_NAME)
runs_volume = modal.Volume.from_name("slm-week7-runs", create_if_missing=True)
hf_cache_volume = modal.Volume.from_name("slm-week7-hf-cache", create_if_missing=True)


@app.function(image=image, gpu=GPU, timeout=TIMEOUT_S,
              volumes={"/vol": runs_volume, "/hf_cache": hf_cache_volume})
def eval_remote(model: str, baseline: str, limit: int, out_name: str) -> int:
    import subprocess
    import sys

    out = f"/vol/eval/{out_name}"
    cmd = [
        sys.executable, f"{REMOTE_ROOT}/eval.py",
        "--model", model,
        "--eval-set", f"{REMOTE_ROOT}/data/ablation/scenarios.jsonl",
        "--out", out,
        "--judge-sample", "0",     # judge runs LOCALLY afterwards; no key here
        "--workers", "1",
    ]
    if baseline:
        cmd += ["--baseline", baseline]
    if limit:
        cmd += ["--limit", str(limit)]
    rc = subprocess.call(cmd, cwd=REMOTE_ROOT)
    runs_volume.commit()
    return rc


@app.local_entrypoint()
def main(model: str, baseline: str = "", limit: int = 0,
         out_name: str = "eval"):
    rc = eval_remote.remote(model, baseline, limit, out_name)
    raise SystemExit(rc)
