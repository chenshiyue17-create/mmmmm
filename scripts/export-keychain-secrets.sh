#!/usr/bin/env bash
set -euo pipefail

ACCOUNT="${USER:-cc}"
PREFIX="freqtrade-deploy"

shell_quote() {
  python3 -c 'import shlex, sys; print(shlex.quote(sys.stdin.read()))'
}

read_secret() {
  local key="$1"
  security find-generic-password \
    -a "$ACCOUNT" \
    -s "${PREFIX}/${key}" \
    -w 2>/dev/null || true
}

emit_export() {
  local name="$1"
  local value="$2"
  if [ -n "$value" ]; then
    printf 'export %s=%s\n' "$name" "$(printf "%s" "$value" | shell_quote)"
  fi
}

emit_export OKX_KEY "$(read_secret OKX_KEY)"
emit_export OKX_SECRET "$(read_secret OKX_SECRET)"
emit_export OKX_PASSWORD "$(read_secret OKX_PASSWORD)"
