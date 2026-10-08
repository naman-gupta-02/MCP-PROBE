# MCP-PROBE

Team 12, USC CSCI 544. We test whether existing MCP tool-poisoning detectors (MCP-Guard, MCP Guardian) still work outside the conditions they were built for. See `CLAUDE.md` for project context and `DECISIONS.md` for the decision log.

## Setup

1. Install [uv](https://docs.astral.sh/uv/).
2. `uv sync` — creates `.venv` with Python 3.11 and the locked dependencies.
3. `cp .env.example .env` and fill in keys locally (never commit `.env`).
4. Get the data: `git clone https://github.com/zhiqiangwang4/MCPTox-Benchmark data/raw/MCPTox-Benchmark`
   (check out the commit recorded in `data/splits/split_report.md`).
5. `uv run python scripts/build_splits.py` — writes `data/processed/{tune,val,test}.jsonl`.
6. `uv run pytest`

Test data is guarded: `data.loader.load_cases("test")` raises unless `FINAL_EVAL=1` is set. Don't look at held-out cases while tuning.

## Branch workflow

- `main` is protected; nobody pushes to it directly.
- One branch per area, named `<area>/<short-topic>` (e.g. `proxy/basic-filter`, `detectors/mcp-guard`).
- All changes go in by pull request with at least one review from a teammate.
