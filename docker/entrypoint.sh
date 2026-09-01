#!/bin/bash
set -Eeuo pipefail

# Render and other PaaS platforms provide PORT at runtime. Run migrations once
# before starting the web process, then let Uvicorn bind directly to the public
# interface. This avoids a second reverse-proxy process and makes port
# ownership deterministic.
export PORT="${PORT:-8000}"

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

echo "Running database migrations..."
python -m alembic upgrade head

echo "Starting FastAPI on 0.0.0.0:${PORT}..."
exec uvicorn ultimate_rag.main:app \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --workers "${WEB_CONCURRENCY:-1}"
