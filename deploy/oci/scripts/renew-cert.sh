#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ADOM Institute - Let's Encrypt certificate renewal (runs 02:17 UTC via cron)
# ---------------------------------------------------------------------------
set -euo pipefail

cd /opt/adom/app

docker compose -f docker-compose.prod.yml run --rm certbot renew --webroot -w /var/www/certbot --quiet
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
echo "[cert] renewal check done"