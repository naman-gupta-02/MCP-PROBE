"""Load processed MCPTox cases.

The test split is guarded: it only loads when FINAL_EVAL=1 is set, so nobody
tunes prompts, rules or thresholds on held-out data by accident.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

PROCESSED_DIR = Path(__file__).resolve().parent / "processed"
SPLITS = ("tune", "val", "test")


class HeldOutAccessError(RuntimeError):
    """Raised when the test split is requested without FINAL_EVAL=1."""


def load_cases(split: str, processed_dir: Path | None = None) -> list[dict]:
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}, got {split!r}")
    if split == "test" and os.environ.get("FINAL_EVAL") != "1":
        raise HeldOutAccessError(
            "Refusing to load the test split. Set FINAL_EVAL=1 only for the final evaluation run."
        )
    path = (processed_dir or PROCESSED_DIR) / f"{split}.jsonl"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Build the processed files first: uv run python scripts/build_splits.py"
        )
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
