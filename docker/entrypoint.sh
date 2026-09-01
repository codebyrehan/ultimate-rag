#!/bin/bash
set -Eeuo pipefail

# Commands explicitly passed to the container remain supported for debugging
# and one-off jobs. The normal production path starts nginx + FastAPI.
case "${1:-}" in
    rq|celery|python|python3|pytest|alembic|tail|sleep)
        exec "$@"
        ;;
esac

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

export PORT="${PORT:-8000}"

echo "Running database migrations..."
python -m alembic upgrade head

echo "Starting application..."
uvicorn ultimate_rag.main:app --host 127.0.0.1 --port 8001 --workers "${WEB_CONCURRENCY:-2}" &
UVICORN_PID=$!

# Start nginx immediately so Render can detect the public port while the
# backend completes its application startup/readiness checks.
echo "Starting nginx on port ${PORT}..."
envsubst '${PORT}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf
nginx -g "daemon off;" &
NGINX_PID=$!

shutdown() {
  echo "Shutting down..."
  kill "$UVICORN_PID" "$NGINX_PID" 2>/dev/null || true
  wait "$UVICORN_PID" "$NGINX_PID" 2>/dev/null || true
}
trap shutdown SIGTERM SIGINT

# Give the backend time to become healthy. If it never does, terminate the
# deployment rather than leaving a frontend-only container running.
echo "Waiting for application health..."
healthy=0
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8001/health >/dev/null 2>&1; then
    healthy=1
    break
  fi
  if ! kill -0 "$UVICORN_PID" 2>/dev/null; then
    echo "Application exited before becoming healthy."
    wait "$UVICORN_PID" || true
    shutdown
    exit 1
  fi
  sleep 1
done

if [ "$healthy" -ne 1 ]; then
  echo "Application did not become healthy within 60 seconds."
  shutdown
  exit 1
fi

echo "Application and nginx are healthy."

# If either foreground service exits, terminate the container instead of
# leaving a half-working deployment alive.
wait -n "$UVICORN_PID" "$NGINX_PID"
status=$?
shutdown
exit "$status"
