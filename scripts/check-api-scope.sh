#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${ROOT_DIR}/user_data/config.json"

python3 - "$CONFIG_FILE" <<'PY'
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text())
exchange = config.get("exchange", {})
api_server = config.get("api_server", {})

errors = []

if exchange.get("name") not in {"okx", "binance"}:
    errors.append("exchange.name must be okx or binance")

if config.get("telegram", {}).get("enabled") is not False:
    errors.append("telegram must stay disabled")

if config.get("webhook", {}).get("enabled"):
    errors.append("webhook must stay disabled or absent")

if config.get("external_message_consumer", {}).get("enabled"):
    errors.append("external_message_consumer must stay disabled or absent")

if config.get("freqai", {}).get("enabled"):
    errors.append("freqai must stay disabled or absent")

if api_server.get("enable_openapi") is not False:
    errors.append("api_server.enable_openapi must stay false")

if api_server.get("enabled") is not True:
    errors.append("local api_server must stay enabled for the bundled local UI")

if errors:
    for error in errors:
        print(f"API scope check failed: {error}", file=sys.stderr)
    raise SystemExit(1)

print("API scope check passed: only exchange APIs are enabled; third-party APIs are disabled.")
PY
