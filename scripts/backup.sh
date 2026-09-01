#!/usr/bin/env bash
# scripts/backup.sh. Snapshot Calypso data (DB + outputs + references).
#
# Run from repo root: `./scripts/backup.sh [target_dir]`
#
# Creates a timestamped tar.gz in the target directory (default: ./backups/).
# Designed for cron / systemd timer. Restoring is just `tar -xzf <file>`.
#
# Phase F.8 deliverable. Complements Phase B self-hosting.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

TARGET="${1:-$ROOT/backups}"
mkdir -p "$TARGET"

TS=$(date +%Y%m%d-%H%M%S)
OUT="$TARGET/calypso-backup-$TS.tar.gz"

echo "==> Backing up to $OUT ..."

tar -czf "$OUT" \
  --exclude='.calypso/calypso.db-wal' \
  --exclude='.calypso/calypso.db-shm' \
  .calypso/calypso.db \
  outputs/ \
  references/ \
  brand/ \
  .env 2>/dev/null || true

echo "==> Done. Size:"
ls -lh "$OUT" | awk '{print "  " $5 "  " $9}'

# Optional: keep last 14 backups.
ls -1t "$TARGET"/calypso-backup-*.tar.gz 2>/dev/null \
  | tail -n +15 \
  | xargs -r rm -f

echo "==> Retained last 14 backups."
