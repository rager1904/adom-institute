# ADOM Institute on OCI — End‑to‑End Deployment Guide

This guide walks you through provisioning the network, compute, storage and
database pieces for the ADOM Institute platform on **Oracle Cloud
Infrastructure**, then deploying the application on top. It is the
click-by-click companion to the kit (see `deploy/oci/README.md`); the
Terraform path in Section 3 automates everything below.

**Target state (single node, scale‑ready):**

| Piece | Resource | Why |
|-------|----------|-----|
| Network | VCN `10.0.0.0/16` + public subnet `10.0.1.0/24` | Isolated, routable network |
| Compute | `VM.Standard.A1.Flex` (Ampere ARM, 2 OCPU / 12 GB) | App + Docker containers |
| Storage | 100 GB block volume (boot = 50 GB) | PostgreSQL data (survives VM rebuilds) |
| Object storage | `adom-media`, `adom-backups` buckets | Media/static + DB backups |
| Database | PostgreSQL 16 + PgBouncer (in Docker) | App data; OCI ADB is Oracle DB, not usable here |
| TLS | nginx + Let's Encrypt (certbot) | HTTPS |

> **Free-tier reality check (mid-2026):** Always Free Ampere compute is
> **2 OCPU + 12 GB in total** for free-only accounts, all resources must live
> in your **home region**, and storage is capped at **200 GB** boot+block
> combined. Upgrading to **Pay-As-You-Go** keeps everything free *and* (per
> Oracle support) restores the older 4 OCPU / 24 GB allowance — strongly
> recommended for the 4-school target. See `deploy/oci/ARCHITECTURE.md`.

---

## 1. Before you start

1. **Create your Oracle Cloud account** at <https://signup.oraclecloud.com>.
   Choose your **home region** carefully (e.g. `US East (Ashburn)`).
2. **Upgrade to Pay-As-You-Go** (recommended): top‑right profile menu →
   *Tenancy: <name>* → **Upgrade to Pay As You Go** → add a payment method.
   You are **never billed** while you stay inside Always Free limits, but you
   get higher provisioning priority and restored/reserved capacity.
3. **Generate an SSH key pair** locally (Windows PowerShell or WSL):
   ```powershell
   ssh-keygen -t ed25519 -C you@yourdomain.com -f $env:USERPROFILE\.ssh\id_ed25519
   ```
   You will paste the **public** key (`id_ed25519.pub`) into the console and
   keep the **private** key (`id_ed25519`) for logging in.
4. (Terraform path only) Create an **API signing key**: profile menu →
   *My profile → API Keys → Add API Key* → download the private `.pem` and
   note the **fingerprint**, **user OCID**, and **tenancy OCID**.

---

## 2. Create the Virtual Cloud Network (VCN)

The wizard creates the subnets, gateways, route tables and security lists in
seconds — do **not** hand-build these.

1. Open the ☰ menu → **Networking → Virtual cloud networks**.
2. Confirm the correct **compartment** (top-left filter).
3. Click **Start VCN Wizard** → select **Create VCN with Internet
   Connectivity** → **Start VCN Wizard**.
4. Fill in:

   | Field | Value |
   |-------|-------|
   | VCN name | `adom-vcn` |
   | Compartment | your compartment (root is fine) |
   | VCN CIDR block | `10.0.0.0/16` |
   | Public subnet CIDR block | `10.0.1.0/24` |
   | Private subnet CIDR block | `10.0.2.0/24` |
   | Use DNS Hostnames | ✅ checked |

5. **Next → Create → View VCN** after it completes.

You now have: a VCN, **internet gateway**, route tables (public subnet →
internet gateway), a **public subnet** and **private subnet**, and **default
security lists** (which already allow SSH on 22).

## 3. Open the application ports in the security list

1. On the `adom-vcn` details page → **Security Lists** (left) →
   **Default Security List for adom-vcn**.
