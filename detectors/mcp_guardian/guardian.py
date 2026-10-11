"""MCP Guardian middleware (Kumar et al., 2025, Sections 3.2 to 3.4).

Two entry points:

* ``filter_tools(tools)`` is the detector slot in the Team 12 proxy. It runs the
  WAF over each tool's metadata (name, description, inputSchema, ...) and drops
  tools that match. The paper's WAF scans call *arguments*, so applying it to
  tool *descriptions* is our adaptation; the rules are unchanged.
* ``guarded_invoke_tool(name, arguments)`` is the paper's call-time path:
  token check, per-token rate limit, WAF on the arguments, then the original
  invoke function. It is a drop-in replacement for ``MCPServer.call_tool``.
"""

from __future__ import annotations

import hashlib
import inspect
import itertools
import json
import logging
import logging.handlers
import os
import queue
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, TypeVar
from urllib.parse import urlsplit

from .waf import WAF_RULES, ScanResult, WafRule, WafScanner

T = TypeVar("T")

TOKENS_ENV_VAR = "MCP_GUARDIAN_TOKENS"
PAYLOAD_LOG_CHARS = 500

_instance_ids = itertools.count()


class GuardianError(Exception):
    status = 400


class Unauthorized(GuardianError):
    status = 401


class Forbidden(GuardianError):
    status = 403


class TooManyRequests(GuardianError):
    status = 429


class WafBlocked(GuardianError):
    status = 403

    def __init__(self, message: str, scan: ScanResult):
        super().__init__(message)
        self.scan = scan


class SlidingWindowRateLimiter:
    """Allows at most ``max_requests`` per key within any ``window_seconds`` span."""

    def __init__(self, max_requests: int, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic):
        if max_requests < 1:
            raise ValueError("max_requests must be at least 1")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            return True


