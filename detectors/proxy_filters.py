"""Adapters that drop our existing detectors into the proxy's detector slot (Experiment 3).

The proxy picks a detector by dotted path and calls ``filter_tools(tools) -> subset``
(see proxy/detector_slot.py). These wrappers reuse the SAME MCP-Guard / MCP Guardian
checkers from Experiments 1-2 (``attacker.detectors.build``), so the live pipeline
scores tool descriptions with identical code -- there is no second detector
implementation to keep in sync. A detector may only BLOCK a tool here; the proxy
enforces (via ``check_subset``) that it cannot rewrite one.

Config example (the three Experiment 3 conditions differ only in this block):

    detector:
      class: detectors.proxy_filters:MCPGuard
      params: {ckpt_root: checkpoints/mcp_guard, variant: mcpguard_full}
"""

from __future__ import annotations

from typing import Any


class DetectorFilter:
    """Keep only the tools whose description a built detector does not block.

    The underlying detector is built lazily (it loads torch / a checkpoint), so the
    proxy process pays that cost once, on the first ``tools/list``. Pass ``_detector``
    to inject a ready checker (used by tests, to avoid loading a model).
    """

    def __init__(self, key: str, ckpt_root: str | None = None,
                 name: str | None = None, _detector: Any = None):
        self.key = key
        self.name = name or key
        self._ckpt_root = ckpt_root
        self._det = _detector

    def _detector(self) -> Any:
        if self._det is None:
            from attacker.detectors import build  # heavy (torch); import only when used
            self._det = build(self.key, self._ckpt_root)
        return self._det

    def filter_tools(self, tools: list) -> list:
        det = self._detector()
        kept = []
        for t in tools:
            desc = getattr(t, "description", None) or ""
            if not det.check(getattr(t, "name", "") or "", desc).blocked:
                kept.append(t)  # unchanged original object -> satisfies the subset contract
        return kept


class MCPGuard(DetectorFilter):
    """MCP-Guard (Stage I regex + Stage II classifier). ``variant`` picks the checkpoint."""

    def __init__(self, ckpt_root: str | None = None, variant: str = "mcpguard_full", **kw):
        super().__init__(variant, ckpt_root=ckpt_root, name=kw.pop("name", "mcp-guard"), **kw)


class MCPGuardian(DetectorFilter):
    """MCP Guardian: the regex/keyword WAF baseline (no checkpoint)."""

    def __init__(self, **kw):
        super().__init__("mcp_guardian", name=kw.pop("name", "mcp-guardian"), **kw)
