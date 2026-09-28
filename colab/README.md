# Colab load & performance harness

Provisions a complete ADOM Institute deployment inside a Google Colab runtime,
seeds a dataset sized to that runtime, and measures the system under concurrent
load. Real PostgreSQL, real Redis, real Celery, real ASGI server, real clients.

Open **`adom_loadtest.ipynb`** in Colab and run it top to bottom. That notebook is
the intended entry point; everything below is reference material for the scripts
it calls and for running them by hand.

## Contents

| File | Purpose |
|---|---|
| `adom_loadtest.ipynb` | The full end-to-end run: install, seed, serve, tunnel, measure, report |
| `harness/scale.py` | Picks a dataset size from the runtime's RAM/CPU and prints a summary |
| `harness/seed.py` | Writes the dataset with `bulk_create` and emits `.colab_loadtest/manifest.json` |
| `harness/scenarios.py` | The scenario catalogue: real URLs, roles, weights, body templates |
| `harness/loadgen.py` | Closed-loop async HTTP driver with a concurrency ladder and percentiles |
| `harness/wsprobe.py` | Django Channels probe: handshake latency and chat fan-out |
| `harness/dbstat.py` | PostgreSQL/Redis diagnostics and `EXPLAIN (ANALYZE, BUFFERS)` on the hot reads |

## Quick start

1. Open `adom_loadtest.ipynb` in Colab and run the cells in order. The tunnel
   cell **must** come before the server cell.
2. The repository is **private**, and a fresh Colab runtime has no GitHub
   credentials, so step 1 needs the source. Pick one:

   | Option | What to do |
   |---|---|
   | Zip (easiest) | Zip the project, upload it with the Colab sidebar (Files -> Upload). Leave `GITHUB_TOKEN` empty; the notebook finds and extracts it automatically. |
   | Colab secret | Colab -> Secrets -> `GITHUB_TOKEN` = a fine-grained PAT with **Contents: read-only**. Picked up automatically, never printed. |
   | Paste a token | Put one in `GITHUB_TOKEN` in the config cell. Revoke it after the run; it appears in the notebook output. |
   | Public repo | Make the repository public and no token is needed. |

   If a zip is present the notebook prefers it, so a failed private-remote
   clone is not fatal.

Tokens are handed to git through `GIT_ASKPASS`, so they never appear in the
command line, in a traceback, or in `ps` output.

### Interpreter: Python 3.12, not the Colab default

Colab now ships Python 3.13, but `requirements.txt` pins `numpy==1.26.4` and
`Django==4.2.7`, which support **Python 3.9-3.12** and publish no 3.13 wheels.
The `Dockerfile` targets 3.11. Installing those pins on 3.13 falls back to a
source build of NumPy that cannot succeed.

