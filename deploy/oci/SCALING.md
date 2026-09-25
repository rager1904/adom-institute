# Scaling the ADOM Institute stack on OCI

Everything below is ordered by cost/effort. You can stop at any phase. The
compose stack and Terraform were designed so each phase is a small change,
not a rewrite.

> Rule of thumb: **vertical first, then horizontal.** A school-management
> platform is read-heavy; one well-sized node with Redis + PgBouncer beats
> two undersized nodes fighting for the same DB.

## Phase 0 — Start (this kit as shipped)

- 1 x `VM.Standard.A1.Flex` (2 OCPU / 12 GB, Always Free)
- Docker Compose: db+pgbouncer+redis+web+ws+worker+beat+nginx+certbot
- **Capacity:** ~25k users / 4 big schools. Good latency; 2 cores are the
  ceiling during school-hour bursts.
- Monitor `docker stats` + `adom` logs. If the VM hovers >70% CPU during
  peak for a week, go Phase 1.

## Phase 1 — Up-size the VM (PAYG, still $0)

Upgrade the tenancy to **Pay-As-You-Go**. Per Oracle support (2026) PAYG
tenancies keep the old Always-Free Ampere allowance — up to **4 OCPU / 24 GB**.
Resize the instance in the console (stop → edit shape → 4 OCPU / 24 GB), then:

```bash
# bump memory-heavy Postgres/Redis settings proportionally
# deploy/oci/postgres/postgresql.conf :
#   shared_buffers = 1GB           effective_cache_size = 8GB
#   work_mem = 32MB                maintenance_work_mem = 256MB
# deploy/oci/.env.production.example :
#   WEB_WORKERS=4   WEB_THREADS=6   CELERY_CONCURRENCY=4   REDIS_MAXMEMORY=1gb
cd /opt/adom/app && docker compose -f docker-compose.prod.yml up -d --force-recreate web ws worker
```

Expected: ~2x throughput, 15–25k users per school load with margin.

## Phase 2 — Split roles onto a second node

Free tier allows 2 ARM instances (or 2 AMD micros) as long as the *sum* stays
≤2 OCPU / 12 GB (free-only) — or use the 2nd free micro VM (`E2.1.Micro`) as a
dedicated tiny proxy/Celery box.

With PAYG 4 OCPU / 24 GB across two VMs:

| Node | Role | Shape | Services |
|------|------|-------|----------|
| `adom-app-1` | app | 2 OCPU / 12 GB | nginx, web, ws, worker, beat |
| `adom-db-1` (new) | data | 2 OCPU / 12 GB | PostgreSQL, PgBouncer, Redis |

Changes:
- `docker-compose.prod.yml` `external: true` networks so containers on both
  hosts join one overlay network (or use the VM private IPs directly in
  `DB_HOST`, `REDIS_HOSTS`).
- `DB_HOST=<adom-db-1 private IP>`; `REDIS_HOSTS=<private IP>:6379`.
- PostgreSQL + Redis host firewall: only allow port 5432/6379 from the app
  subnet (NSG). No public IPs on the DB node (private subnet, route only for
  OCI services).

## Phase 3 — Load Balancer + private subnets

Use the Always Free flexible LB (10 Mbps) — TLS termination and health
checks offload the VM, and you gain a stable front for multiple app nodes.

1. Add an HTTPS listener with a certificate (upload the Let's Encrypt
   certs from the VM, or create a CA-signed one in OCI Certificates).
2. Move `web`/`ws` nodes into a **private subnet**; keep nginx in the public
   subnet (proxy mode) or let the LB reach the private VNICs directly.
3. Backend set: port 8001 with `/healthz/` (or `/`) TCP/HTTP health check;
   a second backend set for `/ws/` on 8002.
4. **WebSocket note:** LB → nginx → daphne keeps the `Upgrade` headers end to
   end; front the LB with a wildcard/dual cert covering the domain and `ws.`.

`main.tf` already lays out VCN + subnets + security lists; uncomment/extend
for the private subnet and add `oci_load_balancer_*` resources.

## Phase 4 — Database headroom & durability

- **Keep `pgdata` on its own block volume** (done by default) — it survives
  VM replacement; attach to the new node and run `restore.sh`.
- **Managed route (optional):** move Postgres to a small paid MySQL/Postgres
  service or a dedicated DB VM when free-tier storage (200 GB) is exhausted.
- **Read replica / reporting DB:** analytics module is read-heavy; point the
  `analytics` app at a PgBouncer-read pool when report generation gets loud.
- **Backups:** daily 03:20 UTC `pg_dump` → `/opt/adom/backups` → uploaded to
  `adom-backups` bucket (S3-compatible). Add an Object Storage **lifecycle
  rule** on the bucket: archive dumps > 7 days to Archive tier, delete after
  90 days — zero egress for same-region copies.

## Phase 5 — Object storage + CDN for files

Switch `USE_S3=True` in `.env` with the OCI bucket (S3-compatible endpoint)
and customer secret keys. Static + media leave the VM entirely:

```
USE_S3=True
AWS_STORAGE_BUCKET_NAME=adom-media
AWS_S3_ENDPOINT_URL=https://<namespace>.compat.objectstorage.<region>.oraclecloud.com
```

For global latency, add an OCI/third-party CDN in front of the bucket
(`AWS_S3_CUSTOM_DOMAIN`), or at minimum set `AWS_QUERYSTRING_AUTH=False` +
public-read bucket policy on the `media/` prefix if uploads are non-sensitive.

## Phase 6 — Big jump: more tenants / campuses

The `Institution` tenancy model means adding schools 5–10 is **a data
operation, not an architecture one** — the same DB, cache, and workers serve
them. The real levers at this stage:

- Re-read `ALLOWED_HOSTS` / CORS per custom subdomain per school
  (`school1.yourdomain.com`), and use a wildcard cert + virtual hosts.
- Move Celery queues to `worker` `-Q high,default` with priority routing.
- If a single Postgres becomes the bottleneck: partition the largest tables
  (attendance, analytics events) by `institution_id`, or shard per school.

## Sizing cheat-sheet

| Users | VM (app) | VM (db) | Redis | Notes |
|-------|----------|---------|-------|-------|
| <25k / 4 schools | 2 OCPU / 12 GB | same node | 512 MB | Phase 0/1 |
| 25–50k | 4 OCPU / 24 GB | same node | 1 GB | Phase 1 |
| 50–100k | 4 OCPU / 24 GB | 4 OCPU / 24 GB | 1–2 GB | Phase 2 split |
| >100k | LB + app ×2–3 | dedicated + replica | 2+ GB | Phases 3–4 |