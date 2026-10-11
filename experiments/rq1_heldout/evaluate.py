"""RQ1 (generalization): score all six detectors on the held-out MCPTox risk categories.

Detectors (existing implementations and checkpoints only; nothing is trained or tuned here):
  frozen_mcpguard   GenTelLab Stage II as released (HF GenTelLab/MCP-Guard, BERT tokenizer)
  mcpguard_full     MCP-Guard weights, all layers fine-tuned on tune      (5 seeds)
  mcpguard_head     MCP-Guard weights, head-only fine-tune                (5 seeds)
  e5base_full       intfloat/multilingual-e5-base + head, full fine-tune  (5 seeds)
  e5base_head       intfloat/multilingual-e5-base + head, head-only       (5 seeds)
  mcp_guardian      MCP Guardian WAF, the paper's 11 rules (fingerprint recorded)

MCP-Guard variants run in two configs: s1-s2 (Stage I regex + Stage II, paper mode,
T_u from configs/mcp_guard.yaml) and s2 (Stage II alone, same T_u). Stage III is not run.

Splits
  heldout  test rows whose risk category is in server_split.json's held_out_categories,
           plus the 64 clean test tools. Needs FINAL_EVAL=1. The 155 seen-category test
           cases are dropped right after loading and never scored.
  val      dev reference (seen categories, val servers + clean val tools), same code.

  uv run python -m experiments.rq1_heldout.evaluate --split val --ckpt-root <dir>
  FINAL_EVAL=1 uv run python -m experiments.rq1_heldout.evaluate --split heldout --ckpt-root <dir>

Writes results/rq1_heldout/<split>/<model>/<run>/{predictions.jsonl,metrics.json,log.txt}
plus results/rq1_heldout/<split>/{runs.csv,summary.csv,summary.json}.
Predictions hold ids, labels and verdicts only, never description text or match excerpts.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
import traceback
from collections import defaultdict
from pathlib import Path

from data.loader import load_cases
from detectors.mcp_guard.metrics import binary_metrics
from detectors.mcp_guard.pipeline import DEFAULT_CONFIG, ROOT, MCPGuard
from detectors.mcp_guardian.team_split import _to_example
from detectors.mcp_guardian.waf import WafScanner

SPLIT_FILE = ROOT / "data" / "splits" / "server_split.json"
OUT_ROOT = ROOT / "results" / "rq1_heldout"
SEEDS = (0, 1, 2, 3, 4)

MODELS = {  # key -> (display name, fine-tune run prefix or None)
    "frozen_mcpguard": ("Frozen MCP-Guard", None),
    "mcpguard_full": ("MCP-Guard Full", "mcpguard_full"),
    "mcpguard_head": ("MCP-Guard Head-Only", "mcpguard_head"),
    "e5base_full": ("Base E5 Full", "e5base_full"),
    "e5base_head": ("Base E5 Head-Only", "e5base_head"),
    "mcp_guardian": ("MCP-Guardian", None),
}
GUARD_CONFIGS = ("s1-s2", "s2")

# Metrics averaged over seeds in summary.csv / summary.json.
SUMMARY_KEYS = ("combined_accuracy", "cat_accuracy", "acc", "precision", "recall", "f1", "fpr", "fpr_nonempty",
                "combined_correct", "combined_n", "tp", "fp", "fn", "tn")


def held_out_categories() -> list[str]:
    return json.loads(SPLIT_FILE.read_text(encoding="utf-8"))["held_out_categories"]


def load_rows(split: str) -> list[dict]:
    if split == "val":
        return load_cases("val")
    held = set(held_out_categories())
    rows = [r for r in load_cases("test") if not r["is_poisoned"] or r["risk_category"] in held]
    n_pos = sum(r["is_poisoned"] for r in rows)
    assert all(r["risk_category"] in held for r in rows if r["is_poisoned"])
    print(f"heldout: {n_pos} poisoned (categories {sorted(held)}) + {len(rows) - n_pos} clean")
    return rows


# ---- scoring ---------------------------------------------------------------

def score_guard(guard: MCPGuard, rows: list[dict]) -> list[dict]:
    verdicts = guard.scan_many(rows)
    return [{
        "blocked": v.blocked, "stage": v.stage, "s2_score": v.s2_score,
        "rules": sorted({h["detector"] for h in v.s1_hits}),
    } for v in verdicts]


def score_guardian(scanner: WafScanner, rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        res = scanner.scan(_to_example(r).tool)  # same {"name", "description"} input as evaluate_rules
        out.append({"blocked": res.blocked, "stage": "waf", "s2_score": None, "rules": res.rules})
    return out


# ---- metrics ---------------------------------------------------------------

def compute_metrics(rows: list[dict], preds: list[dict]) -> dict:
    """Category rows are poisoned-only, so their accuracy is recall; precision needs the clean tools."""
    y = [bool(r["is_poisoned"]) for r in rows]
    p = [bool(x["blocked"]) for x in preds]
    clean_idx = [i for i, r in enumerate(rows) if not r["is_poisoned"]]
    nonempty_clean = [i for i in clean_idx if (rows[i]["description"] or "").strip()]

    by_cat = defaultdict(list)
    for i, r in enumerate(rows):
        if r["is_poisoned"]:
            by_cat[r["risk_category"]].append(i)

    categories = {}
    for cat, idx in sorted(by_cat.items()):
        correct = sum(p[i] for i in idx)
        with_clean = idx + clean_idx
        categories[cat] = {
            "n": len(idx), "correct": correct, "incorrect": len(idx) - correct,
            "accuracy": correct / len(idx),  # == recall: every row in the category is poisoned
            "confusion": {"tp": correct, "fn": len(idx) - correct, "fp": 0, "tn": 0},
            "precision": None,  # undefined: no clean tools inside a risk category
            # Category's poisoned cases + all clean tools of the split, for precision/F1 per category.
            "with_clean": binary_metrics([y[i] for i in with_clean], [p[i] for i in with_clean]),
        }

    pos_idx = [i for i, r in enumerate(rows) if r["is_poisoned"]]
    n_correct = sum(c["correct"] for c in categories.values())
    n_total = sum(c["n"] for c in categories.values())
    assert n_total == len(pos_idx)
    combined = {
        "n": n_total, "correct": n_correct, "incorrect": n_total - n_correct,
        "accuracy": n_correct / n_total,  # pooled over all categories
        "unweighted_mean_of_categories": statistics.mean(c["accuracy"] for c in categories.values()),
        "confusion": {"tp": n_correct, "fn": n_total - n_correct, "fp": 0, "tn": 0},
    }
    assert abs(combined["accuracy"] - sum(p[i] for i in pos_idx) / len(pos_idx)) < 1e-12

    by_paradigm = defaultdict(list)
    for i in pos_idx:
        by_paradigm[rows[i]["paradigm"]].append(i)

    return {
        "categories": categories,
        "combined_poisoned": combined,
        "with_clean": binary_metrics(y, p),  # all poisoned rows + all clean tools
        "clean": {
            "n": len(clean_idx), "fp": sum(p[i] for i in clean_idx),
            "fpr": sum(p[i] for i in clean_idx) / len(clean_idx) if clean_idx else None,
            "n_nonempty": len(nonempty_clean),
            "fpr_nonempty": (sum(p[i] for i in nonempty_clean) / len(nonempty_clean)) if nonempty_clean else None,
        },
        "by_paradigm_recall": {
            k: {"n": len(v), "correct": sum(p[i] for i in v), "recall": sum(p[i] for i in v) / len(v)}
            for k, v in sorted(by_paradigm.items())
        },
        "decided_at_stage": dict(sorted(_count(x["stage"] for x in preds).items())),
    }


def _count(it) -> dict:
    out: dict = defaultdict(int)
    for x in it:
        out[x] += 1
    return out


def flat(m: dict) -> dict:
    """One CSV row's worth of numbers from compute_metrics output."""
    wc, cp = m["with_clean"], m["combined_poisoned"]
    row = {f"acc[{c}]": v["accuracy"] for c, v in m["categories"].items()}
    row.update({f"n[{c}]": v["n"] for c, v in m["categories"].items()})
    row.update({
        "combined_accuracy": cp["accuracy"], "combined_correct": cp["correct"], "combined_n": cp["n"],
        "cat_accuracy": cp["unweighted_mean_of_categories"],
        "acc": wc["accuracy"], "precision": wc["precision"], "recall": wc["recall"], "f1": wc["f1"],
        "fpr": wc["fpr"], "fpr_nonempty": m["clean"]["fpr_nonempty"],
        "tp": wc["tp"], "fp": wc["fp"], "fn": wc["fn"], "tn": wc["tn"],
    })
    return row


