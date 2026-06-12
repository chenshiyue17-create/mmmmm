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

missing=0
for name in OKX_KEY OKX_SECRET OKX_PASSWORD; do
  if [ -z "${!name:-}" ]; then
    echo "missing: $name"
    missing=1
  fi
done

if [ "$missing" = "1" ]; then
  echo "OKX private API check skipped: apiKey/secretKey/passphrase are not complete."
  exit 2
fi

docker compose run --rm \
  -e FREQTRADE__EXCHANGE__KEY="$OKX_KEY" \
  -e FREQTRADE__EXCHANGE__SECRET="$OKX_SECRET" \
  -e FREQTRADE__EXCHANGE__PASSWORD="$OKX_PASSWORD" \
  freqtrade test-pairlist \
  --config /freqtrade/user_data/config.json
