#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/chenshiyue17-create/mmmmm.git}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/opt/freqtrade-deploy}"
RUN_START="${RUN_START:-0}"

need_sudo() {
  if [ "$(id -u)" -eq 0 ]; then
    echo ""
  else
    echo "sudo"
  fi
}

SUDO="$(need_sudo)"

install_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get update
    $SUDO apt-get install -y git curl ca-certificates screen lsof python3 python3-venv
  elif command -v dnf >/dev/null 2>&1; then
    $SUDO dnf install -y git curl ca-certificates screen lsof python3
  elif command -v yum >/dev/null 2>&1; then
    $SUDO yum install -y git curl ca-certificates screen lsof python3
  else
    echo "Unsupported package manager. Install git, curl, screen, lsof, python3, and Docker manually." >&2
    exit 1
  fi
}

install_docker_if_needed() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    return
  fi
  curl -fsSL https://get.docker.com | $SUDO sh
  $SUDO systemctl enable --now docker
}

clone_or_update_repo() {
  if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" fetch origin
    git -C "$APP_DIR" checkout "$BRANCH"
    git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
  else
    $SUDO mkdir -p "$(dirname "$APP_DIR")"
    $SUDO chown "$USER":"$USER" "$(dirname "$APP_DIR")"
    git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
  fi
}

prepare_env() {
  cd "$APP_DIR"
  mkdir -p logs output user_data/logs
  if [ ! -f .env ]; then
    cp .env.server.example .env
    chmod 600 .env
    cat >&2 <<MSG
Created $APP_DIR/.env from .env.server.example.
Edit it on the server before starting:

  nano $APP_DIR/.env

Fill FT_API_PASSWORD, FT_JWT_SECRET_KEY, FT_WS_TOKEN, OKX_KEY, OKX_SECRET, OKX_PASSWORD.
Keep OKX_SANDBOX_MODE=1 for the first server run.
MSG
    exit 2
  fi
}

validate_env() {
  cd "$APP_DIR"
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
  missing=0
  for key in FT_API_PASSWORD FT_JWT_SECRET_KEY FT_WS_TOKEN OKX_KEY OKX_SECRET OKX_PASSWORD; do
    value="${!key:-}"
    if [ -z "$value" ] || [[ "$value" == replace-* ]] || [[ "$value" == change-* ]]; then
      echo "Missing or placeholder value in .env: $key" >&2
      missing=1
    fi
  done
  if [ "${OKX_SANDBOX_MODE:-0}" != "1" ]; then
    echo "Server bootstrap refuses first run unless OKX_SANDBOX_MODE=1." >&2
    missing=1
  fi
  if [ "$missing" -ne 0 ]; then
    exit 2
  fi
}

main() {
  install_packages
  install_docker_if_needed
  clone_or_update_repo
  prepare_env
  validate_env
  cd "$APP_DIR"
  bash scripts/security-leak-check.sh
  bash deploy/aliyun/install-systemd.sh "$APP_DIR"
  if [ "$RUN_START" = "1" ]; then
    $SUDO systemctl start freqtrade-deploy
    scripts/dev-status.sh
  else
    echo "Ready. Start manually with: sudo systemctl start freqtrade-deploy"
  fi
}

main "$@"
