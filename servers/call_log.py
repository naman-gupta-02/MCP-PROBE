"""Append-only call log for the Experiment 3 live pipeline.

Our test MCP servers are inert mocks: a tool call performs NO real action, it
only records here that it was called and with what arguments, then returns a
canned decoy response. The judge (servers.outcome) reads this log afterwards to
decide, deterministically, two things per run:

  - did the agent perform the malicious action?  (attack_success)
  - did the agent still finish the user's task?   (task_success)

Keeping the record here, separate from the servers, means the judge never has to
trust the agent's own words -- it scores what the tools were actually asked to do.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path


class CallLog:
    """One JSONL file of tool calls. Thread-safe append; static reader."""

    def __init__(self, path: str | Path, server: str, run_id: str = ""):
        self.path = Path(path)
        self.server = server
        self.run_id = run_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(self, tool: str, arguments: dict | None = None) -> dict:
        """Log one call and return the record written. No side effects beyond the log."""
        rec = {
            "ts": time.time(),
            "server": self.server,
            "tool": tool,
            "arguments": arguments or {},
            "run_id": self.run_id,
        }
        line = json.dumps(rec, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
        return rec

    @staticmethod
    def read(path: str | Path) -> list[dict]:
        """All records in a log file (empty list if it does not exist)."""
        p = Path(path)
        if not p.is_file():
            return []
        return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
