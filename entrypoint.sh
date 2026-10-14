#!/usr/bin/env sh
# Production entrypoint for the ADOM Institute app container.
# 1. Waits for PostgreSQL and Redis when they are configured.
# 2. Collects static files (no-op safe, works with local or object storage).
# 3. Executes the container command (gunicorn, daphne, celery, ...).
set -e

echo "[entrypoint] starting ($$)"

DB_ENGINE="${DB_ENGINE:-sqlite}"
DB_HOST="${DB_HOST:-}"
DB_PORT="${DB_PORT:-5432}"
REDIS_HOSTS="${REDIS_HOSTS:-}"

wait_for_port() {
  host="$1"
  port="$2"
  service="$3"
  timeout="${WAIT_TIMEOUT:-120}"
  i=0
  while ! python -c "import socket,sys; s=socket.socket(); s.settimeout(2); s.connect((sys.argv[1], int(sys.argv[2])))" "$host" "$port" 2>/dev/null; do
    i=$((i + 1))
    if [ "$i" -ge "$timeout" ]; then
      echo "[entrypoint] ERROR: $service not reachable at $host:$port after ${timeout}s"
      exit 1
    fi
    sleep 1
  done
  echo "[entrypoint] $service reachable at $host:$port"
}

if [ "$DB_ENGINE" = "postgresql" ]; then
  [ -n "$DB_HOST" ] && wait_for_port "$DB_HOST" "$DB_PORT" "postgresql"
fi

# Wait for Redis when we are pointed at one (web/ws/worker need the channel
# layer / broker). Falls back immediately when no redis host is configured.
if [ -n "$REDIS_HOSTS" ] && [ "$REDIS_HOSTS" != "0" ]; then
  for rh in $(echo "$REDIS_HOSTS" | tr ',' ' '); do
    rhost=$(echo "$rh" | cut -d: -f1)
    rport=$(echo "$rh" | cut -d: -f2)
    [ -z "$rport" ] && rport=6379
    wait_for_port "$rhost" "$rport" "redis"
  done
fi

echo "[entrypoint] collecting static files"
python manage.py collectstatic --noinput --verbosity 0

# Apply database migrations. Railway/containers do not run them automatically,
# so a deploy with new migrations would otherwise serve 500s against the old
# schema. Idempotent, so it is safe to run on every start. Set
# RUN_MIGRATIONS=0 to skip (e.g. on extra worker/beat services).
if [ "${RUN_MIGRATIONS:-1}" != "0" ]; then
  echo "[entrypoint] applying database migrations"
  python manage.py migrate --noinput --verbosity 1
fi

exec "$@"
