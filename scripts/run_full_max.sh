#!/usr/bin/env bash
# Full 70-task sweep at the highest supported reasoning effort.
set -u
cd "$(dirname "$0")/.."
LOG_DIR="${EQB_MAX_LOG_DIR:-/tmp/eqb-full-max}"
mkdir -p "$LOG_DIR/logs"
echo "[$(date -u +%FT%TZ)] max-reasoning full sweep starting" | tee -a "$LOG_DIR/driver.log"
MODELS=(
  deepseek-v4-1-flash
  deepseek-v4-pro
  openai-gpt-5-6-luna
  anthropic-claude-haiku-5-5
  zai-glm-5-3-flash
  xiaomi-mimo-v2-6-flash
  minimax-m3
  longcat-2-5-preview-free
)
printf '%s\n' "${MODELS[@]}" | xargs -P 4 -I{} bash -c '
  model="$1"; log_dir="$2"
  echo "[$(date -u +%FT%TZ)] start $model" | tee -a "$log_dir/driver.log"
  .venv/bin/eqb run \
    --model "$model" \
    --dataset datasets/equationbench-v1-test \
    --out "runs/full/$model" \
    --concurrency 2 \
    --timeout 0 \
    --thinking max \
    --retries 2 \
    --max-cost 8 \
    --notes "full 70-task run; highest reasoning; no wall-clock timeout; provider-reported model id" \
    > "$log_dir/logs/$model.log" 2>&1
  code=$?
  echo "[$(date -u +%FT%TZ)] end $model exit=$code" | tee -a "$LOG_DIR/driver.log"
' _ {} "$LOG_DIR"
echo "[$(date -u +%FT%TZ)] max-reasoning sweep finished" | tee -a "$LOG_DIR/driver.log"
