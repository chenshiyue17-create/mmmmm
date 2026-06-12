#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${ROOT_DIR}/logs/desktop-launch.log"

mkdir -p "${ROOT_DIR}/logs"
{
  echo "==== $(date '+%Y-%m-%d %H:%M:%S') Freqtrade OKX sandbox launch ===="
  cd "$ROOT_DIR"
  if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
  fi
  scripts/start-dev.sh
  open "http://localhost:${FREQTRADE_UI_PORT:-8080}${FREQTRADE_START_PATH:-/dashboard}"
  echo "opened http://localhost:${FREQTRADE_UI_PORT:-8080}${FREQTRADE_START_PATH:-/dashboard}"
} 2>&1 | tee -a "$LOG_FILE"
