"""Offline test of the MCP->LangChain tool bridge (no proxy, no LLM, no network)."""

from __future__ import annotations

import anyio
from types import SimpleNamespace

from agent.runner import _bridge_tool


class _FakeRes:
    def __init__(self, text):
        self.structured_content = None
        self.content = [SimpleNamespace(text=text)]


class _FakeClient:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return _FakeRes(f"ran {name}")


def test_bridge_builds_tool_and_forwards_call():
    client = _FakeClient()
    mcp_tool = SimpleNamespace(
        name="send_message",
        description="Send a message. [DESC_MARKER]",
        input_schema={"type": "object",
                      "properties": {"to": {"type": "string"}, "body": {"type": "string"}},
                      "required": ["to", "body"]},
    )
    tool = _bridge_tool(client, mcp_tool)
    assert tool.name == "send_message"
    assert "[DESC_MARKER]" in tool.description          # the agent/detector sees the full description
    assert set(tool.args.keys()) == {"to", "body"}      # schema carried through
    out = anyio.run(lambda: tool.coroutine(to="a@b", body="hi"))
    assert client.calls == [("send_message", {"to": "a@b", "body": "hi"})]  # forwarded to the proxy
    assert "send_message" in out
