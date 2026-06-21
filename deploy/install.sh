#!/usr/bin/env bash
# Run as root INSIDE the LXC container, from the cloned project directory
# (/opt/component-tracker). Idempotent: safe to re-run after a git pull.
set -euo pipefail

APP_DIR="/opt/component-tracker"
cd "$APP_DIR"

# Dedicated unprivileged service user that owns the app + data.
if ! id tracker >/dev/null 2>&1; then
    useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin tracker
fi

# Python venv + dependencies.
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Create / migrate the database (safe to re-run; never wipes data).
./venv/bin/flask --app app init-db

# The service runs as 'tracker', so it must own everything (incl. data/).
chown -R tracker:tracker "$APP_DIR"

# Install (or refresh) the systemd units.
install -m 644 deploy/component-tracker.service        /etc/systemd/system/
install -m 644 deploy/component-tracker-backup.service /etc/systemd/system/
install -m 644 deploy/component-tracker-backup.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now component-tracker.service
systemctl enable --now component-tracker-backup.timer

echo
echo "Component Tracker is running on port 8000."
echo "  Status: systemctl status component-tracker"
echo "  Logs:   journalctl -u component-tracker -f"
echo "REMEMBER: set a real TRACKER_SECRET in /etc/systemd/system/component-tracker.service"
echo "          (openssl rand -hex 32), then: systemctl restart component-tracker"
