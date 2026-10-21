#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
DRIVER_PID="${1:?driver pid required}"
LOG="${EQB_LINEAR_LADDER_LOG_DIR:-/tmp/eqb-linear-ladder}/finalize.log"
echo "[$(date -u +%FT%TZ)] waiting for driver $DRIVER_PID" >> "$LOG"
while kill -0 "$DRIVER_PID" 2>/dev/null; do sleep 30; done
echo "[$(date -u +%FT%TZ)] driver finished; building linear ladder leaderboard" >> "$LOG"
.venv/bin/eqb leaderboard build \
  --runs runs/linear-ladder \
  --dataset datasets/equationbench-v1-test-linear-ladder \
  --out leaderboard-linear-ladder \
  --title "EquationBench Linear Ladder (16/20/24)" \
  --subset-note "L5 16x16 · L6 20x20 · L7 24x24 · max reasoning · direct keys" \
  --bootstrap 2000 >> "$LOG" 2>&1
echo "[$(date -u +%FT%TZ)] build finished exit=$?" >> "$LOG"
