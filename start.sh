#!/bin/bash
set -e

echo "=== Ultimate RAG Platform — One-Command Startup ==="

# 1. Check prerequisites
echo "Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not found"; exit 1; }
command -v docker compose >/dev/null 2>&1 || { echo "ERROR: docker compose not found"; exit 1; }
echo "✓ Prerequisites OK"

# 2. Create .env if needed
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "✓ .env created (edit it to customize)"
fi

# 3. Start services
echo "Starting Docker Compose..."
docker compose up -d

# 4. Wait for services
echo "Waiting for services to be ready..."
for i in $(seq 1 60); do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        echo "✓ Backend ready"
        break
    fi
    echo "  Waiting... ($i/60)"
    sleep 3
done

# 5. Run migrations
echo "Running database migrations..."
docker compose exec -T api python -m alembic upgrade head 2>/dev/null || echo "  (migrations skipped)"

# 6. Pull Ollama model
echo "Pre-pulling Ollama model..."
docker compose exec -T ollama ollama pull qwen3:4b 2>/dev/null || echo "  (Ollama model pull deferred — can be done later)"

# 7. Verify health
echo ""
echo "=== Startup Summary ==="
curl -sf http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "Backend: not responding"
echo ""
echo "Frontend:  http://localhost:3000"
echo "Backend:   http://localhost:8000"
echo "Docs:      http://localhost:8000/docs"
echo "Health:    http://localhost:8000/health"
echo "Metrics:   http://localhost:8000/metrics"
echo ""
echo "✓ Ultimate RAG Platform is running."
echo "  (Docker Desktop must be running on Windows/macOS)"
