#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
DRIVER_PID="${1:?driver pid required}"
LOG="${EQB_LINEAR_HARD_LOG_DIR:-/tmp/eqb-linear-hard}/finalize.log"
echo "[$(date -u +%FT%TZ)] waiting for driver $DRIVER_PID" >> "$LOG"
while kill -0 "$DRIVER_PID" 2>/dev/null; do sleep 30; done
echo "[$(date -u +%FT%TZ)] driver finished; building linear hard leaderboard" >> "$LOG"
.venv/bin/eqb leaderboard build \
  --runs runs/linear-hard \
  --dataset datasets/equationbench-v1-test-linear-hard \
  --out leaderboard-linear-hard \
  --title "EquationBench Linear Hard (L6-L7)" \
  --subset-note "L6 24x24 · L7 30x30 · max reasoning · direct keys" \
  --bootstrap 2000 >> "$LOG" 2>&1
echo "[$(date -u +%FT%TZ)] build finished exit=$?" >> "$LOG"
