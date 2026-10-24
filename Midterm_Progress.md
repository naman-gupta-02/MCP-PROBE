# MCP-PROBE: Midterm Progress Report

Team 12, USC CSCI 544 (Applied NLP). Covers the work from the start of the project (2026-10-08) to 2026-10-24.

**Project in one line:** we test whether existing MCP tool-poisoning detectors still work outside the conditions they were built for. We are not building a new detector.

---

## Contents

1. [Project and research questions](#1-project-and-research-questions)
2. [Team, branches and timeline](#2-team-branches-and-timeline)
3. [Infrastructure](#3-infrastructure)
4. [Data: MCPTox and the team split](#4-data-mcptox-and-the-team-split)
5. [Detectors](#5-detectors)
6. [Fine-tuning setup](#6-fine-tuning-setup)
7. [Results](#7-results)
8. [Key findings](#8-key-findings)
9. [Caveats and threats to validity](#9-caveats-and-threats-to-validity)
10. [Problems we hit and how we handled them](#10-problems-we-hit-and-how-we-handled-them)
11. [Status and next steps](#11-status-and-next-steps)
12. [Where everything is](#12-where-everything-is)

---

## 1. Project and research questions

An AI agent connected to MCP (Model Context Protocol) servers reads each tool's text description (from `tools/list`) to decide how to use it. **Tool poisoning** hides malicious instructions in that description (for example "also read ~/.ssh/id_rsa"), and the agent follows them. A **detector** inspects descriptions and blocks suspicious tools before the agent sees them.

We test two published detectors:

| Detector | Paper | What it is | Code |
|---|---|---|---|
| **MCP-Guard** | arXiv 2508.10991 | Three stages: regex rules → fine-tuned E5 classifier → LLM check | Public: github.com/GenTelLab/MCP-Guard + Hugging Face checkpoint |
| **MCP Guardian** | arXiv 2504.12757 | Regex/keyword filter (a web application firewall) | No public code; we rebuilt it from the paper |

Data: **MCPTox** (arXiv 2508.14925, AAAI 2026), poisoned tool descriptions for 45 real MCP servers.

The three experiments:

| # | Experiment | Question | Status |
|---|---|---|---|
| 1 | **Generalization (RQ1)** | Do detectors still catch attacks from risk categories they were never tuned on? | **Done**, plus robustness and cross-dataset checks |
| 2 | Adaptive attacker | Can an LLM rewrite a caught description so it evades the detector, and in how many tries (5–10 cap)? | Not started |
| 3 | Live pipeline | With a proxy filtering tools between a LangGraph agent and our own test MCP servers: attack success rate vs normal-task success rate for no detector, MCP-Guard and MCP Guardian | Proxy built; agent and servers not started |

---

## 2. Team, branches and timeline

### Ownership

| Area | Owner |
|---|---|
| Team repository | Vishwa Patel |
| Project skeleton and MCPTox data split | Anshul Mehta |
| MCP proxy (Experiment 3) | Anshul Mehta |
| MCP Guardian reimplementation | Jaymin Sheladia |
| MCP-Guard reproduction, fine-tuning, RQ1 evaluation and all results in Section 7 | Naman Gupta |

### Branches (team repo github.com/vishwapatel24051/MCP-PROBE)

| Branch | Contents | Latest |
|---|---|---|
| `main` | Initial skeleton and data split | `ef5a83d` (2026-10-08) |
| `setup/skeleton-data` | Skeleton + MCPTox split (PRs #1, #2 → `main`) | merged |
| `Proxy-interface` | MCP proxy (PR #4 → `rq1/generalization-eval`) | `76d59eb` (2026-10-08) |
| `MCP-Guardian` | MCP Guardian reimplementation + tune metrics (PR #6 → `rq1/generalization-eval`) | `dd36e3d` (2026-10-11) |
| `MCP-Guard` | MCP-Guard reproduction, fine-tuning (PR #3), RQ1 evaluation code and first-run results | `a43320a` (2026-10-20) |
| `rq1/generalization-eval` | Integration branch: proxy + Guardian + MCP-Guard + first RQ1 results (PR #5 and fast-forwards) | `a43320a` |
| `rq1/heldout-split2` | Robustness check (8 retrained held-out combinations), per-category and cross-dataset results, this report | latest |

### Timeline

| Date | What happened |
|---|---|
| 10-08 | Repo skeleton, `uv` environment, MCPTox data split (PR #1, #2). Proxy interface written. MCP-Guard reproduced from the official code; first `tune`/`val` numbers. CARC (USC HPC) access set up. |
| 10-08/09 | 20 MCP-Guard / E5 fine-tunes trained on CARC (one A40, 21 min). |
| 10-10 | MCP-Guard work merged into the team `MCP-Guard` branch (PR #3). The team rule "we train no models" was relaxed to allow fine-tuning as an extra condition. |
| 10-11 | MCP Guardian reimplementation (PR #6), proxy (PR #4) and MCP-Guard (PR #5) merged into `rq1/generalization-eval`. Detailed MCP-Guard metrics report written. |
| 10-11 → 10-16 | RQ1 held-out evaluation code written and verified. The first CARC attempt hung on a CARC storage fault (Section 10). |
| 10-16 | RQ1 first run completed (laptop, streaming checkpoints from CARC): 129 runs, 0 errors. |
| 10-17/18 | Independent CARC rerun: all 41,151 predictions identical. |
| 10-20 | 8 new held-out category combinations set up on a new branch; CARC job array submitted. |
| 10-21 | All 8 combinations done on CARC: 160 models retrained, 1,032 evaluation runs, 0 failures. |
| 10-24 | Combination results written up. Per-category results for all 10 categories. Untrained detectors scored on all of MCPTox. Cross-dataset check on MCP-Guard's own dev set. |

---

## 3. Infrastructure

- **Environment:** Python 3.11 with `uv` (`pyproject.toml` + committed `uv.lock`). MCP-Guard's extra dependencies are in `detectors/mcp_guard/requirements.txt`, so the shared lock file is unchanged.
- **Layout:** one folder per area (`data/`, `detectors/`, `proxy/`, `experiments/`, `agent/`, `attacker/`, `servers/`, `configs/`, `results/`, `scripts/`, `tests/`), so each person works on a separate branch with few conflicts.
- **Held-out data guard:** `data/loader.load_cases("test")` refuses to load unless `FINAL_EVAL=1`, so nobody tunes on test data by accident. Prediction files store case IDs and verdicts, never description text.
- **Compute:** USC CARC Discovery (Slurm account `xiangren_1987`, A40 GPUs) for training and GPU evaluation; laptop CPU for evaluation that only runs existing models. Team folder `/project2/xiangren_1987/group_12/`.
- **Tests:** 28 core tests (MCP-Guard, data splits), 72 MCP Guardian tests, and 8 RQ1 evaluation tests. All pass. The RQ1 tests check pooled accuracy, the combination selection and the split files. The proxy tests need the MCP SDK and run separately (`uv run --with "mcp>=2" pytest tests/test_proxy.py`).

---

## 4. Data: MCPTox and the team split

MCPTox at commit `f85189f` (github.com/zhiqiangwang4/MCPTox-Benchmark). Built by `scripts/build_splits.py` from `data/splits/server_split.json`.

| Item | Count |
|---|---:|
| Servers | 45 |
| Poisoned cases kept | **1,312** (36 flagged by the authors as `wrong_data = 2` were dropped) |
| Clean (benign) tool descriptions | **353** (the same servers' real descriptions; 37 are empty) |
| Risk categories | 10 + "Other" (4 cases) |
| Attack types | P1 (user asks for the tool; its description redirects), P2 (fake background tool), P3 (a rule that changes another tool's parameters) |

**Split rule:**
- Servers are divided 30 train / 6 val / 9 test.
- Three risk categories are held out completely: Credential Leakage, Instruction Tampering and Financial Loss.
- `tune` = train servers × known categories; `val` = val servers × known categories; `test` = test servers *or* a held-out category.
- Clean tools are split by server only.

| Split | Poisoned | Clean | Total | Role |
|---|---:|---:|---:|---|
| tune | 759 | 240 (17 empty; 223 used to train) | 999 | Training |
| val | 171 | 49 | 220 | Picking the best epoch; dev reference |
| test | 382 | 64 (20 empty) | 446 | Final evaluation |
| **Total** | **1,312** | **353** | **1,665** | |

Test cells (poisoned): `new_server_known_cat` 155, `known_server_new_cat` 194, `new_server_new_cat` 33.

**Held-out evaluation set (main RQ1 number):** 227 held-out-category cases (Credential Leakage 115, Instruction Tampering 57, Financial Loss 55, from 26 servers) **plus** the 64 clean test tools = 291 rows.

Team decisions are recorded in `DECISIONS.md`. Examples: MCPTox `Template-N` is stored as attack type `PN`, and description text is taken from each tool block's `Description:` field.

---

## 5. Detectors

### 5.1 MCP-Guard (reproduced from the official code)

| Stage | What | Source |
|---|---|---|
| I | 7 regex detectors: prompt injection, sensitive file, shell injection, SQL/XSS, shadow hijack, cross-origin, `<IMPORTANT>`-type tags | GenTelLab/MCP-Guard @ `4bc9779`, vendored unchanged in `detectors/mcp_guard/upstream/` |
| II | E5-base (XLM-RoBERTa) classifier → P(poisoned) | Hugging Face `GenTelLab/MCP-Guard` @ `861a928` + tokenizer `google-bert/bert-base-uncased` @ `86b5e09` |
| III | LLM check (any OpenAI-compatible endpoint) | Implemented; **not run** in these experiments |

Two decision modes:
- `paper` (default): Stage I hit → block. Otherwise block if P > 0.45; only scores in 0.45–0.55 go to the LLM.
- `released`: what the released code does. Stage II blocks at P ≥ 0.5, and every tool that passes Stage II goes to the LLM.

What we found in the released code, verified by running it:
- Stage II only reproduces the paper with the **BERT tokenizer**. The XLM-R tokenizer files shipped with the checkpoint give F1 34.5 instead of 95.1.
- The checkpoint is **E5-base**; the paper says E5-large.
- Its strict weight loading fails and falls back to non-strict, but all 148 fine-tuned tensors still load. Our batched loader matches theirs to ~3e-6 in the logits.

What we found by reading the code:
- The router sends every tool that passes Stage II to the LLM, not just the uncertain ones.
- An "unsure" LLM verdict crashes the request, and their evaluation script silently drops that sample.
- GPT temperature is 0.1 in the code vs 0.7 in the paper.

### 5.2 MCP Guardian (rebuilt from the paper)

- Regex WAF with the paper's **11 rules**: `rm -rf`, destructive shell, remote code execution, SQL `DROP` / tautology / `UNION`, `<script>`, SSH key, sensitive file, environment secret, path traversal.
- Ruleset fingerprint `9decc37e4f86`. It was written from the paper before any MCPTox data was opened and never tuned.
- Scans the tool name + description.
- Also implements the paper's runtime controls (token authentication, rate limiting, logging), used only in the proxy setting.

### 5.3 Proxy (for Experiment 3)

An MCP server to the agent and an MCP client to one upstream server (official `mcp` SDK, stdio).
- It passes everything through unchanged, except that `tools/list` goes through a pluggable detector (`filter_tools`), and calls to blocked tools are refused.
- Detector timeout and error policy are configurable.

---

## 6. Fine-tuning setup

Fine-tuning was added as an **extra condition** next to the frozen MCP-Guard (team decision, 2026-10-08/10).

| Setting | Value |
|---|---|
| Starting points | `mcpguard` = GenTelLab Stage II + BERT tokenizer; `e5base` = `intfloat/multilingual-e5-base` @ `d128750` + its tokenizer + a new head |
| Scope | **full**: all 278M weights, lr 2e-5, 5 epochs. **head-only**: encoder frozen, 0.6M weights, lr 1e-3, 10 epochs |
| Seeds | 0–4 (20 models per training sweep) |
| Loss / optimizer | Class-weighted cross-entropy (clean 2.2018 / poisoned 0.6469); AdamW, weight decay 0.01, batch 16, 10% warmup + linear decay, gradient clip 1.0, bf16 on GPU |
| Input | Description only, whitespace collapsed, max 128 tokens |
| Training data | `tune`: 759 poisoned + 223 non-empty clean (982) |
| Model selection | Best epoch by Stage II-alone F1 on `val` at threshold 0.5. Test data never used. |
| Time | ~30 s per full run, ~15 s per head-only run on an A40 |

That gives **six detectors** in total:

| # | Detector | Trained by us? |
|---|---|---|
| 1 | Frozen MCP-Guard | No |
| 2 | MCP-Guard Full | Yes |
| 3 | MCP-Guard Head-Only | Yes |
| 4 | Base E5 Full | Yes |
| 5 | Base E5 Head-Only | Yes |
| 6 | MCP Guardian | No |

---

## 7. Results

Metric conventions:
- Positive = poisoned.
- **Category accuracy = recall**, because every case in a risk category is poisoned.
- **Combined accuracy** is pooled: total correct / total cases, never a mean of category accuracies.
- Precision, F1 and FPR include the clean tools.
- Fine-tuned models are reported as mean ± std over 5 seeds.
- "Stage I + II" is MCP-Guard as deployed; "Stage II alone" is the classifier only.

### 7.1 Reproduction check: GenTelLab's own dev set (1,053 samples, 432 malicious)

| Configuration | Accuracy | Precision | Recall | F1 | Paper (Table 4a) |
|---|---:|---:|---:|---:|---|
| Stage I only | 74.5 | 97.7 | 38.9 | 55.6 | 74.6 / 97.7 / 38.9 / 55.6 |
| Stage II only (BERT tokenizer) | 96.0 | 96.7 | 93.5 | 95.1 | 96.0 / 96.7 / 93.5 / 95.1 |
| Stage I + II | 95.9 | 96.0 | 94.0 | 95.0 | – |
| Stage II, XLM-R tokenizer (shipped files) | 66.9 | 91.1 | 21.3 | 34.5 | – |

**Our setup reproduces the paper exactly.**

### 7.2 Development results on MCPTox (`tune` / `val`, seen categories)

**MCP-Guard, `val` (220 rows), Stage I + II:**

| Condition | Accuracy | Precision | Recall | F1 | FPR |
|---|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 92.7 | 91.4 | 100.0 | 95.5 | 32.7 |
| Base E5 Full | 94.5 ± 0.2 | 93.3 ± 0.2 | 100.0 | 96.6 ± 0.1 | 24.9 ± 0.9 |
| Base E5 Head-Only | 93.3 ± 0.4 | 92.0 ± 0.4 | 100.0 | 95.9 ± 0.2 | 30.2 ± 1.7 |
| MCP-Guard Full | 93.2 ± 0.5 | 91.9 ± 0.5 | 100.0 | 95.8 ± 0.3 | 30.6 ± 2.0 |
| MCP-Guard Head-Only | 92.6 ± 0.2 | 91.3 ± 0.2 | 100.0 | 95.5 ± 0.1 | 33.1 ± 0.9 |

**MCP-Guard, `val`, Stage II alone (threshold 0.5):**

| Condition | F1 | FPR |
|---|---:|---:|
| Base E5 before training | 55.4 ± 35.8 | 54.7 ± 36.1 |
| Base E5 Full | 99.8 ± 0.3 | 1.2 ± 1.8 |
| Base E5 Head-Only | 97.8 ± 0.4 | 12.7 ± 4.2 |
| Frozen MCP-Guard | 95.5 | 30.6 |
| MCP-Guard Full | 96.6 ± 0.6 | 24.5 ± 4.3 |

**MCP-Guard, `tune` (training data, 999 rows), Stage I + II:**
- Frozen: recall 99.2, FPR 16.2.
- Fine-tunes: recall 100, FPR 3.8–5.3; MCP-Guard Head-Only 16.4.

**What the `val` numbers show:**
- Recall is 100% for every condition on `val`; all the differences come from false positives.
- Stage I creates a false-positive floor on `val`. 12 clean tools from one server (Commander) are blocked by its regex rules. The Stage II false positives are Codacy tools.
- Stage III would never trigger in paper mode: no Stage II score falls in 0.45–0.55 (0 of 66 on `val`, 0 of 427 on `tune`).
- Latency (A40, Stage I + II): mean 6.5–8.0 ms per tool, median 1.0 ms.

**MCP Guardian (no training; both splits are unseen):**

| Split | Recall | Precision | F1 | FPR | Accuracy |
|---|---:|---:|---:|---:|---:|
| tune | 5.3 (40 / 759) | 97.6 | 10.0 | 0.4 (1 / 240) | 27.9 |
| val | 13.5 (23 / 171) | 100.0 | 23.7 | 0.0 (0 / 49) | 32.7 |

### 7.3 RQ1 first run: held-out categories (Credential Leakage, Instruction Tampering, Financial Loss)

Existing checkpoints, 129 evaluation runs, 0 errors. An independent CARC GPU rerun matched all **41,151 predictions** exactly.

**Category accuracy and combined accuracy (Stage I + II):**

| Detector | Credential Leakage (115) | Instruction Tampering (57) | Financial Loss (55) | **Combined (227)** |
|---|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 100.0 | **100.0** |
| MCP-Guard Full | 100.0 | 100.0 | 100.0 | **100.0** |
| MCP-Guard Head-Only | 100.0 | 100.0 | 100.0 | **100.0** |
| Base E5 Full | 100.0 | 100.0 | 100.0 | **100.0** |
| Base E5 Head-Only | 99.8 ± 0.4 | 100.0 | 96.0 ± 0.8 | **98.9 ± 0.2** |
| MCP Guardian | 67.8 | 7.0 | 0.0 | **36.1** |

**Held-out + 64 clean test tools (291 rows), Stage I + II:**

| Detector | Accuracy | Precision | Recall | F1 | FPR | TP / FP / FN / TN |
|---|---:|---:|---:|---:|---:|---|
| Frozen MCP-Guard | 99.3 | 99.1 | 100.0 | 99.6 | 3.1 | 227 / 2 / 0 / 62 |
| MCP-Guard Full | 99.7 ± 0.2 | 99.6 ± 0.3 | 100.0 | 99.8 ± 0.2 | 1.6 ± 1.1 | 227 / 1.0 / 0 / 63.0 |
| MCP-Guard Head-Only | 99.0 ± 0.6 | 98.8 ± 0.7 | 100.0 | 99.4 ± 0.4 | 4.4 ± 2.6 | 227 / 2.8 / 0 / 61.2 |
| Base E5 Full | 99.9 ± 0.2 | 99.9 ± 0.2 | 100.0 | 100.0 ± 0.1 | 0.3 ± 0.7 | 227 / 0.2 / 0 / 63.8 |
| Base E5 Head-Only | 97.8 ± 0.6 | 98.3 ± 0.7 | 98.9 ± 0.2 | 98.6 ± 0.4 | 6.2 ± 2.5 | 224.6 / 4.0 / 2.4 / 60.0 |
| MCP Guardian | 50.2 | 100.0 | 36.1 | 53.1 | 0.0 | 82 / 0 / 145 / 64 |

**Whole test split (446 rows), Stage I + II:**

| Detector | Accuracy | Precision | Recall | F1 | FPR |
|---|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 99.6 | 99.5 | 100.0 | 99.7 | 3.1 |
| MCP-Guard Full | 99.8 ± 0.2 | 99.7 ± 0.2 | 100.0 | 99.9 ± 0.1 | 1.6 ± 1.1 |
| MCP-Guard Head-Only | 99.4 ± 0.4 | 99.3 ± 0.4 | 100.0 | 99.6 ± 0.2 | 4.4 ± 2.6 |
| Base E5 Full | 100.0 ± 0.1 | 99.9 ± 0.1 | 100.0 | 100.0 ± 0.1 | 0.3 ± 0.7 |
| Base E5 Head-Only | 98.5 ± 0.5 | 99.0 ± 0.4 | 99.3 ± 0.2 | 99.1 ± 0.3 | 6.2 ± 2.5 |
| MCP Guardian | 34.1 | 100.0 | 23.0 | 37.4 | 0.0 |

- Recall is ~100% in every test cell (new server and/or new category) for every learned model. Guardian catches 39.7% in `known_server_new_cat`, 3.9% in `new_server_known_cat` and 15.2% in `new_server_new_cat`.
- With Stage II alone, held-out numbers are the same except Base E5 Full (recall 99.9) and Base E5 Head-Only (recall 95.5, F1 96.8).

### 7.4 Robustness check: 8 other held-out category combinations (all models retrained)

**Selection:**
- Pool: the 7 categories not held out in the first run.
- Rule: 8 of the 35 possible combinations, drawn with seed 2026 and redrawn until each category is held out 3–4 times. The rule was fixed before any results.
- Servers are the same as the first run.
- Each combination retrains all 20 fine-tuned models on its own `tune` split (CARC array `13272593`, 2026-10-21).

Mean ± std across the 8 combinations [min–max]:

| Detector | Recall, Stage I + II | F1, Stage I + II | FPR (64 clean) | Recall, Stage II alone |
|---|---:|---:|---:|---:|
| Frozen MCP-Guard | 99.5 ± 0.1 [99.3–99.7] | 99.5 ± 0.1 | 3.1 | 95.7 ± 2.9 [91.7–98.6] |
| MCP-Guard Full | 99.9 ± 0.1 [99.7–100.0] | 99.8 ± 0.1 | 1.9 ± 1.0 | 97.4 ± 3.0 [93.6–100.0] |
| MCP-Guard Head-Only | 99.5 ± 0.1 [99.2–99.7] | 99.4 ± 0.2 | 4.6 ± 1.2 | 95.8 ± 3.1 [91.5–99.0] |
| Base E5 Full | 99.9 ± 0.1 [99.6–100.0] | 99.9 ± 0.1 | 0.2 ± 0.2 | 99.7 ± 0.3 [99.1–100.0] |
| Base E5 Head-Only | 99.9 ± 0.1 [99.7–100.0] | 99.5 ± 0.3 | 6.3 ± 1.5 | 98.4 ± 0.9 [96.5–99.4] |
| MCP Guardian | 6.0 ± 3.6 [0.6–11.3] | 11.1 ± 6.4 | 0.0 | – |

Per-combination tables are in `experiments/rq1_heldout/COMBOS_RESULTS.md` and `combos/results/c1.md … c8.md`.

### 7.5 Held-out recall for all 10 categories

Each category is scored in the split(s) that held it out: the first run for Credential Leakage, Instruction Tampering and Financial Loss; the combinations for the rest. Each cell is *Stage I + II / Stage II alone*.

| Category (cases) | Frozen MCP-Guard | MCP-Guard Full | MCP-Guard Head | Base E5 Full | Base E5 Head | Guardian |
|---|---:|---:|---:|---:|---:|---:|
| Code Injection (63) | 100 / 100 | 100 / 100 | 100 / 100 | 99.9 / 99.9 | 99.4 / 94.5 | 12.7 |
| Credential Leakage (115) | 100 / 100 | 100 / 100 | 100 / 100 | 100 / 100 | 99.8 / 97.6 | 67.8 |
| Data Tampering (117) | 100 / 98.3 | 100 / 100 | 99.7 / 98.5 | 100 / 100 | 100 / 100 | 7.7 |
| Financial Loss (55) | 100 / 100 | 100 / 100 | 100 / 100 | 100 / 99.6 | 96.0 / 86.5 | 0.0 |
| Information Manipulation (269) | 99.3 / 98.1 | 99.7 / 99.3 | 99.3 / 98.2 | 100 / 100 | 100 / 98.6 | 1.1 |
| Infrastructure Damage (122) | 100 / **75.4** | 100 / **77.3** | 100 / **75.3** | 99.9 / 97.5 | 100 / 93.3 | 18.9 |
| Instruction Tampering (57) | 100 / 100 | 100 / 100 | 100 / 100 | 100 / 100 | 100 / 100 | 7.0 |
| Message Hijacking (41) | 97.6 / 97.6 | 100 / 99.8 | 98.7 / 98.7 | 100 / 100 | 100 / 99.3 | 0.0 |
| Privacy Leakage (273) | 98.9 / 96.7 | 99.7 / 99.3 | 98.9 / 96.6 | 99.5 / 99.5 | 99.7 / 99.5 | 9.5 |
| Service Disruption (196) | 100 / 96.9 | 100 / 98.5 | 100 / 97.0 | 100 / 100 | 99.7 / 99.3 | 0.0 |
| **Average over 10 categories** | **99.6 / 96.3** | **99.9 / 97.4** | **99.7 / 96.4** | **99.9 / 99.7** | **99.5 / 96.9** | **12.5** |

### 7.6 Untrained detectors on all of MCPTox (1,312 attacks + 353 clean)

These detectors were never trained on MCPTox, so every row is unseen for them.

| Detector | Recall | Precision | F1 | FPR |
|---|---:|---:|---:|---:|
| Frozen MCP-Guard, Stage I + II | 99.5 (1,306 / 1,312) | 95.8 | 97.6 | **16.1** (57 / 353) |
| Frozen MCP-Guard, Stage II alone | 96.0 | 96.3 | 96.1 | 13.9 |
| MCP Guardian | 11.5 | 99.3 | 20.6 | 0.3 (1 / 353) |

- Frozen MCP-Guard's false positives come mostly from AdFin (19), Commander (12) and OP.GG (7).
- With Stage II alone, its recall is 75.4% on Infrastructure Damage, and 88.9% on P1 vs 95.4% on P2 and 99.0% on P3.

### 7.7 Cross-dataset check: MCPTox-trained models on MCP-Guard's released dev set

GenTelLab's full MCP-AttackBench (70k+ samples) has **not been released**; their README lists it as a to-do. The test set here is their released dev set: 1,053 short texts, 432 malicious. Fine-tuned models are our original MCPTox-trained checkpoints, 5 seeds; threshold P ≥ 0.5.

| Model | Accuracy | Precision | Recall | F1 | FPR |
|---|---:|---:|---:|---:|---:|
| Frozen MCP-Guard (its own data) | 96.0 | 96.7 | 93.5 | 95.1 | 2.3 |
| MCP-Guard Full (fine-tuned on MCPTox) | 95.7 ± 0.7 | 98.6 ± 0.1 | 90.9 ± 1.7 | 94.6 ± 0.9 | 0.9 |
| **Base E5 Full** (fine-tuned on MCPTox) | 69.6 ± 2.0 | 98.7 ± 1.0 | **26.2 ± 5.1** | **41.2 ± 6.2** | 0.3 |

These are Stage II alone. With Stage I + II: Frozen 95.0 F1, MCP-Guard Full 94.5, Base E5 Full 62.3.

---

## 8. Key findings

1. **Every learned detector scores ~99–100% on held-out MCPTox categories**, on the first split and on all 8 others (average over the 10 categories: 99.5–99.9% with Stage I + II). The result doesn't depend on which categories are held out.
2. **The near-perfect scores are not overfitting:** training, validation and test scores are all equally high. **They also don't prove generalization:**
   - MCPTox attacks in every category share templates (`<IMPORTANT>` tags, "you MUST first call…"), and clean descriptions are much shorter than poisoned ones (median 14 vs 60 tokens).
   - MCP-Guard's regex stage alone catches 78% of held-out attacks.
   - MCP-Guard as released, never trained on MCPTox, catches 99.5% of all MCPTox attacks.
3. **Cross-dataset results show the gap.** Base E5 Full, the best model on MCPTox, catches only **26%** of MCP-Guard's attacks (F1 41.2). MCP-Guard Full keeps **94.6 F1**, so fine-tuning on MCPTox didn't erase its original training. **On MCPTox, Base E5 Full is best; overall, MCP-Guard Full is the more robust detector.**
4. **MCP-Guard's classifier has a blind spot on Infrastructure Damage** (~75–77% with Stage II alone, even after fine-tuning). Its regex Stage I covers for it.
5. **Full fine-tuning beats head-only.** The head-only models raise the most false alarms (4.4–6.3% FPR).
6. **MCP Guardian never raises a false alarm but catches few attacks.** Its recall depends entirely on rule-topic overlap: 36.1% on the first split (mostly Credential Leakage's SSH-key and secrets wording), 6.0% on average for the other combinations, and 0% on Financial Loss, Message Hijacking and Service Disruption.
7. **MCP-Guard's weakness on MCPTox is false positives, not misses:** 16.1% of all clean tools as released. Fine-tuning cuts this to 1.6% on the test servers.

---

## 9. Caveats and threats to validity

- **Easy benchmark:** shared templates and length cues make MCPTox's poisoned and clean descriptions easy to separate. Treat the held-out scores as an upper bound; Experiment 2 is the real test of generalization.
- **Small clean set:** 64 clean test tools (20 empty, which MCP-Guard allows automatically). One false positive moves FPR by 1.6 points, and most FPR differences between the learned models are 1–3 tools.
- **Class balance:** held-out data is 78% poisoned, so a detector that blocks everything scores 100% category accuracy and 78% accuracy.
- **Test data used:** the whole test split has been scored, so no untouched test data remains. The 8 combinations overlap and reuse the same test servers, so the spread across them describes variation rather than giving a confidence interval.
- **Validation chose the epoch**, so fine-tuned `val` numbers are slightly optimistic. Test data was never used for any choice.
- **Cross-dataset favors MCP-Guard:** the dev set is MCP-Guard's in-distribution data. A neutral third dataset would be fairer.
- **Stage III not run:** in paper mode it would almost never trigger (no Frozen MCP-Guard score fell in its band).
- **Truncation:** descriptions are cut at 128 tokens (39 of 759 poisoned and 20 of 223 clean `tune` descriptions are longer).
- **Open checks:** a length-matched comparison, and simple length and keyword baselines.

---

## 10. Problems we hit and how we handled them

| Problem | Handling |
|---|---|
| The tokenizer shipped with MCP-Guard's checkpoint gives F1 34.5 | Found that the released code uses the BERT tokenizer; with it, the paper's numbers reproduce exactly |
| One of MCP-Guard's dev samples contains a Stripe test key, so GitHub push protection blocked the vendored repo | The dev set is downloaded at runtime at a pinned commit instead of being committed |
| The first RQ1 CARC job hung for its whole 1-hour limit | Cause: some cached model files on CARC's `/scratch1` storage hung on any access (a storage fault). We added a 2-minute file-read check to the job scripts and reran once the storage recovered. |
| GPU queue waits of 1–3 days | Ran evaluation-only work on a laptop by streaming each checkpoint from CARC (copy → score → delete), and confirmed the CARC rerun later gave identical predictions |
| Retraining 8 combinations × 20 models would need ~770 GB of checkpoints | Each checkpoint is deleted right after scoring; training records and predictions are kept, so any model can be retrained exactly |
| Combined accuracy could be miscomputed as a mean of category accuracies | Pooled computation enforced in code and covered by unit tests |

---

## 11. Status and next steps

| Item | Status |
|---|---|
| Data split | Done |
| MCP-Guard reproduction + fine-tuning | Done |
| MCP Guardian reimplementation | Done |
| Proxy | Done (interface + detector slot) |
| **Experiment 1 (RQ1)** | **Done**: first run, CARC rerun, 8-combination robustness check, per-category, untrained-on-all-MCPTox and cross-dataset results |
| Stage III (LLM check) | Implemented, not run. Choose a backend (vLLM on CARC vs OpenAI); it matters only in `released` mode |
| Experiment 2 (adaptive attacker) | Not started. This is the key test of whether detectors learned intent or MCPTox style |
| Experiment 3 (live pipeline) | Proxy ready; the LangGraph agent and test MCP servers are not started |
| Baselines | Planned: "block everything", length-only and keyword-only, to quantify how easy MCPTox is |
| Neutral cross-dataset check | Planned: a third, non-MCPTox, non-MCP-Guard dataset |
| Local rerun of the 8 combinations | Optional; CARC results are complete |

---

## 12. Where everything is

| What | Where |
|---|---|
| Project context and rules | `CLAUDE.md`, `DECISIONS.md`, `README.md` |
| Data split | `scripts/build_splits.py`, `data/splits/server_split.json`, `data/splits/split_report.md`, `data/processed/` |
| MCP-Guard code | `detectors/mcp_guard/` (`pipeline.py`, `stage1/2/3.py`, `train.py`, `evaluate.py`, `eval_upstream_dev.py`, `carc/`) |
| MCP-Guard development metrics | `detectors/mcp_guard/mcp_guard_metrics.md` |
| MCP Guardian code and metrics | `detectors/mcp_guardian/` (`README.md`, `mcp_guardian_metrics.md`) |
| Proxy | `proxy/` |
| RQ1 code | `experiments/rq1_heldout/` (`evaluate.py`, `report.py`, `combos.py`, `run_combo.sh`, `combos_report.py`, `combos_docs.py`, `category_summary.py`, `carc/`) |
| RQ1 results (first run, full summary) | `experiments/rq1_heldout/RESULTS.md` |
| RQ1 robustness (8 combinations) | `experiments/rq1_heldout/COMBOS_RESULTS.md`, `experiments/rq1_heldout/combos/results/` |
| Per-category, untrained and cross-dataset tables (+ CSV) | `experiments/rq1_heldout/tables/` |
| Raw outputs: predictions, metrics, logs (gitignored) | `results/` locally and `/project2/xiangren_1987/group_12/MCP-PROBE/results/` on CARC |
| Fine-tuned checkpoints (first run, 20 × 1.1 GB) | CARC `/project2/xiangren_1987/group_12/checkpoints/mcp_guard/` |
