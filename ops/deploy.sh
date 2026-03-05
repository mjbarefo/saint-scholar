#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/saint-scholar}"
APP_USER="${APP_USER:-saintscholar}"
SERVICE_NAME="${SERVICE_NAME:-saint-scholar}"
DOMAIN="${DOMAIN:-saint-scholar.jacob-barefoot.com}"
BACKUP_ROOT="${BACKUP_ROOT:-$APP_DIR/.deploy-backups}"

SYSTEMD_SRC="$APP_DIR/ops/systemd/saint-scholar.service"
SYSTEMD_DST="/etc/systemd/system/$SERVICE_NAME.service"
NGINX_SRC="$APP_DIR/ops/nginx/saint-scholar.conf"
NGINX_DST="/etc/nginx/sites-available/$SERVICE_NAME"
NGINX_ENABLED="/etc/nginx/sites-enabled/$SERVICE_NAME"
VENV_PIP="$APP_DIR/.venv/bin/pip"
VENV_PYTHON="$APP_DIR/.venv/bin/python"
TIMESTAMP="$(date +%Y%m%d%H%M%S)"
RELEASE_DIR="$BACKUP_ROOT/$TIMESTAMP"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (use sudo)." >&2
  exit 1
fi

if [[ ! -d "$APP_DIR" ]]; then
  echo "App directory not found: $APP_DIR" >&2
  exit 1
fi

mkdir -p "$RELEASE_DIR"

if id "$APP_USER" >/dev/null 2>&1; then
  :
else
  useradd --system --create-home --shell /bin/bash "$APP_USER"
fi

if [[ ! -f "$VENV_PIP" ]]; then
  sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
fi

sudo -u "$APP_USER" "$VENV_PIP" install --upgrade pip
sudo -u "$APP_USER" "$VENV_PIP" install -r "$APP_DIR/requirements.txt"
sudo -u "$APP_USER" "$VENV_PIP" install -e "$APP_DIR"

if [[ -f "$SYSTEMD_DST" ]]; then
  cp "$SYSTEMD_DST" "$RELEASE_DIR/systemd.service.prev"
fi
cp "$SYSTEMD_SRC" "$SYSTEMD_DST"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

if [[ -f "$NGINX_SRC" ]]; then
  if [[ -f "$NGINX_DST" ]]; then
    cp "$NGINX_DST" "$RELEASE_DIR/nginx.site.prev"
  fi
  if [[ -L "$NGINX_ENABLED" ]]; then
    readlink "$NGINX_ENABLED" > "$RELEASE_DIR/nginx.enabled.prev"
  fi
  cp "$NGINX_SRC" "$NGINX_DST"
  sed -i "s/server_name .*/server_name $DOMAIN;/" "$NGINX_DST"
  ln -sfn "$NGINX_DST" "$NGINX_ENABLED"
  nginx -t
  systemctl reload nginx
fi

if [[ "${RUN_INGEST:-0}" == "1" ]]; then
  sudo -u "$APP_USER" "$VENV_PYTHON" -m saint_scholar.ingest
fi

echo "$TIMESTAMP" > "$BACKUP_ROOT/latest"
echo "Deploy complete for $DOMAIN"
echo "Backup snapshot: $RELEASE_DIR"
echo "Health check: curl -sS https://$DOMAIN/health"
