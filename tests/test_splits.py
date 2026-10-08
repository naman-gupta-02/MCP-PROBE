import json
from pathlib import Path

import pytest

from data.loader import PROCESSED_DIR, HeldOutAccessError, load_cases

ROOT = Path(__file__).resolve().parent.parent
SPLIT_DEF = json.loads((ROOT / "data" / "splits" / "server_split.json").read_text(encoding="utf-8"))
HELD_OUT = set(SPLIT_DEF["held_out_categories"])
SERVERS = SPLIT_DEF["server_split"]
TEST_CELLS = {"new_server_known_cat", "known_server_new_cat", "new_server_new_cat", "new_server_clean"}

needs_data = pytest.mark.skipif(
    not all((PROCESSED_DIR / f"{s}.jsonl").exists() for s in ("tune", "val", "test")),
    reason="processed files missing; run scripts/build_splits.py",
)


@pytest.fixture
def all_cases(monkeypatch):
    monkeypatch.setenv("FINAL_EVAL", "1")
    return {s: load_cases(s) for s in ("tune", "val", "test")}


def test_test_split_requires_final_eval(monkeypatch):
    monkeypatch.delenv("FINAL_EVAL", raising=False)
    with pytest.raises(HeldOutAccessError):
        load_cases("test")
    monkeypatch.setenv("FINAL_EVAL", "0")
    with pytest.raises(HeldOutAccessError):
        load_cases("test")


def test_missing_files_give_clear_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="build_splits.py"):
        load_cases("tune", processed_dir=tmp_path)


def test_unknown_split_rejected():
    with pytest.raises(ValueError):
        load_cases("train")


def test_server_split_disjoint_and_complete():
    train, val, test = (set(SERVERS[k]) for k in ("train", "val", "test"))
    assert not (train & val) and not (train & test) and not (val & test)
    assert len(train) == 30 and len(val) == 6 and len(test) == 9
    assert len(train | val | test) == 45


@needs_data
def test_no_held_out_category_in_tune_or_val(all_cases):
    for split in ("tune", "val"):
        assert not {c["risk_category"] for c in all_cases[split]} & HELD_OUT


@needs_data
def test_split_servers_match_assignment(all_cases):
    assert {c["server"] for c in all_cases["tune"]} <= set(SERVERS["train"])
    assert {c["server"] for c in all_cases["val"]} <= set(SERVERS["val"])
    for c in all_cases["test"]:
        assert c["server"] in SERVERS["test"] or c["risk_category"] in HELD_OUT
    all_servers = {c["server"] for cases in all_cases.values() for c in cases}
    assert all_servers == {s for v in SERVERS.values() for s in v}


@needs_data
def test_each_case_in_exactly_one_split(all_cases):
    ids = [c["case_id"] for cases in all_cases.values() for c in cases]
    assert len(ids) == len(set(ids))
    for split, cases in all_cases.items():
        assert all(c["split"] == split for c in cases)
    assert sum(len(v) for v in all_cases.values()) == len(ids)
    report = (ROOT / "data" / "splits" / "split_report.md").read_text(encoding="utf-8")
    n_poison = sum(c["is_poisoned"] for cases in all_cases.values() for c in cases)
    n_clean = len(ids) - n_poison
    assert f"| Poisoned cases kept (`wrong_data == 0`) | {n_poison} |" in report
    assert f"| Clean tools | {n_clean} |" in report


@needs_data
def test_test_cell_only_on_test(all_cases):
    for c in all_cases["test"]:
        assert c["test_cell"] in TEST_CELLS
        assert (c["test_cell"] == "new_server_clean") == (not c["is_poisoned"])
    for split in ("tune", "val"):
        assert all(c["test_cell"] is None for c in all_cases[split])
