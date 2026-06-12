#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -x scripts/export-keychain-secrets.sh ]; then
  eval "$(scripts/export-keychain-secrets.sh)"
fi

python3 scripts/security-leak-check.py
