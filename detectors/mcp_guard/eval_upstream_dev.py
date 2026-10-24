"""Cross-dataset check: score a Stage II checkpoint on MCP-Guard's own released dev set.

GenTelLab's full MCP-AttackBench (70k+ samples) is not released (their README lists it as a
to-do). Their repo does ship test_data/dev.csv (1,053 samples, 432 malicious), the data behind
the paper's Table 4a (arXiv 2508.10991), which reproduce_upstream_dev.py matches exactly.
This scores any Stage II model on it, e.g. our MCPTox-trained Base E5 checkpoints, to see how
a model trained on MCPTox transfers to MCP-Guard's data. The frozen MCP-Guard is the reference.

  uv run python -m detectors.mcp_guard.eval_upstream_dev --name frozen_mcpguard
  uv run python -m detectors.mcp_guard.eval_upstream_dev --name e5base_full_seed0 --s2-path <ckpt dir>
  uv run python -m detectors.mcp_guard.eval_upstream_dev --summarize

Writes results/mcp_guard/upstream_dev_eval/<name>/{metrics.json,predictions.jsonl} and summary.{md,json}.
Decision rules, both from the same Stage II scores:
  released: Stage II blocks at P >= 0.5 (what reproduce_upstream_dev.py and upstream use)
  paper:    Stage II blocks at P > 0.45 (T_u from configs/mcp_guard.yaml; what RQ1 uses)
Stage I + II = Stage I hit, or Stage II blocks.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path

from .metrics import binary_metrics
from .pipeline import ROOT, MCPGuard
from .reproduce_upstream_dev import fetch_dev_csv
from .stage1 import PatternStage
from .stage2 import NeuralStage

OUT = ROOT / "results" / "mcp_guard" / "upstream_dev_eval"
RULES = {"released": lambda p: p is not None and p >= 0.5, "paper": lambda p: p is not None and p > 0.45}
CONFIGS = [f"{stages}@{rule}" for stages in ("stage2_only", "stage1+2") for rule in RULES]


def score(name: str, s2_path: str | None, device: str) -> None:
    with fetch_dev_csv().open(encoding="utf-8") as f:
        rows = [(r["description"].strip(), int(r["Label"]) == 1) for r in csv.DictReader(f)]
    tools = [{"tool_name": "test_tool", "description": d} for d, _ in rows]  # upstream main.py uses "test_tool"
    y = [lab for _, lab in rows]

    t0 = time.perf_counter()
    s2 = NeuralStage(loader="finetuned", path=s2_path, device=device) if s2_path else NeuralStage(device=device)
    s2_scores = [v.s2_score for v in MCPGuard(mode="released", stages=("s2",), stage2=s2).scan_many(tools)]
    s1_hits = [sorted({h["detector"] for h in v.s1_hits})
               for v in MCPGuard(mode="released", stages=("s1",), stage1=PatternStage()).scan_many(tools)]
    secs = time.perf_counter() - t0

    preds, metrics = {}, {}
    for rule, block in RULES.items():
        preds[f"stage2_only@{rule}"] = [block(p) for p in s2_scores]
        preds[f"stage1+2@{rule}"] = [bool(h) or block(p) for h, p in zip(s1_hits, s2_scores)]
    for k in CONFIGS:
        metrics[k] = binary_metrics(y, preds[k])

    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "metrics.json").write_text(json.dumps({
        "name": name, "checkpoint": s2.cache_tag, "n": len(rows), "n_malicious": sum(y),
        "data": "GenTelLab/MCP-Guard test_data/dev.csv (results/mcp_guard/upstream_dev.csv)",
        "seconds": round(secs, 1), "metrics": metrics,
    }, indent=2), encoding="utf-8")
    with (d / "predictions.jsonl").open("w", encoding="utf-8") as f:
        for i, (lab, p, h) in enumerate(zip(y, s2_scores, s1_hits)):
            f.write(json.dumps({"row": i, "label_malicious": lab, "s2_score": p, "s1_hits": h,
                                **{k: preds[k][i] for k in CONFIGS}}) + "\n")
    m = metrics["stage2_only@released"]
    print(f"{name}: Stage II alone (P>=0.5) acc {100 * m['accuracy']:.1f} prec {100 * m['precision']:.1f} "
          f"rec {100 * m['recall']:.1f} f1 {100 * m['f1']:.1f} fpr {100 * m['fpr']:.1f}  ({secs:.0f}s)")


def summarize() -> None:
    runs = {p.parent.name: json.loads(p.read_text()) for p in sorted(OUT.glob("*/metrics.json"))}
    groups: dict[str, list[dict]] = {}
    for name, r in runs.items():
        groups.setdefault(name.split("_seed")[0], []).append(r)

    def cell(vals):
        vals = [100 * v for v in vals if v is not None]
        if not vals:
            return "–"
        return f"{vals[0]:.1f}" if len(vals) == 1 else f"{statistics.mean(vals):.1f} ± {statistics.stdev(vals):.1f}"

    L = ["# MCPTox-trained models on MCP-Guard's released dev set", "",
         f"Data: GenTelLab/MCP-Guard `test_data/dev.csv`, {next(iter(runs.values()))['n']} samples "
         f"({next(iter(runs.values()))['n_malicious']} malicious). Fine-tuned rows: mean ± std over seeds.", ""]
    summary = {}
    for cfg in CONFIGS:
        L += [f"## {cfg}", "", "| Model | Runs | Accuracy | Precision | Recall | F1 | FPR | TP | FP | FN | TN |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for g, rs in groups.items():
            ms = [r["metrics"][cfg] for r in rs]
            cnt = lambda k: f"{statistics.mean(m[k] for m in ms):.1f}" if len(ms) > 1 else str(ms[0][k])
            L.append(f"| {g} | {len(ms)} | " + " | ".join(cell([m[k] for m in ms]) for k in
                     ("accuracy", "precision", "recall", "f1", "fpr")) + " | "
                     + " | ".join(cnt(k) for k in ("tp", "fp", "fn", "tn")) + " |")
            summary.setdefault(cfg, {})[g] = {k: [m[k] for m in ms] for k in ms[0]}
        L.append("")
    (OUT / "summary.md").write_text("\n".join(L), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n".join(L))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", help="run name, e.g. e5base_full_seed0 or frozen_mcpguard")
    ap.add_argument("--s2-path", help="fine-tuned Stage II checkpoint dir (omit for the frozen MCP-Guard)")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--summarize", action="store_true")
    args = ap.parse_args()
    if args.summarize:
        summarize()
    elif args.name:
        score(args.name, args.s2_path, args.device)
    else:
        ap.error("--name or --summarize is required")


if __name__ == "__main__":
    main()
