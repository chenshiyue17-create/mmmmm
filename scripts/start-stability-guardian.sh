#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION_NAME="freqtrade-stability-guardian"

cd "$ROOT_DIR"

screen -list 2>/dev/null | awk -v name="$SESSION_NAME" '$1 ~ "^[0-9]+\\." name "$" {print $1}' | while read -r session_id; do
  screen -S "$session_id" -X quit || true
done || true

mkdir -p logs output
export GUARDIAN_RUNTIME_HOURS="${GUARDIAN_RUNTIME_HOURS:-0}"
if command -v caffeinate >/dev/null 2>&1; then
  screen -list 2>/dev/null | awk '$1 ~ /^[0-9]+\\.freqtrade-caffeinate$/ {print $1}' | while read -r session_id; do
    screen -S "$session_id" -X quit || true
  done || true
  screen -dmS freqtrade-caffeinate bash -lc "caffeinate -dimsu"
fi
screen -dmS "$SESSION_NAME" bash -lc "cd '$ROOT_DIR' && GUARDIAN_RUNTIME_HOURS='${GUARDIAN_RUNTIME_HOURS}' python3 scripts/stability-guardian.py"
sleep 1
GUARDIAN_ONCE=1 python3 scripts/stability-guardian.py >/dev/null
echo "stability-guardian: running (${SESSION_NAME})"
echo "status: output/stability-guardian-status.json"
echo "events: output/stability-guardian-events.jsonl"
echo "runtime: ${GUARDIAN_RUNTIME_HOURS} hours (0 means until manual stop)"
