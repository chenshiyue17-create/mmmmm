#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

scripts/start-dev.sh

url="http://localhost:${FREQTRADE_UI_PORT:-8080}/analysis.html"
if [ "${OPEN_BROWSER:-1}" = "1" ]; then
  open "$url"
fi

echo "Freqtrade analysis workspace is ready:"
echo "$url"
