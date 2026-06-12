#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

scripts/prepare-qlib-data.sh

IMAGE="freqtrade-deploy-qlib-research:local"
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  scripts/build-qlib-research-image.sh
fi

CONTAINER="qlib-dump-$$"
docker create --name "$CONTAINER" "$IMAGE" sleep infinity >/dev/null
cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker start "$CONTAINER" >/dev/null
docker exec "$CONTAINER" mkdir -p /workspace/output/qlib/okx_1h
docker cp output/qlib/okx_1h/csv "$CONTAINER":/workspace/output/qlib/okx_1h/csv
docker exec "$CONTAINER" find /workspace/output/qlib/okx_1h/csv -name '._*' -delete
docker exec "$CONTAINER" python3 vendor/qlib/scripts/dump_bin.py dump_all \
  --data_path /workspace/output/qlib/okx_1h/csv \
  --qlib_dir /workspace/output/qlib/okx_1h/qlib_bin \
  --freq 60min \
  --date_field_name date \
  --symbol_field_name symbol \
  --file_suffix .csv \
  --exclude_fields symbol
mkdir -p output/qlib/okx_1h
rm -rf output/qlib/okx_1h/qlib_bin
docker cp "$CONTAINER":/workspace/output/qlib/okx_1h/qlib_bin output/qlib/okx_1h/qlib_bin
find output/qlib/okx_1h/qlib_bin -name '._*' -delete

echo "qlib-dump: complete"
echo "qlib bin: output/qlib/okx_1h/qlib_bin"
