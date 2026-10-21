#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
DRIVER_PID="${1:?driver pid required}"
LOG="${EQB_LINEAR_DIRECT_LOG_DIR:-/tmp/eqb-linear-direct}/finalize.log"
echo "[$(date -u +%FT%TZ)] waiting for driver $DRIVER_PID" >> "$LOG"
while kill -0 "$DRIVER_PID" 2>/dev/null; do sleep 30; done
echo "[$(date -u +%FT%TZ)] driver finished; building linear direct leaderboard" >> "$LOG"
.venv/bin/eqb leaderboard build \
  --runs runs/linear-direct \
  --dataset datasets/equationbench-v1-test-linear \
  --out leaderboard-linear \
  --title "EquationBench Linear Track (Max Reasoning)" \
  --subset-note "max reasoning · direct DeepSeek/OpenAI keys" \
  --bootstrap 2000 >> "$LOG" 2>&1
echo "[$(date -u +%FT%TZ)] build finished exit=$?" >> "$LOG"
