#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose run --rm freqtrade download-data \
  --config /freqtrade/user_data/config.json \
  --timeframes 1h 5m \
  --days "${ML_LOOKBACK_DAYS:-90}" \
  --data-format-ohlcv feather
