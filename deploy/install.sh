#!/usr/bin/env bash
# Installs (or updates) LocalTranslater as a systemd service.
# Usage: sudo ./deploy/install.sh
set -euo pipefail

APP_DIR=/opt/localtranslater
ENV_FILE=/etc/localtranslater.env
SERVICE=localtranslater
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

if ! python3 -c 'import venv, ensurepip' 2>/dev/null; then
  echo "python3-venv is missing. Install it first: sudo apt install python3-venv" >&2
  exit 1
fi

if ! id "$SERVICE" &>/dev/null; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE"
fi

echo "==> Copying application to $APP_DIR"
mkdir -p "$APP_DIR"
rm -rf "$APP_DIR/app"
cp -r "$SRC_DIR/app" "$SRC_DIR/requirements.txt" "$APP_DIR/"
find "$APP_DIR/app" -name '__pycache__' -prune -exec rm -rf {} +

echo "==> Installing Python dependencies"
[[ -d "$APP_DIR/.venv" ]] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
chown -R root:root "$APP_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "==> Creating $ENV_FILE"
  read -rsp "Login password for the web UI: " password; echo
  if [[ -z "$password" ]]; then
    echo "Password must not be empty" >&2
    exit 1
  fi
  # systemd's EnvironmentFile would interpret quotes and backslashes.
  if [[ "$password" =~ [\"\'\\] || "$password" != "${password#[[:space:]]}" || "$password" != "${password%[[:space:]]}" ]]; then
    echo "Password must not contain quotes or backslashes, or start/end with spaces" >&2
    exit 1
  fi
  secret="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  install -m 600 -o root -g root "$SRC_DIR/deploy/localtranslater.env.example" "$ENV_FILE"
  python3 - "$ENV_FILE" "$password" "$secret" <<'PY'
import sys
path, password, secret = sys.argv[1:]
lines = open(path, encoding="utf-8").read().splitlines()
out = []
for line in lines:
    if line.startswith("LT_PASSWORD="):
        line = "LT_PASSWORD=" + password
    elif line.startswith("LT_SECRET_KEY="):
        line = "LT_SECRET_KEY=" + secret
    out.append(line)
open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
PY
else
  echo "==> Keeping existing $ENV_FILE"
fi

echo "==> Installing systemd unit"
install -m 644 "$SRC_DIR/deploy/localtranslater.service" "/etc/systemd/system/$SERVICE.service"
systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null
systemctl restart "$SERVICE"

port="$(grep -E '^LT_PORT=' "$ENV_FILE" | cut -d= -f2)"
echo
systemctl --no-pager --lines=0 status "$SERVICE" || true
echo
echo "Done. Open http://$(hostname -I | awk '{print $1}'):${port:-8000}/ from a device on the LAN."
