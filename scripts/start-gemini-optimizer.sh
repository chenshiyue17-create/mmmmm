#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION_NAME="freqtrade-gemini-optimizer"

cd "$ROOT_DIR"

screen -list 2>/dev/null | awk -v name="$SESSION_NAME" '$1 ~ "^[0-9]+\\." name "$" {print $1}' | while read -r session_id; do
  screen -S "$session_id" -X quit || true
done || true

mkdir -p logs output
screen -dmS "$SESSION_NAME" bash -lc "cd '$ROOT_DIR' && python3 scripts/gemini-optimizer.py"
echo "gemini-optimizer: running (${SESSION_NAME})"
echo "status: output/gemini-optimizer-status.json"
echo "report: output/gemini-optimizer-report.md"
