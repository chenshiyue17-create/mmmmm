#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f output/ml_raw_3mo/features_labels_1h_clean.csv ]; then
  echo "Missing clean ML dataset. Run scripts/accumulate-market-data.sh or scripts/build-ml-dataset.py first." >&2
  exit 1
fi

docker compose run --rm --entrypoint python freqtrade /freqtrade/scripts/train-sequence-models.py

echo "sequence-training: complete"
echo "report: output/ml_sequence_models/sequence_report.json"
echo "predictions: output/ml_sequence_models/sequence_predictions_latest.csv"
