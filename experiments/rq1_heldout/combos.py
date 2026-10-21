"""Held-out category combinations for the RQ1 robustness check (split 2).

The first RQ1 run held out Credential Leakage, Instruction Tampering and Financial Loss.
To check the result isn't specific to those three, we repeat the whole pipeline (retrain
all fine-tuned models, re-evaluate all six detectors) on 8 other 3-category hold-outs.

Selection rule, fixed before any results: pool = the 7 categories not held out in the
first run ("Other", 4 cases, excluded). From the 35 possible 3-of-7 combinations, draw
8 at random with seed SEED, redrawing until every category is held out 3 or 4 times
(balanced coverage). Servers stay exactly as in data/splits/server_split.json.

  uv run python -m experiments.rq1_heldout.combos select            # writes combos/*.json
  uv run python -m experiments.rq1_heldout.combos build --combo c1 --out <dir>

`build` reuses scripts/build_splits.py unchanged (only its input/output paths are
redirected) and writes <dir>/data/{tune,val,test}.jsonl and <dir>/split_report.md.
"""

from __future__ import annotations

import argparse
import collections
import itertools
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_SPLIT = ROOT / "data" / "splits" / "server_split.json"
COMBO_DIR = Path(__file__).resolve().parent / "combos"
SEED = 2026
N_COMBOS = 8
EXCLUDED = {"Other"}  # 4 cases; too small to hold out


def pool() -> list[str]:
    """Categories in the first run's tune split (i.e. not held out then), minus 'Other'."""
    from data.loader import load_cases

    first = set(json.loads(BASE_SPLIT.read_text(encoding="utf-8"))["held_out_categories"])
    cats = sorted({r["risk_category"] for r in load_cases("tune") if r["is_poisoned"]} - EXCLUDED)
    assert len(cats) == 7 and not set(cats) & first, cats
    return cats


def select() -> dict:
    cats = pool()
    all_combos = list(itertools.combinations(cats, 3))
    rng = random.Random(SEED)
    for attempt in itertools.count(1):
        picked = sorted(rng.sample(all_combos, N_COMBOS))
        counts = collections.Counter(c for combo in picked for c in combo)
        if all(3 <= counts[c] <= 4 for c in cats):
            break
    return {
        "rule": f"seeded random draw (seed {SEED}) of {N_COMBOS} of the {len(all_combos)} 3-of-7 combinations, "
                "redrawn until each category is held out 3-4 times; pool excludes the first run's held-out "
                "categories and 'Other'",
        "seed": SEED, "attempts": attempt, "pool": cats,
        "times_held_out": dict(sorted(counts.items())),
        "combos": {f"c{i + 1}": list(c) for i, c in enumerate(picked)},
    }


def cmd_select() -> None:
    sel = select()
    base = json.loads(BASE_SPLIT.read_text(encoding="utf-8"))
    COMBO_DIR.mkdir(exist_ok=True)
    (COMBO_DIR / "combos.json").write_text(json.dumps(sel, indent=2) + "\n", encoding="utf-8")
    for cid, cats in sel["combos"].items():
        (COMBO_DIR / f"{cid}.json").write_text(json.dumps({
            "combo": cid, "held_out_categories": cats, "server_split": base["server_split"],
        }, indent=2) + "\n", encoding="utf-8")
        print(f"{cid}: {', '.join(cats)}")
    print(f"times held out: {sel['times_held_out']}  (attempts: {sel['attempts']})")


def cmd_build(combo: str, out: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_splits as bs  # the team's split builder, used unchanged

    out.mkdir(parents=True, exist_ok=True)
    bs.SPLIT_FILE = COMBO_DIR / f"{combo}.json"
    bs.PROCESSED_DIR = out / "data"
    bs.REPORT_FILE = out / "split_report.md"
    res = bs.build()
    bs.write_report(res)
    ct = collections.Counter((r["split"], r["is_poisoned"]) for r in res["rows"])
    held = res["held_out"]
    n_held = sum(1 for r in res["rows"] if r["risk_category"] in held)
    assert all(r["split"] == "test" for r in res["rows"] if r["risk_category"] in held)
    print(f"{combo} held out {sorted(held)}: {n_held} cases; "
          + "  ".join(f"{s} {ct[(s, True)]}+{ct[(s, False)]}" for s in bs.SPLITS) + f"  -> {bs.PROCESSED_DIR}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("select")
    b = sub.add_parser("build")
    b.add_argument("--combo", required=True)
    b.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    cmd_select() if args.cmd == "select" else cmd_build(args.combo, args.out)


if __name__ == "__main__":
    main()
