#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f output/ml_raw_3mo/features_labels_1h_clean.csv ]; then
  echo "Missing clean ML dataset. Run scripts/accumulate-market-data.sh or scripts/build-ml-dataset.py first." >&2
  exit 1
fi

docker compose build deep-research
docker compose run --rm deep-research python /workspace/scripts/train-deep-sequence-models.py

echo "deep-sequence-training: complete"
echo "report: output/ml_deep_sequence_models/deep_sequence_report.json"
echo "predictions: output/ml_deep_sequence_models/deep_sequence_predictions_latest.csv"
