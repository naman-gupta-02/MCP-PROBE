# RQ3: live pipeline (Experiment 3)

Measure what the detectors actually buy you when a real agent runs against
(poisoned) MCP servers through the proxy. For each task we run the agent under
three conditions — **no detector**, **MCP-Guard**, **MCP Guardian** — many
trials each, and report one table:

| condition | attack-success | task-success | false-block | latency |
|---|---|---|---|---|

- **attack-success** — the agent performed the malicious action (lower is better).
- **task-success** — the agent still completed the benign task (higher is better).
- **false-block** — a benign tool the task needs was dropped by the detector (the
  utility cost of filtering; lower is better).
- **latency** — mean wall-clock per run (the proxy + detector overhead).

The point is the **security/utility trade-off**: a detector that blocks the
attack is only useful if the agent can still do the real task and benign tools
aren't over-blocked.

## Architecture (already built, on `main`)

```
agent (LangGraph ReAct)  ->  proxy (detector filters tools/list)  ->  inert mock server
         |                          |                                       |
   agent/runner.py          configs/proxy/exp3_*.yaml              servers/mock_server.py
                                    |                                       |
                          proxy decision log                        server call log
                                    \                                      /
                                     servers/outcome.py  (deterministic judge)
```

- **Inert servers.** Every tool is a mock: it logs the call (with arguments) and
  returns a canned decoy. Nothing real ever happens, even if the agent is
  tricked — a "send_message" just appends to a log. See `servers/mock_server.py`.
- **Deterministic judge.** `servers/outcome.py` scores task- and attack-success
  from the logged calls by data rules, not an LLM's opinion — reproducible and
  grounded in what the tools were actually asked to do.
- **One `run_id`** ties the proxy decision log and the server call log together.

## The driver (this experiment)

`agent/experiment.py` runs the whole suite and writes the table:

```bash
python -m agent.experiment --tasks configs/exp3/tasks.yaml --trials 10 \
    --model openai/gpt-oss-120b --out results/rq3
# writes results/rq3/{summary.csv, summary.json, SUMMARY.md, per_run.jsonl}
```

It loops task × condition × trial, runs the agent, then scores each run's two
logs (`judge_log` for task/attack success, `tool_decisions` for false blocks)
and aggregates per condition. The agent runner is injectable, so the
loop/judge/aggregate logic is tested offline with no LLM (`tests/test_experiment.py`).

## What the team still needs to supply

The harness is complete; these are **data**, drawn from MCPTox, not something the
harness can invent:

1. **Poisoned server specs** — spec files like `configs/servers/mail_clean.yaml`
   but carrying poisoned tool descriptions from MCPTox, one per attack type
   (P1 / P2 / P3). Kept out of git (like `attacker/rewrite_prompt.txt`); point
   each task's `server_spec` at one.
2. **A task set** — see `configs/exp3/tasks.example.yaml` for the schema: per task
   a `prompt`, `success_rule`, `attack_rule`, `clean_tools`, `paradigm`, and
   `server_spec`.

## Decisions (recommended defaults)

- **Agent LLM:** `openai/gpt-oss-120b` (consistent with Exp2).
- **MCP-Guard Stage III:** off for the main comparison (matches RQ1/RQ2; the
  band-gate finding shows paper-mode Stage III never sees score-minimized
  rewrites). Optionally add one extra "S3-on" condition.
- **Scale:** ~3 servers / 8–12 tasks / 10 trials × 3 conditions ≈ 300 agent runs
  (~1.5k LLM calls) — roughly one Groq daily-budget cycle; the run is paced by
  the same per-day cap as Exp2.

## Status

- **Done + tested (offline, no quota):** mock server, 3 condition configs, agent
  bridge, deterministic judge, and this driver (`agent/experiment.py`,
  `tests/test_experiment.py`).
- **Pending:** the team data above, then the live runs (spend Groq quota), then
  this `RESULTS.md` is filled from `results/rq3/`.
