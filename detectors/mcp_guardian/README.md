# MCP Guardian (reimplementation)

A reimplementation of **MCP Guardian** (Kumar et al., 2025, [arXiv:2504.12757](https://arxiv.org/abs/2504.12757)), the rule-based baseline in Team 12's study *Do MCP Tool Poisoning Detectors Generalize*.

The authors released no code. This version is built from the paper text alone. The core package uses only the Python standard library, so it works with whichever MCP SDK version the proxy uses. Everything lives in `detectors/mcp_guardian/`; nothing outside this folder was changed.

## Why not reuse an existing repo

| Repo | What it actually is | Usable? |
|---|---|---|
| [eqtylab/mcp-guardian](https://github.com/eqtylab/mcp-guardian) | Rust/Tauri desktop app from EQTY Lab that shares the name. It logs messages, supports manual approval, and filters on message type and direction. It has no WAF, tokens or rate limiting. | No, different design |
| [S1LV3RJ1NX/mcp-guardian](https://github.com/S1LV3RJ1NX/mcp-guardian) | Proxy that cuts token use and limits which tools an agent can see. It replaces the tool list with 3 meta-tools and has per-scope allowlists. It has no WAF or rate limiting. | No, and it would change what the agent sees |

## Quick start

Run from the repo root after `uv sync`:

```bash
uv run python -m detectors.mcp_guardian.evaluate_rules     # scores Guardian on tune and val; test stays locked
uv run pytest detectors/mcp_guardian/tests                 # 72 pass; the MCP SDK test file is skipped without mcp
uv run --with "mcp>=2" pytest detectors/mcp_guardian/tests # all 74, including the MCP SDK integration tests
uv run --with "mcp>=2" python -m detectors.mcp_guardian.examples.reproduce_paper   # the paper's Section 4
```

The core package and the scoring need nothing beyond the team's locked dependencies. Only the examples and the integration tests need the MCP Python SDK (v2), which `--with` adds for that one run without changing `pyproject.toml`. The tests sit in this folder rather than the root `tests/`, so a plain `uv run pytest` does not run them.

## How the rest of the project uses it

**Proxy detector slot (Teammate 1).** This matches the roadmap's `filter_tools(tools) -> tools` interface. It accepts plain dicts or MCP SDK `Tool` objects and returns the same objects, in the same order, minus the flagged ones.

```python
from detectors.mcp_guardian import MCPGuardian

detector = MCPGuardian(valid_tokens=[], logfile_path="mcp_guardian.log")  # the paper's 11 WAF rules
safe_tools = detector.filter_tools(result.tools)    # sync; safe to call from async code
```

**Generalization harness (Teammate 4).** Use `scan_tool` here: it doesn't log, so it can run over thousands of tools.

```python
scan = detector.scan_tool(tool)       # dict or Tool model
scan.blocked                          # bool -> the predicted label
scan.rules                            # ["ssh_key", "sensitive_file"]
scan.matches                          # (rule, field path, excerpt) for error analysis
detector.waf.fingerprint              # record this next to every results table
```

**Adaptive attacker (Teammate 5).** `scan.blocked` is the verdict. `scan.reason` is the detector's stated reasoning, e.g. `ssh_key in inputSchema.properties.notes.description: '.ssh'`, for the threat model where the attacker sees why it was caught.

**Call-time path (optional).** These are the paper's runtime controls. The roadmap's proxy only routes `tools/list` through the detector, so they are not needed for Phase 2. To also guard `tools/call`, call `detector.check_request(tool_name, arguments, token)`. It raises `Unauthorized` (401), `Forbidden` (403), `TooManyRequests` (429) or `WafBlocked` (403). The proxy has to turn these into its SDK's tool error; see [examples/weather_server.py](examples/weather_server.py). Be careful with the paper's default of **5 requests per minute per token**: a Phase 3 agent will hit it during legitimate tasks.

## What is implemented

| Paper component | Where | Notes |
|---|---|---|
| API-token authentication (3.2.1a) | `check_request` | Tokens come from the constructor or the `MCP_GUARDIAN_TOKENS` env var. They are stored as SHA-256 hashes, and logs show only an 8-character fingerprint. |
| Per-token tool restrictions (3.2.1b) | `token_permissions={token: {tools}}` | |
| Per-token rate limit, 429 response (3.2.2, 3.4.1) | `SlidingWindowRateLimiter` | Default 5 per 60 s. The paper doesn't say whether its window is fixed or sliding. |
| Regex WAF on arguments (3.2.3, 3.4.1) | `waf.py`, `check_request` | See the rules below |
| Logging of requests and responses (3.2.4, 3.4.2) | JSON lines in `mcp_guardian.log` | `log_payloads=False` drops arguments and responses from the log |
| Remote log endpoint (3.4.2) | `remote_log_url=` | Sent by POST from a background thread |
| Alerts via a custom function (3.4.1) | `alert=callable` | Called on every block. If it fails, the failure is logged and the request continues. |
| `guarded_invoke_tool` override (3.4.1, 3.4.3) | `guarded_invoke_tool` | Drop-in replacement for MCP v2 `MCPServer.call_tool` |
| Applying the WAF to tool metadata | `filter_tools`, `scan_tool` | **Our adaptation, not in the paper.** See below. |

Not implemented: the encrypted or short-lived token store, OpenTelemetry tracing, policy-as-code, and anomaly detection. The paper lists these as optional or future work, and none is needed for the study.

## WAF rules

The paper doesn't publish its ruleset. It names four kinds of indicator: SQL injection strings, `<script>` tags, destructive shell commands, and references to sensitive files or environment variables. It gives one concrete pattern, `rm\s+-rf`. [`WAF_RULES`](waf.py) implements exactly those four kinds, with 11 rules, and each rule records the paper section it comes from:

rm_rf, destructive_shell, remote_code_exec, sql_drop, sql_tautology, sql_union, script_tag, ssh_key, sensitive_file, env_secret, path_traversal. Fingerprint: **`9decc37e4f86`**.

**The rules are not tuned to any benchmark.** They were written from the paper text before any MCPTox data was opened and haven't changed since; the fingerprint proves it, and a test fails if any rule changes. This is deliberate. The project compares detectors *as published*, so Guardian's numbers have to be the paper's design, not an improved version. Some choices were still unavoidable because the paper gives only categories, and they are recorded in each rule's `source`. `remote_code_exec` and `path_traversal` stretch the paper's categories slightly. They stay as written, because changing them now would mean changing rules after seeing results.

`extra_rules=` exists because the paper says administrators can add domain-specific rules (Sec. 3.4.2). Leave it empty for every experiment.

## Results on the team's split

`python -m detectors.mcp_guardian.evaluate_rules` reads `tune` and `val` through the team's `data/loader.py`, so `test` stays locked behind `FINAL_EVAL=1`. One row is one MCPTox case or one clean tool. The team's records hold a name and description but no parameter schema, so Guardian scans those two fields. Since the rules never saw MCPTox, `tune` and `val` are both unseen data for this detector.

| Split | Attacks caught (recall) | Precision | F1 | False alarms on safe tools |
|---|---|---|---|---|
| `tune` | 40 of 759 (5.3%) | 0.976 | 0.100 | 1 of 240 |
| `val` | 23 of 171 (13.5%) | 1.000 | 0.237 | 0 of 49 |

- **Why it misses so much:** the WAF looks for attack *payloads* (`rm -rf`, `DROP TABLE`, `.ssh`). Most MCPTox attacks are plain-language *instructions* ("Before using X, you must first call Y"), so no rule fires. 0 of 186 Information Manipulation and 0 of 140 Service Disruption attacks on `tune` were caught.
- **What it does catch:** attacks that name a sensitive file or command. On `val`, Code Injection is 8 of 8, because those servers' attacks contain SQL or shell commands.
- **The one false alarm** is a safe tool named `printEnv`, flagged by the environment-variable rule.
- **The safe-tool sets are small.** 0 of 49 is consistent with a true false-alarm rate of up to about 7% (two-sided 95% Clopper-Pearson upper bound).
- **One data detail for the team:** in MCPTox's case-level text, which the team's split uses, about a third of attacks are wrapped in `<IMPORTANT>` tags. Guardian has no rule for tags, so this doesn't affect its score, but a detector with a tag rule would get an easy boost. Keep this in mind when comparing detectors.

## Reproducing the paper's Section 4

Output of `examples/reproduce_paper.py` (Apple Silicon laptop, Python 3.12, MCP SDK 2.3.0, stdio transport; the latency figures vary from run to run):

| Check | Paper | This implementation |
|---|---|---|
| Missing or invalid token | "Unauthorized" | `Unauthorized` |
| `rm -rf /` in arguments | Blocked by WAF | `Request blocked by WAF scanning: rm_rf` |
| `DROP TABLE` in arguments | Blocked | `Request blocked by WAF scanning: sql_drop` |
| 100 rapid calls, limit 5 | Calls beyond 5 get 429 | 5 served, 95 rejected with 429 |
| Median latency overhead | +3.8 ms (25.1 → 28.9) | +0.03 ms (0.59 → 0.62) |
| p95 latency overhead | +4.3 ms (32.4 → 36.7) | +0.03 ms (0.66 → 0.70) |

The security results match. The overhead does not. Our baseline returns a canned forecast with no network call, so compare the absolute overhead, not the percentage. Even so, ours is about 100 times smaller than the paper's 3–4 ms, and token lookup, a counter, a dozen regexes and one log line cannot account for theirs. Report this as a discrepancy rather than a reproduction.

Applied to tool metadata through `filter_tools`, the paper's own Section 2.3.1 examples give:

| Tool | Guardian |
|---|---|
| `get_forecast` (benign) | allow |
| `add_numbers` (tool poisoning: reads `.ssh/id_rsa`, `mcp.json`) | **block** (ssh_key, sensitive_file) |
| `sum_numbers` (shadowing: reroutes `send_email`) | **allow (missed)** |

The paper's WAF misses one of its own two attack examples, because the shadowing description names no file, command or SQL string. This supports the review's argument that the evaluation tests lexical filtering, not detection of poisoned descriptions.

## Layout

```
detectors/mcp_guardian/
  waf.py                       rules, WafScanner, ScanResult
  guardian.py                  MCPGuardian, rate limiter, errors, logging
  team_split.py                reads the team's tune/val split through data/loader.py
  evaluate_rules.py            scores Guardian on tune and val
  tests/                       unit tests + in-process MCP SDK integration tests
  examples/weather_server.py   paper-style protected stdio server (Sec. 3.4.3)
  examples/reproduce_paper.py  Sec. 4 security, metadata and overhead checks
```
