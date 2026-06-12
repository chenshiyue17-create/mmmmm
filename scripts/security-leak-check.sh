#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -x scripts/export-keychain-secrets.sh ]; then
  eval "$(scripts/export-keychain-secrets.sh)"
fi

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.11 || command -v python3.10 || command -v python3.9 || command -v python3)}"
"$PYTHON_BIN" scripts/security-leak-check.py
