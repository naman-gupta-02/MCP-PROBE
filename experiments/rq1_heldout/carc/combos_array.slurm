#!/bin/bash --login
# RQ1 held-out combos: one array task per combination c1..c8 (experiments/rq1_heldout/combos/),
# at most 8 at once. Each task trains the 20 fine-tuned models on its own tune split, scores
# all six detectors on val / heldout / test, deletes each checkpoint after scoring, and writes
# results/rq1_combos/<combo>/ (gitignored).
#
#   sbatch experiments/rq1_heldout/carc/combos_array.slurm
#   sbatch --array=2 experiments/rq1_heldout/carc/combos_array.slurm      # just c3
#SBATCH --job-name=rq1-combos
#SBATCH --account=xiangren_1987
#SBATCH --partition=gpu
#SBATCH --gres=gpu:a40:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=03:00:00
#SBATCH --array=0-7%8
#SBATCH --output=/project2/xiangren_1987/group_12/logs/%x-%A_%a.out

set -euo pipefail
GROUP=/project2/xiangren_1987/group_12
REPO=$GROUP/MCP-PROBE
COMBO=c$((SLURM_ARRAY_TASK_ID + 1))

export UV_CACHE_DIR=/scratch1/$USER/.cache/uv
export HF_HOME=/scratch1/$USER/.cache/huggingface
export HF_HUB_OFFLINE=1   # every model is already cached; fail instead of downloading
export PY=$REPO/.venv/bin/python   # no `uv run`: parallel tasks must not sync the shared venv
export CKPT_BASE=$GROUP/checkpoints/rq1_combos
cd "$REPO"
echo "task $SLURM_ARRAY_TASK_ID -> $COMBO on $(hostname)"; nvidia-smi --query-gpu=name --format=csv,noheader
$PY -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" || { echo "no CUDA"; exit 1; }

# Fail fast if the cached model files hang on read (seen 2026-10-12 on /scratch1).
OK_FLAG=/tmp/rq1_preflight_${SLURM_JOB_ID}
( cat "$HF_HOME"/hub/models--GenTelLab--MCP-Guard/snapshots/*/* \
      "$HF_HOME"/hub/models--google-bert--bert-base-uncased/snapshots/*/* \
      "$HF_HOME"/hub/models--intfloat--multilingual-e5-base/snapshots/*/* > /dev/null && touch "$OK_FLAG" ) &
for i in $(seq 1 24); do [ -f "$OK_FLAG" ] && break; sleep 5; done
[ -f "$OK_FLAG" ] || { echo "preflight FAILED: model files did not read within 120 s"; exit 1; }
echo "preflight ok"

bash experiments/rq1_heldout/run_combo.sh "$COMBO"
chmod -R g+rwX "results/rq1_combos/$COMBO" 2>/dev/null || true
