#!/usr/bin/env bash
# Complete the 70-task full-set sweep for the opencode-go models.
set -u
cd "$(dirname "$0")/.."
LOG_DIR="${EQB_FULL_LOG_DIR:-/tmp/eqb-full-remaining}"
mkdir -p "$LOG_DIR/logs"
echo "[$(date -u +%FT%TZ)] remaining full sweep starting" | tee -a "$LOG_DIR/driver.log"
MODELS=(
  openai-gpt-5-6-luna
  anthropic-claude-haiku-5-5
  zai-glm-5-3-flash
  xiaomi-mimo-v2-6-flash
  minimax-m3
  longcat-2-5-preview-free
)
printf '%s\n' "${MODELS[@]}" | xargs -P 3 -I{} bash -c '
  model="$1"; log_dir="$2"
  echo "[$(date -u +%FT%TZ)] start $model" | tee -a "$log_dir/driver.log"
  .venv/bin/eqb run \
    --model "$model" \
    --dataset datasets/equationbench-v1-test \
    --out "runs/full/$model" \
    --concurrency 2 \
    --timeout 0 \
    --retries 2 \
    --thinking off \
    --max-cost 5 \
    --notes "full 70-task run; no wall-clock timeout; provider-reported model id" \
    > "$log_dir/logs/$model.log" 2>&1
  code=$?
  echo "[$(date -u +%FT%TZ)] end $model exit=$code" | tee -a "$log_dir/driver.log"
' _ {} "$LOG_DIR"
echo "[$(date -u +%FT%TZ)] remaining sweep finished" | tee -a "$LOG_DIR/driver.log"
