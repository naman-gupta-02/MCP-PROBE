# RQ1: held-out category evaluation

Scores the six detectors on the three MCPTox risk categories that no detector was tuned on (`held_out_categories` in [server_split.json](../../data/splits/server_split.json): Credential Leakage, Instruction Tampering, Financial Loss). Nothing is trained, tuned or selected here: the scripts load the existing MCP-Guard checkpoints and the frozen MCP Guardian ruleset (fingerprint `9decc37e4f86`).

| Model key | What it is |
|---|---|
| `frozen_mcpguard` | GenTelLab Stage II as released (`GenTelLab/MCP-Guard`, BERT tokenizer) |
| `mcpguard_full` / `mcpguard_head` | MCP-Guard weights fine-tuned on `tune`, all layers / head only (5 seeds each) |
| `e5base_full` / `e5base_head` | `intfloat/multilingual-e5-base` + new head, fine-tuned on `tune`, all layers / head only (5 seeds each) |
| `mcp_guardian` | MCP Guardian WAF reimplementation, the paper's 11 rules |

MCP-Guard variants run as **Stage I + II** (paper mode, T_u = 0.45 from `configs/mcp_guard.yaml`) and as **Stage II alone**. Stage III is not run. Guardian scans tool name + description, as in `detectors/mcp_guardian/evaluate_rules.py`; MCP-Guard scans the description.

## Rows scored

- `heldout`: the 227 held-out-category cases (all poisoned) + the 64 clean test tools (20 have empty descriptions). The script loads `test` with `FINAL_EVAL=1` and immediately drops the 155 seen-category test cases, which are never scored.
- `val`: the dev reference (171 poisoned cases from seen categories on val servers + 49 clean tools), scored by the same code.

## Metrics

- **Category accuracy** = correct / n within a category. Every held-out case is poisoned, so this is recall; a block-everything detector scores 100%.
- **Combined accuracy** = pooled correct / pooled n over the three categories, not a mean of category accuracies (the unweighted mean is also logged for comparison, and the code asserts the pooled value).
- **With clean tools**: accuracy, precision, recall, F1, FPR and confusion matrix over held-out poisoned + clean test tools, overall and per category. FPR is also given over non-empty clean tools only, since MCP-Guard passes empty descriptions without scoring them.
- Fine-tuned variants: each seed is pooled first, then mean ± sample std over the 5 seeds. Per-seed values are in `runs.csv`.

## Run

```bash
sbatch experiments/rq1_heldout/carc/eval_heldout.slurm      # on CARC, where the checkpoints are

# or locally, with checkpoints from detectors/mcp_guard/train.py
uv run python -m experiments.rq1_heldout.evaluate --split val --ckpt-root <dir>
FINAL_EVAL=1 uv run python -m experiments.rq1_heldout.evaluate --split heldout --ckpt-root <dir>
uv run python -m experiments.rq1_heldout.report
```

## Outputs (`results/rq1_heldout/`, gitignored)

- `<split>/<model>/<config>[_seed<k>]/predictions.jsonl`: one line per row with case id, server, label, category, attack type, prediction, deciding stage, Stage II score and rule names. No description text or match excerpts.
- `<split>/<model>/<config>[_seed<k>]/metrics.json` and `log.txt`: checkpoint, sample counts, correct/incorrect, metrics, confusion matrix, evaluation time, any error.
- `<split>/runs.csv`: one row per run. `<split>/summary.{csv,json}`: one row per model and config (seed mean ± std).
- `report.md`: the comparison tables ranked by combined accuracy, metrics with clean tools, and the val → held-out gap.

A run that fails (for example, a missing checkpoint) is recorded with `status: error` and its message. No numbers are filled in for it.
