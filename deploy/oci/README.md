# ADOM Institute — Oracle Cloud Infrastructure deployment kit

Production deployment of the ADOM Institute school-management platform on OCI,
built around the **Always Free** tier with a clear **scale path** for hosting
**4+ big schools** (4 institution tenants) on one plot/platform.

```
deploy/oci/
├── README.md               <- this file (quick start)
├── DEPLOYMENT_GUIDE.md     <- step-by-step: network, instance, storage, deploy (console)
├── ARCHITECTURE.md         <- diagram, free-tier budget, capacity for 4 schools
├── SCALING.md              <- phased scale-out roadmap (0 -> 6)
├── .env.production.example <- production environment template
├── docker-compose.prod.yml <- app stack (also at repo root)
├── nginx/                  <- tuned reverse proxy + site conf (TLS/WS)
├── postgres/               <- PostgreSQL 16 tuning
├── TERRAFORM/              <- VCN + ARM VM + block volume + buckets + cloud-init
└── scripts/                <- deploy (Windows + bash), backup, restore, renew-cert
```

## 1. Prerequisites

- **OCI account in your home region**, upgraded to **Pay-As-You-Go**
  (recommended — keeps Always Free resources and unlocks the 4 OCPU/24 GB ARM
  allowance). If you stay strictly free, the plan still works at 2 OCPU/12 GB.
- An **SSH key pair** (`ssh-keygen -t ed25519`).
- **Terraform >= 1.5** + the OCI **API signing key** (console: *Identity &
  Security → Users → your user → API Keys → Add API Key*).
- A **domain** you control (optional but strongly recommended for TLS).

> The app requires PostgreSQL (`settings.py` refuses anything else when
> `DEBUG=False`), so we run Postgres on the VM. OCI's Always Free
> Autonomous Database is Oracle DB, not Postgres — it is not used here.

## 2. Provision the infrastructure (Terraform)

```powershell
cd deploy/oci/TERRAFORM
Copy-Item terraform.tfvars.example terraform.tfvars   # fill in OCIDs, region, SSH key
terraform init
terraform plan
terraform apply -auto-approve
terraform output instance_public_ip   # (run `terraform refresh` if empty)
```

Creates: VCN (10.0.0.0/16) + public subnet + security list (22/80/443),
1 × `VM.Standard.A1.Flex` (2 OCPU/12 GB), a 100 GB block volume, and the
`<prefix>-media` / `<prefix>-backups` buckets. The VM self-configures via
cloud-init (Docker, block-volume mount, backup/cert cron jobs).

Wait ~3–5 minutes for cloud-init to finish, then verify SSH:

```powershell
ssh -i ~\.ssh\id_ed25519 ubuntu@<public-ip>   # should say "ADOM app node ready"
```

## 3. Point DNS

Create an **A record** `app.yourdomain.com → <public-ip>`. Also used by
certbot for the TLS certificate.

## 4. Deploy the application

From the **repo root** (the kit assumes you run deploys from there):

**Windows (PowerShell):**
```powershell
.\deploy\oci\scripts\deploy.ps1 -PublicIp <ip> -Domain app.yourdomain.com -Email you@example.com
```

**bash / WSL / macOS:**
```bash
chmod +x deploy/oci/scripts/deploy.sh
./deploy/oci/scripts/deploy.sh -i <ip> -d app.yourdomain.com -e you@example.com
```

The script:
1. Generates a strong `SECRET_KEY` + DB passwords and renders `.env.production`
   (gitignored; never commit it).
2. Syncs the project to `/opt/adom/app` (excludes `venv/`, media, etc.).
3. Uploads operator scripts to `/opt/adom/scripts` and installs the `.env`.
4. Builds images, waits for **PostgreSQL → Redis**, runs `migrate`, then starts
   the full stack (`db, pgbouncer, redis, web, ws, worker, beat, nginx`).
5. Issues the **Let's Encrypt** certificate (webroot) and reloads nginx.

### Manual deploy (no automation)

```bash
ssh ubuntu@<ip> "sudo mkdir -p /opt/adom/app /opt/adom/scripts && sudo chown ubuntu:ubuntu /opt/adom"
# copy project + scripts (rsync/scp), then on the VM:
cd /opt/adom/app
docker compose -f docker-compose.prod.yml up -d --build migrate          # one-time schema
docker compose -f docker-compose.prod.yml up -d --build db pgbouncer redis web ws worker beat
# certificate first (standalone), then start nginx:
docker compose -f docker-compose.prod.yml run --rm -p 80:80 certbot certonly \
  --standalone -d app.yourdomain.com --email you@example.com \
  --agree-tos --no-eff-email --non-interactive
docker compose -f docker-compose.prod.yml up -d nginx
```

