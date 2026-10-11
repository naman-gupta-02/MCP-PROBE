"""Load Team 12's official MCPTox split for scoring MCP Guardian.

The split is built by ``scripts/build_splits.py`` and read through the team's
``data/loader.py``, so the test split stays behind the team's ``FINAL_EVAL``
guard. This module only ever asks for ``tune`` and ``val``.

Records carry a tool name and description but no parameter schema, so the
detector sees ``{"name", "description"}`` only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from data.loader import load_cases

DEV_SPLITS = ("tune", "val")


@dataclass(frozen=True)
class Example:
    tool: dict[str, Any]
    poisoned: bool
    server: str
    category: str | None
    """MCPTox risk category; None for clean tools."""
    paradigm: str | None
    """Attack type P1/P2/P3; None for clean tools."""
    source: str
    """The team's case_id."""


def load_split(split: str, processed_dir: Path | None = None) -> list[Example]:
    if split not in DEV_SPLITS:
        raise ValueError(f"only {DEV_SPLITS} are loaded here; the test split is for the team's final evaluation")
    return [_to_example(row) for row in load_cases(split, processed_dir)]


def _to_example(row: dict) -> Example:
    # 37 MCPTox tools have no description (null); the detector then sees only the name.
    tool = {"name": row["tool_name"] or "", "description": row["description"] or ""}
    return Example(
        tool=tool,
        poisoned=row["is_poisoned"],
        server=row["server"],
        category=row["risk_category"],
        paradigm=row["paradigm"],
        source=row["case_id"],
    )
