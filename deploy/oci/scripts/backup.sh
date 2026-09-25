#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ADOM Institute - PostgreSQL backup (runs on the VM as a cron job at 03:20 UTC)
#
#   * Writes a compressed custom-format pg_dump to /opt/adom/backups
#   * Optionally uploads to OCI Object Storage via the S3-compatible API
#     (requires S3-compatible customer secret keys in .env)
#   * Prunes local backups after BACKUP_RETENTION_DAYS (default 14)
#
# NOTE: 'archive' OCI buckets apply a lifecycle policy so bucket copies are
# trimmed automatically (see deploy/oci/README.md).
# ---------------------------------------------------------------------------
set -euo pipefail

cd /opt/adom/app
set -a; . ./.env; set +a

STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR=/opt/adom/backups
mkdir -p "$BACKUP_DIR"

DB_CID=$(docker compose -f docker-compose.prod.yml ps -q db)
DUMP="$BACKUP_DIR/adom-$STAMP.dump"

echo "[backup] $STAMP starting"
docker exec -T "$DB_CID" pg_dump -U "${POSTGRES_USER:-adom_app}" -d "${POSTGRES_DB:-adom_institute}" -Fc \
  | gzip -1 > "$DUMP.gz"

echo "[backup] wrote $DUMP.gz ($(du -h "$DUMP.gz" | cut -f1))"

# Push to object storage when configured
if [ -n "${S3_ENDPOINT_URL:-}" ] && [ -n "${BACKUP_BUCKET:-}" ]; then
  export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
  export AWS_DEFAULT_REGION="${AWS_S3_REGION_NAME:-us-ashburn-1}"
  aws --endpoint-url "$S3_ENDPOINT_URL" s3 cp "$DUMP.gz" "s3://$BACKUP_BUCKET/backups/adom-$STAMP.dump.gz" >/dev/null
  echo "[backup] uploaded to s3://$BACKUP_BUCKET/backups/adom-$STAMP.dump.gz"
fi

# Prune local backups older than retention (default 14 days)
find "$BACKUP_DIR" -name 'adom-*.dump.gz' -mtime +"${BACKUP_RETENTION_DAYS:-14}" -delete
echo "[backup] done"