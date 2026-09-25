# ADOM Institute on OCI — Architecture & Capacity Plan

## What we're deploying

ADOM Institute is a **multi-tenant** Django school-management platform (the
`Institution` model is the tenant boundary). "4 big schools in one plot"
therefore means **one deployment, four institution tenants** — exactly what
this stack is built for, with headroom to add more.

### Reference architecture (start state — single Always-Free node)

```
                          Internet
                             |
                     DNS A record -> public IP
                             |
                    [ OCI Flexible LB ]          <- Phase 3+ (scaling)
                             |
                     VCN public subnet
                             |
                      nginx :80/:443  (TLS termination, gzip, WS upgrade)
                       /            \
              http /ws ->           http rest ->
              daphne :8002           gunicorn :8001     (web containers)
                    \                /
                     \              /
                      +------------+
                      |    Redis   |   db 1 = channel layer
                      |  :6379     |   db 1 = cache + cached_db sessions
                      +------------+   db 0 = Celery broker/result
                              |
                      +------------+
                      |  PgBouncer |   transaction pooling (no conn storms)
                      +------------+
                              |
                     PostgreSQL 16  (data on dedicated 100 GB block volume)
                              |
              Celery worker + beat   (fees, reports, notifications)
                              |
             OCI Object Storage      (media + backups; buckets pre-created)
```

Single-node Compose runs on **one `VM.Standard.A1.Flex` (2 OCPU / 12 GB ARM)**
inside the VCN with a block volume for Postgres data and two object-storage
buckets (`adom-media`, `adom-backups`).

## Always Free Budget (important — limits changed June 15, 2026)

As of mid-2026 Oracle **halved** the free Ampere allowance. A free-only tenancy
gets, in **home region only**:

| Resource | Always Free allowance | Used by this stack |
|----------|-----------------------|--------------------|
| Ampere A1 compute | **2 OCPU total + 12 GB RAM** total | 1 VM @ 2 OCPU / 12 GB |
| AMD micro instances | up to 2 x `VM.Standard.E2.1.Micro` | unused (spare) |
| Block volume | 200 GB combined (boot + block) | ~50 GB boot + 100 GB data = **150 GB** (headroom 50 GB) |
| Object storage | 10 GB standard + 10 GB archive | ~1–2 GB media + compressed dumps |
| Flexible Load Balancer | 1 x 10 Mbps (free) | used from Phase 3 |
| Autonomous DB | 2 x 20 GB (Oracle DB) | **not used** — the app requires PostgreSQL |
| Egress | 10 TB / month | typically ≪ 100 GB |

> **Key decision — upgrade to Pay-As-You-Go (PAYG).** Pay-as-you-go keeps every
> Always Free resource free, *and* per Oracle support (July 2026) restores the
> older **4 OCPU / 24 GB** Ampere allowance. That single change doubles this
> stack's compute at zero cost and removes the risk of free-tier instances
> being shut down for exceeding the reduced limit. Nothing in the kit bills you
> unless you deliberately choose paid shapes/storage later.

## Capacity estimate — 4 big schools

Assumptions per "big school": ~2,000 students, ~4,000 parents/guardians,
~140 staff, i.e. **~6,100 active accounts × 4 ≈ 25,000 users**.

| Workload | Peak estimate | Handled by |
|----------|---------------|------------|
| Concurrent logins / browsers | 600–1,000 at morning check-in & exam results | gunicorn threads + Redis cached sessions |
| API anonymous (throttled) | ~200 req/hr anonymous per DRF config | Redis-backed throttling counters |
| Authenticated API | ~6,000 req/hr/user-daily ceilings | per-user throttle |
| WebSocket connections (notifications) | a few hundred | daphne + Redis channel layer |
| Attendance write-heavy burst (07:30–09:00) | ~4 schools × classes in ≤30 min | PgBouncer pool absorbs spike; async Celery offloads |
| Celery tasks / day | fee reminders, attendance alerts, daily reports | worker ×2 + beat |

**Tuning already baked into the kit** (this is the "improved latency /
throughput" part):

1. **Redis-backed cache + `cached_db` sessions** — repeated dashboard queries
   and DB session lookups move to memory (add `cache.set`/`cache_page` in
   views for further wins).
2. **PgBouncer transaction pooling** — Django connections (gunicorn threads ×
   workers, daphne, Celery workers) map to ~25 real DB connections, so the
   breakfast-time attendance burst never exhausts Postgres.
3. **Postgres 16 tuned** for the box: `shared_buffers=512MB`,
   `work_mem=16MB`, autovacuum tuned, 1s slow-query logging.
4. **gunicorn worker/thread sizing** — CPU-bound work is threaded to avoid
   2-core starvation; `--max-requests` recycles leaky workers.
5. **nginx**: gzip on, keepalive, WS upgrade proxying, static/media caching
   headers, `X-Forwarded-Proto` → Django `SECURE_PROXY_SSL_HEADER`.
6. **DRF throttle rates** raised for a 25k-user multi-tenant platform.
7. **Optional OCI Object Storage** (S3-compatible) — offloads file serving
   from the VM and survives VM rebuilds; static+media go to the bucket.
8. **Robust Celery beat** — schedule entries for tasks that don't exist yet
   are skipped instead of spamming workers (fix included in `adom/celery.py`).

## What the numbers look like on a 2-core ARM VM

Django + gunicorn (2 workers × 4 threads) + nginx on Ampere A1 comfortably
serves **200–400 RPS** of typical school-management pages (read-heavy with
Redis cache warm). With the DB bottleneck removed by pooling, per-request
latency lands in the **30–80 ms** range for cached pages and **80–200 ms** for
DB-backed ones. That is ample for the 4-school target; the PAYG 4 OCPU/24 GB
upsize roughly doubles it (see `SCALING.md`).

## Cost

* PAYG account, staying inside Always Free limits: **$0/month**.
* The moment you exceed free limits (bigger shape, more storage, more egress)
  you pay standard on-demand rates — set **OCI Budgets alert at $1** and use
  the console Cost Analysis to watch it. The kit itself creates nothing billed.
* Intentionally paid levers for headroom later: 4 OCPU/24 GB via PAYG,
  a 2nd VM, LB bandwidth >10 Mbps, more block volume.