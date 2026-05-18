#!/usr/bin/env bash
set -euo pipefail

APP_NAME="exterior-quote-assistant"
APP_DIR="/opt/${APP_NAME}"
REPO_URL="https://github.com/cdorman1/exterior-quote-assistant.git"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root or with sudo."
  exit 1
fi

apt-get update
apt-get install -y git python3 python3-venv python3-pip nginx

if [[ -d "${APP_DIR}/.git" ]]; then
  git -C "${APP_DIR}" pull --ff-only
else
  rm -rf "${APP_DIR}"
  git clone "${REPO_URL}" "${APP_DIR}"
fi

cd "${APP_DIR}"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m src.seed_data

cp deploy/exterior-quote-assistant.service "${SERVICE_FILE}"
systemctl daemon-reload
systemctl enable "${APP_NAME}"
systemctl restart "${APP_NAME}"

cp deploy/nginx-exterior-quote-assistant.conf /etc/nginx/sites-available/exterior-quote-assistant
ln -sf /etc/nginx/sites-available/exterior-quote-assistant /etc/nginx/sites-enabled/exterior-quote-assistant
nginx -t
systemctl reload nginx

systemctl status "${APP_NAME}" --no-pager
echo "Deployment complete. App service is listening on localhost:8501 behind nginx."
