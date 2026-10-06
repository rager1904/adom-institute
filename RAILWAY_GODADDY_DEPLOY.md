# Deploy to Railway + GoDaddy (`adominstitute.com`)

End-to-end runbook for putting ADOM Institute on Railway behind your own GoDaddy domain.

Order matters. Part 1 gets a working service on the `*.up.railway.app` URL. Part 2 points
`adominstitute.com` at it. Do not start the DNS step until Part 1 is verified — a
certificate will not issue for a host that isn't serving.

---

## Part 0 — What the deploy reads from this repo

| File | Purpose |
|---|---|
| `nixpacks.toml` | Build phases (system libs, pip, `collectstatic`) + start command |
| `runtime.txt` | Pins Python 3.11 |
| `Procfile` | Fallback start command if `nixpacks.toml` is ever removed |
| `railway.json` | Healthcheck path + restart policy |
| `.railwayignore` | Keeps `.venv/`, `media/`, `staticfiles/`, `logs/` out of the upload |
| `entrypoint.sh` | Waits for Postgres/Redis, runs `collectstatic`, execs gunicorn |

Two config details that are easy to miss:

- `entrypoint.sh` is committed mode `755`. The exec bit comes from git, not your local
  filesystem. The `Dockerfile` does its own `chmod +x`, which is why a `644` mode went
  unnoticed until Railway.
- `logs/` is gitignored, but `settings.py` writes to `BASE_DIR/logs/django.log` via
  `FileHandler`. Missing directory means a crash at startup, so the start command
  `mkdir -p`s it.

---

## Part 1 — Railway service

### Step 1. Create the project

Railway dashboard → **New Project** → **Deploy from GitHub repo** → select
`rager1904/adom-institute`. The build starts immediately from `nixpacks.toml`.

### Step 2. Add Postgres (before the first successful deploy)

**+ New** → **Database** → **PostgreSQL**.

Railway injects `PGHOST`, `PGPASSWORD`, `PGDATABASE`, `PGPORT`, `PGUSER` into the app
service automatically.

### Step 3. Map `PG*` to the names this project expects

`adom/settings.py:124-128` reads `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`,
`DB_PORT`. Railway does not know that, so nothing wires up on its own.

**Option A (recommended, least error-prone):** Copy values from Postgres

1. Go to the **PostgreSQL** service → **Connect** tab.
2. Copy `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGPORT`.
3. Go to your **app** service → **Variables** → **Raw Variables** and add:

```
DB_NAME     = <PGDATABASE>
DB_USER     = <PGUSER>
DB_PASSWORD = <PGPASSWORD>
DB_HOST     = <PGHOST>
DB_PORT     = <PGPORT>
```

**Option B (shared variable references):** If you prefer references, the service name must
match exactly. In the app service → **Variables** → **Shared Variable**:

```
DB_NAME     = ${{postgres.PGDATABASE}}
DB_USER     = ${{postgres.PGUSER}}
DB_PASSWORD = ${{postgres.PGPASSWORD}}
DB_HOST     = ${{postgres.PGHOST}}
DB_PORT     = ${{postgres.PGPORT}}
```

If your Postgres service is named differently, update the prefix to match. For a service
named `PostgreSQL` (capital P/S), use `${{PostgreSQL.*}}` instead.

**Verify after setting:** In the app service → **Deployments** → latest → **View Logs**
or run a one-off command: `python -c "import os; print({k: bool(os.getenv(k)) for k in ('DB_NAME','DB_USER','DB_PASSWORD','DB_HOST','DB_PORT')})"`
All five should be `True`.

Skipping this is the single most common failure. Symptoms: `DB_ENGINE=postgresql is
required when DEBUG=False`, or a connection refused error on first request.

### Step 4. Generate a secret key

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Step 5. Set the app variables

App service → **Variables** → **Raw Variables**:

```
DEBUG=False
SECRET_KEY=<paste the generated value>
DB_ENGINE=postgresql
ALLOWED_HOSTS=adominstitute.com,www.adominstitute.com,<app>.up.railway.app
CORS_ALLOWED_ORIGINS=https://adominstitute.com,https://www.adominstitute.com
ADOM_INSTITUTE_AI_ENABLED=False
```

