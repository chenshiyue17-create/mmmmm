#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOOKBACK_DAYS="${ML_LOOKBACK_DAYS:-90}"
TIMEFRAMES="${ML_DOWNLOAD_TIMEFRAMES:-1h 5m}"
PAIRS_FILE="output/ml_raw_3mo/relevant-pairs.json"

mkdir -p output/ml_raw_3mo
python3 scripts/accumulate-market-data.py

docker compose run --rm freqtrade download-data \
  --config /freqtrade/user_data/config.json \
  --pairs-file "/freqtrade/${PAIRS_FILE}" \
  --days "$LOOKBACK_DAYS" \
  --timeframes $TIMEFRAMES \
  --data-format-ohlcv feather \
  --trading-mode spot

docker compose run --rm --entrypoint python freqtrade /freqtrade/scripts/build-ml-dataset.py

echo "market-data: accumulated ${LOOKBACK_DAYS} days"
echo "pairs: ${PAIRS_FILE}"
echo "dataset: output/ml_raw_3mo/features_labels_1h.csv"
echo "evidence: output/ml_raw_3mo/gemini_evidence_pack.json"
