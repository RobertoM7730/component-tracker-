#!/usr/bin/env bash
# Consistent nightly backup of the SQLite inventory. Uses SQLite's own .backup
# so it is safe even while the app is writing. Keeps the most recent $KEEP
# copies, gzipped. Schedule it a few minutes BEFORE your Proxmox vzdump window
# so each container backup also contains a known-good snapshot.
set -euo pipefail

APP_DIR="/opt/component-tracker"
DB="$APP_DIR/data/components.db"
DEST="$APP_DIR/data/backups"
KEEP=14

mkdir -p "$DEST"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$DEST/components-$STAMP.db"

sqlite3 "$DB" ".backup '$OUT'"
gzip -f "$OUT"

# Prune everything past the newest $KEEP backups.
ls -1t "$DEST"/components-*.db.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f

echo "backup written: $OUT.gz"
