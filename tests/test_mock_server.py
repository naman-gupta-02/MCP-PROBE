"""Tests for the inert mock MCP server (needs the mcp SDK; no network)."""

from __future__ import annotations

import anyio

from servers.call_log import CallLog
from servers.mock_server import build_server, load_spec

SPEC = {
    "name": "mail",
    "instructions": "test",
    "tools": [
        {"name": "list_messages", "description": "List subjects.", "params": ["folder"], "response": "a, b"},
        {"name": "send_message", "description": "Send a message. [DESC_MARKER]",
         "params": ["to", "body"], "response": "queued"},
    ],
}


def test_tools_exposed_with_descriptions_and_schema(tmp_path):
    log = CallLog(tmp_path / "m.jsonl", server="mail", run_id="r")
    srv = build_server(SPEC, log)
    tools = {t.name: t for t in anyio.run(srv.list_tools)}
    assert set(tools) == {"list_messages", "send_message"}
    # the full (possibly poisoned) description text is what the agent/detector sees
    assert "[DESC_MARKER]" in tools["send_message"].description
    assert set(tools["send_message"].input_schema["properties"]) == {"to", "body"}


def test_call_is_inert_and_logged_with_args(tmp_path):
    p = tmp_path / "m.jsonl"
    log = CallLog(p, server="mail", run_id="r")
    srv = build_server(SPEC, log)
    res = anyio.run(lambda: srv.call_tool("send_message", {"to": "x@y", "body": "hi"}))
    # returns only the canned decoy -- nothing real happened
    assert res.content[0].text == "queued"
    # but the call, with its arguments, is in the log for the judge to score
    rows = CallLog.read(p)
    assert len(rows) == 1
    assert rows[0]["tool"] == "send_message"
    assert rows[0]["arguments"] == {"to": "x@y", "body": "hi"}


def test_load_clean_spec_from_disk():
    spec = load_spec("configs/servers/mail_clean.yaml")
    assert spec["name"] == "mail"
    assert {t["name"] for t in spec["tools"]} == {"list_messages", "read_message", "send_message"}
