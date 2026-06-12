#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker CLI is not installed. Run: scripts/install-runtime.sh" >&2
  exit 127
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is not available. Run: scripts/install-runtime.sh" >&2
  exit 127
fi

scripts/check-api-scope.sh
find user_data/strategies -name '._*' -type f -delete
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
if [ -x scripts/export-keychain-secrets.sh ]; then
  eval "$(scripts/export-keychain-secrets.sh)"
fi

tmp_config="$(mktemp)"
trap 'rm -f "$tmp_config"' EXIT

docker compose run --rm freqtrade show-config \
  --config /freqtrade/user_data/config.json \
  >"$tmp_config"

python3 - <<'PY'
import json
import os
from pathlib import Path

config = json.loads(Path("user_data/config.json").read_text())
is_okx_sandbox = (
    config["exchange"]["name"] == "okx"
    and config["dry_run"] is False
    and os.getenv("OKX_SANDBOX_MODE") == "1"
)
assert config["dry_run"] is True or is_okx_sandbox, "dry_run=false is only allowed for OKX sandbox mode"
assert config["strategy"] == "DatugouBreakoutStrategy", "strategy must be the OKX meme breakout strategy"
pairs = set(config["exchange"]["pair_whitelist"])
assert ".*/USDT" in pairs, "dynamic OKX USDT market boundary must be enabled"
assert "BTC/USDT" in set(config["exchange"]["pair_blacklist"]), "BTC/USDT must be excluded from meme discovery"
assert config["pairlists"][0]["method"] == "PercentChangePairList", "pairlist must dynamically discover movers"
assert config["pairlists"][0]["refresh_period"] <= 900, "dynamic pairlist must refresh quickly"
assert config["force_entry_enable"] is True, "force entry is enabled for sandbox UI operations"
assert config["api_server"]["enabled"] is True, "api server must be enabled"
assert config["api_server"]["enable_openapi"] is False, "openapi must remain disabled"
assert config["exchange"]["name"] in {"okx", "binance"}, "unsupported exchange"
assert config["exchange"]["key"] == "", "exchange key must come from env only"
assert config["exchange"]["secret"] == "", "exchange secret must come from env only"
assert config["exchange"].get("enable_ws") is False, "websocket must stay disabled for stable local sandbox"
assert Path("user_data/strategies/DatugouBreakoutStrategy.py").exists(), "strategy file missing"
PY

echo "Freqtrade config validation passed."
