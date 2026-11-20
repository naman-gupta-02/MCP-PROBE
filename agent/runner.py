"""LangGraph agent for the Experiment 3 live pipeline.

Flow:  agent  -->  proxy (detector inside)  -->  inert mock server

The agent launches the proxy as a stdio MCP subprocess from one of the condition
configs (configs/proxy/exp3_*.yaml), lists the tools the proxy exposes -- already
filtered by that condition's detector -- bridges them to LangChain tools, and runs
a ReAct agent (ChatGroq) on a task prompt. Every tool call travels through the
proxy to the inert mock server, which records it; the judge (servers.outcome)
scores the run afterwards from that log. One ``run_id`` ties the proxy's decision
log and the server's call log together.

    python -m agent.runner --config configs/proxy/exp3_none.yaml \
        --prompt "Summarise my latest message." --run-id R1

Running the agent needs GROQ_API_KEY (loaded from .env) and spends Groq quota, so
it is a separate step from the offline-testable bridge below.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from langchain_core.tools import StructuredTool
from mcp import Client, StdioServerParameters

REPO = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "openai/gpt-oss-120b"


def _bridge_tool(client, mcp_tool) -> StructuredTool:
    """Wrap one proxy-exposed MCP tool as a LangChain tool the agent can call.

    The LangChain tool keeps the MCP tool's name, (possibly poisoned) description
    and input schema, and forwards calls to the proxy via the MCP client.
    """
    name = mcp_tool.name

    async def _call(**kwargs):
        res = await client.call_tool(name, kwargs)
        if res.structured_content is not None:
            return res.structured_content
        return "\n".join(getattr(c, "text", "") or "" for c in (res.content or []))

    return StructuredTool.from_function(
        coroutine=_call,
        name=name,
        description=mcp_tool.description or "",
        args_schema=mcp_tool.input_schema,
        infer_schema=False,
    )


def _prepare_config(base_config: str | Path, run_id: str, call_log_dir: str) -> tuple[Path, str]:
    """Write a per-run proxy config that threads run_id + call-log dir down to the
    upstream mock server (via upstream.env), so the proxy's decision log and the
    server's call log share one run_id. Returns (temp_config_path, upstream_name)."""
    cfg = yaml.safe_load(Path(base_config).read_text(encoding="utf-8"))
    cfg["run_id"] = run_id
    up = cfg.setdefault("upstream", {})
    env = dict(up.get("env") or {})
    env["RUN_ID"] = run_id
    env["CALL_LOG_DIR"] = call_log_dir
    up["env"] = env
    tmp = Path(tempfile.mkdtemp(prefix="exp3-")) / "proxy.run.yaml"
    tmp.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return tmp, up["name"]


@asynccontextmanager
async def proxied_tools(base_config: str | Path, run_id: str, call_log_dir: str = "results/server_logs"):
    """Launch the proxy for a condition and yield (client, tools, server_call_log_path)."""
    tmp_cfg, server_name = _prepare_config(base_config, run_id, call_log_dir)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "proxy", "--config", str(tmp_cfg), "--run-id", run_id],
        cwd=str(REPO),
    )
    call_log_path = Path(call_log_dir) / f"{run_id}.{server_name}.calls.jsonl"
    async with Client(params, read_timeout_seconds=60) as client:
        listed = await client.list_tools()
        yield client, [_bridge_tool(client, t) for t in listed.tools], call_log_path


def _ensure_groq_key() -> None:
    """ChatGroq wants a single GROQ_API_KEY. Load .env and, if only the project's
    comma-separated GROQ_API_KEYS is set, use its first key."""
    from attacker.llm import load_dotenv

    load_dotenv()
    if not os.environ.get("GROQ_API_KEY"):
        keys = [k.strip() for k in os.environ.get("GROQ_API_KEYS", "").split(",") if k.strip()]
        if keys:
            os.environ["GROQ_API_KEY"] = keys[0]


def build_agent(tools, model: str = DEFAULT_MODEL, temperature: float = 0.0, system: str | None = None):
    """A ReAct agent over the bridged tools. Imported lazily so the bridge stays testable offline."""
    from langchain_groq import ChatGroq
    from langgraph.prebuilt import create_react_agent

    _ensure_groq_key()
    llm = ChatGroq(model=model, temperature=temperature)
    return create_react_agent(llm, tools, prompt=system)


async def run_task(proxy_config, run_id, prompt, model: str = DEFAULT_MODEL, system: str | None = None):
    """Run one task end-to-end and return the agent's final state."""
    async with proxied_tools(proxy_config, run_id) as (_client, tools, call_log_path):
        agent = build_agent(tools, model=model, system=system)
        state = await agent.ainvoke({"messages": [("user", prompt)]})
        return {"state": state, "call_log": str(call_log_path)}


def main() -> None:
    import anyio

    from attacker.llm import load_dotenv  # reuse the .env reader -> GROQ_API_KEY for ChatGroq

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, help="proxy condition config (configs/proxy/exp3_*.yaml)")
    ap.add_argument("--prompt", required=True, help="the user task")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--system", default=None, help="optional system prompt")
    args = ap.parse_args()

    load_dotenv()
    result = anyio.run(lambda: run_task(args.config, args.run_id, args.prompt, args.model, args.system))
    final = result["state"]["messages"][-1]
    print(getattr(final, "content", final))
    print(f"[call log: {result['call_log']}]", file=sys.stderr)


if __name__ == "__main__":
    main()
