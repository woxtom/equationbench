#!/usr/bin/env bash
# Run the full 70-task public test set for the cheap/flash model set.
#
# The per-task timeout is 0: providers may be fast or slow, and we do not want
# throughput to decide the score. Each model gets two workers; four models run
# concurrently to keep gateway load reasonable.
set -u
cd "$(dirname "$0")/.."

LOG_DIR="${EQB_FULL_LOG_DIR:-/tmp/eqb-full}"
mkdir -p "$LOG_DIR/logs"
echo "[$(date -u +%FT%TZ)] full 70-task sweep starting" | tee -a "$LOG_DIR/driver.log"

MODELS=(
  deepseek-v4-1-flash
  zai-glm-5-3-flash
  openai-gpt-5-6-luna
  anthropic-claude-haiku-5-5
  deepseek-v4-pro
  xiaomi-mimo-v2-6-flash
  minimax-m3
  longcat-2-5-preview-free
)

printf '%s\n' "${MODELS[@]}" | xargs -P 4 -I{} bash -c '
  model="$1"
  log_dir="$2"
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

echo "[$(date -u +%FT%TZ)] full sweep finished" | tee -a "$LOG_DIR/driver.log"