class MCPGuardian:
    name = "mcp_guardian"

    def __init__(
        self,
        valid_tokens: Iterable[str] | None = None,
        logfile_path: str | os.PathLike[str] | None = "mcp_guardian.log",
        max_requests_per_token: int = 5,
        remote_log_url: str | None = None,
        *,
        token_permissions: Mapping[str, Iterable[str]] | None = None,
        rate_window_seconds: float = 60.0,
        extra_rules: Iterable[WafRule] = (),
        token_param: str = "guardian_token",
        log_payloads: bool = True,
        alert: Callable[[dict[str, Any]], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        """
        Args:
            valid_tokens: Accepted API tokens. ``None`` reads a comma-separated
                list from the ``MCP_GUARDIAN_TOKENS`` environment variable.
            logfile_path: JSON-lines log file; ``None`` disables file logging.
            max_requests_per_token: Rate limit per token per window (paper default 5/min).
            remote_log_url: Optional HTTP(S) endpoint that receives each log record by POST.
            token_permissions: Optional map from token to the tool names it may call.
                Tokens listed here are valid even if absent from ``valid_tokens``.
            extra_rules: Domain-specific rules added to the paper's WAF (Sec. 3.4.2).
                Leave empty to test MCP Guardian as published.
            token_param: Argument key that carries the token in ``guarded_invoke_tool``.
                It is removed before the arguments are scanned or forwarded.
            log_payloads: Log call arguments and responses (truncated). Turn off when
                they may contain data that should not sit in a log file.
            alert: Called with the log record whenever a request or tool is blocked.
        """
        if valid_tokens is None:
            valid_tokens = [t.strip() for t in os.environ.get(TOKENS_ENV_VAR, "").split(",") if t.strip()]
        permissions = token_permissions or {}
        self._token_hashes = {_hash(t) for t in [*valid_tokens, *permissions]}
        self._permissions = {_hash(t): frozenset(tools) for t, tools in permissions.items()}

        self.waf = WafScanner([*WAF_RULES, *extra_rules])
        self.rate_limiter = SlidingWindowRateLimiter(max_requests_per_token, rate_window_seconds, clock)
        self.token_param = token_param
        self.log_payloads = log_payloads
        self.alert = alert
        self.original_invoke_tool: Callable[..., Any] | None = None

        # One logger per instance so two guardians never write into each other's files.
        self._logger = logging.getLogger(f"{__name__}.{next(_instance_ids)}")
        self._logger.setLevel(logging.INFO)
        # Records can carry call arguments and responses; keep them out of the host app's logs.
        self._logger.propagate = False
        self._handlers: list[logging.Handler] = []
        self._listener: logging.handlers.QueueListener | None = None
        if logfile_path is not None:
            file_handler = logging.FileHandler(logfile_path, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter("%(message)s"))
            self._add_handler(file_handler)
        if remote_log_url is not None:
            self._add_remote_handler(remote_log_url)
        if not self._handlers:
            # Stops logging's last-resort handler from printing blocked events to stderr.
            self._add_handler(logging.NullHandler())

    # ---- detector slot: tools/list ----

    def scan_tool(self, tool: Any) -> ScanResult:
        """Run the WAF over every string in a tool's metadata (dict or MCP ``Tool`` model)."""
        return self.waf.scan(_tool_as_dict(tool))

    def filter_tools(self, tools: Sequence[T]) -> list[T]:
        """Return ``tools`` without the ones the WAF flags, preserving order and type."""
        kept = []
        for tool in tools:
            scan = self.scan_tool(tool)
            record = {"event": "tools/list", "tool": _tool_name(tool), "ruleset": self.waf.fingerprint}
            if scan.blocked:
                self._emit(logging.WARNING, record, decision="blocked", rules=scan.rules, reason=scan.reason)
            else:
                kept.append(tool)
                self._emit(logging.INFO, record, decision="allowed")
        return kept

    # ---- call-time path: tools/call ----

    def check_request(self, tool_name: str, arguments: Mapping[str, Any] | None, token: str | None) -> None:
        """Raise a ``GuardianError`` if the call must not reach the server.

        Order follows the paper (Sec. 3.3): token, permissions, rate limit, WAF.
        ``arguments[token_param]`` is ignored, so the token is never scanned or logged.
        """
        arguments = {k: v for k, v in (arguments or {}).items() if k != self.token_param}
        token_hash = _hash(token) if token else None
        record = {"event": "tools/call", "tool": tool_name, "token": token_hash[:8] if token_hash else None}
        if self.log_payloads:
            record["arguments"] = _truncate(arguments)

        def deny(error: GuardianError, **extra: Any) -> GuardianError:
            self._emit(logging.WARNING, record, decision="blocked", status=error.status, reason=str(error), **extra)
            return error

        if token_hash is None or token_hash not in self._token_hashes:
            raise deny(Unauthorized("Unauthorized"))
        allowed_tools = self._permissions.get(token_hash)
        if allowed_tools is not None and tool_name not in allowed_tools:
            raise deny(Forbidden(f"Forbidden: token may not call {tool_name!r}"))
        if not self.rate_limiter.allow(token_hash):
            raise deny(TooManyRequests("429 Too Many Requests"))
        scan = self.waf.scan(arguments, "arguments")
        if scan.blocked:
            raise deny(WafBlocked("Request blocked by WAF scanning: " + ", ".join(scan.rules), scan), rules=scan.rules)

    async def guarded_invoke_tool(
        self,
        tool_name: str,
        arguments: Mapping[str, Any] | None = None,
        *args: Any,
        token: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Check the call, forward it to ``original_invoke_tool``, and log the response.

        The token is taken from ``token=`` or, failing that, popped from
        ``arguments[token_param]``. Extra positional and keyword arguments are
        passed through, so this can replace ``MCPServer.call_tool`` directly.
        """
        if self.original_invoke_tool is None:
            raise RuntimeError("set guardian.original_invoke_tool before calling guarded_invoke_tool")
        arguments = dict(arguments or {})
        carried_token = arguments.pop(self.token_param, None)
        token = token if token is not None else carried_token

        started = time.perf_counter()
        self.check_request(tool_name, arguments, token)
        guard_ms = (time.perf_counter() - started) * 1000

        result = self.original_invoke_tool(tool_name, arguments, *args, **kwargs)
        if inspect.isawaitable(result):
            result = await result

        record = {"event": "tools/call", "tool": tool_name, "token": _hash(token)[:8], "guard_ms": round(guard_ms, 3)}
        if self.log_payloads:
            record["arguments"] = _truncate(arguments)
            record["response"] = _truncate(result)
        self._emit(logging.INFO, record, decision="allowed")
        return result

    # ---- logging ----

    def close(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        for handler in self._handlers:
            self._logger.removeHandler(handler)
            handler.close()
        self._handlers.clear()

    def _add_handler(self, handler: logging.Handler) -> None:
        self._logger.addHandler(handler)
        self._handlers.append(handler)

    def _add_remote_handler(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError(f"remote_log_url must be an http(s) URL, got {url!r}")
        http_handler = logging.handlers.HTTPHandler(
            parts.netloc, parts.path or "/", method="POST", secure=parts.scheme == "https"
        )
        # POSTing on a background thread keeps network latency off the request path.
        records: queue.Queue[logging.LogRecord] = queue.Queue()
        self._listener = logging.handlers.QueueListener(records, http_handler)
        self._listener.start()
        self._add_handler(logging.handlers.QueueHandler(records))

    def _emit(self, level: int, record: dict[str, Any], **fields: Any) -> None:
        entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), **record, **fields}
        self._logger.log(level, json.dumps(entry, default=str))
        if self.alert is not None and entry.get("decision") == "blocked":
            try:
                self.alert(entry)
            except Exception as exc:  # noqa: BLE001 - a broken alert hook must not break the request path
                failure = {"ts": entry["ts"], "event": "alert_failed", "error": repr(exc)}
                self._logger.error(json.dumps(failure))


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _tool_as_dict(tool: Any) -> Any:
    if isinstance(tool, Mapping):
        return tool
    if hasattr(tool, "model_dump"):
        return tool.model_dump(mode="json", by_alias=True, exclude_none=True)
    return vars(tool)


def _jsonable(value: Any) -> Any:
    return value.model_dump(mode="json", by_alias=True, exclude_none=True) if hasattr(value, "model_dump") else value


def _tool_name(tool: Any) -> str | None:
    return tool.get("name") if isinstance(tool, Mapping) else getattr(tool, "name", None)


def _truncate(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(_jsonable(value), default=str)
    return text if len(text) <= PAYLOAD_LOG_CHARS else text[:PAYLOAD_LOG_CHARS] + "..."
