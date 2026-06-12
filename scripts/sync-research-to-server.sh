#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SERVER_HOST="${SERVER_HOST:-}"
SERVER_USER="${SERVER_USER:-root}"
SERVER_PORT="${SERVER_PORT:-22}"
SERVER_APP_DIR="${SERVER_APP_DIR:-/opt/freqtrade-deploy}"
RESTART_AFTER_SYNC="${RESTART_AFTER_SYNC:-0}"

if [ -z "$SERVER_HOST" ]; then
  cat >&2 <<'MSG'
SERVER_HOST is required.

Example:
  SERVER_HOST=1.2.3.4 SERVER_USER=root scripts/sync-research-to-server.sh
MSG
  exit 2
fi

FILES=(
  "user_data/datugou_flow.json"
  "user_data/datugou_flow.autopilot.json"
  "user_data/strategies/DatugouBreakoutStrategy.py"
  "user_data/config.json"
)

for file in "${FILES[@]}"; do
  if [ ! -f "$file" ]; then
    echo "Missing sync source: $file" >&2
    exit 1
  fi
done

bash scripts/security-leak-check.sh >/dev/null

REMOTE="${SERVER_USER}@${SERVER_HOST}"
SSH=(ssh -p "$SERVER_PORT" "$REMOTE")
SCP=(scp -P "$SERVER_PORT")

"${SSH[@]}" "mkdir -p '$SERVER_APP_DIR/user_data/strategies' '$SERVER_APP_DIR/output/local-sync'"

for file in "${FILES[@]}"; do
  "${SCP[@]}" "$file" "$REMOTE:$SERVER_APP_DIR/$file"
done

cat > /tmp/freqtrade-local-sync-manifest.json <<JSON
{
  "synced_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "source": "local-research-node",
  "files": [
    "user_data/datugou_flow.json",
    "user_data/datugou_flow.autopilot.json",
    "user_data/strategies/DatugouBreakoutStrategy.py",
    "user_data/config.json"
  ],
  "secrets_synced": false,
  "market_data_synced": false,
  "logs_synced": false,
  "sqlite_synced": false
}
JSON
"${SCP[@]}" /tmp/freqtrade-local-sync-manifest.json "$REMOTE:$SERVER_APP_DIR/output/local-sync/manifest.json"
rm -f /tmp/freqtrade-local-sync-manifest.json

"${SSH[@]}" "cd '$SERVER_APP_DIR' && python3 scripts/generate-analysis-data.py >/dev/null && scripts/dev-status.sh"

if [ "$RESTART_AFTER_SYNC" = "1" ]; then
  "${SSH[@]}" "sudo systemctl restart freqtrade-deploy && cd '$SERVER_APP_DIR' && scripts/dev-status.sh"
else
  echo "Synced research outputs. Existing server trading process was not restarted."
  echo "Set RESTART_AFTER_SYNC=1 only when you intentionally want Freqtrade to reload code/config."
fi
