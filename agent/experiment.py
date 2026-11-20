"""RQ3 live-pipeline experiment driver.

Runs a task set through the proxy under each detector condition, for several
trials, scores every run with the deterministic judge, and writes the results
table the experiment reports:

    condition x {attack-success rate, task-success rate, false-block rate, latency}

Flow per run:  agent  -->  proxy (detector inside)  -->  inert mock server
Each run gets a unique run_id so the server call log (what the agent actually
did) and the proxy decision log (what the detector allowed/blocked) can be found
and scored afterwards. The agent call spends LLM quota, so the live run is a
separate, opt-in step; the driver's loop/judge/aggregate logic is exercised
offline by injecting a fake ``runner`` (see tests/test_experiment.py).

    python -m agent.experiment --tasks configs/exp3/tasks.yaml --trials 10 \
        --model openai/gpt-oss-120b --out results/rq3

The three conditions differ only in the detector block of their proxy config
(configs/proxy/exp3_{none,mcpguard,guardian}.yaml). A task may name its own
``server_spec`` (a poisoned or clean spec); the driver points every condition at
that spec for the task's runs, so one task set can cover several servers.
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from collections import defaultdict
from pathlib import Path

import yaml

from servers.outcome import judge_log, tool_decisions

REPO = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_CONDITIONS = {
    "none": "configs/proxy/exp3_none.yaml",
    "mcpguard": "configs/proxy/exp3_mcpguard.yaml",
    "guardian": "configs/proxy/exp3_guardian.yaml",
}


# --- locating this run's logs -------------------------------------------------

def _safe(s: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in str(s))


def run_id_for(task_id: str, condition: str, trial: int) -> str:
    return _safe(f"{task_id}__{condition}__t{trial}")


def decisions_path_for(condition_config: str | Path, upstream_name: str, run_id: str) -> Path:
    """Where the proxy writes its allow/block decisions for this run.

    Mirrors proxy.decision_log: ``<log_dir>/<run_id>.<upstream>.decisions.jsonl``.
    ``upstream_name`` is the resolved name from ``_config_for_task`` so it matches
    whatever the proxy actually used (the spec's name when the task overrides it)."""
    cfg = yaml.safe_load(Path(condition_config).read_text(encoding="utf-8"))
    log_dir = cfg.get("log_dir", "results/proxy_logs")
    return Path(log_dir) / f"{run_id}.{upstream_name}.decisions.jsonl"


def _config_for_task(base_config: str | Path, server_spec: str | None) -> tuple[str | Path, str]:
    """Return ``(config_path, upstream_name)``. If the task names a server_spec, write a
    temp condition config whose upstream serves that spec AND whose ``upstream.name``
    is set to the spec's own name -- so the server call log, the proxy decision log, and
    the path ``run_task`` returns all agree on the name. The detector block and log_dir
    are untouched, so the condition (none/mcpguard/guardian) is preserved exactly."""
    cfg = yaml.safe_load(Path(base_config).read_text(encoding="utf-8"))
    if not server_spec:
        return base_config, cfg.get("upstream", {}).get("name", "upstream")
    spec_name = yaml.safe_load(Path(server_spec).read_text(encoding="utf-8")).get("name", "upstream")
    up = cfg.setdefault("upstream", {})
    args = list(up.get("args", []))
    if "--spec" in args:
        args[args.index("--spec") + 1] = server_spec
    else:
        args += ["--spec", server_spec]
    up["args"] = args
    up["name"] = spec_name  # keep the config name == the spec name the server logs under
    tmp = Path(tempfile.mkdtemp(prefix="exp3-cond-")) / "cond.yaml"
    tmp.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return tmp, spec_name


# --- scoring one run ----------------------------------------------------------

def score_run(task: dict, call_log_path: str | Path, decisions_path: str | Path,
              latency_ms: float, run_id: str, condition: str, trial: int) -> dict:
    """Turn one run's two logs into a scored record (no LLM, pure data rules)."""
    outcome = judge_log(call_log_path, task)  # task_success, attack_success, n_calls
    decisions = tool_decisions(decisions_path)
    blocked = sorted(t for t, d in decisions.items() if d == "blocked")
    clean = task.get("clean_tools") or []
    # a false block = a benign tool the task needs that the detector dropped
    false_blocked = sorted(set(blocked) & set(clean))
    return {
        "task_id": task.get("task_id"),
        "condition": condition,
        "trial": trial,
        "run_id": run_id,
        "paradigm": task.get("paradigm"),
        "task_success": outcome["task_success"],
        "attack_success": outcome["attack_success"],
        "n_calls": outcome["n_calls"],
        "tools_blocked": blocked,
        "false_blocked": false_blocked,
        "false_block": bool(false_blocked),
        "latency_ms": round(latency_ms, 1),
    }


# --- running the suite --------------------------------------------------------

async def run_one(task: dict, condition: str, condition_config: str | Path, trial: int,
                  model: str, runner) -> dict:
    """Run one (task, condition, trial) and score it. ``runner`` is the async agent
    entry point (agent.runner.run_task by default); injected in tests."""
    rid = run_id_for(task["task_id"], condition, trial)
    cfg, upstream_name = _config_for_task(condition_config, task.get("server_spec"))
    t0 = time.perf_counter()
    result = await runner(cfg, rid, task["prompt"], model=model)
    latency_ms = (time.perf_counter() - t0) * 1000
    return score_run(task, result["call_log"], decisions_path_for(condition_config, upstream_name, rid),
                     latency_ms, rid, condition, trial)


def run_key(rec: dict) -> tuple:
    return (rec["task_id"], rec["condition"], rec["trial"])


def _is_quota(exc: Exception) -> bool:
    """A Groq daily/rate limit (vs an ordinary per-run failure)."""
    s = str(exc).lower()
    return any(t in s for t in ("rate limit", "rate_limit", "429", "too many requests",
                                "per day", "rpd", "quota", "insufficient"))


async def run_suite(tasks: list[dict], conditions: dict, trials: int, model: str,
                    runner=None, done: set | None = None, on_record=None) -> list[dict]:
    """Every task x condition x trial not already in ``done``, scored. Calls ``on_record``
    for each new record (for incremental writing). Stops cleanly on a Groq rate/daily
    limit so a rerun resumes; records other per-run failures and continues."""
    if runner is None:
        from agent.runner import run_task  # lazy: keeps the driver importable without mcp/langgraph
        runner = run_task
    done = done or set()
    records = []
    for task in tasks:
        for condition, cfg in conditions.items():
            for trial in range(1, trials + 1):
                if (task["task_id"], condition, trial) in done:
                    continue
                try:
                    rec = await run_one(task, condition, cfg, trial, model, runner)
                except Exception as e:
                    if _is_quota(e):  # clean, resumable halt -- do not burn the rest as errors
                        print(f"stopped on a rate/daily limit after {len(records)} new runs: {str(e)[:120]}")
                        return records
                    rec = {  # ordinary failure: record it and keep going
                        "task_id": task.get("task_id"), "condition": condition, "trial": trial,
                        "run_id": run_id_for(task["task_id"], condition, trial),
                        "paradigm": task.get("paradigm"), "error": str(e)[:300],
                        "task_success": False, "attack_success": False, "n_calls": 0,
                        "tools_blocked": [], "false_blocked": [], "false_block": False,
                        "latency_ms": None,
                    }
                records.append(rec)
                if on_record is not None:
                    on_record(rec)
    return records


# --- aggregation + output -----------------------------------------------------

def aggregate(records: list[dict]) -> list[dict]:
    """Per-condition rates: attack-success, task-success, false-block, mean latency."""
    by_cond: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_cond[r["condition"]].append(r)
    rows = []
    for cond, rs in by_cond.items():
        ok = [r for r in rs if not r.get("error")]  # rates are over runs that actually completed
        n = len(ok)
        lat = [r["latency_ms"] for r in ok if r.get("latency_ms") is not None]
        rows.append({
            "condition": cond,
            "runs": len(rs),
            "errors": len(rs) - n,
            "attack_success_rate": (sum(r["attack_success"] for r in ok) / n) if n else 0.0,
            "task_success_rate": (sum(r["task_success"] for r in ok) / n) if n else 0.0,
            "false_block_rate": (sum(r["false_block"] for r in ok) / n) if n else 0.0,
            "mean_latency_ms": round(statistics.mean(lat), 1) if lat else 0.0,
        })
    order = {"none": 0, "mcpguard": 1, "guardian": 2}
    rows.sort(key=lambda r: order.get(r["condition"], 99))
    return rows


def write_results(records: list[dict], summary: list[dict], out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "per_run.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    cols = ["condition", "runs", "errors", "attack_success_rate", "task_success_rate",
            "false_block_rate", "mean_latency_ms"]
    lines = [",".join(cols)]
    md = ["| condition | runs | errors | attack-success | task-success | false-block | latency (ms) |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for s in summary:
        lines.append(",".join(str(s[c]) for c in cols))
        md.append(f"| {s['condition']} | {s['runs']} | {s.get('errors', 0)} | {s['attack_success_rate']:.1%} | "
                  f"{s['task_success_rate']:.1%} | {s['false_block_rate']:.1%} | {s['mean_latency_ms']:.0f} |")
    (out / "summary.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "SUMMARY.md").write_text("# RQ3 live-pipeline results\n\n" + "\n".join(md) + "\n", encoding="utf-8")


def load_tasks(path: str | Path) -> list[dict]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return data["tasks"] if isinstance(data, dict) else data


def read_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.is_file():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def latest_by_key(records: list[dict]) -> list[dict]:
    """Dedupe per (task, condition, trial), last record wins (a resumed success
    supersedes an earlier error line for the same run)."""
    by = {run_key(r): r for r in records}
    return list(by.values())


def main() -> None:
    import anyio

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks", required=True, help="task set YAML (see experiments/rq3_live/README.md)")
    ap.add_argument("--trials", type=int, default=10, help="trials per (task, condition)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="agent LLM")
    ap.add_argument("--out", default="results/rq3", help="output directory")
    ap.add_argument("--conditions", nargs="+", default=None,
                    help="subset of conditions to run (default: none mcpguard guardian)")
    args = ap.parse_args()

    conds = DEFAULT_CONDITIONS if not args.conditions else {
        c: DEFAULT_CONDITIONS[c] for c in args.conditions}
    tasks = load_tasks(args.tasks)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    per_run = out / "per_run.jsonl"
    done = {run_key(r) for r in read_jsonl(per_run) if not r.get("error")}  # resume: skip completed runs
    if done:
        print(f"resuming: {len(done)} runs already recorded")

    with per_run.open("a", encoding="utf-8") as f:
        def on_record(rec):
            f.write(json.dumps(rec) + "\n")
            f.flush()
        new = anyio.run(lambda: run_suite(tasks, conds, args.trials, args.model,
                                          done=done, on_record=on_record))

    all_records = latest_by_key(read_jsonl(per_run))  # existing + new, deduped
    summary = aggregate(all_records)
    write_results(all_records, summary, out)  # rewrites per_run deduped + summary files
    total = len(tasks) * len(conds) * args.trials
    print(f"recorded {len(all_records)}/{total} runs ({len(new)} new this pass)")
    for s in summary:
        print(f"  {s['condition']:9s} attack={s['attack_success_rate']:.0%} "
              f"task={s['task_success_rate']:.0%} false-block={s['false_block_rate']:.0%} "
              f"latency={s['mean_latency_ms']:.0f}ms errors={s.get('errors', 0)}")
    print(f"wrote {out}/summary.{{csv,json}}, SUMMARY.md, per_run.jsonl")


if __name__ == "__main__":
    main()
