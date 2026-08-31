# Deployment

## Quick Start (Docker Compose)

```bash
./start.sh        # Linux/macOS
.\start.ps1       # Windows
```

Or manually:

```bash
cp .env.example .env
docker compose up --build
```

## Default Ports

| Service  | Port  |
|----------|-------|
| Frontend | 3000  |
| API      | 8000  |
| PostgreSQL | 5432 |
| Redis    | 6379  |
| Ollama   | 11434 |

## Environment Variables

Key settings (see `.env.example` for full list):

```env
# Database
DATABASE_URL=postgresql+psycopg://rag_user:rag_pass@postgres:5432/ultimate_rag

# Embeddings
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

# LLM
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
LLM_MODEL=qwen3:4b

# Vector Store
VECTOR_STORE_PROVIDER=pgvector

# Worker
INLINE_WORKER=0  # Use RQ worker instead of inline processing
```

## Production Notes

- Set `SECRET_KEY` to a long random string
- Use PostgreSQL + pgvector for production-scale vector search
- Use Redis + RQ for background ingestion jobs
- Set `CACHE_ENABLED=true` and `CACHE_TTL_SECONDS=300` to cache embeddings
- Use Ollama locally for free LLM inference
- Configure appropriate rate limits
- Set `LOG_FORMAT=json` for structured logs
- JWT access tokens expire in 1 hour; refresh tokens last 24 hours. The `/auth/refresh` endpoint rotates refresh tokens on each use.
- Always terminate TLS at the load balancer; set `X-Forwarded-Proto: https` so the app emits HSTS headers.
- The API container runs as a non-root user for defense in depth.
