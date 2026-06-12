#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker build -f docker/qlib-research.Dockerfile -t freqtrade-deploy-qlib-research:local .
docker run --rm freqtrade-deploy-qlib-research:local
