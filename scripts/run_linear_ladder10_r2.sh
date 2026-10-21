#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
LOG_DIR="${EQB_LADDER10_R2_LOG_DIR:-/tmp/eqb-linear-ladder10-r2}"
mkdir -p "$LOG_DIR/logs"
echo "[$(date -u +%FT%TZ)] 10-task ladder repeat run starting" | tee -a "$LOG_DIR/driver.log"
MODELS=(
  deepseek-v4-1-flash
  openai-gpt-5-6-sol
  openai-gpt-6-luna
  openai-gpt-6-sol
  openai-gpt-6-1-sol
)
printf '%s\n' "${MODELS[@]}" | xargs -P 5 -I{} bash -c '
  model="$1"; log_dir="$2"
  echo "[$(date -u +%FT%TZ)] start $model" | tee -a "$log_dir/driver.log"
  .venv/bin/eqb run \
    --model "$model" \
    --dataset datasets/equationbench-v1-test-linear-ladder-10 \
    --out "runs/linear-ladder-10-r2/$model" \
    --concurrency 2 \
    --timeout 1800 \
    --thinking max \
    --retries 0 \
    --max-cost 5 \
    --notes "repeat run of 10-task ladder; fresh predictions; max reasoning; direct keys" \
    > "$log_dir/logs/$model.log" 2>&1
  code=$?
  echo "[$(date -u +%FT%TZ)] end $model exit=$code" | tee -a "$LOG_DIR/driver.log"
' _ {} "$LOG_DIR"
echo "[$(date -u +%FT%TZ)] 10-task repeat run finished" | tee -a "$LOG_DIR/driver.log"
