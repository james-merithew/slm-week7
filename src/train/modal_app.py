"""Modal app: run the SAME src/train/train.py (Unsloth path) on an A100.

The whole src/train/ directory is baked into the image, so Modal runs exactly
the code and config that live in this repo — one frozen harness, remote or
local. Run outputs land on a persistent Modal Volume ("slm-week7-runs") laid
out identically to local runs/, and HF model downloads are cached on a second
volume so sweep runs don't re-download the base model.

EXACT COMMANDS (from repo root, after `pip install modal` + `modal setup`).
Note the ::main / ::sweep qualifier — this file has two entrypoints, so
`modal run` requires it:

  # smoke test on the A100 (tiny model, 10 steps):
  modal run src/train/modal_app.py::main --config src/train/config.smoke.yaml

  # single full run:
  modal run src/train/modal_app.py::main --config src/train/config.yaml --n 300 --seed 3407

  # masking verification on the real model/template:
  modal run src/train/modal_app.py::main --config src/train/config.smoke.yaml --verify-masking

  # the data-efficiency sweep (N in 75,150,300,600,1200 — five sequential runs):
  modal run src/train/modal_app.py::sweep --config src/train/config.yaml --seed 3407

  # list finished runs / download one:
  modal volume ls slm-week7-runs
  modal volume get slm-week7-runs <run-name> runs/<run-name>

Notes:
  * Pins are in PINNED_PACKAGES below — bump deliberately, in one place.
  * Gated models (Llama fallback) need `modal secret create huggingface
    HF_TOKEN=...`; the Qwen models are ungated. The secret is optional-mounted.
"""

from __future__ import annotations

from pathlib import Path

import modal

APP_NAME = "slm-week7-train"
GPU = "L4"                  # card-free accounts can't use A100-class GPUs; 4-bit 4B QLoRA fits on L4's 24GB (batch lowered via CLI overrides)
TIMEOUT_S = 4 * 60 * 60

# Single place for remote pins. unsloth pins its own compatible
# transformers/trl/torch range; we add what the harness itself imports.
PINNED_PACKAGES = [
    "unsloth==2026.8.18",   # pulls compatible torch/transformers/trl/peft/bitsandbytes/xformers
    "datasets>=3.2",
    "pyyaml>=6.0",
]

LOCAL_TRAIN_DIR = Path(__file__).resolve().parent          # src/train
REMOTE_TRAIN_DIR = "/root/project/src/train"
REMOTE_RUNS_DIR = "/vol/runs"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(*PINNED_PACKAGES)
    .env({"HF_HOME": "/hf_cache"})  # own top-level mount: Modal forbids nested volume mounts
    .add_local_dir(str(LOCAL_TRAIN_DIR), REMOTE_TRAIN_DIR)
)

app = modal.App(APP_NAME)
runs_volume = modal.Volume.from_name("slm-week7-runs", create_if_missing=True)
hf_cache_volume = modal.Volume.from_name("slm-week7-hf-cache", create_if_missing=True)

# Qwen models are ungated — no HF token needed. (An optional
# Secret.from_name("huggingface") reference fails LAZILY at run time on
# current Modal when the secret doesn't exist, so it can't be a soft default;
# add the secret back here only if switching to the gated Llama fallback.)
_secrets: list = []


def _run_train(config_rel: str, overrides: list[str], verify_masking: bool) -> int:
    """Shared body: invoke train.py's main() inside the container."""
    import sys
    sys.path.insert(0, REMOTE_TRAIN_DIR)
    import common
    # Redirect repo-relative outputs onto the persistent volume:
    # config's output.runs_dir ("runs") resolves to /vol/runs.
    common.PROJECT_ROOT = Path("/vol")

    # src/train/ was baked wholesale into the image, so resolve the config (and
    # any src/train-relative dataset like the smoke set) by basename there.
    config_path = f"{REMOTE_TRAIN_DIR}/{Path(config_rel).name}"
    argv = ["--config", config_path]
    for ov in overrides:
        argv += ["--set", ov]
    cfg = common.load_config(config_path, overrides)
    dpath = str(cfg["data"]["path"]).replace("\\", "/")
    if dpath.startswith("src/train/"):
        argv += ["--set", f"data.path={REMOTE_TRAIN_DIR}/{Path(dpath).name}"]
    # NOTE: the real benefits-notice dataset (when it exists under data/) must
    # be uploaded once to the runs volume and referenced with
    #   --extra "data.path=/vol/data/benefits_notices.jsonl"
    #   (upload: modal volume put slm-week7-runs data/benefits_notices.jsonl data/benefits_notices.jsonl)
    if verify_masking:
        argv += ["--verify-masking"]

    import train
    rc = train.main(argv)
    runs_volume.commit()
    return rc


@app.function(image=image, gpu=GPU, timeout=TIMEOUT_S,
              volumes={"/vol": runs_volume, "/hf_cache": hf_cache_volume},
              secrets=_secrets)
def train_remote(config: str, overrides: list[str], verify_masking: bool = False) -> int:
    return _run_train(config, overrides, verify_masking)


@app.local_entrypoint()
def main(config: str = "src/train/config.yaml",
         n: int = 0, seed: int = 0, verify_masking: bool = False,
         extra: str = ""):
    """Single run. --n / --seed are conveniences for the sweep axes;
    --extra takes semicolon-separated config overrides ("a.b=1;c.d=2")."""
    overrides = []
    if n:
        overrides.append(f"data.n={n}")
    if seed:
        overrides.append(f"train.seed={seed}")
    if extra:
        overrides += [s for s in extra.split(";") if s]
    rc = train_remote.remote(config, overrides, verify_masking)
    raise SystemExit(rc)


@app.local_entrypoint()
def sweep(config: str = "src/train/config.yaml", seed: int = 3407):
    """Data-efficiency sweep: N in {75, 150, 300, 600, 1200}, fixed seed.

    Runs sequentially (same GPU class, deterministic order). Requires the real
    dataset (>=1200 rows) to be configured under data.path first.
    """
    for n in [75, 150, 300, 600, 1200]:
        print(f"\n===== sweep: N={n} seed={seed} =====")
        rc = train_remote.remote(config, [f"data.n={n}", f"train.seed={seed}"])
        if rc != 0:
            raise SystemExit(f"sweep failed at N={n} (rc={rc})")
    print("sweep complete — adapters + RUN.json on volume slm-week7-runs")