The notebook therefore installs a real 3.12 with
[`uv`](https://github.com/astral-sh/uv) when the default interpreter is too new,
  and creates the venv with `uv venv`. That second part is not cosmetic: Colab's
  CPython ships **without `ensurepip`**, so `python3 -m venv` fails with
  `returned non-zero exit status 1`. Installing Debian's `python3-venv` does not
  help, because that package only provides `ensurepip` for *Debian's* interpreter,
  not the one in `/usr/local` that `python3` resolves to.

  `uv venv` deliberately seeds **no pip at all**, so the venv it creates has
  `bin/python` but no `bin/pip`. Every install therefore runs as
  `<venv>/bin/python -m pip ...` rather than calling `bin/pip` directly, and pip
  is bootstrapped into the venv first (`ensurepip`, falling back to
  `uv pip install --python <venv>/bin/python`).

An existing `.venv` is judged by **the version of the interpreter inside it**,
not by whether the directory exists. A venv left behind by an earlier failed run
on the 3.13 default looks perfectly valid to an existence check, and then fails
several minutes later with pip's `No matching distribution found for
numpy==1.26.4` — which reads like a bad pin but is really a version mismatch.
Such a venv is discarded and rebuilt; a healthy one is reused.

Requirements are installed with `--only-binary=:all:`, so an unsatisfiable pin
fails in seconds with a clear message instead of minutes of doomed compilation.

## Running the scripts by hand

All five scripts take `--help`. They are plain scripts, not Django management
commands, so they must be run from the repository root with the environment the
server is using.

```bash
# 1. What would this machine get?
python colab/harness/scale.py

# 2. Populate the database (needs DJANGO_SETTINGS_MODULE + DB_* + DEBUG=False + ALLOWED_HOSTS)
python colab/harness/seed.py --reset

# 3. What will the load driver hit?
python colab/harness/loadgen.py --list

# 4. Drive load
python colab/harness/loadgen.py \
    --manifest .colab_loadtest/manifest.json \
    --base-url http://127.0.0.1:8000 \
    --host-header your-tunnel-host.trycloudflare.com \
    --concurrency 1,5,10,20,40 \
    --duration 10 --warmup 5 \
    --out .colab_loadtest/http_results.json

# 5. WebSockets (log in via the HTML form; Channels uses session cookies)
python colab/harness/wsprobe.py \
    --manifest .colab_loadtest/manifest.json \
    --base-url http://127.0.0.1:8000 \
    --notifications 25 --chat 25 \
    --out .colab_loadtest/ws_results.json

# 6. Why is it slow?
python colab/harness/dbstat.py --repo . --redis-url redis://127.0.0.1:6379/0
```

## Design notes worth knowing before you trust a number

### `DEBUG=False` is mandatory, and it constrains everything else

`adom/settings.py` makes this non-optional:

* **Lines 33-38** raise `ImproperlyConfigured` if `ALLOWED_HOSTS` contains `*`,
  `localhost`, `127.0.0.1` or `testserver` while `DEBUG=False`.
* **Lines 89-91** append `DebugToolbarMiddleware` while `DEBUG=True`, and
  `INTERNAL_IPS` is `['127.0.0.1']` (lines 363-365). A `DEBUG=True` benchmark
  would therefore measure the debug toolbar, because the load driver connects
  from `127.0.0.1`.

So the harness runs with `DEBUG=False`, puts **only** the tunnel hostname in
`ALLOWED_HOSTS`, and has every client send that hostname as its `Host` header
while still connecting to `127.0.0.1`. The benchmark exercises the real
`DisallowedHost` and CSRF-origin paths without putting the tunnel in the request
path — tunnel latency would otherwise dominate the measurement.

If you disable the tunnel, the notebook falls back to `DEBUG=True` and says so
loudly. Do not trust latency from that mode.

### The load generator never logs in

`seed.py` mints DRF `Token` objects and writes them to the manifest, so the
driver spends no time on authentication. That is deliberate: authentication cost
(PBKDF2, session, middleware) would swamp the query cost that actually matters
here, and it is constant across scenarios anyway.

The seeder also computes **one** password hash and reuses it for every account.
Hashing 3,000+ passwords with PBKDF2 would otherwise dominate the seeding step.
The shared password is `LoadTest!2345` and is printed in the manifest.

### The WebSocket probe does log in

Channels authenticates with a session cookie, not a DRF token
(`adom/asgi.py:24` wraps the router in `AuthMiddlewareStack`). The probe performs
a real form login — CSRF token, cookies and all — once per virtual user, then
opens the socket. That is a one-time cost, excluded from the fan-out number.

`wsprobe.py` omits the `Origin` header by default. Channels'
`AllowedHostsOriginValidator` compares `Origin` against the request `Host` and
explicitly permits a *missing* `Origin`; sending `http://127.0.0.1` would be
rejected once `ALLOWED_HOSTS` holds only the tunnel hostname. The browser path
through the tunnel still exercises the full validator. If you pass `--origin`,
the probe retries without it on a denied handshake rather than reporting a false
failure.

Note that the chat probe **writes** `Message` rows, because `ChatConsumer`
persists inbound messages. That is intentional — it makes write volume realistic.

### Throttles are disabled

`DRF_USER_THROTTLE_RATE` and `DRF_ANON_THROTTLE_RATE` are raised to
`100000/min`. DRF's defaults (`1000/hour` per user) would have the driver
measuring the throttle rather than the query. Set them back to production values
in the notebook env block if you want to measure throttling.

### Redis databases are split

Four databases, matching the intent documented at `settings.py:237-247`:

| DB | Purpose |
|---|---|
| 0 | Django cache + sessions |
| 1 | Celery broker |
| 2 | Channels channel layer |
| 3 | Celery result backend |

This matters: leaving the defaults would put the channel layer and the Celery
result backend both on DB 2, which pollutes both under load.

## Sizing

`scale.py` reads the runtime's RAM and CPU and picks one of three tiers.

| Tier | Requires | Students | Teachers | Attendance rows |
|---|---|---|---|---|
| `standard` | anything | 2,000 | 120 | 40,000 |
| `highmem` | 8 GB+ | 5,000 | 300 | 120,000 |
| `ultra` | 16 GB+ | 10,000 | 600 | 300,000 |

Override any value with `ADOM_SEED_*` environment variables, e.g.
`ADOM_SEED_STUDENTS=500 ADOM_SEED_TEACHERS=60 python colab/harness/seed.py`.
Run `scale.py` first to see what your machine would get.

RAM is a floor, not a target: Colab reports the *host's* RAM, which can exceed
the billed allocation, so the tier can be more aggressive than you expect. Check
`python colab/harness/scale.py` output rather than assuming.

## How to read the results

**Read the shape, not the absolute milliseconds.** A Colab runtime is shared,
throttled, and preemptible, and its 12 GB / 2 vCPU is a different machine class
from the VM in `deploy/oci/SCALING.md` that targets the full ~25,000-user
production dataset. Treat Colab output as *"cost per request on this data
shape"* and run any comparison at least three times.

Useful signals:

* **p99 growing faster than p50** — queueing, usually a connection pool or
  worker limit.
* **rps flattening while latency climbs** — you have found the knee.
* **A scenario with 100% 4xx** — an auth or permission problem, not a performance
  result. `status_counts` in the JSON tells you which.

### Known query problems this harness is designed to expose

`dbstat.py` prints `EXPLAIN (ANALYZE, BUFFERS)` for each of these:

* **Teacher-scoped student list** (`accounts/permissions.py`) joins
  `students → classes → class_schedules → teachers` with `DISTINCT`. With 40
  classes × 35 weekly periods there are 1,400 schedule rows, so the fan-out is
  real. Expect a hash join plus a `DISTINCT` sort; an external merge sort means
  `work_mem` is too small.
* **Attendance summary** — the existing index is `(student, date, status)`, so a
  predicate on `date` alone cannot use it. This is the highest-value index to
  add: `(date, status)`.
* **Student search** — `icontains` on `student_id` forces a sequential scan
  regardless of indexes. If that is a hot user path in production, `pg_trgm` is
  the fix.
* **Overdue fees** — already indexed on `(payment_status, due_date)`, so this
  one *should* be an index scan. If the plan disagrees, the predicate and the
  index do not match.

Also worth watching: `attendance/views.py` calls `Student.objects.get()` inside
the bulk-attendance loop, which is an N+1 — one query per submitted student.

## Caveats

* **The tunnel is for looking, not measuring.** Cloudflare quick tunnels are
  rate-limited and add latency. They exist so you can open the app from a phone.
* **Cold caches dominate the first minutes.** The warmup phase exists for this.
* **`idx_scan = 0` and the cache hit ratio are only meaningful after a run.** On
  a fresh seed every index is unscanned by definition. Run `dbstat.py` *after*
  the load test.
* **Log I/O is on.** `settings.py:368-389` logs at INFO to `logs/django.log`.
  That file I/O is part of the system under test and matches production, so it
  is deliberately left enabled.
* **Write scenarios mutate the seeded data.** That is intended — it keeps write
  volume realistic — but it means results are not reproducible from run to run
  without re-seeding.

## Troubleshooting

**Server exits immediately with `ImproperlyConfigured`.** `DEBUG=False` requires
`SECRET_KEY` (line 30), `DB_ENGINE=postgresql` (line 143) and a non-localhost
`ALLOWED_HOSTS` (line 33). The notebook sets all three; if you run a server by
hand you must too.

**`DisallowedHost` on every request.** The client is not sending the tunnel
hostname as its `Host` header. Use `--host-header` on `loadgen.py`.

**Seeding fails on a unique constraint.** The seeder was validated against the
models statically but never executed against a live database, because the
development machine had no Django install and no network access to PyPI. The
first Colab run is where the seeder is actually exercised. If it fails, the
`IntegrityError` names the table and values, which is enough to fix the generator.

**`page_login` / static files 500.** `collectstatic` must have run;
`STORAGES['staticfiles']` is `CompressedManifestStaticFilesStorage` in both debug
and non-debug mode, so a missing `staticfiles.json` breaks `{% static %}`.
