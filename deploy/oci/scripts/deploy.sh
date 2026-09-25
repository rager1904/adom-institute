#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ADOM Institute - deploy to the OCI app node (bash / WSL / Linux / macOS)
#
# Usage:
#   ./deploy.sh -i <public-ip> -d app.yourdomain.com -e you@example.com [-u ubuntu]
#
# Prereqs: rsync, ssh, scp. Run from the repo root.
# ---------------------------------------------------------------------------
set -euo pipefail

IP=""
DOMAIN=""
EMAIL=""
USER="ubuntu"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"

while getopts "i:d:e:u:k:h" opt; do
  case "$opt" in
    i) IP="$OPTARG" ;;
    d) DOMAIN="$OPTARG" ;;
    e) EMAIL="$OPTARG" ;;
    u) USER="$OPTARG" ;;
    k) SSH_KEY="$OPTARG" ;;
    h) echo "Usage: $0 -i <ip> -d <domain> -e <email> [-u user] [-k key]"; exit 0 ;;
    *) exit 1 ;;
  esac
done

[ -n "$IP" ] && [ -n "$DOMAIN" ] && [ -n "$EMAIL" ] || { echo "Missing -i/-d/-e"; exit 1; }

SSHOPTS="-i $SSH_KEY -o StrictHostKeyChecking=accept-new"
SSH="ssh $SSHOPTS $USER@$IP"
SCP="scp $SSHOPTS"

echo "==> Building production .env from deploy/oci/.env.production.example"
SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(50))")
DB_PASS=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))")
sed -e "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" \
    -e "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=$DOMAIN|" \
    -e "s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=https://$DOMAIN|" \
    -e "s|^DB_PASSWORD=.*|DB_PASSWORD=$DB_PASS|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$DB_PASS|" \
    deploy/oci/.env.production.example > .env.production

echo "==> Syncing project to /opt/adom/app (excluding local junk)"
$SSH "mkdir -p /opt/adom/app /opt/adom/scripts"
rsync -az --delete \
  --exclude 'venv' --exclude '.git' --exclude '.venv' \
  --exclude 'media' --exclude 'staticfiles' --exclude 'logs' \
  --exclude '*.sqlite3' --exclude '.env' --exclude '.env.*' \
  --exclude '__pycache__' --exclude 'deploy/oci/TERRAFORM/.terraform' \
  -e "ssh $SSHOPTS" ./ "$USER@$IP:/opt/adom/app/"

echo "==> Uploading operator scripts + production env"
$SCP deploy/oci/scripts/*.sh "$USER@$IP:/opt/adom/scripts/"
$SCP .env.production "$USER@$IP:/opt/adom/app/.env"
$SSH "chmod +x /opt/adom/scripts/*.sh && sed -i 's/DOMAIN_PLACEHOLDER/$DOMAIN/g' /opt/adom/app/deploy/oci/nginx/adom.conf"

echo "==> Building images + running migrations + starting app services"
$SSH "cd /opt/adom/app && docker compose -f docker-compose.prod.yml up -d --build migrate && docker compose -f docker-compose.prod.yml up -d --build db pgbouncer redis web ws worker beat"

echo "==> Issuing TLS certificate (certbot, standalone - nginx not started yet)"
$SSH "cd /opt/adom/app && docker compose -f docker-compose.prod.yml run --rm -p 80:80 certbot certonly --standalone -d $DOMAIN --email $EMAIL --agree-tos --no-eff-email --non-interactive"

echo "==> Starting nginx with the new certificate"
$SSH "cd /opt/adom/app && docker compose -f docker-compose.prod.yml up -d nginx && docker compose -f docker-compose.prod.yml exec nginx nginx -s reload || true"

echo ""
echo "Deploy complete. Next steps:"
echo "  1. Create a superuser:"
echo "     ssh -i $SSH_KEY $USER@$IP 'cd /opt/adom/app && docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser'"
echo "  2. Point DNS A record $DOMAIN -> $IP"
echo "  3. Optional: enable OCI Object Storage (see deploy/oci/README.md 'Object storage')"
echo "  4. Verify:  https://$DOMAIN  and  https://$DOMAIN/admin/"
exit 0