#!/usr/bin/env bash
set -euo pipefail

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required to install Docker CLI, Compose, and Colima." >&2
  exit 127
fi

brew install docker docker-compose colima

mkdir -p "$HOME/.docker"
if [ ! -f "$HOME/.docker/config.json" ]; then
  cat > "$HOME/.docker/config.json" <<'JSON'
{
  "auths": {},
  "currentContext": "colima",
  "cliPluginsExtraDirs": [
    "/opt/homebrew/lib/docker/cli-plugins"
  ]
}
JSON
else
  echo "Docker config exists at $HOME/.docker/config.json. Ensure it contains cliPluginsExtraDirs for /opt/homebrew/lib/docker/cli-plugins."
fi

colima start --cpu 4 --memory 8 --disk 60 --mount /Volumes/NINJAV:w
docker context use colima
docker compose version
