#!/bin/bash
set -Eeuo pipefail

# Commands explicitly passed to the container remain supported for debugging
# and one-off jobs. The normal production path below starts nginx + FastAPI.
case "${1:-}" in
    rq|celery|python|python3|pytest|alembic|tail|sleep)
        exec "$@"
        ;;
esac

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

export PORT="${PORT:-8000}"

# Render/Nginx must not advertise a healthy frontend while the backend has
# failed migrations. Run migrations first and fail the container if they fail.
echo "Running database migrations..."
python -m alembic upgrade head

echo "Starting application..."
uvicorn ultimate_rag.main:app --host 127.0.0.1 --port 8001 --workers "${WEB_CONCURRENCY:-2}" &
UVICORN_PID=$!

# Wait until the backend is actually accepting connections before starting
# nginx. This prevents nginx from masking an application startup failure.
echo "Waiting for application health..."
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8001/health >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$UVICORN_PID" 2>/dev/null; then
    echo "Application exited before becoming healthy."
    wait "$UVICORN_PID" || true
    exit 1
  fi
  sleep 1
done

if ! curl -fsS http://127.0.0.1:8001/health >/dev/null 2>&1; then
  echo "Application did not become healthy within 60 seconds."
  kill "$UVICORN_PID" 2>/dev/null || true
  wait "$UVICORN_PID" || true
  exit 1
fi

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

# If either foreground service exits, terminate the container instead of
# leaving a half-working deployment alive.
wait -n "$UVICORN_PID" "$NGINX_PID"
status=$?
shutdown
exit "$status"
