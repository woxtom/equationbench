#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
LOG_DIR="${EQB_LINEAR_DIRECT_LOG_DIR:-/tmp/eqb-linear-direct}"
mkdir -p "$LOG_DIR/logs"
echo "[$(date -u +%FT%TZ)] direct-key linear sweep starting" | tee -a "$LOG_DIR/driver.log"
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
    --dataset datasets/equationbench-v1-test-linear \
    --out "runs/linear-direct/$model" \
    --concurrency 2 \
    --timeout 0 \
    --thinking max \
    --retries 2 \
    --max-cost 2 \
    --notes "linear-only 10-task sweep; direct DeepSeek/OpenAI keys; max reasoning" \
    > "$log_dir/logs/$model.log" 2>&1
  code=$?
  echo "[$(date -u +%FT%TZ)] end $model exit=$code" | tee -a "$log_dir/driver.log"
' _ {} "$LOG_DIR"
echo "[$(date -u +%FT%TZ)] direct-key linear sweep finished" | tee -a "$LOG_DIR/driver.log"
