# RQ1: held-out category evaluation

Results and analysis: [RESULTS.md](RESULTS.md) (first run) and [COMBOS_RESULTS.md](COMBOS_RESULTS.md) (8 other held-out combinations; per-combination files in [combos/results/](combos/results/)).

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
- `test`: the whole test split, 446 rows: 382 poisoned cases in three test cells (`new_server_known_cat` 155, `known_server_new_cat` 194, `new_server_new_cat` 33) + the same 64 clean tools. Needs `FINAL_EVAL=1`. This one also scores the seen-category cases on test servers.
- `val`: the dev reference (171 poisoned cases from seen categories on val servers + 49 clean tools), scored by the same code.

## Metrics

- **Category accuracy** = correct / n within a category. Every held-out case is poisoned, so this is recall; a block-everything detector scores 100%.
- **Combined accuracy** = pooled correct / pooled n over the three categories, not a mean of category accuracies (the unweighted mean is also logged for comparison, and the code asserts the pooled value).
- **Test cell recall** (`test` and `heldout`): pooled recall within each test cell, poisoned cases only.
- **With clean tools**: accuracy, precision, recall, F1, FPR and confusion matrix over held-out poisoned + clean test tools, overall and per category. FPR is also given over non-empty clean tools only, since MCP-Guard passes empty descriptions without scoring them.
- Fine-tuned variants: each seed is pooled first, then mean ± sample std over the 5 seeds. Per-seed values are in `runs.csv`.

## Run

```bash
sbatch experiments/rq1_heldout/carc/eval_heldout.slurm      # on CARC, where the checkpoints are: val + held-out
sbatch --dependency=afterany:<heldout job id> experiments/rq1_heldout/carc/eval_test.slurm   # whole test split

# or locally, with checkpoints from detectors/mcp_guard/train.py
uv run python -m experiments.rq1_heldout.evaluate --split val --ckpt-root <dir>
FINAL_EVAL=1 uv run python -m experiments.rq1_heldout.evaluate --split heldout --ckpt-root <dir>
FINAL_EVAL=1 uv run python -m experiments.rq1_heldout.evaluate --split test --ckpt-root <dir>
uv run python -m experiments.rq1_heldout.evaluate --split heldout --summarize-only   # rebuild summaries from saved runs
uv run python -m experiments.rq1_heldout.report                # -> report.md
uv run python -m experiments.rq1_heldout.report --split test   # -> report_test.md
```

Run the test job after the held-out one (`--dependency`): both write the shared Stage II score cache (`results/mcp_guard/cache.sqlite`), and the test report's gap table uses the val results.

## Outputs (`results/rq1_heldout/`, gitignored)

- `<split>/<model>/<config>[_seed<k>]/predictions.jsonl`: one line per row with case id, server, label, category, attack type, prediction, deciding stage, Stage II score and rule names. No description text or match excerpts.
- `<split>/<model>/<config>[_seed<k>]/metrics.json` and `log.txt`: checkpoint, sample counts, correct/incorrect, metrics, confusion matrix, evaluation time, any error.
- `<split>/runs.csv`: one row per run. `<split>/summary.{csv,json}`: one row per model and config (seed mean ± std).
- `report.md`: the comparison tables ranked by combined accuracy, metrics with clean tools, and the val → held-out gap.
- `report_test.md`: the same for the whole test split, with recall by test cell and by all ten risk categories.

A run that fails (for example, a missing checkpoint) is recorded with `status: error` and its message. No numbers are filled in for it.

## Robustness check: other held-out combinations (branch `rq1/heldout-split2`)

To check that the RQ1 result is not specific to the three categories above, the whole pipeline is repeated on 8 other 3-category hold-outs: build the split, **retrain** the 20 fine-tuned models on that split's `tune`, score all six detectors on its val / held-out / whole test, and summarize.

- **Selection** ([combos.py](combos.py), fixed before any results). The pool is the 7 categories not held out in the first run (`Other`, 4 cases, excluded). We drew 8 of the 35 three-category combinations at random with seed 2026, redrawing until each category is held out 3–4 times. The draw is in [combos/combos.json](combos/combos.json), and each combination has its own split file `combos/c<k>.json`. Servers are the same as in `server_split.json`.
- **Splits** are built by `scripts/build_splits.py`, unchanged: [combos.py](combos.py) only redirects its input and output paths. Rebuilding the original split this way reproduces `data/processed/` byte for byte.
- **Per combination**, [run_combo.sh](run_combo.sh) trains each model, scores it, then deletes its checkpoint. It keeps `train_meta/<run>.json` and its log, and uses its own Stage II score cache.
- **On CARC**, [carc/combos_array.slurm](carc/combos_array.slurm) is a job array with one A40 task per combination, up to 8 at once. Training uses the same settings as the first run (`detectors/mcp_guard/train.py` defaults).

| Combo | Held-out categories |
|---|---|
| c1 | Code Injection, Data Tampering, Message Hijacking |
| c2 | Code Injection, Data Tampering, Privacy Leakage |
| c3 | Code Injection, Privacy Leakage, Service Disruption |
| c4 | Data Tampering, Information Manipulation, Service Disruption |
| c5 | Data Tampering, Infrastructure Damage, Privacy Leakage |
| c6 | Information Manipulation, Infrastructure Damage, Message Hijacking |
| c7 | Information Manipulation, Infrastructure Damage, Service Disruption |
| c8 | Information Manipulation, Message Hijacking, Service Disruption |

```bash
sbatch experiments/rq1_heldout/carc/combos_array.slurm          # all 8 on CARC
bash experiments/rq1_heldout/run_combo.sh c3                    # one combo locally (DEVICE=mps|cpu|cuda)
uv run python -m experiments.rq1_heldout.combos_report          # all combos side by side -> results/rq1_combos/combos_report.md
```

Outputs go to `results/rq1_combos/<combo>/` (gitignored), with the same layout as `results/rq1_heldout/` plus `data/`, `split_report.md` and `train_meta/`.
