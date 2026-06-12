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

python3 -m pytest tests
scripts/validate-config.sh

docker compose ps --status running | grep -q "freqtrade-dryrun"
for _ in $(seq 1 30); do
  if curl -fsS "http://localhost:${BACKEND_PORT}/api/v1/ping" | grep -q '"pong"'; then
    API_READY=1
    break
  fi
  sleep 1
done
test "${API_READY:-0}" = "1"
SCREEN_OUTPUT="$(screen -list 2>/dev/null || true)"
grep -q "[.]${SESSION_NAME}[[:space:]]" <<< "$SCREEN_OUTPUT"
if [ "$READONLY_PROXY_ENABLED" = "1" ]; then
  grep -q "[.]${PROXY_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"
fi
BOT_LOGS="$(docker logs --tail 300 freqtrade-dryrun 2>&1)"
grep -Eq "Starting Local Rest Server|Uvicorn running|Application startup complete|state='RUNNING'" <<< "$BOT_LOGS"
if [ "$READONLY_PROXY_ENABLED" = "1" ]; then
  test "$(curl -sS -o /tmp/freqtrade-proxy-api-check.txt -w '%{http_code}' "http://localhost:${PORT}/api/v1/ping")" = "403"
  test "$(curl -sS -o /tmp/freqtrade-proxy-openapi-check.txt -w '%{http_code}' "http://localhost:${PORT}/openapi.json")" = "403"
  grep -q "交易安全模式" /tmp/freqtrade-proxy-api-check.txt
else
  curl -fsS "http://localhost:${PORT}/api/v1/ping" | grep -q '"pong"'
  curl -fsS "http://localhost:${PORT}${FREQTRADE_START_PATH:-/dashboard}" | grep -Eiq "freqtrade|root|html"
fi

echo "Runtime verification passed."
