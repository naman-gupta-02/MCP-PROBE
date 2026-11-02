# attacker/ — Experiment 2: adaptive-attacker robustness evaluation

Measures whether a detector that caught a poisoned MCPTox description can be evaded by an LLM that
rewrites the description, and how many tries it takes. This is adversarial-robustness evaluation of
the detectors (same methodology as MCP-ITP, arXiv 2601.07395, on the same MCPTox data).

## What is here

| File | Role | Status |
|---|---|---|
| `llm.py` | OpenAI-compatible chat client (Groq by default): per-minute rate budgeting, 429 back-off, clean stop on a daily limit; `StubLLM` for tests. | ready |
| `detectors.py` | One `check(tool_name, description) -> Check` interface over all 6 detectors, same setups as RQ1 (seed-0 checkpoints). | ready |
| `prompts.py` | Judge prompt + parsing; the `Attacker` protocol. | ready |
| `judge.py` | Runs the judge panel over a results file and labels each rewrite PRESERVED / BROKEN / UNSURE. | ready |
| `metrics.py` | Evasion rate and tries-to-evade, overall and by attack type / category. | ready |
| `rewrite.py` | `PromptedAttacker` (loads your prompt from a file, calls the LLM, parses one `candidate`) + `RewriteTask`. | ready |
| `run.py` | The loop: finds caught seeds, retries the rewrite to the cap, scores each with the real detector, writes records; resumes and stops cleanly on a daily limit. | ready |
| **`rewrite_prompt.txt`** | The attacker system prompt. **Team-supplied** — the harness loads it from here and ships none. | **you add this** |

## The part the team writes

The only missing piece is `attacker/rewrite_prompt.txt`: the system prompt that rewords a caught
description to keep the attack but get past the detector. This is the research contribution and the
harness does not ship one — `run.py` raises with a pointer until the file exists. Drop your prompt
in that file and the whole pipeline runs. (Decide for yourselves whether to commit it; it contains
an attack-rewrite prompt.)

`rewrite.PromptedAttacker` already does the wiring around it: it builds the user turn from the
harness inputs (`tool_name`, `original_description`, `current_description`, `tool_context`,
`length_target`, `previous_attempts`, and the `feedback` dict), calls the model, and extracts the
`{"candidate": ...}` even through think-blocks, fences and preamble. Feedback is a raw passthrough
of the detector's own outputs (no coaching added); if you want a coached variant, that's your edit.

`feedback` is whatever your chosen setting exposes (the user picked **both**, run separately):
- `verdict_score`: `{"blocked": bool, "stage": "s1|s2|waf", "score": float|None, "rules": [...]}`
- `blocked_only`: `{"blocked": bool}`

## Results record schema (one JSON object per line)

```json
{
  "case_id": "...", "detector": "e5base_full", "attacker_model": "llama-3.3-70b-versatile",
  "feedback_mode": "verdict_score", "paradigm": "P1", "risk_category": "Credential Leakage",
  "split": "val", "original_description": "<MCPTox poisoned text>",
  "caught_by_detector": true,
  "attempts": [{"n": 1, "description": "...", "blocked": true, "stage": "s2", "score": 0.97, "rules": []}],
  "evaded": false, "n_attempts": 10, "final_description": "<last rewrite tried>"
}
```

`judge.py` adds `judge_verdicts` and `attack_preserved`; `metrics.py` counts an evasion only when
`evaded` is true **and** `attack_preserved == "preserved"`.

## Run order

```bash
# 0. add attacker/rewrite_prompt.txt (your attacker system prompt)
# 1. run the loop  ->  results/attacker/run.jsonl  (resumes if rerun)
uv run python -m attacker.run --split val --ckpt-root <checkpoints dir> \
    --detectors frozen_mcpguard mcpguard_full mcpguard_head e5base_full e5base_head mcp_guardian \
    --attackers llama-3.3-70b-versatile openai/gpt-oss-120b openai/gpt-oss-20b qwen/qwen3.8-27b \
    --feedback-modes verdict_score blocked_only --cap 10 --out results/attacker/val.jsonl
# 2. judge the rewrites
uv run python -m attacker.judge --in results/attacker/val.jsonl \
    --judges llama-3.3-70b-versatile openai/gpt-oss-120b openai/gpt-oss-20b
# 3. metrics
uv run python -m attacker.metrics --in results/attacker/val.jsonl --out results/attacker/
```

Results files hold poisoned and rewritten descriptions, so they stay under `results/` (gitignored).
The loop prints only counts and rates, never description text.

## Config chosen for this experiment (2026-11-01)

- Attacker models to compare (Groq): `llama-3.3-70b-versatile`, `openai/gpt-oss-120b`,
  `openai/gpt-oss-20b`, `qwen/qwen3.8-27b` (preview — may be withdrawn).
- Judges: a multi-model panel (majority); keep each judge out of its own attacker comparison where possible.
- Feedback: both `verdict_score` and `blocked_only`, reported side by side.
- Seeds: develop on `val`, final numbers on `test` (`FINAL_EVAL=1`); held-out rewrites not read by us.
- Detectors: all 6, seed-0 checkpoints.
- `GROQ_API_KEY` goes in `.env` (gitignored). **Free-plan quota is the binding constraint** — see note in the team channel; the full grid will not fit in one day, so expect to resume across days or move to CARC-hosted models.
