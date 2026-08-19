"""Prompt-Ceiling Ablation runner (Ablation 1).

Proves, with numbers, that prompting has a ceiling below the reliability bar:
>= 2 frontier models from different families x >= 3 strategies x >= 30
scenarios each. The HEADLINE metric is the deterministic checker
(src/checker), run on every conversation for free; the LLM judge audits only
a sampled fraction (--judge-sample, deterministic by scenario id hash so
reruns pick the same subset). FIRST-PASS only: no regeneration anywhere.

Usage:
  python -m src.ablation.run_ablation \
      --scenarios data/ablation/scenarios.jsonl \
      --out evidence/2026-08-17/ablation \
      [--models claude:claude-opus-5 openrouter:openai/gpt-5.2] \
      [--strategies zero_shot few_shot structured_cot] \
      [--limit 3]           # smoke test on first N scenarios
      [--workers 8]
      [--judge-sample 0.25] # LLM-judge audit fraction (checker always runs)

Env: ANTHROPIC_API_KEY, OPENROUTER_API_KEY

Outputs in --out:
  transcripts.jsonl    - every conversation + checker verdicts (+ judge audit
                         when sampled); grader-rerunnable; per-turn
                         compliance-by-turn-index series for the drift chart
  judge_verdicts.jsonl - raw judge verdicts for the audited subset
  results.csv          - one row per model x strategy
  results.md           - the results table for the defense doc
"""

import argparse
import csv
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic
from openai import OpenAI

from .checker_bridge import check_conversation
from .judge import judge_conversation
from .strategies import STRATEGIES

# Owner call 2026-08-18: Claude + Mistral (free tier, no card). Supersedes
# Gemini free tier, whose 20-requests/day/model cap cannot execute the
# ablation (~270 requests). mistral-large-latest = the family's flagship alias;
# verify with a smoke completion once MISTRAL_API_KEY exists.
DEFAULT_MODELS = [
    "claude:claude-opus-5",
    "mistral:mistral-large-latest",
]

# Free-tier RPM caps: keep concurrent in-flight calls per provider low and
# retry 429s patiently, honoring the server's "retry in Ns" hint.
# Mistral free tier is ~1 request/second -> strictly serial.
PROVIDER_MAX_CONCURRENCY = {"google": 2, "mistral": 1}
THROTTLES: dict = {}


def _retry_seconds(err_text: str) -> float | None:
    m = re.search(r"retry in ([0-9.]+)s", err_text)
    return float(m.group(1)) if m else None


def call_with_retry(fn, provider: str, attempts: int = 8):
    throttle = THROTTLES.get(provider)
    for attempt in range(attempts):
        try:
            if throttle:
                with throttle:
                    return fn()
            return fn()
        except Exception as e:
            # Free tiers throw both 429s (quota) and 503s (demand spikes);
            # retry both patiently, fail fast on anything else (auth, 400s).
            retryable = type(e).__name__ in (
                "RateLimitError", "InternalServerError", "APITimeoutError",
                "APIConnectionError",
            )
            if not retryable or attempt == attempts - 1:
                raise
            delay = _retry_seconds(str(e)) or min(70.0, 5.0 * 2 ** attempt)
            log(f"[{provider}] {type(e).__name__}; sleeping {delay:.0f}s (attempt {attempt + 1})")
            time.sleep(delay + random.uniform(0, 2))

# Generous: thinking models (Gemini 3.x, Claude) spend reasoning tokens inside
# this cap; 1024 truncated Gemini replies mid-sentence in smoke tests.
MAX_SUBJECT_TOKENS = 2048

# provider -> (env var, OpenAI-compatible base_url or None for api.openai.com)
PROVIDER_ENV = {
    "openai": ("OPENAI_API_KEY", None),
    "google": ("GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai/"),
    "mistral": ("MISTRAL_API_KEY", "https://api.mistral.ai/v1"),
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1"),
}

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def load_scenarios(path: Path) -> list[dict]:
    scenarios = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                scenarios.append(json.loads(line))
    ids = [s["id"] for s in scenarios]
    assert len(ids) == len(set(ids)), "duplicate scenario ids"
    return scenarios


