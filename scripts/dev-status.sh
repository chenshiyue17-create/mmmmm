#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION_NAME="freqtrade-deploy"

cd "$ROOT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

PORT="${FREQTRADE_UI_PORT:-8080}"
READONLY_PROXY_ENABLED="${READONLY_PROXY_ENABLED:-0}"
if [ "$READONLY_PROXY_ENABLED" = "1" ]; then
  BACKEND_PORT="${FREQTRADE_BACKEND_PORT:-18080}"
else
  BACKEND_PORT="$PORT"
fi
PROXY_SESSION="${SESSION_NAME}-proxy"
WATCH_SESSION="freqtrade-auto-watch"
GEMINI_SESSION="freqtrade-gemini-optimizer"
GUARDIAN_SESSION="freqtrade-stability-guardian"
CAFFEINATE_SESSION="freqtrade-caffeinate"

echo "Project: $ROOT_DIR"
SCREEN_OUTPUT="$(screen -list 2>/dev/null || true)"
if grep -q "[.]${SESSION_NAME}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  echo "screen: running (${SESSION_NAME})"
else
  echo "screen: stopped"
fi
if [ "$READONLY_PROXY_ENABLED" = "1" ] && grep -q "[.]${PROXY_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  echo "proxy: running (${PROXY_SESSION})"
elif [ "$READONLY_PROXY_ENABLED" = "1" ]; then
  echo "proxy: stopped"
else
  echo "proxy: disabled"
fi
if grep -q "[.]${WATCH_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  echo "auto-watch: running (${WATCH_SESSION})"
else
  echo "auto-watch: stopped"
fi
if grep -q "[.]${GEMINI_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  echo "gemini-optimizer: running (${GEMINI_SESSION})"
else
  echo "gemini-optimizer: stopped"
fi
if grep -q "[.]${GUARDIAN_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  echo "stability-guardian: running (${GUARDIAN_SESSION})"
else
  echo "stability-guardian: stopped"
fi
if command -v caffeinate >/dev/null 2>&1; then
  if grep -q "[.]${CAFFEINATE_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
    echo "sleep-prevention: running (${CAFFEINATE_SESSION})"
  else
    echo "sleep-prevention: stopped"
  fi
else
  echo "sleep-prevention: unavailable"
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose ps
  if curl -fsS "http://localhost:${BACKEND_PORT}/api/v1/ping" >/dev/null 2>&1; then
    echo "backend api: reachable on 127.0.0.1:${BACKEND_PORT}"
  else
    echo "backend api: not reachable yet"
  fi
  if curl -fsS "http://localhost:${PORT}/api/v1/ping" >/dev/null 2>&1; then
    echo "ui/api entry: reachable on 127.0.0.1:${PORT}"
  else
    echo "ui/api entry: not reachable yet"
  fi
else
  echo "docker: unavailable"
fi

echo "UI: http://localhost:${PORT}${FREQTRADE_START_PATH:-/dashboard}"
