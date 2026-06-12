#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ "$#" -eq 0 ]; then
  cat >&2 <<'USAGE'
Usage:
  scripts/freqtrade.sh <freqtrade-command> [args...]

Examples:
  scripts/freqtrade.sh list-strategies --userdir /freqtrade/user_data
  scripts/freqtrade.sh show-config --config /freqtrade/user_data/config.json
  scripts/freqtrade.sh backtesting --config /freqtrade/user_data/config.json --strategy DatugouBreakoutStrategy --timerange 20240101-
USAGE
  exit 2
fi

docker compose run --rm freqtrade "$@"
