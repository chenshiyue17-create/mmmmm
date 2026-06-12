#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose run --rm freqtrade backtesting \
  --config /freqtrade/user_data/config.json \
  --strategy DatugouBreakoutStrategy \
  --timerange 20240101-
