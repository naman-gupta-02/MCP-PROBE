"""Experiment 2 runner: drive the rewrite loop over caught seeds and write the results JSONL.

  uv run python -m attacker.run --split val --ckpt-root <dir with seed-0 checkpoints> \
      --detectors e5base_full mcp_guardian --attackers llama-3.3-70b-versatile \
      --feedback-modes verdict_score blocked_only --cap 10 --out results/attacker/val.jsonl

This is orchestration only: for each detector it finds the caught seeds (blocked at attempt 0),
then for each (caught case x attacker x feedback mode) it retries the team's rewrite step up to the
cap, scoring each candidate with the real detector, and records one line per trajectory. Feedback
is a raw passthrough of the detector's own outputs. The rewrite prompt is loaded from a file (see
rewrite.PromptedAttacker); nothing here contains rewrite guidance.

Results files hold poisoned and rewritten descriptions, so they stay under results/ (gitignored).
Progress is written incrementally and the run resumes: rerun the same command to continue, and it
skips trajectories already in --out. It stops cleanly when a Groq daily limit is hit.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from data.loader import load_cases
from .detectors import DETECTORS, build
from .llm import ChatClient, DailyLimitReached
from .rewrite import PromptedAttacker, RewriteTask

ROOT = Path(__file__).resolve().parents[1]


class _StopRun(Exception):
    """Internal: stop early once --max-trajectories is reached."""


def build_feedback(check, mode: str) -> dict:
    """Raw passthrough of the detector's outputs; no coaching added."""
    if check is None:
        return {}
    if mode == "blocked_only":
        return {"blocked": check.blocked}
    return {"blocked": check.blocked, "stage": check.stage, "score": check.score, "rules": check.rules}


def run_trajectory(task: RewriteTask, detector, attacker, cap: int, feedback_mode: str) -> dict:
    """Retry the rewrite up to `cap` times; stop as soon as the detector passes a candidate."""
    attempts: list[dict] = []
    current = task.original_description
    last_check = None
    evaded = False
    final = None
    for n in range(1, cap + 1):
        feedback = build_feedback(last_check, feedback_mode) if last_check is not None else {}
        produced = [a["description"] for a in attempts if a.get("description")]
        try:
            cand = attacker.rewrite(task, current, n, feedback, produced)  # may raise DailyLimitReached
        except RuntimeError as e:  # client gave up (e.g. persistent rate limit); don't kill the run
            attempts.append({"n": n, "description": None, "error": f"client_error: {str(e)[:120]}"})
            break
        if not cand:
            attempts.append({"n": n, "description": None, "error": "no_candidate"})
            continue
        chk = detector.check(task.tool_name, cand)
        attempts.append({"n": n, "description": cand, "blocked": chk.blocked,
                         "stage": chk.stage, "score": chk.score, "rules": chk.rules})
        final = cand
        if not chk.blocked:
            evaded = True
            break
        current, last_check = cand, chk
    return {"attempts": attempts, "evaded": evaded,
            "n_attempts": sum(1 for a in attempts if a.get("description")),
            "final_description": final}


def record_key(rec: dict) -> tuple:
    return (rec["case_id"], rec["detector"], rec["attacker_model"], rec["feedback_mode"])


def done_keys(path: Path) -> set:
    if not path.is_file():
        return set()
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.add(record_key(json.loads(line)))
    return out


def stratified(cases: list[dict], n: int, seed: int) -> list[dict]:
    """Balance a sample across (paradigm, risk_category) buckets."""
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for c in cases:
        buckets[(c.get("paradigm"), c.get("risk_category"))].append(c)
    rng = random.Random(seed)
    for b in buckets.values():
        rng.shuffle(b)
    picked, i = [], 0
    keys = sorted(buckets, key=lambda k: str(k))
    while len(picked) < n and any(buckets.values()):
        b = buckets[keys[i % len(keys)]]
        if b:
            picked.append(b.pop())
        i += 1
    return picked[:n]


def seeds_for(split: str, sample: int | None, seed: int) -> list[dict]:
    rows = [r for r in load_cases(split, None) if r["is_poisoned"] and (r["description"] or "").strip()]
    if sample:
        rows = stratified(rows, sample, seed)
    return rows


