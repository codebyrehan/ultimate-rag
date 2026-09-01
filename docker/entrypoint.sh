#!/bin/sh
set -eu

export PORT="${PORT:-8000}"
export HOST="${HOST:-0.0.0.0}"

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

echo "Running database migrations..."
python -m alembic upgrade head || echo "WARNING: migrations failed or already applied"

echo "Starting FastAPI on ${HOST}:${PORT}..."
exec python -m uvicorn ultimate_rag.main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --workers "${WEB_CONCURRENCY:-1}"
