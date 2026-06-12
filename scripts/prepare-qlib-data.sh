#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BUNDLED_PYTHON="/Users/cc/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
PYTHON_BIN="${PYTHON_BIN:-$BUNDLED_PYTHON}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

QLIB_RUNTIME_ROOT=/workspace "$PYTHON_BIN" scripts/prepare-qlib-data.py

cat <<'MSG'
qlib-fusion: prepared CSV and workflow config

Next steps:
scripts/build-qlib-research-image.sh
scripts/run-qlib-dump.sh
scripts/run-qlib-qrun.sh
MSG