2. Click **Add Ingress Rules** and add **each** row below (leave *Stateless*
   unchecked, *Source Type* = CIDR):

   | Source CIDR | IP Protocol | Destination Port | Purpose |
   |-------------|-------------|------------------|---------|
   | `0.0.0.0/0` | TCP | `80` | HTTP (certbot challenge + redirect) |
   | `0.0.0.0/0` | TCP | `443` | HTTPS (the app) |
   | `YOUR_IP/32` | TCP | `22` | SSH — restrict to your office/public IP |

   > Find your public IP with `curl ifconfig.me`. Open 22 to `0.0.0.0/0`
   > during bootstrap if you must, then **replace with `YOUR_IP/32`** — the
   > default wizard rule `Allow TCP traffic for SSH` targets the same
   > security list; you can edit its source CIDR instead of adding a new row.
   > Internet scanning bots will hammer an open 22 — keep it locked.

3. Click **Add Ingress Rules**.

## 4. Create the compute instance

1. ☰ menu → **Compute → Instances** → **Create instance**.
2. **Name:** `adom-app-1` (compartment: your compartment).
3. **Placement:** leave default Availability Domain. If you get
   *"out of host capacity"*, try AD-2/AD-3 or upgrade to PAYG.
4. **Image:** click **Change image** → *Platform images* →
   **Canonical Ubuntu 24.04** (look for the **Always Free-eligible** tag;
   avoid "Minimal"/"aarch64" variants — the standard image auto-selects ARM
   for this shape) → **Select image**.
5. **Shape:** click **Change shape** → *Shape series* tab → **Ampere** →
   select `VM.Standard.A1.Flex` (badge: **Always Free-eligible**) →
   set:

   | Setting | Value |
   |---------|-------|
   | OCPUs | `2` (free) — `4` if on PAYG |
   | Memory | `12` GB (free) — `24` GB if on PAYG |

   → **Select shape**.
6. **Networking:** *Select existing virtual cloud network* →
   `adom-vcn`; *Subnet* → `Public Subnet-adom-vcn (Regional)` →
   tick **Assign a public IPv4 address**.
   > If the public-IP toggle is greyed out, you are on a private subnet — go
   > back and pick the **public** subnet (create the VCN first, as in §2, then
   > this toggle works).
7. **Add SSH keys:** paste the contents of your `id_ed25519.pub`.
8. **Boot volume:** leave defaults (≈50 GB).
9. **Advanced options → Management** → **Initialization script**:
   paste the contents of
   [`deploy/oci/TERRAFORM/cloud-init/app-node.sh`](TERRAFORM/cloud-init/app-node.sh)
   (it installs Docker + Compose, mounts the block volume from §5, and
   schedules the backup/cert-renewal cron jobs). The console base64-encodes
   automatically.
   > **Skipped it?** No problem — the manual commands are in §11.
10. Click **Create**. Wait for status → **RUNNING** (1–3 min), then note the
    **Public IP address**.

### (Optional) Keep your public IP stable

Instances get an *ephemeral* public IP that changes on stop/start. To pin it:

- ☰ menu → **Networking → Reserved public IPs** → **Create Reserved Public
  IP Address** → name `adom-public-ip` → then on the instance → *Attached
  VNICs → Actions → Edit → IP addresses → assign the reserved IP*.

(Recommended, since you will point DNS at this IP.)

## 5. Create and attach the PostgreSQL block volume

1. ☰ menu → **Block Storage → Block Volumes** → **Create Block Volume**:

   | Field | Value |
   |-------|-------|
   | Name | `adom-pg-data` |
   | Availability Domain | **same AD as the instance** |
   | Size | `100` GB (your 200 GB free pool: 50 boot + 100 data = 150 used) |
   | Backup policy | none / default |

2. Click **Create Block Volume**, wait until **AVAILABLE**, then from its
   details page → **Attach to instance** → *Paravirtualized* →
   select `adom-app-1` → **Attach**.

