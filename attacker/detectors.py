"""The six detectors under attack, behind one interface: check(tool_name, description) -> Check.

Same setups as RQ1 (experiments/rq1_heldout/evaluate.py): MCP-Guard variants run Stage I + II
in paper mode (block if a regex fires or P > T_u = 0.45); fine-tuned variants use the seed-0
checkpoint of the first training sweep; MCP Guardian is the 11-rule WAF.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DETECTORS = {  # key -> (display name, checkpoint dir name or None)
    "frozen_mcpguard": ("Frozen MCP-Guard", None),
    "mcpguard_full": ("MCP-Guard Full", "mcpguard_full_seed0"),
    "mcpguard_head": ("MCP-Guard Head-Only", "mcpguard_head_seed0"),
    "e5base_full": ("Base E5 Full", "e5base_full_seed0"),
    "e5base_head": ("Base E5 Head-Only", "e5base_head_seed0"),
    "mcp_guardian": ("MCP Guardian", None),
}


@dataclass
class Check:
    blocked: bool
    stage: str                      # s1 | s2 | waf | empty | pass
    score: float | None = None      # Stage II P(poisoned); None for Guardian
    rules: list[str] = field(default_factory=list)  # regex detectors / WAF rules that fired


class Detector:
    def __init__(self, key: str, check_fn, tag: str):
        self.key, self.name = key, DETECTORS[key][0]
        self._check = check_fn
        self.tag = tag  # what exactly was loaded, for the run metadata

    def check(self, tool_name: str | None, description: str) -> Check:
        return self._check(tool_name, description)


def build(key: str, ckpt_root: Path | None = None, device: str = "auto") -> Detector:
    if key == "mcp_guardian":
        from detectors.mcp_guardian.waf import WafScanner

        s = WafScanner()

        def check(name, desc):
            res = s.scan({"name": name or "", "description": desc or ""})  # same input as RQ1
            return Check(res.blocked, "waf" if res.blocked else "pass", None, res.rules)

        return Detector(key, check, f"MCP Guardian WAF, {len(s.rules)} rules, fingerprint {s.fingerprint}")

    from detectors.mcp_guard.pipeline import DEFAULT_CONFIG, MCPGuard

    ckpt = DETECTORS[key][1]
    s2 = None
    if ckpt:
        if ckpt_root is None:
            raise ValueError(f"{key} needs --ckpt-root (folder holding {ckpt}/)")
        path = Path(ckpt_root) / ckpt
        if not path.is_dir():
            raise FileNotFoundError(f"checkpoint not found: {path}")
        s2 = {"loader": "finetuned", "path": str(path), "device": device}
    g = MCPGuard.from_config(DEFAULT_CONFIG, mode="paper", stages=("s1", "s2"), stage2=s2)

    def check(name, desc):
        v = g.scan(name, desc)
        return Check(v.blocked, v.stage if v.blocked else "pass", v.s2_score, sorted({h["detector"] for h in v.s1_hits}))

    return Detector(key, check, f"{g.s2.cache_tag} | stages=s1+s2 tu={g.tu}")