# ---- one run ---------------------------------------------------------------

def write_run(out_dir: Path, rows: list[dict], preds: list[dict], meta: dict, metrics: dict | None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if preds:
        with (out_dir / "predictions.jsonl").open("w", encoding="utf-8") as f:
            for r, x in zip(rows, preds):
                f.write(json.dumps({
                    "case_id": r["case_id"], "server": r["server"], "is_poisoned": r["is_poisoned"],
                    "risk_category": r["risk_category"], "paradigm": r["paradigm"],
                    "test_cell": r["test_cell"], "empty_description": not (r["description"] or "").strip(),
                    "predicted_poisoned": x["blocked"], "correct": x["blocked"] == r["is_poisoned"],
                    "stage": x["stage"], "s2_score": x["s2_score"], "rules": x["rules"],
                }) + "\n")
    (out_dir / "metrics.json").write_text(json.dumps({"meta": meta, "metrics": metrics}, indent=2), encoding="utf-8")
    (out_dir / "log.txt").write_text(render_log(meta, metrics), encoding="utf-8")


def _p(x) -> str:
    return f"{100 * x:6.2f}%" if x is not None else "     -"


def render_log(meta: dict, m: dict | None) -> str:
    lines = [f"{k}: {v}" for k, v in meta.items() if k != "traceback"]
    if meta.get("traceback"):
        lines += ["", meta["traceback"]]
    if m is None:
        return "\n".join(lines) + "\n"
    lines += ["", f"{'category':28s} {'n':>5s} {'correct':>8s} {'wrong':>6s} {'accuracy':>9s}   "
              f"(+clean) {'prec':>7s} {'rec':>7s} {'f1':>7s}"]
    for c, v in m["categories"].items():
        w = v["with_clean"]
        lines.append(f"{c:28s} {v['n']:5d} {v['correct']:8d} {v['incorrect']:6d} {_p(v['accuracy']):>9s}   "
                     f"         {_p(w['precision'])} {_p(w['recall'])} {_p(w['f1'])}")
    cp, wc, cl = m["combined_poisoned"], m["with_clean"], m["clean"]
    lines += [
        f"{'COMBINED (pooled)':28s} {cp['n']:5d} {cp['correct']:8d} {cp['incorrect']:6d} {_p(cp['accuracy']):>9s}",
        f"  (unweighted mean of category accuracies, for reference only: {_p(cp['unweighted_mean_of_categories'])})",
        "",
        f"poisoned + clean: n={wc['n']}  TP={wc['tp']} FP={wc['fp']} FN={wc['fn']} TN={wc['tn']}",
        f"  acc {_p(wc['accuracy'])}  prec {_p(wc['precision'])}  rec {_p(wc['recall'])}  "
        f"f1 {_p(wc['f1'])}  FPR {_p(wc['fpr'])}",
        f"clean tools: {cl['n']} ({cl['n'] - cl['n_nonempty']} empty)  FP={cl['fp']}  "
        f"FPR {_p(cl['fpr'])}  FPR(non-empty) {_p(cl['fpr_nonempty'])}",
        "recall by attack type: " + "; ".join(
            f"{k} {v['correct']}/{v['n']} {_p(v['recall'])}" for k, v in m["by_paradigm_recall"].items()),
        f"decided at stage: {m['decided_at_stage']}",
    ]
    return "\n".join(lines) + "\n"


def run_one(split, model, config, seed, rows, build) -> dict:
    run = config + (f"_seed{seed}" if seed is not None else "")
    out_dir = OUT_ROOT / split / model / run
    meta = {"model": MODELS[model][0], "model_key": model, "config": config, "seed": seed, "split": split,
            "n_rows": len(rows), "n_poisoned": sum(r["is_poisoned"] for r in rows)}
    preds, metrics = [], None
    t0 = time.perf_counter()
    try:
        checkpoint, score = build()
        meta["checkpoint"] = checkpoint
        preds = score(rows)
        metrics = compute_metrics(rows, preds)
        meta["status"] = "ok"
    except Exception as e:  # record and move on; never fill in numbers for a failed run
        meta["status"] = "error"
        meta["error"] = f"{type(e).__name__}: {e}"
        meta["traceback"] = traceback.format_exc()
    meta["eval_seconds"] = round(time.perf_counter() - t0, 2)
    write_run(out_dir, rows, preds, meta, metrics)
    cp = metrics["combined_poisoned"]["accuracy"] if metrics else None
    print(f"[{meta['status']}] {model}/{run}: combined {_p(cp)}  ({meta['eval_seconds']}s)"
          + (f"  {meta['error']}" if meta["status"] == "error" else ""), flush=True)
    return {"meta": meta, "metrics": metrics}


def guard_builder(config_path, ckpt, stages):
    def build():
        s2 = {"loader": "finetuned", "path": str(ckpt)} if ckpt else None
        if ckpt and not Path(ckpt).is_dir():
            raise FileNotFoundError(f"checkpoint not found: {ckpt}")
        g = MCPGuard.from_config(config_path, mode="paper", stages=stages, stage2=s2)
        tag = g.s2.cache_tag if g.s2 else None
        return f"{tag} | stages={'+'.join(stages)} tu={g.tu}", lambda rows: score_guard(g, rows)
    return build


def guardian_builder():
    def build():
        s = WafScanner()
        return f"MCP Guardian WAF, {len(s.rules)} rules, fingerprint {s.fingerprint}", \
            lambda rows: score_guardian(s, rows)
    return build


# ---- summary ---------------------------------------------------------------

def summarize(split: str, results: list[dict]) -> None:
    out = OUT_ROOT / split
    run_rows = []
    for r in results:
        m = r["meta"]
        row = {"model": m["model"], "model_key": m["model_key"], "config": m["config"], "seed": m["seed"],
               "status": m["status"], "eval_seconds": m["eval_seconds"], "error": m.get("error", "")}
        if r["metrics"]:
            row.update(flat(r["metrics"]))
        run_rows.append(row)
    fields = list(dict.fromkeys(k for row in run_rows for k in row))
    with (out / "runs.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(run_rows)

    groups = defaultdict(list)
    for row in run_rows:
        groups[(row["model_key"], row["config"])].append(row)
    summary = []
    for (key, config), rs in groups.items():
        ok = [x for x in rs if x["status"] == "ok"]
        entry = {"model": MODELS[key][0], "model_key": key, "config": config,
                 "seeds_ok": len(ok), "seeds_total": len(rs),
                 "errors": [x["error"] for x in rs if x["status"] != "ok"]}
        keys = [k for k in fields if k.startswith("acc[") or k.startswith("n[")] + list(SUMMARY_KEYS)
        for k in keys:
            vals = [x[k] for x in ok if x.get(k) is not None]
            if not vals:
                continue
            entry[k] = statistics.mean(vals)
            if not k.startswith("n["):
                entry[f"{k}_std"] = statistics.stdev(vals) if len(vals) > 1 else 0.0
                entry[f"{k}_seeds"] = vals
        summary.append(entry)
    (out / "summary.json").write_text(json.dumps({
        "split": split, "held_out_categories": held_out_categories() if split == "heldout" else None,
        "seed_note": "fine-tuned rows: pooled metric per seed, then mean and sample std over seeds",
        "rows": summary,
    }, indent=2), encoding="utf-8")
    sfields = list(dict.fromkeys(k for e in summary for k in e if not k.endswith("_seeds")))
    with (out / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=sfields)
        w.writeheader()
        for e in summary:
            w.writerow({k: (" | ".join(e[k]) if k == "errors" else e.get(k)) for k in sfields})
    print(f"wrote {out.relative_to(ROOT)}/{{runs.csv,summary.csv,summary.json}}")


def main() -> None:
    ap = argparse.ArgumentParser(description="RQ1: score all six detectors on held-out MCPTox categories.")
    ap.add_argument("--split", required=True, choices=["heldout", "val"])
    ap.add_argument("--ckpt-root", required=True, help="directory with <init>_<scope>_seed<k>/ from train.py")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--models", default=",".join(MODELS), help="comma list of model keys")
    ap.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    args = ap.parse_args()

    rows = load_rows(args.split)
    seeds = [int(s) for s in args.seeds.split(",")]
    results = []
    t0 = time.perf_counter()
    for key in args.models.split(","):
        prefix = MODELS[key][1]
        if key == "mcp_guardian":
            results.append(run_one(args.split, key, "waf", None, rows, guardian_builder()))
            continue
        for config in GUARD_CONFIGS:
            stages = ("s1", "s2") if config == "s1-s2" else ("s2",)
            for seed in (seeds if prefix else [None]):
                ckpt = Path(args.ckpt_root) / f"{prefix}_seed{seed}" if prefix else None
                results.append(run_one(args.split, key, config, seed, rows,
                                       guard_builder(args.config, ckpt, stages)))
    summarize(args.split, results)
    n_err = sum(r["meta"]["status"] != "ok" for r in results)
    print(f"{len(results)} runs, {n_err} errors, {time.perf_counter() - t0:.1f}s total")


if __name__ == "__main__":
    main()
