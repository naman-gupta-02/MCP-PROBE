"""Per-category and cross-dataset summary tables for all six detectors (committed CSV + markdown).

  uv run python -m experiments.rq1_heldout.category_summary

Inputs (gitignored): results/rq1_heldout/{heldout,all}/, results/rq1_combos/<combo>/heldout/,
results/mcp_guard/upstream_dev_eval/. Outputs (committed, numbers only):
  experiments/rq1_heldout/tables/heldout_recall_by_category.csv
  experiments/rq1_heldout/tables/untrained_all_mcptox_by_category.csv
  experiments/rq1_heldout/tables/upstream_dev_cross_dataset.csv
  experiments/rq1_heldout/tables/TABLES.md
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

from .combos import COMBO_DIR
from .evaluate import MODELS, ROOT

OUT = Path(__file__).resolve().parent / "tables"
FIRST = ROOT / "results" / "rq1_heldout"
COMBOS = ROOT / "results" / "rq1_combos"
DEV = ROOT / "results" / "mcp_guard" / "upstream_dev_eval" / "summary.json"
FIRST_HELD = json.loads((ROOT / "data" / "splits" / "server_split.json").read_text())["held_out_categories"]
CFGS = {"s1-s2": "Stage I + II", "s2": "Stage II alone"}


def summary(path: Path) -> dict:
    return {(e["model_key"], e["config"]): e for e in json.loads(path.read_text())["rows"]}


def cfg_for(key: str, cfg: str) -> str:
    return "waf" if key == "mcp_guardian" else cfg


def pct(v) -> str:
    return "–" if v is None else f"{100 * v:.1f}"


def heldout_by_category() -> tuple[list[dict], list[str]]:
    """Recall on each category in the split(s) where it was held out (first run or the 8 combos)."""
    combos = json.loads((COMBO_DIR / "combos.json").read_text())["combos"]
    sources = {c: [("first run", FIRST / "heldout" / "summary.json")] for c in FIRST_HELD}
    for cid, cats in combos.items():
        for c in cats:
            sources.setdefault(c, []).append((cid, COMBOS / cid / "heldout" / "summary.json"))
    rows = []
    for cat in sorted(sources):
        sums = [(sid, summary(p)) for sid, p in sources[cat]]
        n = int(sums[0][1][("frozen_mcpguard", "s1-s2")][f"n[{cat}]"])
        for cfg in CFGS:
            for key, (name, _) in MODELS.items():
                vals = [s[(key, cfg_for(key, cfg))][f"acc[{cat}]"] for _, s in sums]  # seed mean per split
                rows.append({
                    "category": cat, "n_cases": n, "held_out_in": "; ".join(sid for sid, _ in sums),
                    "config": CFGS[cfg] if key != "mcp_guardian" else "rules", "model": name,
                    "recall_mean": statistics.mean(vals), "recall_min": min(vals), "recall_max": max(vals),
                    "n_splits": len(vals),
                })
    return rows, sorted(sources)


def untrained_all_by_category() -> list[dict]:
    """Frozen MCP-Guard and Guardian on every MCPTox row (never trained on MCPTox)."""
    rows = []
    for key, cfgs in (("frozen_mcpguard", ("s1-s2", "s2")), ("mcp_guardian", ("waf",))):
        for cfg in cfgs:
            m = json.loads((FIRST / "all" / key / cfg / "metrics.json").read_text())["metrics"]
            for cat, v in m["categories"].items():
                w = v["with_clean"]
                rows.append({"model": MODELS[key][0], "config": {"s1-s2": "Stage I + II", "s2": "Stage II alone"}.get(cfg, "rules"),
                             "category": cat, "n_cases": v["n"], "correct": v["correct"], "recall": v["accuracy"],
                             "precision_vs_all_clean": w["precision"], "f1_vs_all_clean": w["f1"]})
            w, c = m["with_clean"], m["clean"]
            rows.append({"model": MODELS[key][0], "config": {"s1-s2": "Stage I + II", "s2": "Stage II alone"}.get(cfg, "rules"),
                         "category": "ALL (pooled)", "n_cases": m["combined_poisoned"]["n"],
                         "correct": m["combined_poisoned"]["correct"], "recall": w["recall"],
                         "precision_vs_all_clean": w["precision"], "f1_vs_all_clean": w["f1"],
                         "fpr": w["fpr"], "fp": w["fp"], "n_clean": c["n"]})
    return rows


def cross_dataset() -> list[dict]:
    S = json.loads(DEV.read_text())
    names = {"frozen_mcpguard": "Frozen MCP-Guard", "mcpguard_full": "MCP-Guard Full", "e5base_full": "Base E5 Full"}
    rows = []
    for cfg, label in (("stage2_only@released", "Stage II alone (P>=0.5)"), ("stage1+2@released", "Stage I + II (P>=0.5)"),
                       ("stage2_only@paper", "Stage II alone (P>0.45)"), ("stage1+2@paper", "Stage I + II (P>0.45)")):
        for g, name in names.items():
            if g not in S[cfg]:
                continue
            m = S[cfg][g]
            r = {"config": label, "model": name, "seeds": len(m["f1"])}
            for k in ("accuracy", "precision", "recall", "f1", "fpr"):
                r[f"{k}_mean"] = statistics.mean(m[k])
                r[f"{k}_std"] = statistics.stdev(m[k]) if len(m[k]) > 1 else 0.0
            for k in ("tp", "fp", "fn", "tn"):
                r[k] = statistics.mean(m[k])
            rows.append(r)
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    held, cats = heldout_by_category()
    allm = untrained_all_by_category()
    cross = cross_dataset()
    write_csv(OUT / "heldout_recall_by_category.csv", held)
    write_csv(OUT / "untrained_all_mcptox_by_category.csv", allm)
    write_csv(OUT / "upstream_dev_cross_dataset.csv", cross)

    L = ["# Per-category and cross-dataset tables", "",
         "Generated by `category_summary.py` from the saved results; the CSV files next to this file hold the same numbers.", ""]
    for cfg_label in ("Stage I + II", "Stage II alone"):
        L += [f"## Held-out recall per category, all 10 categories — {cfg_label}", "",
              "Recall on each category **in the split(s) where it was held out**: the first run for Credential Leakage, "
              "Instruction Tampering and Financial Loss; otherwise the 3–4 combinations that held it out (seed mean per "
              "split, then mean over splits; range in brackets). Guardian (rules) is the same in both tables.", "",
              "| Category (cases; held out in) | " + " | ".join(n for n, _ in MODELS.values()) + " |",
              "|---|" + "---:|" * len(MODELS)]
        per_model = {n: [] for n, _ in MODELS.values()}
        for cat in cats:
            rs = {r["model"]: r for r in held if r["category"] == cat and r["config"] in (cfg_label, "rules")}
            first = next(iter(rs.values()))
            cells = []
            for n, _ in MODELS.values():
                r = rs[n]
                per_model[n].append(r["recall_mean"])
                rng = f" ({pct(r['recall_min'])}–{pct(r['recall_max'])})" if r["recall_max"] - r["recall_min"] >= 0.0005 else ""
                cells.append(pct(r["recall_mean"]) + rng)
            L.append(f"| {cat} ({first['n_cases']}; {first['held_out_in']}) | " + " | ".join(cells) + " |")
        L.append("| **Average over the 10 categories** | " + " | ".join(
            f"**{pct(statistics.mean(v))}**" for v in per_model.values()) + " |")
        L.append("| Lowest category | " + " | ".join(pct(min(v)) for v in per_model.values()) + " |")
        L.append("")

    L += ["## Untrained detectors on all of MCPTox, per category", "",
          "Frozen MCP-Guard and MCP Guardian were never trained on MCPTox, so every row (1,312 poisoned + 353 clean, "
          "tune + val + test) is unseen for them. Precision/F1 per category compare that category's cases against all "
          "353 clean tools, so they mostly reflect category size.", "",
          "| Category | Cases | Frozen MCP-Guard, Stage I + II | Frozen MCP-Guard, Stage II alone | MCP Guardian |",
          "|---|---:|---:|---:|---:|"]
    get = lambda model, cfg, cat: next(r for r in allm if r["model"] == model and r["config"] == cfg and r["category"] == cat)
    cats_all = [r["category"] for r in allm if r["model"] == "Frozen MCP-Guard" and r["config"] == "Stage I + II"]
    for cat in cats_all:
        a, b, g = get("Frozen MCP-Guard", "Stage I + II", cat), get("Frozen MCP-Guard", "Stage II alone", cat), get("MCP-Guardian", "rules", cat)
        L.append(f"| {cat} | {a['n_cases']} | {pct(a['recall'])} | {pct(b['recall'])} | {pct(g['recall'])} |")
    for label, (model, cfg) in (("Frozen MCP-Guard, Stage I + II", ("Frozen MCP-Guard", "Stage I + II")),
                                ("Frozen MCP-Guard, Stage II alone", ("Frozen MCP-Guard", "Stage II alone")),
                                ("MCP Guardian", ("MCP-Guardian", "rules"))):
        r = get(model, cfg, "ALL (pooled)")
        L.append(f"\n{label}: precision {pct(r['precision_vs_all_clean'])}, F1 {pct(r['f1_vs_all_clean'])}, "
                 f"FPR {pct(r['fpr'])} ({r['fp']} of {r['n_clean']} clean tools).")
    L += ["", "## Cross-dataset: MCP-Guard's released dev set (1,053 samples, 432 malicious)", "",
          "GenTelLab's full MCP-AttackBench is not released; this is the dev set behind the paper's Table 4a. "
          "Fine-tuned models: our original-run checkpoints (trained on MCPTox `tune`), 5 seeds.", "",
          "| Configuration | Model | Accuracy | Precision | Recall | F1 | FPR | TP | FP | FN | TN |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in cross:
        f = lambda k: pct(r[f"{k}_mean"]) + (f" ± {100 * r[f'{k}_std']:.1f}" if r["seeds"] > 1 else "")
        L.append(f"| {r['config']} | {r['model']} | " + " | ".join(f(k) for k in ("accuracy", "precision", "recall", "f1", "fpr"))
                 + " | " + " | ".join(f"{r[k]:.1f}" if r["seeds"] > 1 else f"{r[k]:.0f}" for k in ("tp", "fp", "fn", "tn")) + " |")
    (OUT / "TABLES.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\nwrote {OUT}/{{TABLES.md,heldout_recall_by_category.csv,untrained_all_mcptox_by_category.csv,upstream_dev_cross_dataset.csv}}")


if __name__ == "__main__":
    main()
