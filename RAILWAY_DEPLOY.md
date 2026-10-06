# Railway Deployment Guide — ADOM Institute

Single-service deploy (Django + gunicorn + WhiteNoise) on Railway.

## What Railway reads from this repo

| File | Purpose |
|---|---|
| `nixpacks.toml` | Build phases (system deps, pip install, collectstatic) + start command. Takes priority over auto-detection. |
| `runtime.txt` | Pins Python 3.11 (matches the Docker image). |
| `Procfile` | Fallback start command if `nixpacks.toml` is ever removed. |
| `railway.json` | Healthcheck (`/health/`) + restart policy. |
| `.railwayignore` | Keeps `.venv/`, `media/`, `staticfiles/`, `logs/` out of the upload. |
| `entrypoint.sh` | Waits for Postgres/Redis, runs `collectstatic`, then execs gunicorn. |

## 1. Create the project

1. Push the changes to GitHub.
2. Railway → **New Project** → **Deploy from GitHub repo** → pick this repo.
3. Railway auto-detects Django. Because `nixpacks.toml` exists it will use it.

## 2. Add PostgreSQL

1. Project → **+ New** → **Database** → **PostgreSQL**.
2. Railway auto-injects `DATABASE_URL`, `PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`, `PGPORT`.
3. This project reads `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT`, **not** `DATABASE_URL`.

**Option A (recommended):** Copy from Postgres → Connect and set raw variables on the app service:
```
DB_NAME     = <PGDATABASE>
DB_USER     = <PGUSER>
DB_PASSWORD = <PGPASSWORD>
DB_HOST     = <PGHOST>
DB_PORT     = <PGPORT>
```

**Option B (shared references):** App service → Variables → Shared Variable (service name must match exactly):
```
DB_NAME     = ${{postgres.PGDATABASE}}
DB_USER     = ${{postgres.PGUSER}}
DB_PASSWORD = ${{postgres.PGPASSWORD}}
DB_HOST     = ${{postgres.PGHOST}}
DB_PORT     = ${{postgres.PGPORT}}
```
(If your service is named `PostgreSQL`, use `${{PostgreSQL.*}}` instead.)

**Verify:** Run `python -c "import os; print({k: bool(os.getenv(k)) for k in ('DB_NAME','DB_USER','DB_PASSWORD','DB_HOST','DB_PORT')})"` in a Railway one-off command — all should be `True`.

(Alternatively skip this and set `DB_*` by hand from the Postgres service's connect dialog.)

## 3. Required service variables

Set on the Django service:

```
DEBUG=False
SECRET_KEY=<python -c "import secrets;print(secrets.token_urlsafe(50))">
DB_ENGINE=postgresql
ALLOWED_HOSTS=<your-app>.up.railway.app
CORS_ALLOWED_ORIGINS=https://<your-app>.up.railway.app
ADOM_INSTITUTE_AI_ENABLED=False
```

> `ALLOWED_HOSTS` must be the **real hostname**. `adom/settings.py` raises `ImproperlyConfigured`
> if `DEBUG=False` and `ALLOWED_HOSTS` contains `*`, `localhost`, or `127.0.0.1`.
>
> Chicken-and-egg: you don't know the hostname until the first deploy. Either use
> `DEBUG=True` for the first deploy (SQLite fallback, no host check), read the generated
> domain from the deploy log, then set `DEBUG=False` + the real host and redeploy — or
> generate a domain first: Railway → service → **Settings → Networking → Generate Domain**,
> then set the variables before the first successful deploy.

Security flags are already on by default when `DEBUG=False`
(`SECURE_SSL_REDIRECT`, secure cookies, HSTS). Railway terminates TLS and sets
`X-Forwarded-Proto: https`, which `SECURE_PROXY_SSL_HEADER` already trusts, so no
override is needed.

## 4. Redis / Celery / Channels — optional

The app degrades gracefully: with no Redis configured, `REDIS_HOSTS` is empty and
`entrypoint.sh` skips the wait. Channels falls back to the in-memory layer and Celery
tasks just queue up unused.

Add a Railway **Redis** service only if you need it, then set:

```
REDIS_HOSTS=<redis-host>:<redis-port>
REDIS_URL=redis://<redis-host>:<redis-port>/1
REDIS_CHANNEL_URL=redis://<redis-host>:<redis-port>/2
CELERY_BROKER_URL=redis://<redis-host>:<redis-port>/0
CELERY_RESULT_BACKEND=redis://<redis-host>:<redis-port>/0
```

For background jobs, add a second service from the same repo with start command:

```
celery -A adom worker -l info
```

and a third for the beat scheduler:

```
celery -A adom beat -l info --schedule /app/beat-schedule/celerybeat-schedule
```

## 5. Migrations

Railway does not run them. After the first successful deploy, use
**Deployments → Run Command** (or `railway run` locally):

```
python manage.py migrate --noinput
```

Then create an admin user:

```
python manage.py createsuperuser
```

Create a superuser before opening `/admin/` — there is no registration path into the
Django admin.

## 6. Verify

| Check | Expected |
|---|---|
| `GET /health/` | `{"status": "ok", "service": "adom-institute"}` |
| `GET /` | Home page renders |
| `GET /admin/login/` | Admin login page |
| `/swagger/` | API docs |

## Static & media files

- **Static** — `collectstatic` runs during build, WhiteNoise middleware serves it.
  Nothing else needed; no S3 required.
- **Media** — ephemeral. The container filesystem resets on every deploy, so uploaded
  files disappear. Fine for a smoke test. For persistence set `USE_S3=True` plus
  `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`,
  `AWS_S3_REGION_NAME` (and `AWS_S3_ENDPOINT_URL` / `AWS_QUERYSTRING_AUTH` for
  S3-compatible providers).

## Troubleshooting

**`ImproperlyConfigured: ALLOWED_HOSTS must contain only production hostnames`**
`ALLOWED_HOSTS` is `*`, `localhost`, `127.0.0.1`, or unset. Use the real Railway hostname.

**`ImproperlyConfigured: SECRET_KEY must be configured`**
Set a real `SECRET_KEY`.

**`ImproperlyConfigured: DB_ENGINE=postgresql is required when DEBUG=False`**
Set `DB_ENGINE=postgresql` (and the `DB_*` values from step 2).

**`DisallowedHost` / bad CSRF on form posts**
Hostname mismatch between `ALLOWED_HOSTS` and the URL you're visiting. Railway serves both
`*.up.railway.app` and your custom domain — list every host you use, comma-separated.

**Healthcheck fails → deploys marked failed**
Check `/health/` actually returns 200. If you changed the route, update
`railway.json` → `healthcheckPath`.

**Build killed / out of memory**
`matplotlib`, `pandas`, `numpy` are heavy. The `nixPkgs` list in `nixpacks.toml` is
already trimmed to what the image needs; if builds still fail, drop `libwebp` and
`shared-mime-info` (only needed by exotic Pillow builds) or build the Docker image
instead.

**Migrations not applied / table does not exist**
Run `python manage.py migrate --noinput` from Deployments → Run Command.

## Cost note

Railway's free tier is **$5/month in usage credits**, not unlimited compute. A small
Django + Postgres project typically stays inside that. Past it, services pause until
topped up or usage drops.