Replace `<app>.up.railway.app` with the name Railway actually generated. Keep it in
`ALLOWED_HOSTS` during setup so you retain a fallback entry point.

Why these are written this way:

- `ALLOWED_HOSTS` rejects `*`, `localhost`, and `127.0.0.1` when `DEBUG=False` —
  `settings.py:33-38` raises `ImproperlyConfigured`.
- There is no `CSRF_TRUSTED_ORIGINS` anywhere in this project. Django 4 validates CSRF
  referrers against `ALLOWED_HOSTS`, so that list is what makes form posts work on a new
  hostname.
- `CORS_ALLOWED_ORIGINS` only matters if a separate frontend calls the API. Safe to leave
  set.
- `ADOM_INSTITUTE_AI_ENABLED=False` because the AI stack expects Ollama on
  `localhost:11434`, which does not exist on Railway.

Do not override the security flags. `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`,
`CSRF_COOKIE_SECURE`, and HSTS all default on when `DEBUG=False`, and
`SECURE_PROXY_SSL_HEADER` already trusts Railway's `X-Forwarded-Proto: https`.

### Step 6. Deploy, then run migrations

Railway does not run migrations. Dashboard → latest **Deployment** → **Run Command**:

```
python manage.py migrate --noinput
```

Then again:

```
python manage.py createsuperuser
```

Create the superuser **before** opening `/admin/`. There is no registration path into
Django's admin, so skipping this locks you out of the admin site entirely.

### Step 7. Verify before touching DNS

| Check | Expected |
|---|---|
| `GET https://<app>.up.railway.app/health/` | `{"status": "ok", "service": "adom-institute"}` |
| `GET https://<app>.up.railway.app/` | Home page renders |
| `GET https://<app>.up.railway.app/admin/login/` | Admin login page |
| `GET https://<app>.up.railway.app/swagger/` | API docs |

If `/health/` returns a redirect instead of 200, stop. That means the SSL redirect is
still catching the probe path and the container will look unhealthy.

---

## Part 2 — GoDaddy domain

### Step 8. Attach the domain in Railway

App service → **Settings** → **Networking**. Confirm you have a `*.up.railway.app`
domain, then **Custom Domains** → **Add Custom Domain**.

Start with **`www.adominstitute.com`**, not the apex. Railway needs to point the hostname
at `<app>.up.railway.app`. `www` is a plain CNAME and works everywhere; the apex
usually needs ALIAS-style flattening, which GoDaddy only partially supports.

Railway may show a verification record. Add it in GoDaddy, then wait for the cert to
issue — usually under a minute, occasionally a few.

### Step 9. GoDaddy DNS records

GoDaddy → **My Domains** → `adominstitute.com` → **DNS** → **Add record**:

| Type | Name | Value | TTL |
|---|---|---|---|
| CNAME | `www` | `<app>.up.railway.app` | 600 |
| TXT | `_railway` | *(value Railway gave you)* | 600 |

Do not touch the `@` apex record yet. A bad apex entry can break the working `www`
setup.

If Railway reports the domain as unverified and DNS isn't resolving, confirm GoDaddy is
actually authoritative — **Nameservers** should be `ns1.godaddy.com` / `ns2.godaddy.com`.
If the domain was registered at a different registrar, GoDaddy's DNS panel does nothing.

### Step 10. Point the apex at `www`

Once `www` is verified and working:

| Type | Name | Value |
|---|---|---|
| CNAME | `@` | `www.adominstitute.com` |

GoDaddy supports CNAME at the apex. If it rejects that, use GoDaddy's flattening A record
instead:

| Type | Name | Value |
|---|---|---|
| A | `@` | `76.76.21.21` |

### Step 11. Re-verify on the real domain

- `https://www.adominstitute.com/health/` → 200 JSON
- `https://www.adominstitute.com/admin/login/` → renders
- Log in and submit any form → confirms CSRF passes on the new hostname

Railway marks the domain **Verified** once the cert is live. Propagation is usually a few
minutes, occasionally a few hours.

---

## Part 3 — Hardening

