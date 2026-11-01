#!/usr/bin/env bash
# Run several models on a small frontier probe in parallel, with per-model logs.
#
# Usage:
#   LEVELS=6-7 TASKS=2 THINKING=high CONCURRENCY=4 PARALLEL=3 \
#     scripts/batch_frontier.sh model-key-a model-key-b model-key-c
set -u

MODELS=("$@")
if [ "${#MODELS[@]}" -eq 0 ]; then
  echo "usage: $0 <model-key> [model-key ...]" >&2
  exit 2
fi

LEVELS="${LEVELS:-6-7}"
TASKS="${TASKS:-2}"
THINKING="${THINKING:-high}"
CONCURRENCY="${CONCURRENCY:-4}"
TIMEOUT="${TIMEOUT:-900}"
RETRIES="${RETRIES:-1}"
MAX_COST="${MAX_COST:-1.5}"
BOOTSTRAP="${BOOTSTRAP:-100}"
PARALLEL="${PARALLEL:-3}"
OUT_ROOT="${OUT_ROOT:-runs/probes/2026-10/batch}"
EQB_BIN="${EQB_BIN:-.venv/bin/eqb}"

mkdir -p "$OUT_ROOT"
echo "batch: levels=$LEVELS tasks/level=$TASKS thinking=$THINKING concurrency=$CONCURRENCY parallel=$PARALLEL"
echo "logs:  $OUT_ROOT/<model>.log"
echo "runs:  $OUT_ROOT/<model>"

pids=()
keys=()
flush() {
  local i
  for i in "${!pids[@]}"; do
    wait "${pids[$i]}" || true
    echo "done: ${keys[$i]} (see $OUT_ROOT/${keys[$i]}.log)"
  done
  pids=()
  keys=()
}

for key in "${MODELS[@]}"; do
  log="$OUT_ROOT/$key.log"
  run="$OUT_ROOT/$key"
  echo "launch: $key"
  "$EQB_BIN" run-frontier \
    --model "$key" \
    --levels "$LEVELS" \
    --tasks-per-level "$TASKS" \
    --out "$run" \
    --thinking "$THINKING" \
    --concurrency "$CONCURRENCY" \
    --timeout "$TIMEOUT" \
    --retries "$RETRIES" \
    --max-cost "$MAX_COST" \
    --bootstrap "$BOOTSTRAP" \
    --notes "batch stability probe: go route, L$LEVELS, $TASKS/level, thinking=$THINKING" \
    >"$log" 2>&1 &
  pids+=("$!")
  keys+=("$key")
  if [ "${#pids[@]}" -ge "$PARALLEL" ]; then
    flush
  fi
done
flush

echo
echo "=== summaries ==="
for key in "${MODELS[@]}"; do
  echo "--- $key ---"
  tail -12 "$OUT_ROOT/$key.log" 2>/dev/null || echo "no log"
done