## 5. Verify

- `https://app.yourdomain.com/` → login page
- `https://app.yourdomain.com/admin/` → Django admin
- `https://app.yourdomain.com/swagger/` → API docs
- WebSockets: open two browser tabs → one triggers a notification in the other.

**Create the admin superuser:**
```powershell
ssh -i ~\.ssh\id_ed25519 ubuntu@<ip> "cd /opt/adom/app && docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser"
```

## 6. Object storage for media/static (optional but recommended)

First log in with the app superuser and upload a test image to confirm the
local media path works, then migrate to the bucket:

1. Console: *Identity & Security → Users → your user → Customer Secret Keys →
   Generate Secret Key* → note **Access Key** + **Secret Key**.
2. Get your endpoint/namespace: `terraform output object_storage_namespace`
   → endpoint `https://<namespace>.compat.objectstorage.<region>.oraclecloud.com`.
3. On the VM, edit `/opt/adom/app/.env` (or re-render locally and scp):

```
USE_S3=True
AWS_ACCESS_KEY_ID=<access key>
AWS_SECRET_ACCESS_KEY=<secret key>
AWS_STORAGE_BUCKET_NAME=<prefix>-media
AWS_S3_REGION_NAME=us-ashburn-1
AWS_S3_ENDPOINT_URL=https://<namespace>.compat.objectstorage.<region>.oraclecloud.com
```

4. `docker compose -f docker-compose.prod.yml restart web ws worker && docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput`

Existing local media can be copied once:
`aws s3 --endpoint-url <endpoint> sync /opt/adom-data/mediafiles s3://<bucket>/media/`

## 7. Backups & restores

- **DB:** daily 03:20 UTC — compressed `pg_dump` to `/opt/adom/backups`, then
  uploaded to the `*-backups` bucket when S3 keys are configured.
  Add a **lifecycle rule** on the bucket: archive > 7 days, delete > 90 days.
- **Manual backup:** `sudo /opt/adom/scripts/backup.sh`
- **Restore:** `sudo /opt/adom/scripts/restore.sh [path.dump.gz]`
- **Cert renew:** automatic 02:17 UTC via `renew-cert.sh` + cron.

## 8. Security checklist

- [ ] Security list: restrict SSH to your office CIDR (`ssh_ingress_cidr`),
      not `0.0.0.0/0`.
- [ ] `.env` has a generated `SECRET_KEY`, strong DB passwords; file is
      gitignored and `chmod 600`.
- [ ] `SECURE_SSL_REDIRECT / SESSION_COOKIE_SECURE / CSRF_COOKIE_SECURE`
      are `True` in production `.env` (pre-set).
- [ ] TLS certificate valid; HSTS enabled (pre-set).
- [ ] OCI **Budgets alert at $1** + notifications, and check
      *Cost Analysis* after the first month.
- [ ] Limit `ALLOWED_HOSTS` to real domains (settings refuses localhost/* in prod).
- [ ] Enable 2FA for staff accounts (feature exists in the app).

## 9. Monitoring & troubleshooting

```bash
docker compose -f docker-compose.prod.yml ps                # container states
docker compose -f docker-compose.prod.yml logs -f web       # app/access logs
docker compose -f docker-compose.prod.yml logs -f worker    # celery logs
docker stats                                                # CPU/memory per container
tail -f /app/logs/django.log                                # (inside web container)
```

**Common issues**

| Symptom | Fix |
|---------|-----|
| `migrate` fails to reach DB | PgBouncer starts before `db` healthy; wait or `docker compose up -d db` first |
| Site is HTTP-only / loops | certbot failed → re-run the `certonly` command (standalone, port 80 free), or check your A record resolves to the VM |
| WebSockets drop | confirm nginx `/ws/` proxy + `Upgrade` headers; `docker compose logs ws` |
| 502 from nginx | `web`/`ws` not up: `docker compose up -d --build web ws` |
| Slow at peak | Phase 1/2 in `SCALING.md`; also `docker stats` to see whether Redis or DB is the hot component |
| Static 404 after S3 switch | re-run `collectstatic` (step 6) |

## 10. Cost guardrails

PAYG with this stack inside Always Free limits = **$0/month**. Before
stepping outside free limits (bigger shape, extra volume, LB >10 Mbps,
more egress), read `SCALING.md` and set an OCI Budget.

---

Next: read **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full capacity plan,
then **[SCALING.md](SCALING.md)** before the tenant count grows past 4 schools.