def task_for(row: dict, length_target: int | None, length_tolerance: int | None) -> RewriteTask:
    return RewriteTask(
        case_id=row["case_id"], tool_name=row["tool_name"] or "",
        original_description=row["description"],
        tool_context=f"server: {row['server']}; risk_category: {row['risk_category']}; attack_type: {row['paradigm']}",
        length_target=length_target, length_tolerance=length_tolerance,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", default="val", choices=["val", "test"])
    ap.add_argument("--detectors", nargs="+", default=list(DETECTORS), choices=list(DETECTORS))
    ap.add_argument("--attackers", nargs="+", required=True, help="Groq model ids")
    ap.add_argument("--feedback-modes", nargs="+", default=["verdict_score"], choices=["verdict_score", "blocked_only"])
    ap.add_argument("--cap", type=int, default=10, help="max rewrite attempts per trajectory")
    ap.add_argument("--ckpt-root", help="folder with the seed-0 checkpoints (needed for MCP-Guard variants)")
    ap.add_argument("--prompt-path", default=str(ROOT / "attacker" / "rewrite_prompt.txt"))
    ap.add_argument("--out", default="results/attacker/run.jsonl")
    ap.add_argument("--sample", type=int, help="stratified subset size (default: all caught seeds)")
    ap.add_argument("--max-trajectories", type=int, help="stop after this many trajectories (for smoke tests)")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--length-target", type=int)
    ap.add_argument("--length-tolerance", type=int)
    ap.add_argument("--json-mode", action="store_true", help="ask Groq for response_format=json_object")
    ap.add_argument("--reasoning-effort", default="low", help="gpt-oss/qwen reasoning budget; 'default' to omit")
    ap.add_argument("--temperature", type=float, default=0.9)
    ap.add_argument("--max-tokens", type=int, default=900, help="attacker completion cap (room for low reasoning + the description)")
    ap.add_argument("--rpm", type=int, default=25, help="per-key requests/min budget (free plan ~30)")
    ap.add_argument("--tpm", type=int, default=7000, help="per-key tokens/min budget (free plan ~8000)")
    ap.add_argument("--base-url", default="https://api.groq.com/openai/v1")
    args = ap.parse_args()

    seeds = seeds_for(args.split, args.sample, args.seed)
    print(f"{len(seeds)} poisoned seeds on {args.split}")

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    done = done_keys(out)
    if done:
        print(f"resuming: {len(done)} trajectories already recorded")

    # Caught set per detector (blocked at attempt 0). Scoring only; no LLM calls, no description text logged.
    caught: dict[str, list[dict]] = {}
    for dk in args.detectors:
        det = build(dk, args.ckpt_root)
        hits = [row for row in seeds if det.check(row["tool_name"], row["description"]).blocked]
        caught[dk] = hits
        print(f"  {DETECTORS[dk][0]}: caught {len(hits)}/{len(seeds)} at attempt 0")
        del det  # free the model before the next one
    (out.parent / "caught_sets.json").write_text(json.dumps(
        {dk: [r["case_id"] for r in rows] for dk, rows in caught.items()}, indent=2), encoding="utf-8")

    extra = {}
    if args.json_mode:
        extra["response_format"] = {"type": "json_object"}
    if args.reasoning_effort != "default":
        extra["reasoning_effort"] = args.reasoning_effort
    attackers = {m: PromptedAttacker(
        ChatClient(m, base_url=args.base_url, rpm=args.rpm, tpm=args.tpm, extra_body=extra or None),
        prompt_path=args.prompt_path, temperature=args.temperature, max_tokens=args.max_tokens)
        for m in args.attackers}

    written = 0
    try:
        with out.open("a", encoding="utf-8") as f:
            for dk in args.detectors:
                det = build(dk, args.ckpt_root)
                for row in caught[dk]:
                    task = task_for(row, args.length_target, args.length_tolerance)
                    for model, attacker in attackers.items():
                        for mode in args.feedback_modes:
                            base = {"case_id": row["case_id"], "detector": dk, "attacker_model": model,
                                    "feedback_mode": mode, "paradigm": row["paradigm"],
                                    "risk_category": row["risk_category"], "split": args.split,
                                    "original_description": row["description"], "caught_by_detector": True}
                            if record_key(base) in done:
                                continue
                            traj = run_trajectory(task, det, attacker, args.cap, mode)
                            f.write(json.dumps({**base, **traj}) + "\n")
                            f.flush()
                            written += 1
                            if args.max_trajectories and written >= args.max_trajectories:
                                del det
                                raise _StopRun
                del det
    except _StopRun:
        print(f"reached --max-trajectories ({args.max_trajectories})")
    except DailyLimitReached as e:
        print(f"\nstopped on a Groq daily limit after writing {written} new trajectories: {e}")
        print("rerun the same command tomorrow (or with another key) to resume.")
        return
    print(f"\ndone: wrote {written} new trajectories to {out}")
    print("next: run attacker.judge then attacker.metrics over this file.")


if __name__ == "__main__":
    main()
