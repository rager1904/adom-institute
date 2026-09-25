#!/usr/bin/env bash
# ADOM Institute - OCI app node bootstrap (runs as root via cloud-init)
set -euo pipefail

log() { echo "[bootstrap] $*"; }

export DEBIAN_FRONTEND=noninteractive

log "starting bootstrap"

# ---------------------------------------------------------------------------
# 1. Mount the attached PostgreSQL block volume (paravirtualized /dev/sdb)
# ---------------------------------------------------------------------------
DATA=/opt/adom-data
mkdir -p "$DATA"

find_block_dev() {
  for dev in /dev/sdb /dev/sdc /dev/oracleoci/oraclevdb /dev/oracleoci/oraclevdc; do
    if [ -b "$dev" ]; then echo "$dev"; return 0; fi
  done
  # fall back to the largest non-root disk
  lsblk -dpno NAME,SIZE | grep -v loop | while read -r name size; do
    if mountpoint -q "$name" 2>/dev/null; then continue; fi
    case "$size" in
      *G) echo "$name"; return 0;;
    esac
  done
}

BLOCK_DEV=$(find_block_dev || true)
if [ -n "$BLOCK_DEV" ] && ! mountpoint -q "$DATA"; then
  log "formatting and mounting $BLOCK_DEV at $DATA"
  mkfs.ext4 -F "$BLOCK_DEV" >/dev/null 2>&1 || true
  mount "$BLOCK_DEV" "$DATA"
  UUID=$(blkid -s UUID -o value "$BLOCK_DEV")
  grep -q "$UUID" /etc/fstab || echo "UUID=$UUID $DATA ext4 defaults,nofail 0 2" >> /etc/fstab
else
  log "no block volume found; using local disk for $DATA"
fi

mkdir -p "$DATA"/{pgdata,redis,staticfiles,mediafiles,certs,certdata,logs}
mkdir -p /opt/adom/app /opt/adom/scripts /opt/adom/backups

# ---------------------------------------------------------------------------
# 2. Docker Engine + Compose plugin
# ---------------------------------------------------------------------------
if ! command -v docker >/dev/null; then
  log "installing docker"
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg awscli
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  # shellcheck disable=SC1091
  . /etc/os-release
  echo "deb [arch=arm64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
else
  log "docker already installed"
fi

docker --version
docker compose version

# ---------------------------------------------------------------------------
# 3. Scheduled jobs (backup 03:20, cert renewal 02:17 - UTC)
#    Scripts are placed on the VM by the deploy script.
# ---------------------------------------------------------------------------
cat > /etc/cron.d/adom <<'EOF'
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
20 3 * * * root /opt/adom/scripts/backup.sh >> /var/log/adom-backup.log 2>&1
17 2 * * * root /opt/adom/scripts/renew-cert.sh >> /var/log/adom-cert.log 2>&1
EOF
chmod 644 /etc/cron.d/adom
systemctl restart cron || true

log "bootstrap complete"
echo "---------------------------------------------------------------------"
echo " ADOM app node ready. Deploy the app with scripts/deploy.sh (or .ps1)."
echo " SSH: ssh ubuntu@<public-ip>"
echo "---------------------------------------------------------------------"