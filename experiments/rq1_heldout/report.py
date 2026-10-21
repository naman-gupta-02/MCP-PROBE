"""Build the RQ1 comparison tables from results/rq1_heldout/{heldout|test,val}/summary.json.

  uv run python -m experiments.rq1_heldout.report                 # held-out categories -> report.md
  uv run python -m experiments.rq1_heldout.report --split test    # whole test split -> report_test.md

Numbers only; no case text.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from detectors.mcp_guard.pipeline import ROOT

OUT = ROOT / "results" / "rq1_heldout"
CONFIG_TITLES = {
    "s1-s2": "MCP-Guard Stage I + II (paper mode)",
    "s2": "MCP-Guard Stage II alone",
}


def load(split: str) -> dict | None:
    p = OUT / split / "summary.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def fmt(e: dict, k: str) -> str:
    if k not in e or e[k] is None:
        return "-"
    v = 100 * e[k]
    return f"{v:.1f} ± {100 * e[f'{k}_std']:.1f}" if e.get("seeds_ok", 1) > 1 else f"{v:.1f}"


def rows_for(summary: dict, config: str) -> list[dict]:
    """Rows of one MCP-Guard config plus Guardian, best combined held-out accuracy first."""
    rs = [e for e in summary["rows"] if e["config"] in (config, "waf")]
    return sorted(rs, key=lambda e: -(e.get("combined_accuracy") or -1))


def seeds(e: dict) -> str:
    s = f"{e['seeds_ok']}/{e['seeds_total']}" if e["seeds_total"] > 1 else "-"
    return s + (" ⚠" if e["errors"] else "")


def ranked_table(L: list[str], rs: list[dict], cols: list[tuple[str, str]], combined: str) -> None:
    L += ["| Rank | Model | " + " | ".join(h for h, _ in cols) + f" | {combined} | Seeds |",
          "|---:|---|" + "---:|" * (len(cols) + 2)]
    for i, e in enumerate(rs, 1):
        L.append(f"| {i} | {e['model']} | " + " | ".join(fmt(e, k) for _, k in cols)
                 + f" | **{fmt(e, 'combined_accuracy')}** | {seeds(e)} |")
    L.append("")


def main() -> None:
    ap = argparse.ArgumentParser(description="RQ1 comparison tables.")
    ap.add_argument("--split", default="heldout", choices=["heldout", "test"])
    ap.add_argument("--out-root", type=Path, help="results dir (default results/rq1_heldout)")
    args = ap.parse_args()
    split = args.split
    global OUT
    OUT = args.out_root or OUT
    held, val = load(split), load("val")
    if held is None:
        raise SystemExit(f"results/rq1_heldout/{split}/summary.json missing; run evaluate --split {split} first")
    held_out = held["held_out_categories"]
    any_row = next(e for e in held["rows"] if e["seeds_ok"])
    n_clean = round(any_row["fp"] + any_row["tn"])
    rows_name = "held-out" if split == "heldout" else "test"

    if split == "heldout":
        cats = held_out
        counts = {c: int(any_row[f"n[{c}]"]) for c in cats}
        n_pos = sum(counts.values())
        L = ["# RQ1: held-out MCPTox categories", "",
             "Held-out categories: "
             + ", ".join(f"C{i + 1} = {c} (n={counts[c]})" for i, c in enumerate(cats))
             + f". Pooled: {n_pos} poisoned cases. Clean test tools: {n_clean}.", "",
             "Every held-out case is poisoned, so category accuracy = recall (a block-everything detector "
             "scores 100%). Combined accuracy = correct / total over all held-out cases (pooled, not a mean of "
             "category accuracies). Fine-tuned rows: mean ± std over 5 seeds, each seed pooled first. "
             "Rows are ranked by combined accuracy.", ""]
    else:
        cats = sorted(k[4:-1] for k in any_row if k.startswith("acc[") and k.endswith("]"))
        cells = sorted(k[5:-1] for k in any_row if k.startswith("cell[") and k.endswith("]"))
        n_pos = round(any_row["tp"] + any_row["fn"])
        L = ["# RQ1: whole MCPTox test split", "",
             f"All {n_pos + n_clean} test rows: {n_pos} poisoned cases + {n_clean} clean test tools. Test cells: "
             + ", ".join(f"{c} (n={int(any_row[f'ncell[{c}]'])})" for c in cells)
             + f". Held-out categories: {', '.join(held_out)}.", "",
             "Recall columns are over poisoned cases only. Combined = pooled recall over all poisoned test cases. "
             "Fine-tuned rows: mean ± std over 5 seeds, each seed pooled first. Rows are ranked by combined.", ""]

    for config, title in CONFIG_TITLES.items():
        rs = rows_for(held, config)
        if split == "heldout":
            L += [f"## Table 1 — {title}", ""]
            ranked_table(L, rs, [(f"C{i + 1} Acc ({c})", f"acc[{c}]") for i, c in enumerate(cats)], "Combined Acc")
        else:
            L += [f"## Table 1 — {title}: recall by test cell", ""]
            ranked_table(L, rs, [(c, f"cell[{c}]") for c in cells], "Combined recall")
            L += [f"### Recall by risk category (* = held out) — {title}", ""]
            ranked_table(L, rs, [(c + (" *" if c in held_out else "") + f" (n={int(any_row[f'n[{c}]'])})",
                                  f"acc[{c}]") for c in cats], "Combined recall")

        L += [f"### Table 2 — {title}: {rows_name} poisoned + {n_clean} clean test tools", "",
              "| Model | Accuracy | Precision | Recall | F1 | FPR (all clean) | FPR (non-empty clean) | TP | FP | FN | TN |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for e in rs:
            cm = " | ".join(f"{e[k]:.1f}" if e["seeds_total"] > 1 else f"{e[k]:.0f}" for k in ("tp", "fp", "fn", "tn")) \
                if "tp" in e else "- | - | - | -"
            L.append(f"| {e['model']} | {fmt(e, 'acc')} | {fmt(e, 'precision')} | {fmt(e, 'recall')} | "
                     f"{fmt(e, 'f1')} | {fmt(e, 'fpr')} | {fmt(e, 'fpr_nonempty')} | {cm} |")
        L.append("")

        if val:
            vrows = {(e["model_key"], e["config"]): e for e in val["rows"]}
            L += [f"### Generalization gap — {title}: val (seen categories) → {rows_name}", "",
                  f"| Model | Recall val | Recall {rows_name} | Δ | F1 val | F1 {rows_name} | FPR val | FPR {rows_name} |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
            for e in rs:
                v = vrows.get((e["model_key"], e["config"]))
                if not v or "combined_accuracy" not in v or "combined_accuracy" not in e:
                    L.append(f"| {e['model']} | - | {fmt(e, 'combined_accuracy')} | - | - | {fmt(e, 'f1')} | - | {fmt(e, 'fpr')} |")
                    continue
                d = 100 * (e["combined_accuracy"] - v["combined_accuracy"])
                L.append(f"| {e['model']} | {fmt(v, 'combined_accuracy')} | {fmt(e, 'combined_accuracy')} | "
                         f"{d:+.1f} | {fmt(v, 'f1')} | {fmt(e, 'f1')} | {fmt(v, 'fpr')} | {fmt(e, 'fpr')} |")
            v_any = next(e for e in val["rows"] if e["seeds_ok"])
            L += ["", "val recall = pooled recall over all val poisoned cases (seen categories, val servers); "
                  f"F1/FPR use each split's own clean tools (val {round(v_any['fp'] + v_any['tn'])}, "
                  f"{rows_name} {n_clean}).", ""]

    errs = [(e["model"], e["config"], x) for s in (held, val) if s for e in s["rows"] for x in e["errors"]]
    L += ["## Errors", ""] + ([f"- {m} / {c}: {x}" for m, c, x in errs] or ["None."]) + [""]
    out = OUT / ("report.md" if split == "heldout" else "report_test.md")
    out.write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
