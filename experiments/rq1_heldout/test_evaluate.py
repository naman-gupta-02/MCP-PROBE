"""Metric checks for the RQ1 evaluator on synthetic rows (no MCPTox data).

  uv run pytest -q experiments/rq1_heldout
"""

from experiments.rq1_heldout.evaluate import compute_metrics, flat


def _row(i, poisoned, cat=None, paradigm=None, desc="text"):
    return {"case_id": f"c{i}", "server": "s", "is_poisoned": poisoned, "risk_category": cat,
            "paradigm": paradigm, "test_cell": "x", "description": desc}


def _pred(blocked):
    return {"blocked": blocked, "stage": "s2", "s2_score": None, "rules": []}


def _data():
    # A: 10 poisoned, 9 caught. B: 2 poisoned, 0 caught. 4 clean (1 empty): 2 flagged, both non-empty.
    rows, blocked = [], []
    for i in range(10):
        rows.append(_row(i, True, "A", "P1" if i < 5 else "P2"))
        blocked.append(i < 9)
    for i in range(10, 12):
        rows.append(_row(i, True, "B", "P3"))
        blocked.append(False)
    for i, (desc, b) in enumerate([("t", True), ("t", True), ("t", False), ("", False)], start=12):
        rows.append(_row(i, False, desc=desc))
        blocked.append(b)
    return rows, [_pred(b) for b in blocked]


def test_combined_accuracy_is_pooled_not_mean():
    m = compute_metrics(*_data())
    cp = m["combined_poisoned"]
    assert (cp["n"], cp["correct"], cp["incorrect"]) == (12, 9, 3)
    assert cp["accuracy"] == 9 / 12
    assert cp["unweighted_mean_of_categories"] == (0.9 + 0.0) / 2  # differs from pooled on unequal n


def test_category_rows_are_recall_and_with_clean_metrics():
    m = compute_metrics(*_data())
    a = m["categories"]["A"]
    assert (a["n"], a["correct"], a["accuracy"], a["precision"]) == (10, 9, 0.9, None)
    assert a["confusion"] == {"tp": 9, "fn": 1, "fp": 0, "tn": 0}
    w = a["with_clean"]  # A's poisoned + all 4 clean tools
    assert (w["tp"], w["fp"], w["fn"], w["tn"]) == (9, 2, 1, 2)
    assert w["precision"] == 9 / 11


def test_overall_with_clean_and_fpr():
    m = compute_metrics(*_data())
    wc = m["with_clean"]
    assert (wc["n"], wc["tp"], wc["fp"], wc["fn"], wc["tn"]) == (16, 9, 2, 3, 2)
    assert wc["accuracy"] == 11 / 16
    assert m["clean"]["fpr"] == 2 / 4
    assert m["clean"]["fpr_nonempty"] == 2 / 3
    assert m["by_paradigm_recall"]["P2"] == {"n": 5, "correct": 4, "recall": 0.8}
    assert m["by_test_cell_recall"] == {"x": {"n": 12, "correct": 9, "recall": 0.75}}  # poisoned rows only
    f = flat(m)
    assert f["combined_accuracy"] == 9 / 12 and f["acc[B]"] == 0.0 and f["n[A]"] == 10
    assert f["cell[x]"] == 0.75 and f["ncell[x]"] == 12


def test_block_everything_scores_full_category_accuracy():
    rows, preds = _data()
    m = compute_metrics(rows, [_pred(True) for _ in preds])
    assert m["combined_poisoned"]["accuracy"] == 1.0
    assert m["clean"]["fpr"] == 1.0
