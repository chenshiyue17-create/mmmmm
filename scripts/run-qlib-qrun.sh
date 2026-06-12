#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CONFIG_PATH="/workspace/output/qlib/okx_1h/qlib_okx_lgbm_config.yaml"
HOST_LOG="logs/qlib-qrun.log"
mkdir -p logs

IMAGE="freqtrade-deploy-qlib-research:local"
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  scripts/build-qlib-research-image.sh
fi

CONTAINER="qlib-qrun-$$"
docker create --name "$CONTAINER" "$IMAGE" sleep infinity >/dev/null
cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker start "$CONTAINER" >/dev/null
docker exec "$CONTAINER" mkdir -p /workspace/output/qlib
docker cp output/qlib/okx_1h "$CONTAINER":/workspace/output/qlib/okx_1h
docker exec "$CONTAINER" find /workspace/output/qlib/okx_1h -name '._*' -delete
docker exec "$CONTAINER" mkdir -p /workspace/mlruns
docker exec -w /tmp \
  -e MLFLOW_ALLOW_FILE_STORE=true \
  -e MLFLOW_TRACKING_URI=file:/workspace/mlruns \
  "$CONTAINER" qrun "$CONFIG_PATH" | tee "$HOST_LOG"
mkdir -p output/qlib/okx_1h
rm -rf output/qlib/okx_1h/mlruns
if docker exec "$CONTAINER" sh -c "find /workspace/mlruns -type f | grep -q ."; then
  docker cp "$CONTAINER":/workspace/mlruns output/qlib/okx_1h/mlruns
elif docker exec "$CONTAINER" sh -c "test -d /tmp/mlruns && find /tmp/mlruns -type f | grep -q ."; then
  docker cp "$CONTAINER":/tmp/mlruns output/qlib/okx_1h/mlruns
else
  mkdir -p output/qlib/okx_1h/mlruns
fi
find output/qlib/okx_1h/mlruns -name '._*' -delete

echo "qlib-qrun: complete"
echo "log: ${HOST_LOG}"
