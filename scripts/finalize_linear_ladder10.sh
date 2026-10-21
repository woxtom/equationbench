#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
DRIVER_PID="${1:?driver pid required}"
LOG="${EQB_LADDER10_LOG_DIR:-/tmp/eqb-linear-ladder10}/finalize.log"
echo "[$(date -u +%FT%TZ)] waiting for driver $DRIVER_PID" >> "$LOG"
while kill -0 "$DRIVER_PID" 2>/dev/null; do sleep 30; done
echo "[$(date -u +%FT%TZ)] driver finished; building 10-task ladder leaderboard" >> "$LOG"
.venv/bin/eqb leaderboard build \
  --runs runs/linear-ladder-10 \
  --dataset datasets/equationbench-v1-test-linear-ladder-10 \
  --out leaderboard-linear-ladder \
  --title "EquationBench Linear Ladder (10 tasks)" \
  --subset-note "2 tasks each at 16/18/20/22/24 variables · max reasoning · direct keys" \
  --bootstrap 2000 >> "$LOG" 2>&1
echo "[$(date -u +%FT%TZ)] build finished exit=$?" >> "$LOG"
