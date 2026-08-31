#!/bin/bash
set -e

case "$1" in
    rq|celery|python|python3|pytest|alembic|tail|sleep)
        exec "$@"
        ;;
esac

if [ $# -gt 0 ]; then
    exec "$@"
fi

echo "Starting nginx..."
export PORT=${PORT:-8000}
envsubst '${PORT}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf
nginx -g "daemon off;" &
NGINX_PID=$!

echo "Running database migrations..."
python -m alembic upgrade head || echo "Migrations failed or not configured"

echo "Starting application..."
uvicorn ultimate_rag.main:app --host 127.0.0.1 --port 8001 --workers 2 &
UVICORN_PID=$!

shutdown() {
  echo "Shutting down..."
  kill "$UVICORN_PID" "$NGINX_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap shutdown SIGTERM SIGINT

wait "$UVICORN_PID"
shutdown
