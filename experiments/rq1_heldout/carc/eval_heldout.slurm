#!/bin/bash --login
# RQ1: all six detectors on val (dev reference) and on the held-out MCPTox categories.
# Inference only: loads the existing fine-tuned checkpoints, trains nothing.
#
#   sbatch experiments/rq1_heldout/carc/eval_heldout.slurm
#
# The held-out run sets FINAL_EVAL=1 (team test guard). evaluate.py keeps only held-out
# categories + clean test tools; the seen-category test cases are never scored.
#SBATCH --job-name=rq1-heldout
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

# Fail fast if the cached model files hang on read (seen 2026-10-12 on /scratch1: the job sat
# in stat() until the time limit). Read everything Stage II needs; give up after 120 s.
OK_FLAG=/tmp/rq1_preflight_$SLURM_JOB_ID
( cat "$HF_HOME"/hub/models--GenTelLab--MCP-Guard/snapshots/*/* \
      "$HF_HOME"/hub/models--google-bert--bert-base-uncased/snapshots/*/* \
      "$CKPT_ROOT"/*/config.json "$CKPT_ROOT"/*/tokenizer_config.json > /dev/null && touch "$OK_FLAG" ) &
for i in $(seq 1 24); do [ -f "$OK_FLAG" ] && break; sleep 5; done
[ -f "$OK_FLAG" ] || { echo "preflight FAILED: model files did not read within 120 s"; exit 1; }
echo "preflight ok"

uv run python -m experiments.rq1_heldout.evaluate --split val --ckpt-root "$CKPT_ROOT"
FINAL_EVAL=1 uv run python -m experiments.rq1_heldout.evaluate --split heldout --ckpt-root "$CKPT_ROOT"
uv run python -m experiments.rq1_heldout.report

chmod -R g+rwX results/rq1_heldout 2>/dev/null || true
