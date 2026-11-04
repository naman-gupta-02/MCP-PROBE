# agent/ — LangGraph agent for the live pipeline (Experiment 3)

`runner.py` launches the proxy as a stdio MCP subprocess from a condition config
(`configs/proxy/exp3_{none,mcpguard,guardian}.yaml`), lists the tools the proxy
exposes (already filtered by that condition's detector), bridges each to a
LangChain tool, and runs a ChatGroq ReAct agent on a task prompt.

    python -m agent.runner --config configs/proxy/exp3_none.yaml \
        --prompt "Summarise my latest message." --run-id R1

Every tool call goes agent → proxy → inert mock server, which logs it; the run_id
is threaded through so the proxy decision log and the server call log line up for
the judge (`servers.outcome`). Running the agent needs `GROQ_API_KEY` (from `.env`)
and spends Groq quota. The MCP→LangChain bridge is unit-tested offline.
