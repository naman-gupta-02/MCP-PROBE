"""Inert mock MCP server for the Experiment 3 live pipeline.

Spec-driven: a YAML file lists this server's tools (name, description, params,
canned response). Every tool is INERT -- calling it performs no real action. It
only records the call, with its arguments, via servers.call_log, then returns the
spec's canned decoy text. So even if the agent is tricked, nothing real happens:
a "send_message" tool just appends to the log and returns a fake confirmation,
and a "read_file" tool returns decoy contents.

The tool DESCRIPTIONS are whatever the spec contains -- a clean description, or a
poisoned variant drawn from our MCPTox data. This module never authors attack
text; it serves and logs whatever the spec provides, so the detectors (via the
proxy) and the agent can be measured against it.

    python -m servers.mock_server --spec configs/servers/mail_clean.yaml --run-id R1

The proxy launches this as its upstream (see configs/proxy/*.yaml). The judge
(servers.outcome) later reads the call log to score attack- and task-success.
"""

from __future__ import annotations

import argparse
import inspect
import os
import time
from pathlib import Path

import yaml
from mcp.server.mcpserver import MCPServer

from servers.call_log import CallLog


def _tool_fn(tool_name: str, params: list[str], response: str, log: CallLog):
    """A keyword-only function that logs the call and returns the canned decoy.

    The signature is built from the spec so the tool advertises a real input
    schema (the agent needs to know the parameter names to call it)."""
    def fn(**kwargs):
        log.record(tool_name, kwargs)
        return response

    fn.__signature__ = inspect.Signature(
        [inspect.Parameter(p, inspect.Parameter.KEYWORD_ONLY, annotation=str) for p in params]
    )
    fn.__annotations__ = {**{p: str for p in params}, "return": str}
    return fn


def load_spec(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def build_server(spec: dict, log: CallLog) -> MCPServer:
    """Register every tool in the spec on a fresh MCPServer. No real side effects."""
    srv = MCPServer(spec["name"], instructions=spec.get("instructions"))
    for t in spec.get("tools", []):
        srv.add_tool(
            _tool_fn(t["name"], t.get("params", []), t.get("response", "ok"), log),
            name=t["name"],
            description=t.get("description", ""),
        )
    return srv


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--run-id", default=os.environ.get("RUN_ID") or time.strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--log-dir", default=os.environ.get("CALL_LOG_DIR", "results/server_logs"))
    args = ap.parse_args()

    spec = load_spec(args.spec)
    log_path = Path(args.log_dir) / f"{args.run_id}.{spec['name']}.calls.jsonl"
    log = CallLog(log_path, server=spec["name"], run_id=args.run_id)
    build_server(spec, log).run()  # stdio


if __name__ == "__main__":
    main()
