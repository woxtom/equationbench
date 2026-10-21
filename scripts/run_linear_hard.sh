#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
LOG_DIR="${EQB_LINEAR_HARD_LOG_DIR:-/tmp/eqb-linear-hard}"
mkdir -p "$LOG_DIR/logs"
echo "[$(date -u +%FT%TZ)] linear hard L6-L7 sweep starting" | tee -a "$LOG_DIR/driver.log"
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
    --dataset datasets/equationbench-v1-test-linear-hard \
    --out "runs/linear-hard/$model" \
    --concurrency 2 \
    --timeout 1800 \
    --thinking max \
    --retries 1 \
    --max-cost 2 \
    --notes "linear-hard L6/L7 sweep; 24x24 and 30x30; direct DeepSeek/OpenAI keys" \
    > "$log_dir/logs/$model.log" 2>&1
  code=$?
  echo "[$(date -u +%FT%TZ)] end $model exit=$code" | tee -a "$log_dir/driver.log"
' _ {} "$LOG_DIR"
echo "[$(date -u +%FT%TZ)] linear hard sweep finished" | tee -a "$LOG_DIR/driver.log"
