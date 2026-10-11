#!/bin/bash --login
# RQ1: all six detectors on the whole MCPTox test split (446 rows: every test cell + clean test tools).
# Inference only: loads the existing fine-tuned checkpoints, trains nothing.
#
#   sbatch experiments/rq1_heldout/carc/eval_test.slurm
#
# Sets FINAL_EVAL=1 (team test guard). Unlike eval_heldout.slurm, this also scores the
# seen-category cases on test servers. The val reference comes from eval_heldout.slurm;
# report_test.md adds the val -> test gap once results/rq1_heldout/val/ exists.
#SBATCH --job-name=rq1-test
#SBATCH --account=xiangren_1987
#SBATCH --partition=gpu
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=/project2/xiangren_1987/group_12/logs/%x-%j.out

set -euo pipefail
GROUP=/project2/xiangren_1987/group_12
REPO=$GROUP/MCP-PROBE
CKPT_ROOT=${CKPT_ROOT:-$GROUP/checkpoints/mcp_guard}

export UV_CACHE_DIR=/scratch1/$USER/.cache/uv
export HF_HOME=/scratch1/$USER/.cache/huggingface
export HF_HUB_OFFLINE=1   # every model is already cached; fail instead of downloading
export PATH=$HOME/.local/bin:$PATH
cd "$REPO"
git log -1 --format='commit %H' && nvidia-smi --query-gpu=name --format=csv,noheader

FINAL_EVAL=1 uv run python -m experiments.rq1_heldout.evaluate --split test --ckpt-root "$CKPT_ROOT"
uv run python -m experiments.rq1_heldout.report --split test

chmod -R g+rwX results/rq1_heldout 2>/dev/null || true
