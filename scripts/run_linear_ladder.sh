#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
LOG_DIR="${EQB_LINEAR_LADDER_LOG_DIR:-/tmp/eqb-linear-ladder}"
mkdir -p "$LOG_DIR/logs"
echo "[$(date -u +%FT%TZ)] linear ladder sweep starting" | tee -a "$LOG_DIR/driver.log"
MODELS=(
  deepseek-v4-1-flash
  openai-gpt-6-luna
  openai-gpt-6-sol
  openai-gpt-6-1-sol
)
printf '%s\n' "${MODELS[@]}" | xargs -P 4 -I{} bash -c '
  model="$1"; log_dir="$2"
  echo "[$(date -u +%FT%TZ)] start $model" | tee -a "$log_dir/driver.log"
  .venv/bin/eqb run \
    --model "$model" \
    --dataset datasets/equationbench-v1-test-linear-ladder \
    --out "runs/linear-ladder/$model" \
    --concurrency 2 \
    --timeout 1800 \
    --thinking max \
    --retries 0 \
    --max-cost 2 \
    --notes "linear ladder 16x16/20x20/24x24; max reasoning; direct keys" \
    > "$log_dir/logs/$model.log" 2>&1
  code=$?
  echo "[$(date -u +%FT%TZ)] end $model exit=$code" | tee -a "$LOG_DIR/driver.log"
' _ {} "$LOG_DIR"
echo "[$(date -u +%FT%TZ)] linear ladder sweep finished" | tee -a "$LOG_DIR/driver.log"