The `cloud-init` script in step 4-9 formats it (`ext4`), mounts it at
`/opt/adom-data/pgdata`, adds an fstab entry, and Docker runs Postgres from
there — **nothing else to do**.

## 6. Object Storage buckets

1. ☰ menu → **Object Storage → Buckets** → **Create Bucket**:

   | Field | `adom-media` | `adom-backups` |
   |-------|--------------|----------------|
   | Compartment | your compartment | your compartment |
   | Bucket name | `adom-media` | `adom-backups` |
   | Storage tier | Standard | Standard |
   | Access | NoPublicAccess | NoPublicAccess |

2. On `adom-backups` → **Lifecycle rules** → add a rule that
   **archives objects after 7 days** and **deletes after 90 days** so dumps
   are trimmed automatically.

## 7. S3-compatible keys (for media + backups from the app)

1. ☰ menu → **Identity & Security → Users → <your user>** →
   **Customer Secret Keys → Generate Secret Key**.
2. Copy the displayed **Access Key** and **Secret Key** (shown once) — these
   are what the app and backup script use against the S3-compatible endpoint:

   ```
   https://<namespace>.compat.objectstorage.<region>.oraclecloud.com
   ```

   Your **namespace** is shown on any Bucket page ("Object Storage
   namespace") — it is the same for the whole tenancy.

> Media/backups work fine on local disk first; you can enable object storage
> later (`deploy/oci/README.md` §6). The DB backups always write to
> `/opt/adom/backups` and upload to the bucket **only when keys are set**.

## 8. DNS

At your DNS provider create:

| Record | Name | Value |
|--------|------|-------|
| A | `app` | `<public IP>` |

i.e. `app.yourdomain.com → <public IP>`. (Also used for the TLS certificate.)

---

## 9. Deploy the application

### Option A — one-command deploy (recommended)

From the **repo root** on your machine:

**Windows PowerShell:**
```powershell
.\deploy\oci\scripts\deploy.ps1 -PublicIp <public-ip> -Domain app.yourdomain.com -Email you@example.com
```

**bash / WSL / macOS:**
```bash
./deploy/oci/scripts/deploy.sh -i <public-ip> -d app.yourdomain.com -e you@example.com
```

What it does (in order):
1. Generates `SECRET_KEY` + DB passwords, renders `.env.production`
   (gitignored).
2. Syncs the project to `/opt/adom/app` (excludes `venv`, media, logs, `.env`).
3. Uploads operator scripts + the production `.env`.
4. Builds images; waits for Postgres → Redis; runs `migrate`; starts
   `db, pgbouncer, redis, web, ws, worker, beat`.
5. Issues the **Let's Encrypt** certificate (standalone, before nginx starts).
6. Starts **nginx** with the certificate.

### Option B — manual (no automation)

```bash
# from your machine
scp -i ~/.ssh/id_ed25519 -r . ubuntu@<ip>:/tmp/  # or rsync (see deploy.sh)
ssh ubuntu@<ip>

# on the VM
sudo mkdir -p /opt/adom && sudo chown ubuntu:ubuntu /opt/adom
mv /tmp/adom-institute /opt/adom/app
cp /opt/adom/app/deploy/oci/.env.production.example /opt/adom/app/.env
# edit /opt/adom/app/.env : SECRET_KEY, ALLOWED_HOSTS, CORS, DB/Postgres passwords, email
cd /opt/adom/app
docker compose -f docker-compose.prod.yml up -d --build migrate
docker compose -f docker-compose.prod.yml up -d --build db pgbouncer redis web ws worker beat
docker compose -f docker-compose.prod.yml run --rm -p 80:80 certbot certonly \
  --standalone -d app.yourdomain.com --email you@example.com \
  --agree-tos --no-eff-email --non-interactive
docker compose -f docker-compose.prod.yml up -d nginx
```

## 10. Verify and finish

1. **HTTPS:** open `https://app.yourdomain.com` (expect the login page) and
   `https://app.yourdomain.com/admin/` (Django admin).
2. **Create the superuser:**
   ```bash
   ssh ubuntu@<ip> "cd /opt/adom/app && docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser"
   ```
3. **Confirm services are up:**
   ```bash
   ssh ubuntu@<ip> "cd /opt/adom/app && docker compose -f docker-compose.prod.yml ps"
   ```
4. **On-board your 4 schools:** log into `/admin/` → **Institutions → Add**
   → create each school with a unique code (e.g. `SCHL-001`). Multi-tenancy
   is handled by the app's `Institution` model; no re-architecture needed.
5. **Enable object storage (optional):** `deploy/oci/README.md` §6 (set
   `USE_S3=True`, `AWS_*` keys in `.env`, restart, re-run `collectstatic`).

---

## 11. If you skipped the cloud-init script (manual host setup)

```bash
# on the VM as ubuntu, then:
sudo apt-get update && sudo apt-get install -y ca-certificates curl gnupg awscli
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=arm64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER   # re-login afterwards

# mount the block volume (from §5)
sudo mkdir -p /opt/adom-data/pgdata
DEV=$(lsblk -dpno NAME | grep -E 'sdb$|oraclevdb$' | head -n1)
sudo mkfs.ext4 "$DEV" && sudo mount "$DEV" /opt/adom-data/pgdata
echo "UUID=$(sudo blkid -s UUID -o value $DEV) /opt/adom-data/pgdata ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab

# scheduled jobs
sudo mkdir -p /opt/adom/scripts /opt/adom/app
# ...then copy the project + scripts, and continue from Option B above
```

---

## 12. Security & cost checklist (do once)

- [ ] SSH (port 22) locked to your IP in the security list (§3).
- [ ] Reserved public IP attached (§4) so DNS never breaks.
- [ ] `.env` `chmod 600`, strong `SECRET_KEY` / DB passwords, never committed.
- [ ] Budget alert: ☰ → **Billing & Cost Management → Budgets → Create
  Budget** → threshold **$1** → attach **Notifications** topic with your email.
- [ ] First month: check **Cost Analysis** — staying inside free limits = **$0**.
- [ ] Enable app-level 2FA for staff (feature exists in the app).
- [ ] Object Storage lifecycle rules configured for `adom-backups` (§6).

## 13. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ssh: connect to host ... port 22: Connection refused/timed out` | Security list lacks 22, or instance on **private** subnet (re-attach to public subnet); check **Instance state = RUNNING** |
| *Out of host capacity* at instance creation | Try another AD; or **upgrade to PAYG** (capacity priority, still free within limits) |
| Public IP toggle disabled | You're creating a new VCN/subnet inline — create the VCN first (§2), then pick **public** subnet (§4-6) |
| `migrate` fails: DB unreachable | PgBouncer waits for Postgres; ensure `db` is healthy first: `docker compose up -d db && docker compose up -d pgbouncer` |
| Site loads on HTTP only | Certificate step failed — re-run the standalone `certonly`; confirm DNS A record resolves to the VM |
| 502 Bad Gateway from nginx | `web`/`ws` containers not running: `docker compose up -d --build web ws` and check `docker compose logs web` |
| Nothing on port 80/443 from outside | Security list rules missing (Add ingress 80 + 443, §3) |
| Static files 404 after enabling object storage | Re-run `docker compose exec web python manage.py collectstatic --noinput` |
| Container host reboot → app down | Confirm `restart: unless-stopped` (set in compose) and Docker enabled at boot (`systemctl enable docker`) |
| Block volume not mounted after re-create | fstab entry uses the volume UUID; if you replaced the volume, re-run the mount commands in §11 |

---

Next steps after this guide:
- Understand the capacity plan → [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Grow past 4 schools → [`SCALING.md`](SCALING.md)