#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/opt/freqtrade-deploy}"

if [ "$(id -u)" -ne 0 ]; then
  SUDO=sudo
else
  SUDO=
fi

$SUDO tee /etc/systemd/system/freqtrade-deploy.service >/dev/null <<UNIT
[Unit]
Description=Freqtrade OKX sandbox deployment
Requires=docker.service
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${APP_DIR}
ExecStart=/usr/bin/env bash ${APP_DIR}/scripts/start-dev.sh
ExecStop=/usr/bin/env bash ${APP_DIR}/scripts/stop-dev.sh
TimeoutStartSec=600
TimeoutStopSec=120

[Install]
WantedBy=multi-user.target
UNIT

$SUDO systemctl daemon-reload
$SUDO systemctl enable freqtrade-deploy
echo "Installed systemd unit: freqtrade-deploy"
