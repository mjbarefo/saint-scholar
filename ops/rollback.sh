#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/saint-scholar}"
SERVICE_NAME="${SERVICE_NAME:-saint-scholar}"
BACKUP_ROOT="${BACKUP_ROOT:-$APP_DIR/.deploy-backups}"
SYSTEMD_DST="/etc/systemd/system/$SERVICE_NAME.service"
NGINX_DST="/etc/nginx/sites-available/$SERVICE_NAME"
NGINX_ENABLED="/etc/nginx/sites-enabled/$SERVICE_NAME"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (use sudo)." >&2
  exit 1
fi

if [[ ! -d "$BACKUP_ROOT" ]]; then
  echo "Backup directory not found: $BACKUP_ROOT" >&2
  exit 1
fi

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  if [[ -f "$BACKUP_ROOT/latest" ]]; then
    TARGET="$(cat "$BACKUP_ROOT/latest")"
  else
    TARGET="$(ls -1 "$BACKUP_ROOT" | grep -E '^[0-9]{14}$' | sort | tail -n1 || true)"
  fi
fi

if [[ -z "$TARGET" ]]; then
  echo "No backup snapshots found in $BACKUP_ROOT" >&2
  exit 1
fi

RELEASE_DIR="$BACKUP_ROOT/$TARGET"
if [[ ! -d "$RELEASE_DIR" ]]; then
  echo "Snapshot not found: $RELEASE_DIR" >&2
  exit 1
fi

RESTORED_ANY=0

if [[ -f "$RELEASE_DIR/systemd.service.prev" ]]; then
  cp "$RELEASE_DIR/systemd.service.prev" "$SYSTEMD_DST"
  systemctl daemon-reload
  systemctl restart "$SERVICE_NAME"
  RESTORED_ANY=1
fi

if [[ -f "$RELEASE_DIR/nginx.site.prev" ]]; then
  cp "$RELEASE_DIR/nginx.site.prev" "$NGINX_DST"
  if [[ -f "$RELEASE_DIR/nginx.enabled.prev" ]]; then
    PREV_TARGET="$(cat "$RELEASE_DIR/nginx.enabled.prev")"
    if [[ -n "$PREV_TARGET" ]]; then
      ln -sfn "$PREV_TARGET" "$NGINX_ENABLED"
    fi
  else
    ln -sfn "$NGINX_DST" "$NGINX_ENABLED"
  fi
  nginx -t
  systemctl reload nginx
  RESTORED_ANY=1
fi

if [[ "$RESTORED_ANY" -eq 0 ]]; then
  echo "Snapshot exists but contains no restorable files: $RELEASE_DIR" >&2
  exit 1
fi

echo "Rollback complete from snapshot: $RELEASE_DIR"

