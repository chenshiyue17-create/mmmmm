#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION_NAME="freqtrade-deploy"
PROXY_SESSION="${SESSION_NAME}-proxy"
WATCH_SESSION="freqtrade-auto-watch"
GEMINI_SESSION="freqtrade-gemini-optimizer"
GUARDIAN_SESSION="freqtrade-stability-guardian"
CAFFEINATE_SESSION="freqtrade-caffeinate"

cd "$ROOT_DIR"

stop_screen_sessions() {
  local name="$1"
  screen -list 2>/dev/null | awk -v name="$name" '$1 ~ "^[0-9]+\\." name "$" {print $1}' | while read -r session_id; do
    screen -S "$session_id" -X quit || true
  done || true
}

SCREEN_OUTPUT="$(screen -list 2>/dev/null || true)"
if grep -q "[.]${SESSION_NAME}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  stop_screen_sessions "$SESSION_NAME"
fi
if grep -q "[.]${PROXY_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  stop_screen_sessions "$PROXY_SESSION"
fi
if grep -q "[.]${WATCH_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  stop_screen_sessions "$WATCH_SESSION"
fi
if grep -q "[.]${GEMINI_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  stop_screen_sessions "$GEMINI_SESSION"
fi
if grep -q "[.]${GUARDIAN_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  stop_screen_sessions "$GUARDIAN_SESSION"
fi
if grep -q "[.]${CAFFEINATE_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  stop_screen_sessions "$CAFFEINATE_SESSION"
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose down
fi

echo "Stopped ${SESSION_NAME}, ${PROXY_SESSION}, ${WATCH_SESSION}, ${GEMINI_SESSION}, ${GUARDIAN_SESSION}, and ${CAFFEINATE_SESSION}."
