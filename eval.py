"""Standalone evaluator: regenerate the full results table from nothing.

    python eval.py --model <subject> --eval-set <path-to-scenarios.jsonl>

is the brief's verification requirement: given a model and an eval set (same
JSONL schema as data/ablation/scenarios.jsonl), it runs every scenario,
scores every conversation with the DETERMINISTIC CHECKER (headline metric,
first-pass only, no regeneration), audits a sampled fraction with the LLM
judge, and emits the same output files as the ablation runner:

  transcripts.jsonl / judge_verdicts.jsonl / results.csv / results.md

Subject model specs (--model / --baseline):
  hf:<repo-id-or-local-path>   loaded via transformers; greedy decoding,
                               max_new_tokens=1024, chat template, with the
                               behavior spec (src/ablation/prompts/
                               behavior_spec.md) as the system message
  claude:<model-id>            Anthropic API (ANTHROPIC_API_KEY)
  google:<model-id>            Gemini OpenAI-compatible API (GEMINI_API_KEY)
  openrouter:<model-id>        OpenRouter (OPENROUTER_API_KEY)
  openai:<model-id>            OpenAI (OPENAI_API_KEY)

--baseline runs a second model over the same eval set and appends a
side-by-side base-vs-tuned table to results.md (M3's mechanism).

Examples:
  python eval.py --model hf:./checkpoints/tuned --eval-set data/ablation/scenarios.jsonl
  python eval.py --model hf:org/tuned-repo --baseline hf:org/base-repo \
      --eval-set data/ablation/scenarios.jsonl --out evidence/2026-08-20/m3
"""

import argparse
import json
import os
import sys
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from src.ablation.checker_bridge import check_conversation  # noqa: E402
from src.ablation.judge import judge_conversation  # noqa: E402
from src.ablation.run_ablation import (  # noqa: E402
    PROVIDER_ENV,
    PROVIDER_MAX_CONCURRENCY,
    THROTTLES,
    aggregate,
    judge_is_selected,
    load_scenarios,
    log,
    make_api_completer,
    run_subject_conversation,
    write_outputs,
)
from src.ablation.strategies import STRATEGIES  # noqa: E402

HF_MAX_NEW_TOKENS = 1024


def make_hf_completer(model_path: str, system: str):
    """complete(turns) -> reply for a local/HF transformers model.

    Greedy decoding, max_new_tokens=1024, chat template with the behavior
    spec as the system message. Loaded lazily so API-only runs never need
    torch installed.
    """
    try:
        import torch  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:
        raise SystemExit(
            f"ERROR: 'hf:{model_path}' needs torch + transformers, which are "
            f"not importable here ({e}). Install them (pip install torch "
            "transformers) or use a claude:/google:/openrouter: subject."
        )
    log(f"[hf] loading {model_path} ...")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(
        model_path, torch_dtype="auto", device_map="auto")
    model.eval()
    log(f"[hf] loaded {model_path} on {model.device}")
    lock = threading.Lock()  # one generation at a time on the device

    def complete(turns: list[dict]) -> str:
        messages = [{"role": "system", "content": system}] + [
            {"role": t["role"], "content": t["content"]} for t in turns
        ]
        with lock, torch.no_grad():
            enc = tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, return_tensors="pt")
            # transformers >=4.58 returns a BatchEncoding here; older returns
            # a bare tensor. Handle both.
            input_ids = (enc if torch.is_tensor(enc) else enc["input_ids"])
            input_ids = input_ids.to(model.device)
            out = model.generate(
                input_ids,
                max_new_tokens=HF_MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )
        return tokenizer.decode(
            out[0][input_ids.shape[-1]:], skip_special_tokens=True).strip()

    return complete


def parse_subject(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise SystemExit(
            f"ERROR: bad --model '{spec}': expected <provider>:<id> with "
            "provider one of hf, claude, google, openrouter, openai.")
    provider, ident = spec.split(":", 1)
    if provider not in ("hf", "claude") and provider not in PROVIDER_ENV:
        raise SystemExit(f"ERROR: unknown provider '{provider}' in '{spec}'")
    return provider, ident


def build_completer(spec: str, system: str, anthropic_client, oai_clients):
    provider, ident = parse_subject(spec)
    if provider == "hf":
        return make_hf_completer(ident, system)
    return make_api_completer(provider, ident, system, anthropic_client, oai_clients)


def run_model(
    spec: str, strategy_name: str, system: str, scenarios: list[dict],
    anthropic_client, oai_clients, judge_fraction: float, workers: int,
) -> tuple[list[dict], list[tuple]]:
    """Run one subject over every scenario. Checker always; judge sampled."""
    complete = build_completer(spec, system, anthropic_client, oai_clients)
    if spec.startswith("hf:"):
        workers = 1  # sequential generation on one device

    def one(scenario: dict) -> dict:
        turns = run_subject_conversation(complete, scenario["turns"])
        checker = check_conversation(scenario, turns)
        judge = None
        if judge_is_selected(scenario["id"], judge_fraction):
            judge = judge_conversation(anthropic_client, turns, scenario)
        return {
            "model": spec,
            "strategy": strategy_name,
            "scenario_id": scenario["id"],
            "category": scenario.get("category", "clean"),
            "turns": turns,
            "checker": checker,
            "judge": judge,
        }

    records, errors = [], []
    total = len(scenarios)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, sc): sc["id"] for sc in scenarios}
        for done, fut in enumerate(as_completed(futures), 1):
            sid = futures[fut]
            try:
                records.append(fut.result())
                log(f"[{done}/{total}] ok  {spec} {sid}")
            except Exception:
                errors.append((spec, strategy_name, sid, traceback.format_exc()))
                log(f"[{done}/{total}] ERR {spec} {sid}")
    return records, errors


