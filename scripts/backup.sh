#!/usr/bin/env bash
# PostgreSQL backup for wespeak.ai CRM.
# Usage: ./scripts/backup.sh   (run via cron for scheduled backups)
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/wespeak-crm/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
POSTGRES_USER="${POSTGRES_USER:-crm_user}"
POSTGRES_DB="${POSTGRES_DB:-wespeak_crm}"
# When running with docker-compose, DB is service "db"
DB_HOST="${DB_HOST:-db}"

mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)
FILE="$BACKUP_DIR/wespeak_crm_$STAMP.sql.gz"

echo "Backing up $POSTGRES_DB -> $FILE"
PGPASSWORD="${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}" \
  pg_dump -h "$DB_HOST" -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$FILE"

# Prune old backups
find "$BACKUP_DIR" -name 'wespeak_crm_*.sql.gz' -mtime +"$RETENTION_DAYS" -delete
echo "Done. Retained backups from last $RETENTION_DAYS days."