def make_api_completer(
    provider: str, model_id: str, system: str,
    anthropic_client: anthropic.Anthropic, oai_clients: dict,
):
    """Return complete(turns) -> reply_text for an API-hosted subject model.

    Shared by the ablation runner and eval.py so both entry points call
    subjects identically.
    """
    if provider == "claude":
        def complete(turns: list[dict]) -> str:
            resp = anthropic_client.messages.create(
                model=model_id,
                max_tokens=MAX_SUBJECT_TOKENS,
                # The ~30k-token spec+word-list prefix is identical across every
                # call; cached re-reads bill at ~0.1x input price.
                system=[{"type": "text", "text": system,
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": t["role"], "content": t["content"]} for t in turns],
            )
            if resp.stop_reason == "refusal":
                return "[MODEL REFUSED]"
            return "".join(b.text for b in resp.content if b.type == "text")
    elif provider in oai_clients:
        def complete(turns: list[dict]) -> str:
            resp = call_with_retry(
                lambda: oai_clients[provider].chat.completions.create(
                    model=model_id,
                    max_tokens=MAX_SUBJECT_TOKENS,
                    messages=[{"role": "system", "content": system}]
                    + [{"role": t["role"], "content": t["content"]} for t in turns],
                ),
                provider,
            )
            return resp.choices[0].message.content or ""
    else:
        raise ValueError(f"unknown provider: {provider}")
    return complete


def run_subject_conversation(complete, user_turns: list[str]) -> list[dict]:
    """Play scripted user turns against a subject; return the full transcript.

    *complete* is any callable turns -> reply_text (API or local HF model).
    FIRST-PASS: each reply is taken as-is; there is no regeneration.
    """
    turns: list[dict] = []
    for user_msg in user_turns:
        turns.append({"role": "user", "content": user_msg})
        turns.append({"role": "assistant", "content": complete(list(turns))})
    return turns


def judge_is_selected(scenario_id: str, fraction: float) -> bool:
    """Deterministic audit sampling: hash the scenario id so reruns (and both
    models/strategies within a run) pick the same scenario subset."""
    if fraction >= 1.0:
        return True
    if fraction <= 0.0:
        return False
    h = int(hashlib.sha256(scenario_id.encode("utf-8")).hexdigest()[:8], 16)
    return h / 0x100000000 < fraction


def run_one(
    combo: tuple, scenario: dict,
    anthropic_client: anthropic.Anthropic, oai_clients: dict,
    judge_fraction: float = 0.25,
) -> dict:
    provider, model_id, strategy_name, system = combo
    complete = make_api_completer(
        provider, model_id, system, anthropic_client, oai_clients)
    turns = run_subject_conversation(complete, scenario["turns"])
    # Deterministic checker: the headline metric, run on EVERY conversation.
    checker = check_conversation(scenario, turns)
    # LLM judge: audit-only, on a deterministic sample of scenarios.
    judge = None
    if judge_is_selected(scenario["id"], judge_fraction):
        judge = judge_conversation(anthropic_client, turns, scenario)
    return {
        "model": f"{provider}:{model_id}",
        "strategy": strategy_name,
        "scenario_id": scenario["id"],
        "category": scenario.get("category", "clean"),
        "turns": turns,
        "checker": checker,
        "judge": judge,
    }


def aggregate(records: list[dict]) -> list[dict]:
    """Per model x strategy, from the DETERMINISTIC CHECKER (headline):
    spec_adherence = strict first-pass rate over all scenarios; robustness =
    the same over adversarial-category scenarios; mean violations/100 words;
    violation-type counts (top-3, "must"-softened, anchor breaks). The LLM
    judge contributes only the audit columns (n_judged / judge pass rate)."""
    rows = {}
    for r in records:
        key = (r["model"], r["strategy"])
        row = rows.setdefault(
            key, {"model": r["model"], "strategy": r["strategy"],
                  "n": 0, "n_pass": 0, "n_adv": 0, "n_adv_pass": 0,
                  "_v100": [], "_by_rule": Counter(), "_advisory": Counter(),
                  "n_judged": 0, "n_judge_pass": 0},
        )
        checker = r["checker"]
        passed = bool(checker["strict_pass"])
        row["n"] += 1
        row["n_pass"] += passed
        if r["category"] == "adversarial":
            row["n_adv"] += 1
            row["n_adv_pass"] += passed
        row["_v100"].append(checker.get("violations_per_100_words", 0.0))
        row["_by_rule"].update(checker.get("by_rule", {}))
        row["_advisory"].update(checker.get("advisory_by_rule", {}))
        judge = r.get("judge")
        if judge is not None:
            row["n_judged"] += 1
            row["n_judge_pass"] += bool(judge.get("conversation_pass"))
    out = []
    for row in rows.values():
        v100 = row.pop("_v100")
        by_rule = row.pop("_by_rule")
        advisory = row.pop("_advisory")
        row["spec_adherence"] = row["n_pass"] / row["n"] if row["n"] else 0.0
        row["robustness"] = (
            row["n_adv_pass"] / row["n_adv"] if row["n_adv"] else None
        )
        row["mean_violations_per_100_words"] = (
            round(sum(v100) / len(v100), 2) if v100 else 0.0
        )
        # Checker v1.1: rule g (softened_modal) is ADVISORY — it reports via
        # advisory_by_rule and never fails a turn. Older records that carried
        # it in by_rule are still counted.
        row["softened_modal_count"] = (
            advisory.get("softened_modal", 0) + by_rule.get("softened_modal", 0)
        )
        row["anchor_break_count"] = (
            by_rule.get("paraphrased_anchor", 0)
            + by_rule.get("missing_operative_deadline", 0)
        )
        top = sorted(by_rule.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        row["top_violations"] = "; ".join(f"{k}:{v}" for k, v in top) or "none"
        row["judge_pass_rate"] = (
            row["n_judge_pass"] / row["n_judged"] if row["n_judged"] else None
        )
        out.append(row)
    out.sort(key=lambda r: (r["model"], r["strategy"]))
    return out


CSV_FIELDS = [
    "model", "strategy", "n", "n_pass", "spec_adherence",
    "n_adv", "n_adv_pass", "robustness",
    "mean_violations_per_100_words", "softened_modal_count",
    "anchor_break_count", "top_violations", "n_judged", "n_judge_pass",
    "judge_pass_rate",
]

MD_HEADER = (
    "| Model | Strategy | N | Strict pass (checker) | Robustness (adversarial) "
    "| Viol/100w | \"Must\" softened | Anchor breaks | Top violation types "
    "| Judge audit |"
)


def summary_md_lines(summary: list[dict]) -> list[str]:
    lines = [MD_HEADER, "|" + " --- |" * 10]
    for row in summary:
        rob = f"{row['robustness']:.0%}" if row["robustness"] is not None else "n/a"
        audit = (
            f"{row['n_judge_pass']}/{row['n_judged']} pass"
            if row["n_judged"] else "n/a"
        )
        lines.append(
            f"| {row['model']} | {row['strategy']} | {row['n']} "
            f"| {row['spec_adherence']:.0%} | {rob} "
            f"| {row['mean_violations_per_100_words']:.2f} "
            f"| {row['softened_modal_count']} | {row['anchor_break_count']} "
            f"| {row['top_violations']} | {audit} |"
        )
    return lines


def write_outputs(out_dir: Path, records: list[dict], summary: list[dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Full transcripts: per-turn checker series (checker.turns) stays in each
    # record for the compliance-by-turn-index drift chart.
    with (out_dir / "transcripts.jsonl").open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Raw judge verdicts for the audited subset.
    with (out_dir / "judge_verdicts.jsonl").open("w", encoding="utf-8") as f:
        for r in records:
            if r.get("judge") is not None:
                f.write(json.dumps(
                    {"model": r["model"], "strategy": r["strategy"],
                     "scenario_id": r["scenario_id"], "judge": r["judge"]},
                    ensure_ascii=False) + "\n")

    with (out_dir / "results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in summary:
            writer.writerow({k: row.get(k) for k in writer.fieldnames})

    (out_dir / "results.md").write_text(
        "\n".join(summary_md_lines(summary)) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--strategies", nargs="+", default=list(STRATEGIES))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--judge-sample", type=float, default=0.25,
        help="Fraction of scenarios audited by the LLM judge (deterministic "
             "by scenario id hash; the checker always runs on everything).")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        # SDK may still resolve an `ant auth` profile; warn, don't fail.
        log("note: ANTHROPIC_API_KEY not set; relying on ambient credentials")

    providers = {m.split(":", 1)[0] for m in args.models} - {"claude"}
    oai_clients = {}
    for provider in sorted(providers):
        if provider not in PROVIDER_ENV:
            log(f"ERROR: unknown provider '{provider}'")
            return 2
        env_var, base_url = PROVIDER_ENV[provider]
        key = os.environ.get(env_var)
        if not key:
            log(f"ERROR: {env_var} not set but a {provider}: model was requested")
            return 2
        oai_clients[provider] = OpenAI(api_key=key, base_url=base_url)
        if provider in PROVIDER_MAX_CONCURRENCY:
            THROTTLES[provider] = threading.Semaphore(PROVIDER_MAX_CONCURRENCY[provider])

    anthropic_client = anthropic.Anthropic()

    scenarios = load_scenarios(args.scenarios)
    if args.limit:
        scenarios = scenarios[: args.limit]
    if len(scenarios) < 30 and not args.limit:
        log(f"WARNING: only {len(scenarios)} scenarios; the brief requires >= 30")

    combos = []
    for m in args.models:
        provider, model_id = m.split(":", 1)
        for strat in args.strategies:
            combos.append((provider, model_id, strat, STRATEGIES[strat]()))

    total = len(combos) * len(scenarios)
    log(f"Running {len(combos)} combos x {len(scenarios)} scenarios = {total} conversations")

    records, errors = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(run_one, combo, sc, anthropic_client, oai_clients,
                        args.judge_sample):
                (combo[0] + ":" + combo[1], combo[2], sc["id"])
            for combo in combos for sc in scenarios
        }
        done = 0
        for fut in as_completed(futures):
            model, strat, sid = futures[fut]
            done += 1
            try:
                records.append(fut.result())
                log(f"[{done}/{total}] ok  {model} {strat} {sid}")
            except Exception:
                errors.append((model, strat, sid, traceback.format_exc()))
                log(f"[{done}/{total}] ERR {model} {strat} {sid}")

    summary = aggregate(records)
    write_outputs(args.out, records, summary)

    log("\n" + (args.out / "results.md").read_text(encoding="utf-8"))
    if errors:
        log(f"\n{len(errors)} conversations failed:")
        for model, strat, sid, tb in errors[:5]:
            log(f"--- {model} {strat} {sid}\n{tb.splitlines()[-1]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
