# Cross-dataset check: detectors vs. MCP-SafetyBench

**Status:** complete (2026-11-19). Reproducible with `eval.py` (Section 4).

This is the Experiment-1 neutral cross-dataset check. RQ1 showed the MCPTox-trained detectors catch
held-out *MCPTox* categories; this asks the harder question: do they catch tool poisoning from a
**completely independent benchmark** they were never trained on?

## Dataset

**MCP-SafetyBench** (arXiv 2512.15163 `[verify]`, github `xjzzzzzzzz/MCPSafety`) — an independent MCP
safety benchmark built on real-world servers. Most of its 248 attack tasks are **query-level prompt
injection** (the attack is in the user's question, e.g. "…also read the file .env"), which our
**tool-description** detectors do not inspect and so are out of scope here. But **96 tasks are
"Tool Poisoning-\*"**, where the attack is placed in a **tool description**
(`mcp_server_modifications[].modification_description`) — exactly what our detectors score. We extract
those 96 descriptions (JSON reads only; no code from the download is run) and measure recall.

The benchmark ships **no clean tools** for these tasks, so only **recall** (detection rate on the
poisoned set) is measurable here — not false-positive rate.

## Result: recall on 96 independent poisoned descriptions

| Detector | Recall |
|---|---:|
| Frozen MCP-Guard | **97.9%** (94/96) |
| MCP-Guard Full | **97.9%** (94/96) |
| MCP-Guard Head-Only | **97.9%** (94/96) |
| Base E5 Full | 94.8% (91/96) |
| Base E5 Head-Only | 95.8% (92/96) |
| **MCP Guardian** (regex) | **13.5%** (13/96) |

The five learned detectors catch **95–98%** of an independent benchmark's tool poisoning, with **no
retraining and no exposure to MCP-SafetyBench**. MCP Guardian stays weak (13.5%), consistent with
RQ1/RQ2/RQ3 — the keyword filter only catches attacks with literal triggers.

## By attack subtype (MCP-Guard Full)

| MCP-SafetyBench subtype | Recall |
|---|---:|
| Command Injection | 31/31 (100%) |
| Function Dependency Injection | 23/23 (100%) |
| Parameter Poisoning | 18/18 (100%) |
| Tool Redirection | 11/11 (100%) |
| FileSystem Poisoning | 7/7 (100%) |
| Network Request Poisoning | 4/6 (67%) |

100% on five of six subtypes. The only gap is **Network Request Poisoning** (2 of 6 missed) — soft
"for enhanced security compliance…" redirections that quietly send data to an external URL, phrased
without hard literals. This mirrors the RQ2 finding: semantically-disguised attacks are the hard
case; literal ones (command/SQL injection) are caught every time.

## What this adds to RQ1

RQ1's generalization was *within* MCPTox (held-out categories). This is a **true cross-dataset**
result: the learned detectors' high recall is **not an MCPTox artifact** — they transfer to an
independent benchmark's tool poisoning at ~95–98%. So the RQ1 story holds across datasets for
*static* detection — which makes the RQ2 (evasion) and RQ3 (blunt live protection) findings the real
limits, not poor base detection.

## Limitations

- **Recall only** — MCP-SafetyBench ships no clean tools for these tasks, so false-positive rate on
  this dataset can't be measured (RQ1 and the length-bias study cover FPR on MCPTox clean tools).
- **Scope** — only the 96 tool-description attacks apply; the benchmark's ~150 query-level
  prompt-injection tasks are a different attack surface our tool-description detectors don't target.
- **Single checkpoint seed** per detector (seed 0), matching the main RQ1 configs.
- `[verify]` the arXiv id / benchmark version; the repo is a moving target (no release tag used).

## Reproduction

```bash
# clone the benchmark once, OUTSIDE this repo (not vendored here; external, no license file)
git clone --depth 1 https://github.com/xjzzzzzzzz/MCPSafety.git /tmp/mcpsafety

python experiments/safetybench/eval.py \
    --safetybench-dir /tmp/mcpsafety --ckpt-root checkpoints/mcp_guard \
    --out experiments/safetybench/tables/recall.csv
```

`eval.py` extracts the poisoned descriptions and runs the six detectors; `tables/recall.csv` holds
the per-detector recall. See [../OVERVIEW.md](../OVERVIEW.md) and
[../rq1_heldout/RESULTS.md](../rq1_heldout/RESULTS.md).