### Trim `ALLOWED_HOSTS`

Once the domain is stable, drop the Railway fallback if you don't want it publicly
reachable:

```
ALLOWED_HOSTS=adominstitute.com,www.adominstitute.com
```

Keep it until you're confident the domain works — it's your recovery path.

### Media uploads are ephemeral

The container filesystem resets on every deploy, so uploaded files vanish. Acceptable
while testing. To persist, set:

```
USE_S3=True
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=adom-media
AWS_S3_REGION_NAME=us-east-1
```

### Review the protected-media rules

`deploy/oci/nginx/adom.conf` returns 404 for `/media/library/digital/` and
`/media/assignments/`. Those protections live in nginx, and Railway has no nginx in front.
Worth reviewing before this is publicly reachable with real student uploads — the
`protected_media` view and `MATERIALS_READ_ONLY` /
`ALLOW_MATERIAL_DOWNLOADS` settings are what actually need to carry that.

### Celery and Channels degrade gracefully

With no Redis configured, `REDIS_HOSTS` is empty and `entrypoint.sh` skips the wait.
Channels falls back to the in-memory layer; Celery tasks queue up and are never run.

To enable, add a Railway **Redis** service and set:

```
REDIS_HOSTS=<redis-host>:<redis-port>
REDIS_URL=redis://<redis-host>:<redis-port>/1
REDIS_CHANNEL_URL=redis://<redis-host>:<redis-port>/2
CELERY_BROKER_URL=redis://<redis-host>:<redis-port>/0
CELERY_RESULT_BACKEND=redis://<redis-host>:<redis-port>/0
```

Then add worker and beat services from the same repo:

```
celery -A adom worker -l info
celery -A adom beat -l info --schedule /app/beat-schedule/celerybeat-schedule
```

---

## Troubleshooting

**`ImproperlyConfigured: ALLOWED_HOSTS must contain only production hostnames`**
`ALLOWED_HOSTS` is `*`, `localhost`, `127.0.0.1`, or unset. Use the real hostname.

**`ImproperlyConfigured: SECRET_KEY must be configured`**
No real `SECRET_KEY` set, or the placeholder from `.env.production.example` was used.

**`ImproperlyConfigured: DB_ENGINE=postgresql is required when DEBUG=False`**
`DB_ENGINE` unset. See Step 3 for the full `DB_*` mapping.

**`DisallowedHost` or CSRF failure on form posts**
Hostname mismatch. Railway serves both `*.up.railway.app` and your custom domain — list
every host you actually visit, comma-separated.

**Domain unverified in Railway, GoDaddy looks correct**
Usually one of: nameservers not pointed at GoDaddy; the TXT record on the wrong name;
propagation still in flight. Railway's domain page shows the exact record it expects.

**Cert issues after DNS changes**
Railway reissues automatically, but it can take a few minutes. Force a redeploy from the
deployment's **Redeploy** button if it stays stuck.

**`/health/` never goes green**
Confirm it returns 200. If you changed the route, update `railway.json` →
`deploy.healthcheckPath`.

**Build killed / out of memory**
`matplotlib`, `pandas`, and `numpy` are heavy. The `nixPkgs` list is already trimmed to
what the image needs; if builds still fail, drop `libwebp` and `shared-mime-info` (only
needed by exotic Pillow builds).

**`relation does not exist` on first request**
Migrations never ran. Step 6.

---

## Rollback

Railway keeps previous deployments. Dashboard → **Deployments** → pick the last known
good build → **Redeploy**. For domain changes, revert the GoDaddy DNS records; the
Railway fallback hostname keeps serving throughout.

---

## Cost

Railway's free tier is **$5/month in usage credits**, not unlimited compute. A small
Django + Postgres project usually stays under that. Past it, services pause until topped
up or usage drops below the threshold.

---

## Related

- `deploy/oci/` — Terraform, nginx, and compose stack for the Oracle Cloud path
- `Dockerfile` + `docker-compose.prod.yml` — self-hosted alternative
- Outstanding: the `Dockerfile` fix for `libgdk-pixbuf-2.0-dev` is still uncommitted, so
  the Docker build is broken independently of this Railway path