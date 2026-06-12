#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f output/ml_raw_3mo/features_labels_1h.csv ]; then
  echo "Missing ML dataset. Run scripts/accumulate-market-data.sh first." >&2
  exit 1
fi

docker compose run --rm --entrypoint python freqtrade /freqtrade/scripts/train-ml-models.py

echo "ml-training: complete"
echo "report: output/ml_models/training_report.json"
echo "signals: output/ml_models/latest_signals.json"
echo "predictions: output/ml_models/predictions_latest.csv"
