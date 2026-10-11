"""Scoring reads only the team's tune/val split, never test."""

import pytest
from detectors.mcp_guardian.team_split import _to_example, load_split


def test_test_split_is_refused():
    with pytest.raises(ValueError, match="final evaluation"):
        load_split("test")


def test_null_description_becomes_empty_text():
    row = {
        "case_id": "clean::X::t",
        "server": "X",
        "tool_name": "t",
        "description": None,
        "is_poisoned": False,
        "paradigm": None,
        "risk_category": None,
    }
    assert _to_example(row).tool == {"name": "t", "description": ""}
