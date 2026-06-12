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

if [ -x scripts/export-keychain-secrets.sh ]; then
  eval "$(scripts/export-keychain-secrets.sh)"
fi

docker compose run --rm \
  -e OKX_KEY="${OKX_KEY:-}" \
  -e OKX_SECRET="${OKX_SECRET:-}" \
  -e OKX_PASSWORD="${OKX_PASSWORD:-}" \
  --entrypoint python \
  freqtrade /freqtrade/scripts/check-okx-sandbox-api.py

python3 scripts/generate-okx-balance-ui.py
