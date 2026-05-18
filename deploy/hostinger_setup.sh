#!/usr/bin/env bash
set -euo pipefail

APP_NAME="exterior-quote-assistant"
APP_DIR="/opt/${APP_NAME}"
REPO_URL="https://github.com/cdorman1/exterior-quote-assistant.git"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
TRAEFIK_DYNAMIC_DIR="/etc/traefik/dynamic"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root or with sudo."
  exit 1
fi

apt-get update
apt-get install -y git python3 python3-venv python3-pip

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

if [[ -d "${TRAEFIK_DYNAMIC_DIR}" ]]; then
  cp deploy/traefik-exterior-quote-assistant.yml "${TRAEFIK_DYNAMIC_DIR}/exterior-quote-assistant.yml"
  echo "Wrote Traefik dynamic config to ${TRAEFIK_DYNAMIC_DIR}/exterior-quote-assistant.yml"
  echo "Traefik should reload automatically if file provider is enabled."
else
  echo "Traefik dynamic config directory not found at ${TRAEFIK_DYNAMIC_DIR}"
  echo "Create the directory or place deploy/traefik-exterior-quote-assistant.yml into the Traefik file provider path."
fi

systemctl status "${APP_NAME}" --no-pager
echo "Deployment complete. App service is listening on 0.0.0.0:8501."
