#!/usr/bin/env bash
set -euo pipefail

ACCOUNT="${USER:-cc}"
PREFIX="freqtrade-deploy"
PROMPT_PASSWORD=0

if [ "${1:-}" = "--prompt-password" ]; then
  PROMPT_PASSWORD=1
fi

store_secret() {
  local key="$1"
  local value="$2"
  security add-generic-password \
    -U \
    -a "$ACCOUNT" \
    -s "${PREFIX}/${key}" \
    -w "$value" >/dev/null
}

has_secret() {
  local key="$1"
  security find-generic-password \
    -a "$ACCOUNT" \
    -s "${PREFIX}/${key}" \
    -w >/dev/null 2>&1
}

if [ -z "${OKX_KEY:-}" ] && ! has_secret OKX_KEY; then
  echo "Missing required environment variable: OKX_KEY" >&2
  exit 2
fi

if [ -z "${OKX_SECRET:-}" ] && ! has_secret OKX_SECRET; then
  echo "Missing required environment variable: OKX_SECRET" >&2
  exit 2
fi

if [ "$PROMPT_PASSWORD" = "1" ] && [ -z "${OKX_PASSWORD:-}" ]; then
  printf "OKX API passphrase: " >&2
  IFS= read -r -s OKX_PASSWORD
  printf "\n" >&2
fi

if [ -n "${OKX_KEY:-}" ]; then
  store_secret OKX_KEY "$OKX_KEY"
fi
if [ -n "${OKX_SECRET:-}" ]; then
  store_secret OKX_SECRET "$OKX_SECRET"
fi
if [ -n "${OKX_PASSWORD:-}" ]; then
  store_secret OKX_PASSWORD "$OKX_PASSWORD"
fi

echo "OKX API credentials stored in macOS Keychain."
