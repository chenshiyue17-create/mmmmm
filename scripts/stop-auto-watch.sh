#!/usr/bin/env bash
set -euo pipefail

SESSION_NAME="freqtrade-auto-watch"

screen -list 2>/dev/null | awk -v name="$SESSION_NAME" '$1 ~ "^[0-9]+\\." name "$" {print $1}' | while read -r session_id; do
  screen -S "$session_id" -X quit || true
done || true

echo "Stopped ${SESSION_NAME}."
