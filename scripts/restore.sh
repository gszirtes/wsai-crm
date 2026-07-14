#!/usr/bin/env bash
# Restore a wespeak.ai CRM backup.
# Usage: ./scripts/restore.sh /path/to/backup.sql.gz
set -euo pipefail

FILE="${1:?Usage: restore.sh <backup.sql.gz>}"
POSTGRES_USER="${POSTGRES_USER:-crm_user}"
POSTGRES_DB="${POSTGRES_DB:-wespeak_crm}"
DB_HOST="${DB_HOST:-db}"

echo "Restoring $FILE into $POSTGRES_DB ..."
gunzip -c "$FILE" | PGPASSWORD="${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}" \
  psql -h "$DB_HOST" -U "$POSTGRES_USER" "$POSTGRES_DB"
echo "Restore complete."
