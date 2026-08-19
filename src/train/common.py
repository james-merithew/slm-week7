"""Shared harness utilities: config, provenance, run directories, CSV loss log.

One frozen harness rule: everything that can change a result lives in the YAML
config; every run writes an immutable copy of that config plus RUN.json
provenance (config hash, dataset hash, wall time, library versions) into its
own runs/<timestamp>-N<size>-seed<seed>/ directory.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import random
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # C:\dev\slm-week7
DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.yaml"

# Sweep values for the data-efficiency experiment (docs reference).
SWEEP_NS = [75, 150, 300, 600, 1200]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(path: str | os.PathLike | None = None,
                overrides: list[str] | None = None) -> dict:
    """Load YAML config; apply dotted-path overrides like train.seed=42."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["_config_path"] = str(cfg_path)
    for ov in overrides or []:
        key, _, raw = ov.partition("=")
        if not _:
            raise SystemExit(f"Bad --set override (need key=value): {ov!r}")
        node = cfg
        parts = key.strip().split(".")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = yaml.safe_load(raw)  # YAML-parse value: ints/floats/bools/null
    return cfg


def config_hash(cfg: dict) -> str:
    """Stable hash of the effective config (ignoring bookkeeping keys)."""
    clean = {k: v for k, v in cfg.items() if not k.startswith("_")}
    blob = json.dumps(clean, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def file_sha256(path: str | os.PathLike) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def resolve_path(p: str | os.PathLike) -> Path:
    """Resolve a config-relative path against the project root."""
    p = Path(p)
    return p if p.is_absolute() else (PROJECT_ROOT / p)


def set_all_seeds(seed: int) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Run directory + provenance
# ---------------------------------------------------------------------------

def make_run_dir(cfg: dict, n_effective: int) -> Path:
    """Create runs/<UTC ts>-N<size>-seed<seed>/ and copy the effective config."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    seed = cfg["train"]["seed"]
    run_dir = resolve_path(cfg["output"]["runs_dir"]) / f"{ts}-N{n_effective}-seed{seed}"
    run_dir.mkdir(parents=True, exist_ok=False)
    # Immutable copy of the *effective* config (after CLI overrides).
    clean = {k: v for k, v in cfg.items() if not k.startswith("_")}
    with open(run_dir / "config.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(clean, f, sort_keys=False)
    return run_dir


def library_versions() -> dict[str, str]:
    vers: dict[str, str] = {"python": sys.version.split()[0], "platform": platform.platform()}
    for mod in ("torch", "transformers", "peft", "trl", "bitsandbytes",
                "unsloth", "datasets", "accelerate"):
        try:
            m = __import__(mod)
            vers[mod] = getattr(m, "__version__", "unknown")
        except Exception:
            vers[mod] = "not-installed"
    try:
        import torch
        vers["cuda_available"] = str(torch.cuda.is_available())
        if torch.cuda.is_available():
            vers["gpu"] = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return vers


def write_run_json(run_dir: Path, cfg: dict, dataset_path: Path,
                   n_effective: int, wall_time_s: float,
                   trainer_path: str, extra: dict | None = None) -> None:
    """Git-less provenance record for the run."""
    record = {
        "harness_version": cfg.get("harness_version"),
        "trainer_path": trainer_path,            # "unsloth" or "peft-fallback"
        "config_hash": config_hash(cfg),
        "dataset_path": str(dataset_path),
        "dataset_sha256": file_sha256(dataset_path),
        "n_examples": n_effective,
        "seed": cfg["train"]["seed"],
        "model_id": cfg["model"]["id"],
        "wall_time_seconds": round(wall_time_s, 2),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "library_versions": library_versions(),
        "argv": sys.argv,
    }
    record.update(extra or {})
    with open(run_dir / "RUN.json", "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)


# ---------------------------------------------------------------------------
# CSV loss logging (transformers Trainer callback)
# ---------------------------------------------------------------------------

def make_csv_logger_callback(run_dir: Path):
    """TrainerCallback writing every logged step to loss_log.csv."""
    from transformers import TrainerCallback

    class CsvLossLogger(TrainerCallback):
        def __init__(self) -> None:
            self.path = run_dir / "loss_log.csv"
            self.t0 = time.time()
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(
                    ["step", "epoch", "loss", "learning_rate", "grad_norm", "elapsed_s"])

        def on_log(self, args, state, control, logs=None, **kwargs):
            if not logs or "loss" not in logs:
                return
            with open(self.path, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    state.global_step,
                    round(state.epoch or 0.0, 4),
                    logs.get("loss"),
                    logs.get("learning_rate"),
                    logs.get("grad_norm"),
                    round(time.time() - self.t0, 1),
                ])

    return CsvLossLogger()
