#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION_NAME="freqtrade-deploy"
MOUNT_ROOT="/Volumes/NINJAV"

cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.11 || command -v python3.10 || command -v python3.9 || command -v python3)}"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
if [ -x scripts/export-keychain-secrets.sh ]; then
  eval "$(scripts/export-keychain-secrets.sh)"
fi

PORT="${FREQTRADE_UI_PORT:-8080}"
READONLY_PROXY_ENABLED="${READONLY_PROXY_ENABLED:-0}"
if [ "$READONLY_PROXY_ENABLED" = "1" ]; then
  BACKEND_PORT="${FREQTRADE_BACKEND_PORT:-18080}"
else
  BACKEND_PORT="$PORT"
fi
export FREQTRADE_BACKEND_PORT="$BACKEND_PORT"
PROXY_SESSION="${SESSION_NAME}-proxy"
WATCH_SESSION="freqtrade-auto-watch"
GEMINI_SESSION="freqtrade-gemini-optimizer"
GUARDIAN_SESSION="freqtrade-stability-guardian"
CAFFEINATE_SESSION="freqtrade-caffeinate"

stop_screen_sessions() {
  local name="$1"
  screen -list 2>/dev/null | awk -v name="$name" '$1 ~ "^[0-9]+\\." name "$" {print $1}' | while read -r session_id; do
    screen -S "$session_id" -X quit || true
  done || true
}

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker CLI is not installed. Run: scripts/install-runtime.sh" >&2
  exit 127
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is not available. Run: scripts/install-runtime.sh" >&2
  exit 127
fi

if command -v colima >/dev/null 2>&1; then
  if ! colima status >/dev/null 2>&1; then
    colima start --cpu 4 --memory 8 --disk 60 --mount "${MOUNT_ROOT}:w"
  fi
  docker context use colima >/dev/null 2>&1 || true
  if ! docker info >/dev/null 2>&1; then
    echo "Docker daemon is not responding. Restarting Colima ..."
    colima stop || true
    colima start --cpu 4 --memory 8 --disk 60 --mount "${MOUNT_ROOT}:w"
    docker context use colima >/dev/null 2>&1 || true
  fi
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not available after runtime startup." >&2
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Edit secrets before live trading."
fi

mkdir -p logs user_data/logs output
chmod a+rwx user_data logs user_data/logs output
chmod -R a+rwX logs user_data/logs output
find user_data/strategies -name '._*' -type f -delete
"$PYTHON_BIN" scripts/import-research-flow.py >/dev/null
"$PYTHON_BIN" scripts/generate-local-login.py >/dev/null
"$PYTHON_BIN" scripts/generate-analysis-data.py >/dev/null

SCREEN_OUTPUT="$(screen -list 2>/dev/null || true)"
if grep -q "[.]${SESSION_NAME}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  stop_screen_sessions "$SESSION_NAME"
  sleep 1
fi
if grep -q "[.]${PROXY_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  stop_screen_sessions "$PROXY_SESSION"
  sleep 1
fi
if grep -q "[.]${WATCH_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  stop_screen_sessions "$WATCH_SESSION"
  sleep 1
fi
if grep -q "[.]${GEMINI_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  stop_screen_sessions "$GEMINI_SESSION"
  sleep 1
fi
if grep -q "[.]${GUARDIAN_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  stop_screen_sessions "$GUARDIAN_SESSION"
  sleep 1
fi
if grep -q "[.]${CAFFEINATE_SESSION}[[:space:]]" <<< "$SCREEN_OUTPUT"; then
  stop_screen_sessions "$CAFFEINATE_SESSION"
  sleep 1
fi

compose_down() {
  docker compose down --remove-orphans >/dev/null 2>&1 || true
}

compose_up() {
  docker compose up -d
}

compose_down

for occupied_port in $(printf "%s\n%s\n" "$PORT" "$BACKEND_PORT" | sort -u); do
  if lsof -ti tcp:"$occupied_port" >/dev/null 2>&1; then
    lsof -ti tcp:"$occupied_port" | xargs kill -9
  fi
done

if ! compose_up; then
  if command -v colima >/dev/null 2>&1; then
    echo "Compose startup failed. Restarting Colima and retrying ..."
    colima stop || true
    colima start --cpu 4 --memory 8 --disk 60 --mount "${MOUNT_ROOT}:w"
    docker context use colima >/dev/null 2>&1 || true
    compose_down
    compose_up
  else
    exit 1
  fi
fi
screen -dmS "$SESSION_NAME" bash -lc "cd '$ROOT_DIR' && docker compose logs -f freqtrade 2>&1 | tee -a logs/freqtrade-compose.log"
API_READY=0
for _ in $(seq 1 60); do
  if curl -fsS "http://localhost:${BACKEND_PORT}/api/v1/ping" >/dev/null 2>&1; then
    API_READY=1
    break
  fi
  sleep 1
done
if [ "$API_READY" != "1" ]; then
  echo "Freqtrade API did not become reachable on port ${BACKEND_PORT}." >&2
  docker logs --tail 160 freqtrade-dryrun >&2 || true
  exit 1
fi
if [ "$READONLY_PROXY_ENABLED" = "1" ]; then
  screen -dmS "$PROXY_SESSION" bash -lc "cd '$ROOT_DIR' && FREQTRADE_UI_PORT='$PORT' FREQTRADE_BACKEND_PORT='$BACKEND_PORT' '$PYTHON_BIN' scripts/read_only_proxy.py 2>&1 | tee -a logs/read-only-proxy.log"
  for _ in $(seq 1 30); do
    if curl -fsS "http://localhost:${PORT}/analysis.html" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi
screen -dmS "$WATCH_SESSION" bash -lc "cd '$ROOT_DIR' && AUTO_WATCH_INTERVAL_SECONDS='${AUTO_WATCH_INTERVAL_SECONDS:-30}' '$PYTHON_BIN' scripts/auto-watch.py"
WATCH_READY=0
for _ in $(seq 1 90); do
  if AUTO_WATCH_ONCE=1 "$PYTHON_BIN" scripts/auto-watch.py >/dev/null 2>&1; then
    WATCH_READY=1
    break
  fi
  sleep 1
done
if [ "$WATCH_READY" != "1" ]; then
  echo "auto-watch did not become ready after Freqtrade startup." >&2
  tail -20 logs/auto-watch.log >&2 || true
  exit 1
fi
if [ "${GEMINI_OPTIMIZER_ENABLED:-1}" = "1" ]; then
  scripts/start-gemini-optimizer.sh >/dev/null
fi
if command -v caffeinate >/dev/null 2>&1; then
  screen -dmS "$CAFFEINATE_SESSION" bash -lc "caffeinate -dimsu"
fi
if [ "${STABILITY_GUARDIAN_ENABLED:-1}" = "1" ]; then
  export GUARDIAN_RUNTIME_HOURS="${GUARDIAN_RUNTIME_HOURS:-0}"
  scripts/start-stability-guardian.sh >/dev/null
fi
scripts/dev-status.sh
