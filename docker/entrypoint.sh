#!/bin/bash
set -euo pipefail

export PORT="${PORT:-8000}"
export HOST="${HOST:-0.0.0.0}"

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

echo "Running database migrations..."
if ! python -m alembic upgrade head; then
    echo "ERROR: Database migrations failed" >&2
    exit 1
fi

echo "Starting FastAPI on ${HOST}:${PORT}..."
exec uvicorn ultimate_rag.main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --workers "${WEB_CONCURRENCY:-1}"
