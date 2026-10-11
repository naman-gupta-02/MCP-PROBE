"""Regex Web Application Firewall (WAF) from MCP Guardian.

Kumar et al. (2025) do not publish their ruleset. Sections 3.2, 3.4.1 and 3.4.2
name the indicator families the WAF flags: SQL injection strings, <script>
tags, destructive shell commands, and references to sensitive files (SSH keys
in particular) or environment variables. Section 4.1 gives the only concrete
pattern, rm\\s+-rf. WAF_RULES implements exactly those families.

The rules were written from the paper text before any MCPTox data was opened,
and they have not been changed since (fingerprint 9decc37e4f86). They are
deliberately not tuned to any benchmark: Team 12 tests MCP Guardian as
published, as the simple baseline.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

EXCERPT_CHARS = 80


@dataclass(frozen=True)
class WafRule:
    name: str
    pattern: str
    source: str
    """Where the rule comes from, so every rule can be traced back to the paper."""

    regex: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "regex", re.compile(self.pattern, re.IGNORECASE))


WAF_RULES: tuple[WafRule, ...] = (
    # Destructive shell commands (Sections 3.2, 3.4.1, 4.1).
    WafRule(
        "rm_rf",
        r"\brm\s+(-[a-z]*(rf|fr)[a-z]*|-r\s+-f|-f\s+-r|--recursive|--no-preserve-root)\b",
        "Sec. 4.1: rm\\s+-rf",
    ),
    WafRule(
        "destructive_shell",
        r"\b(mkfs(\.\w+)?|shred)\b|\bdd\s+if=|:\(\)\s*\{|\bchmod\s+(-R\s+)?777\s+/|>\s*/dev/sd[a-z]",
        "Sec. 3.4.1: destructive shell commands",
    ),
    WafRule(
        "remote_code_exec",
        r"\b(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b|\bnc\s+(-\w+\s+)*-e\b",
        "Sec. 2.3.1 (5): command injection",
    ),
    # SQL injection signatures (Sections 3.2, 3.4.2, 4.3).
    WafRule("sql_drop", r"\b(drop|truncate)\s+(table|database|schema)\b", "Sec. 4.3: drop table"),
    WafRule(
        "sql_tautology",
        r"['\"]\s*or\s+['\"]?(\w+)['\"]?\s*=\s*['\"]?\1\b",
        "Sec. 3.4.1: SQL injection strings",
    ),
    WafRule("sql_union", r"\bunion\s+(all\s+)?select\b", "Sec. 3.4.1: SQL injection strings"),
    # Script tags (Section 3.4.2).
    WafRule("script_tag", r"<\s*script\b|\bjavascript\s*:", "Sec. 3.4.2: <script> tags"),
    # Sensitive files and environment variables (Sections 3.4.1, 2.3.1).
    WafRule(
        "ssh_key",
        r"\.ssh\b|\bid_(rsa|dsa|ecdsa|ed25519)\b|\bauthorized_keys\b",
        "Sec. 3.4.1: references to SSH files",
    ),
    WafRule(
        "sensitive_file",
        r"\bmcp\.json\b|\bclaude_desktop_config\.json\b|\.aws/credentials\b|/etc/(passwd|shadow)\b"
        r"|\.netrc\b|\.git-credentials\b|\.kube/config\b|(^|[\s/'\"~])\.env\b",
        "Sec. 3.4.1: references to sensitive files; Sec. 2.3.1 (1): ~/.cursor/mcp.json",
    ),
    WafRule(
        "env_secret",
        r"\$\{?\w*(key|token|secret|passw(or)?d|credential)\w*\}?|\bos\.environ\b|\bprocess\.env\b"
        r"|\bprintenv\b|\bgetenv\s*\(",
        "Sec. 3.4.1: references to environment variables; Sec. 3.4: secrets or tokens",
    ),
    WafRule("path_traversal", r"(\.\.[/\\]){2,}", "Sec. 3.4.1: references to sensitive files"),
)


@dataclass(frozen=True)
class WafMatch:
    rule: str
    field: str
    """Path to the matched string, e.g. ``description`` or ``inputSchema.properties.notes.description``."""
    excerpt: str


@dataclass(frozen=True)
class ScanResult:
    matches: tuple[WafMatch, ...] = ()

    @property
    def blocked(self) -> bool:
        return bool(self.matches)

    @property
    def rules(self) -> list[str]:
        return sorted({m.rule for m in self.matches})

    @property
    def reason(self) -> str:
        """Human-readable explanation, usable as the detector's stated reasoning."""
        if not self.matches:
            return "no WAF rule matched"
        return "; ".join(f"{m.rule} in {m.field or '<value>'}: {m.excerpt!r}" for m in self.matches)


class WafScanner:
    def __init__(self, rules: Iterable[WafRule] = WAF_RULES):
        self.rules = tuple(rules)
        names = [r.name for r in self.rules]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ValueError(f"duplicate WAF rule names: {sorted(duplicates)}")
        text = "\n".join(f"{r.name}\t{r.pattern}" for r in self.rules)
        self.fingerprint = hashlib.sha256(text.encode()).hexdigest()[:12]
        """Short hash of the active rules. Record it with results to show the ruleset was frozen."""

    def scan(self, value: Any, path: str = "") -> ScanResult:
        """Scan every string inside ``value`` (dict keys included) against every rule."""
        matches = []
        for field_path, text in _strings(value, path):
            for rule in self.rules:
                hit = rule.regex.search(text)
                if hit:
                    matches.append(WafMatch(rule.name, field_path, hit.group(0)[:EXCERPT_CHARS]))
        return ScanResult(tuple(matches))


def _strings(value: Any, path: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if isinstance(key, str):
                yield child_path, key
            yield from _strings(child, child_path)
    elif isinstance(value, (list, tuple)):
        for i, child in enumerate(value):
            yield from _strings(child, f"{path}[{i}]")
