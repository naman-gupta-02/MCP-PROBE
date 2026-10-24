"""Write the committed results documents for the held-out combinations.

  uv run python -m experiments.rq1_heldout.combos_docs [--base results/rq1_combos]

Reads results/rq1_combos/<combo>/ (gitignored) and writes
  experiments/rq1_heldout/combos/results/<combo>.md   one detailed file per combination
  experiments/rq1_heldout/combos/results/tables.md    cross-combination tables (feeds COMBOS_RESULTS.md)
Numbers and counts only; no case text.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

from .combos import COMBO_DIR
from .evaluate import MODELS, ROOT

DOC_DIR = COMBO_DIR / "results"
ORIG = ROOT / "results" / "rq1_heldout"
VARIANTS = [("mcpguard_full", "MCP-Guard Full"), ("mcpguard_head", "MCP-Guard Head-Only"),
            ("e5base_full", "Base E5 Full"), ("e5base_head", "Base E5 Head-Only")]


def summary(d: Path, split: str) -> dict:
    p = d / split / "summary.json"
    return {(e["model_key"], e["config"]): e for e in json.loads(p.read_text())["rows"]} if p.exists() else {}


def demote(md: str) -> str:
    """Shift markdown headings one level down so a report nests under a section."""
    return re.sub(r"^(#+) ", lambda m: "#" + m.group(1) + " ", md, flags=re.M)


def split_tables(report: str) -> str:
    """The count tables of a split_report.md (everything from the first '## ' heading on)."""
    i = report.find("\n## ")
    return demote(report[i + 1:]) if i >= 0 else ""


def training_table(d: Path) -> list[str]:
    L = ["| Variant | Runs | Train rows (poisoned + clean) | Val rows | Best epoch per seed | Best val F1 (Stage II, 0.5) | Train time per run |",
         "|---|---:|---:|---:|---|---:|---:|"]
    for key, name in VARIANTS:
        metas = [json.loads(p.read_text()) for p in sorted((d / "train_meta").glob(f"{key}_seed*.json"))]
        if not metas:
            L.append(f"| {name} | 0 | – | – | – | – | – |")
            continue
        f1 = [m["best_val"]["f1"] for m in metas if m.get("best_val")]
        L.append(f"| {name} | {len(metas)} | {metas[0]['n_train']} | {metas[0]['n_val']} | "
                 f"{', '.join(str(m['best_epoch']) for m in metas)} | "
                 f"{100 * statistics.mean(f1):.1f} | {statistics.mean(m['train_seconds'] for m in metas):.0f} s |")
    dev = {json.loads(p.read_text()).get("device") for p in (d / "train_meta").glob("*.json")}
    commit = {json.loads(p.read_text()).get("git_commit", "")[:7] for p in (d / "train_meta").glob("*.json")}
    L += ["", f"Device: {', '.join(sorted(dev))}. Code commit: {', '.join(sorted(commit))}. "
          "Same hyperparameters as the first run (`detectors/mcp_guard/train.py` defaults); "
          "best epoch picked on this combination's val split."]
    return L


def combo_doc(cid: str, cats: list[str], d: Path, job: str) -> str:
    held = summary(d, "heldout")
    fz = held.get(("frozen_mcpguard", "s1-s2"), {})
    L = [f"# RQ1 combination {cid}: {', '.join(cats)}", "",
         f"Held-out categories: **{', '.join(cats)}**"
         + (f" ({int(fz['combined_n'])} poisoned cases), scored with the 64 clean test tools." if fz else "."),
         "", "Part of the RQ1 robustness check (see [../../COMBOS_RESULTS.md](../../COMBOS_RESULTS.md) and "
         "[../../README.md](../../README.md)). All 20 fine-tuned models were retrained on this combination's "
         "own `tune` split; Frozen MCP-Guard and MCP Guardian are unchanged. "
         f"Run on CARC (A40), job `{job}`, 2026-10-21.", ""]
    rep = d / "split_report.md"
    if rep.exists():
        L += ["## 1. Split", "", split_tables(rep.read_text()), ""]
    L += ["## 2. Training", ""] + training_table(d) + [""]
    for title, f in (("3. Held-out categories", "report.md"), ("4. Whole test split", "report_test.md")):
        p = d / f
        L += [f"## {title}", ""]
        if p.exists():
            body = p.read_text().split("\n", 1)[1]  # drop the report's own title line
            L += [demote(demote(body)).strip(), ""]
        else:
            L += ["Missing: not run or failed.", ""]
    return "\n".join(L) + "\n"


def category_table(combos: dict, base: Path, cfg: str) -> list[str]:
    """Recall per category, averaged over the combinations in which that category was held out."""
    vals = defaultdict(lambda: defaultdict(list))  # cat -> model -> [seed-mean recall per combo]
    n_combos = defaultdict(int)
    for cid, cats in combos.items():
        s = summary(base / cid, "heldout")
        for c in cats:
            n_combos[c] += 1
            for key in MODELS:
                e = s.get((key, "waf" if key == "mcp_guardian" else cfg))
                if e and f"acc[{c}]" in e:
                    vals[c][key].append(e[f"acc[{c}]"])
    L = ["| Held-out category (times held out) | " + " | ".join(MODELS[k][0] for k in MODELS) + " |",
         "|---|" + "---:|" * len(MODELS)]
    for c in sorted(vals):
        cells = []
        for key in MODELS:
            v = vals[c][key]
            cells.append("–" if not v else f"{100 * statistics.mean(v):.1f}" + (
                f" ({100 * min(v):.1f}–{100 * max(v):.1f})" if len(v) > 1 and max(v) - min(v) >= 0.0005 else ""))
        L.append(f"| {c} ({n_combos[c]}) | " + " | ".join(cells) + " |")
    return L


def per_combo_summary(cid: str, cats: list[str], d: Path) -> list[str]:
    """One compact table per combination: per-category + combined recall, F1, FPR, Stage II-alone recall."""
    h, t = summary(d, "heldout"), summary(d, "test")

    def f(e, k):
        if not e or k not in e:
            return "–"
        v = 100 * e[k]
        return f"{v:.1f}" if e["seeds_total"] == 1 else f"{v:.1f} ± {100 * e[k + '_std']:.1f}"

    fz = h.get(("frozen_mcpguard", "s1-s2"), {})
    ns = {c: int(fz.get(f"n[{c}]", 0)) for c in cats}
    L = [f"### {cid}: {', '.join(cats)} ({sum(ns.values())} held-out cases) — [details]({cid}.md)", "",
         "| Model | " + " | ".join(f"{c} (n={ns[c]})" for c in cats)
         + " | **Combined** | F1 | FPR | Combined, Stage II alone | Whole-test recall |",
         "|---|" + "---:|" * (len(cats) + 5)]
    for key, (name, _) in MODELS.items():
        c1 = "waf" if key == "mcp_guardian" else "s1-s2"
        c2 = "waf" if key == "mcp_guardian" else "s2"
        e = h.get((key, c1), {})
        L.append(f"| {name} | " + " | ".join(f(e, f"acc[{c}]") for c in cats)
                 + f" | **{f(e, 'combined_accuracy')}** | {f(e, 'f1')} | {f(e, 'fpr')} | "
                 + f"{f(h.get((key, c2), {}), 'combined_accuracy')} | {f(t.get((key, c1), {}), 'combined_accuracy')} |")
    return L + [""]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", type=Path, default=ROOT / "results" / "rq1_combos")
    ap.add_argument("--job", default="13272593", help="CARC array job id, for the record")
    args = ap.parse_args()
    combos = json.loads((COMBO_DIR / "combos.json").read_text())["combos"]
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    for i, (cid, cats) in enumerate(combos.items()):
        (DOC_DIR / f"{cid}.md").write_text(combo_doc(cid, cats, args.base / cid, f"{args.job}_{i}"), encoding="utf-8")
        print(f"wrote {DOC_DIR / cid}.md")

    T = ["<!-- generated by combos_docs.py; do not edit by hand -->", "",
         "## Per-combination results (Stage I + II unless noted; held-out poisoned + 64 clean test tools)", ""]
    for cid, cats in combos.items():
        T += per_combo_summary(cid, cats, args.base / cid)
    rep = args.base / "combos_report.md"
    if rep.exists():
        T += [demote(rep.read_text().split("\n", 1)[1]).strip(), ""]
    for cfg, title in (("s1-s2", "Stage I + II"), ("s2", "Stage II alone")):
        T += [f"## Recall per held-out category, averaged over the combinations that held it out — {title}", "",
              "Seed mean per combination, then mean over combinations (range across combinations in brackets).", ""]
        T += category_table(combos, args.base, cfg) + [""]
    (DOC_DIR / "tables.md").write_text("\n".join(T), encoding="utf-8")
    print(f"wrote {DOC_DIR / 'tables.md'}")


if __name__ == "__main__":
    main()
