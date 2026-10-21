#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
DRIVER_PID="${1:?driver pid required}"
LOG="${EQB_LADDER6_LOG_DIR:-/tmp/eqb-linear-ladder6}/finalize.log"
echo "[$(date -u +%FT%TZ)] waiting for driver $DRIVER_PID" >> "$LOG"
while kill -0 "$DRIVER_PID" 2>/dev/null; do sleep 30; done
echo "[$(date -u +%FT%TZ)] driver finished; building 6-task ladder leaderboard" >> "$LOG"
.venv/bin/eqb leaderboard build \
  --runs runs/linear-ladder-6 \
  --dataset datasets/equationbench-v1-test-linear-ladder-6 \
  --out leaderboard-linear-ladder \
  --title "EquationBench Linear Ladder (6 tasks)" \
  --subset-note "2 tasks each at 16x16 / 20x20 / 24x24 · max reasoning · direct keys" \
  --bootstrap 2000 >> "$LOG" 2>&1
echo "[$(date -u +%FT%TZ)] build finished exit=$?" >> "$LOG"
