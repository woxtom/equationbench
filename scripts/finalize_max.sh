#!/usr/bin/env bash
# Wait for the max-reasoning sweep, then build the public leaderboard.
set -u
cd "$(dirname "$0")/.."
DRIVER_PID="${1:?driver pid required}"
LOG="${EQB_MAX_LOG_DIR:-/tmp/eqb-full-max}/finalize.log"
echo "[$(date -u +%FT%TZ)] waiting for driver $DRIVER_PID" >> "$LOG"
while kill -0 "$DRIVER_PID" 2>/dev/null; do sleep 60; done
echo "[$(date -u +%FT%TZ)] driver finished; building leaderboard" >> "$LOG"
.venv/bin/eqb leaderboard build \
  --runs runs/full \
  --dataset datasets/equationbench-v1-test \
  --out leaderboard \
  --title "EquationBench Max-Reasoning Leaderboard" \
  --bootstrap 2000 >> "$LOG" 2>&1
echo "[$(date -u +%FT%TZ)] leaderboard build finished exit=$?" >> "$LOG"