def side_by_side_md(summary: list[dict], base: str, tuned: str) -> str:
    rows = {r["model"]: r for r in summary}
    b, t = rows.get(base), rows.get(tuned)
    if not b or not t:
        return ""

    def fmt(row, key, pct=False):
        val = row.get(key)
        if val is None:
            return "n/a"
        return f"{val:.0%}" if pct else f"{val}"

    lines = [
        "",
        "## Base vs tuned",
        "",
        f"| Metric | base: {base} | tuned: {tuned} |",
        "| --- | --- | --- |",
        f"| Strict pass (checker) | {fmt(b, 'spec_adherence', pct=True)} "
        f"| {fmt(t, 'spec_adherence', pct=True)} |",
        f"| Robustness (adversarial) | {fmt(b, 'robustness', pct=True)} "
        f"| {fmt(t, 'robustness', pct=True)} |",
        f"| Viol/100w | {b['mean_violations_per_100_words']:.2f} "
        f"| {t['mean_violations_per_100_words']:.2f} |",
        f"| \"Must\" softened | {b['softened_modal_count']} "
        f"| {t['softened_modal_count']} |",
        f"| Anchor breaks | {b['anchor_break_count']} "
        f"| {t['anchor_break_count']} |",
        f"| Top violation types | {b['top_violations']} | {t['top_violations']} |",
        f"| Judge audit | {b['n_judge_pass']}/{b['n_judged']} pass "
        f"| {t['n_judge_pass']}/{t['n_judged']} pass |",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate the results table for a subject model over an "
                    "eval set (deterministic checker headline + judge audit).")
    parser.add_argument("--model", required=True,
                        help="Subject: hf:<repo-or-path> | claude:<id> | "
                             "google:<id> | openrouter:<id> | openai:<id>")
    parser.add_argument("--eval-set", required=True, type=Path,
                        help="Scenario JSONL (schema: data/ablation/SCENARIOS.md)")
    parser.add_argument("--baseline", default=None,
                        help="Optional second subject for a side-by-side "
                             "base-vs-tuned table (same spec formats)")
    parser.add_argument("--out", type=Path,
                        default=Path("evidence") / date.today().isoformat() / "eval")
    parser.add_argument("--strategy", default="zero_shot", choices=list(STRATEGIES),
                        help="System-prompt strategy (default: zero_shot = the "
                             "behavior spec verbatim)")
    parser.add_argument("--judge-sample", type=float, default=0.25,
                        help="LLM-judge audit fraction (deterministic by "
                             "scenario id hash; checker always runs)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    specs = [args.model] + ([args.baseline] if args.baseline else [])
    providers = {parse_subject(s)[0] for s in specs}

    # API clients for whichever providers the subjects (and judge) need.
    oai_clients = {}
    for provider in sorted(providers - {"hf", "claude"}):
        env_var, base_url = PROVIDER_ENV[provider]
        key = os.environ.get(env_var)
        if not key:
            log(f"ERROR: {env_var} not set but a {provider}: model was requested")
            return 2
        import openai
        oai_clients[provider] = openai.OpenAI(api_key=key, base_url=base_url)
        if provider in PROVIDER_MAX_CONCURRENCY:
            THROTTLES.setdefault(
                provider, threading.Semaphore(PROVIDER_MAX_CONCURRENCY[provider]))

    anthropic_client = None
    if "claude" in providers or args.judge_sample > 0:
        import anthropic
        if not os.environ.get("ANTHROPIC_API_KEY"):
            log("note: ANTHROPIC_API_KEY not set; relying on ambient credentials")
        anthropic_client = anthropic.Anthropic()

    scenarios = load_scenarios(args.eval_set)
    if args.limit:
        scenarios = scenarios[: args.limit]

    system = STRATEGIES[args.strategy]()
    log(f"Eval set: {len(scenarios)} scenarios | strategy: {args.strategy} | "
        f"judge sample: {args.judge_sample:.0%}")

    records, errors = [], []
    # Baseline first so "base" rows sort as run order in the transcripts.
    for spec in ([args.baseline] if args.baseline else []) + [args.model]:
        recs, errs = run_model(
            spec, args.strategy, system, scenarios,
            anthropic_client, oai_clients, args.judge_sample, args.workers)
        records += recs
        errors += errs

    summary = aggregate(records)
    write_outputs(args.out, records, summary)

    if args.baseline:
        extra = side_by_side_md(summary, args.baseline, args.model)
        if extra:
            results_md = args.out / "results.md"
            results_md.write_text(
                results_md.read_text(encoding="utf-8") + extra, encoding="utf-8")

    log("\n" + (args.out / "results.md").read_text(encoding="utf-8"))
    if errors:
        log(f"\n{len(errors)} conversations failed:")
        for spec, strat, sid, tb in errors[:3]:
            tail = "\n".join(tb.splitlines()[-10:])
            log(f"--- {spec} {strat} {sid}\n{tail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
