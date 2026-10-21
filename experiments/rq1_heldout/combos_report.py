"""Compare all held-out combinations side by side (plus the original split as reference).

  uv run python -m experiments.rq1_heldout.combos_report [--base results/rq1_combos]

Reads <base>/<combo>/{heldout,test,val}/summary.json and results/rq1_heldout/ (original split);
writes <base>/combos_report.md and <base>/combos_summary.csv. Numbers only; no case text.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

from .combos import COMBO_DIR
from .evaluate import MODELS, ROOT

ORIG = ROOT / "results" / "rq1_heldout"
CONFIGS = {"s1-s2": "Stage I + II", "s2": "Stage II alone"}
METRICS = [("combined_accuracy", "Held-out combined accuracy (= recall)"), ("f1", "Held-out F1 (with 64 clean)"),
           ("fpr", "FPR on 64 clean test tools")]


def load(base: Path, split: str) -> dict | None:
    p = base / split / "summary.json"
    return {(e["model_key"], e["config"]): e for e in json.loads(p.read_text())["rows"]} if p.exists() else None


def pct(v):
    return "–" if v is None else f"{100 * v:.1f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=ROOT / "results" / "rq1_combos")
    base = ap.parse_args().base
    combos = json.loads((COMBO_DIR / "combos.json").read_text())["combos"]
    sets = {"orig": (["Credential Leakage", "Instruction Tampering", "Financial Loss"], ORIG)}
    sets.update({cid: (cats, base / cid) for cid, cats in combos.items()})

    data, csv_rows, missing = {}, [], []
    for sid, (cats, d) in sets.items():
        for split in ("heldout", "test", "val"):
            s = load(d, split)
            if s is None:
                missing.append(f"{sid}/{split}")
            data[(sid, split)] = s or {}

    L = ["# RQ1 robustness: all held-out category combinations", "",
         "Each combination retrains the 20 fine-tuned models on its own `tune` split and scores all six detectors. "
         "`orig` is the first RQ1 run. Per combination: mean over 5 seeds for fine-tuned models. "
         "Across combinations: mean ± std of the 8 new combinations (orig excluded), then min–max.", "",
         "| Set | Held-out categories | Held-out cases |", "|---|---|---:|"]
    for sid, (cats, _) in sets.items():
        e = data[(sid, "heldout")].get(("frozen_mcpguard", "s1-s2"))
        n = int(e["combined_n"]) if e else "–"
        L.append(f"| {sid} | {', '.join(cats)} | {n} |")
    L.append("")
    if missing:
        L += [f"Missing (not run or failed): {', '.join(missing)}", ""]

    for cfg, cfg_title in CONFIGS.items():
        for mkey, mtitle in METRICS:
            L += [f"## {mtitle} — {cfg_title}", "",
                  "| Model | " + " | ".join(sets) + " | Mean ± std (8 new) | Min–max (8 new) |",
                  "|---|" + "---:|" * (len(sets) + 2)]
            for key, name in MODELS.items():
                c = "waf" if key == "mcp_guardian" else cfg
                vals = {sid: data[(sid, "heldout")].get((key, c), {}).get(mkey) for sid in sets}
                new = [v for sid, v in vals.items() if sid != "orig" and v is not None]
                agg = (f"{100 * statistics.mean(new):.1f} ± {100 * statistics.stdev(new):.1f}" if len(new) > 1 else "–")
                rng = f"{100 * min(new):.1f}–{100 * max(new):.1f}" if new else "–"
                L.append(f"| {name[0]} | " + " | ".join(pct(vals[s]) for s in sets) + f" | {agg} | {rng} |")
                for sid, v in vals.items():
                    csv_rows.append({"set": sid, "categories": "; ".join(sets[sid][0]), "model": name[0],
                                     "config": c, "metric": mkey, "split": "heldout", "value": v})
            L.append("")

    # Whole-test and val combined recall, Stage I + II, for context.
    for split, title in (("test", "Whole test split recall"), ("val", "val recall (dev)")):
        L += [f"## {title} — Stage I + II", "", "| Model | " + " | ".join(sets) + " |", "|---|" + "---:|" * len(sets)]
        for key, name in MODELS.items():
            c = "waf" if key == "mcp_guardian" else "s1-s2"
            L.append(f"| {name[0]} | " + " | ".join(
                pct(data[(sid, split)].get((key, c), {}).get("combined_accuracy")) for sid in sets) + " |")
        L.append("")

    errs = [f"{sid}/{split}: {e['model']} {e['config']}: {x}" for (sid, split), s in data.items()
            for e in s.values() for x in e.get("errors", [])]
    L += ["## Errors", ""] + (errs or ["None."]) + [""]
    base.mkdir(parents=True, exist_ok=True)
    (base / "combos_report.md").write_text("\n".join(L), encoding="utf-8")
    with (base / "combos_summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(csv_rows[0]))
        w.writeheader()
        w.writerows(csv_rows)
    print("\n".join(L))
    print(f"wrote {base}/combos_report.md and combos_summary.csv")


if __name__ == "__main__":
    main()
