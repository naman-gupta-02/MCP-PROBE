"""Checks for the held-out combinations (selection rule and split files; counts only, no case text).

  uv run pytest -q experiments/rq1_heldout
"""

import json
from collections import Counter

import pytest

from experiments.rq1_heldout.combos import BASE_SPLIT, COMBO_DIR, ROOT, cmd_build, pool, select

FIRST_RUN = set(json.loads(BASE_SPLIT.read_text())["held_out_categories"])


def test_selection_is_reproducible_and_matches_committed_file():
    committed = json.loads((COMBO_DIR / "combos.json").read_text())
    assert select() == committed  # same seed -> same 8 combinations


def test_selection_is_balanced_and_avoids_first_run_categories():
    sel = select()
    combos = list(sel["combos"].values())
    assert len(combos) == 8 and len({tuple(c) for c in combos}) == 8
    assert all(len(c) == 3 for c in combos)
    assert set(pool()).isdisjoint(FIRST_RUN | {"Other"})
    counts = Counter(c for combo in combos for c in combo)
    assert set(counts) == set(pool()) and all(3 <= n <= 4 for n in counts.values())


def test_combo_split_files_keep_the_server_split():
    base = json.loads(BASE_SPLIT.read_text())["server_split"]
    for cid, cats in json.loads((COMBO_DIR / "combos.json").read_text())["combos"].items():
        f = json.loads((COMBO_DIR / f"{cid}.json").read_text())
        assert f["held_out_categories"] == cats and f["server_split"] == base


@pytest.mark.skipif(not (ROOT / "data/raw/MCPTox-Benchmark/response_all.json").exists(), reason="needs raw MCPTox")
def test_built_split_puts_held_out_categories_only_in_test(tmp_path, capsys):
    cmd_build("c1", tmp_path)
    held = set(json.loads((COMBO_DIR / "c1.json").read_text())["held_out_categories"])
    rows = {s: [json.loads(l) for l in open(tmp_path / "data" / f"{s}.jsonl")] for s in ("tune", "val", "test")}
    assert not any(r["risk_category"] in held for s in ("tune", "val") for r in rows[s])
    assert sum(r["risk_category"] in held for r in rows["test"]) == 221
    # The first run's held-out categories are ordinary training categories here.
    assert FIRST_RUN <= {r["risk_category"] for r in rows["tune"] if r["is_poisoned"]}
