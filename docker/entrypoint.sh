#!/bin/bash
set -e

echo "Running database migrations..."
python -m alembic upgrade head || echo "Migrations failed or not configured"

echo "Starting application..."
exec "$@"
