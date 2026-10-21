#!/bin/bash
# Full RQ1 pipeline for one held-out category combination (see combos.py):
# build the split, train the 20 fine-tuned models on its tune split, score all six
# detectors on val / heldout / test, delete each checkpoint after scoring, summarize.
#
#   experiments/rq1_heldout/run_combo.sh c3
#
# Environment (all optional):
#   PY         python to use (default .venv/bin/python)
#   OUT_BASE   results root (default results/rq1_combos); writes $OUT_BASE/<combo>/
#   CKPT_BASE  temporary checkpoint root (default $OUT_BASE/_ckpt); emptied as it goes
#   DEVICE     training device for train.py (default auto)
#   SEEDS      default "0 1 2 3 4";  INITS default "mcpguard e5base";  SCOPES default "full head"
#   TRAIN_ARGS extra train.py args (e.g. "--limit 32 --epochs 1" for a smoke test)
set -uo pipefail
COMBO=$1
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
PY=${PY:-$ROOT/.venv/bin/python}
OUT_BASE=${OUT_BASE:-$ROOT/results/rq1_combos}
OUT=$OUT_BASE/$COMBO
CKPT=${CKPT_BASE:-$OUT_BASE/_ckpt}/$COMBO
SEEDS=${SEEDS:-"0 1 2 3 4"}
INITS=${INITS:-"mcpguard e5base"}
SCOPES=${SCOPES:-"full head"}
DEVICE=${DEVICE:-auto}
TRAIN_ARGS=${TRAIN_ARGS:-}
export FINAL_EVAL=1 PYTHONWARNINGS=ignore
mkdir -p "$OUT/train_meta" "$CKPT"
echo "== $(date +%T) $COMBO: $(git log -1 --format=%h) -> $OUT"

"$PY" -m experiments.rq1_heldout.combos build --combo "$COMBO" --out "$OUT" || exit 1
# Per-combo Stage II score cache, so parallel combos never share one sqlite file.
sed "s#^cache_path:.*#cache_path: $OUT/cache.sqlite#" configs/mcp_guard.yaml > "$OUT/mcp_guard.yaml"
COMMON=(--split-file "experiments/rq1_heldout/combos/$COMBO.json" --data-dir "$OUT/data"
        --out-root "$OUT" --config "$OUT/mcp_guard.yaml" --ckpt-root "$CKPT")
EV() { "$PY" -m experiments.rq1_heldout.evaluate "${COMMON[@]}" "$@" 2>&1 | grep -E '^\[|runs,|^heldout:'; }

for split in val heldout test; do EV --split $split --models frozen_mcpguard,mcp_guardian; done

for init in $INITS; do
  for scope in $SCOPES; do
    for seed in $SEEDS; do
      run=${init}_${scope}_seed${seed}
      t0=$(date +%s)
      if "$PY" -m detectors.mcp_guard.train --init $init --scope $scope --seed $seed --device "$DEVICE" \
           --data-dir "$OUT/data" --out-root "$CKPT" $TRAIN_ARGS > "$OUT/train_meta/$run.log" 2>&1; then
        cp "$CKPT/$run/train_meta.json" "$OUT/train_meta/$run.json"
        echo "== $(date +%T) trained $run in $(( $(date +%s) - t0 ))s ($(tail -1 "$OUT/train_meta/$run.log"))"
      else
        echo "== $(date +%T) TRAIN FAILED $run (see train_meta/$run.log)"   # evaluate records it as an error
      fi
      for split in val heldout test; do EV --split $split --models ${init}_${scope} --seeds $seed; done
      rm -rf "$CKPT/$run"
    done
  done
done

for split in val heldout test; do "$PY" -m experiments.rq1_heldout.evaluate "${COMMON[@]}" --split $split --summarize-only | tail -1; done
"$PY" -m experiments.rq1_heldout.report --out-root "$OUT" > /dev/null
"$PY" -m experiments.rq1_heldout.report --out-root "$OUT" --split test > /dev/null
rmdir "$CKPT" 2>/dev/null
echo "== $(date +%T) $COMBO DONE: $(ls "$OUT"/report*.md | xargs -n1 basename | tr '\n' ' ')"
