#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ADOM Institute - PostgreSQL restore (run manually on the VM)
#
# Usage:  ./restore.sh [path-to-backup.dump.gz]
#         If no path is given, the latest local backup is used.
# ---------------------------------------------------------------------------
set -euo pipefail

cd /opt/adom/app
set -a; . ./.env; set +a

BACKUP_FILE="${1:-$(ls -t /opt/adom/backups/adom-*.dump.gz | head -n1)}"
[ -f "$BACKUP_FILE" ] || { echo "Backup not found: $BACKUP_FILE"; exit 1; }

DB_CID=$(docker compose -f docker-compose.prod.yml ps -q db)

echo "[restore] restoring $BACKUP_FILE into ${POSTGRES_DB:-adom_institute}"
gunzip -c "$BACKUP_FILE" |
  docker exec -i "$DB_CID" pg_restore -U "${POSTGRES_USER:-adom_app}" \
    -d "${POSTGRES_DB:-adom_institute}" --clean --if-exists --no-owner --no-privileges

echo "[restore] done. Restart the stack: docker compose -f docker-compose.prod.yml restart web ws worker"