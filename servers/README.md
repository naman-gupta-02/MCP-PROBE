# servers/ — test MCP servers + outcome judge for the live pipeline (Experiment 3)

**Inert mocks.** A tool call performs no real action; it records the call (with
arguments) via `call_log.py` and returns a canned decoy. Even if the agent is
tricked, nothing real happens.

- `mock_server.py` — a spec-driven MCP server. `python -m servers.mock_server --spec <spec.yaml>`.
  Reads `RUN_ID` / `CALL_LOG_DIR` from the env (the proxy threads these through).
- `call_log.py` — append-only JSONL of tool calls **with arguments** (the proxy logs names only).
- `outcome.py` — deterministic judge: `task_success` + `attack_success` by rule over the call log,
  plus a reader for the proxy's allow/block decisions (false-block rate).
- specs: `configs/servers/*.yaml`. Tool **descriptions** come from the spec — clean examples are
  committed; poisoned variants (from MCPTox data) are supplied separately and kept out of git.
