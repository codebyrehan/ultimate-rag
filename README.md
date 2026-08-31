# Ultimate RAG Platform

A **modular, open-source-first, self-hostable** Advanced RAG and Document Intelligence platform.

Run locally for free using local models (Sentence Transformers + Ollama). No paid APIs required.

---

## Features

- **Multi-tenant architecture** with strict tenant isolation
- **JWT authentication** with PBKDF2-SHA256 password hashing
- **Document ingestion**: PDF extraction (PyMuPDF), OCR fallback, semantic chunking
- **Hybrid retrieval**: dense embeddings + BM25 → RRF fusion → cross-encoder reranking
- **Multi-query expansion**, query rewriting, and optional HyDE
- **Local LLM generation** via Ollama (streaming + non-streaming)
- **Grounded answers** with metadata-backed citations and confidence scoring
- **Claim verification** and faithfulness checking
- **Conversation memory** with full history persistence
- **Async job queue** with RQ (Redis) or inline mode
- **Rate limiting** with per-route sliding-window limits
- **Structured logging** with request IDs
- **Metrics endpoint** with latency histograms
- **React frontend** with chat, document management, and conversation history
- **Evaluation framework** with ablation study support
- **Docker Compose** for one-command local deployment

---

## Quick Start

### One-command local startup

```bash
# Linux/macOS
./start.sh

# Windows
.\start.ps1
```

Or with Docker directly:

```bash
docker compose up
```

### Development (no Docker)

```bash
# Backend
cd backend
pip install -e ".[dev]"
python -m uvicorn ultimate_rag.main:app --reload

# Frontend
cd ../frontend
npm install
npm run dev
```

---

## Architecture

```
                    User
                      │
                      ▼
                 React Frontend
                      │
                      ▼
                  FastAPI API
                      │
            ┌────────┴─────────┐
            │  Auth (JWT)      │
            │  Rate Limiting   │
            └────────┬─────────┘
                      ▼
                Query Service
                      │
            ┌────────┴─────────┐
            │  Query Rewrite    │
            │  Query Expansion  │
            │  HyDE (optional)  │
            └────────┬─────────┘
                      ▼
              ┌──────────────┐
              │ Dense + BM25 │
              │   RRF Fusion │
              └──────┬───────┘
                      ▼
                  Reranking
                      │
                      ▼
             Context Compression
                      │
                      ▼
           Grounded Generation
                      │
              ┌──────┴───────┐
              │ Claim Extract │
              │ Verify        │
              │ Confidence    │
              └──────────────┘
                      │
                      ▼
                 Final Response
```

---

## Configuration

All settings are environment-driven. Copy the example:

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./rag.db` | PostgreSQL or SQLite |
| `EMBEDDING_PROVIDER` | `local` | `local` or `openai` |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model |
| `LLM_PROVIDER` | `ollama` | `ollama`, `openai`, `hf`, or `stub` |
| `LLM_MODEL` | `qwen3:4b` | Ollama model name |
| `VECTOR_STORE_PROVIDER` | `in_memory` | `in_memory`, `pgvector`, or `qdrant` |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for job queue and cache |
| `INLINE_WORKER` | `1` | Run jobs inline (no Redis needed for dev) |
| `CACHE_ENABLED` | `true` | Enable tenant-scoped caching of embeddings and retrieval results |
| `CACHE_TTL_SECONDS` | `300` | Cache time-to-live in seconds |
| `SECRET_KEY` | (dev default) | Change in production! |
| `JWT_EXPIRE_SECONDS` | `3600` | Access token lifetime |
| `REFRESH_EXPIRE_SECONDS` | `86400` | Refresh token lifetime |

See [.env.example](.env.example) for the full list.

---

## Documentation

- [Architecture](docs/architecture.md)
- [RAG Pipeline](docs/rag-pipeline.md)
- [Security](docs/security.md)
- [Deployment](docs/deployment.md)
- [Performance](docs/performance.md)
- [Evaluation](docs/evaluation.md)

---

## Testing

```bash
cd backend
python -m pytest ultimate_rag/tests -q
```

Test coverage includes:

- Unit tests: auth, embeddings, chunking, BM25, fusion, query transform, verification, reranker, cache, ablation
- Integration tests: auth routes, chat routes, document routes, jobs routes, search routes, ingestion pipeline, rate limiting, query service, database, security headers
- Security tests: tenant isolation, IDOR, SQL injection, filename sanitization, duplicate detection, password validation

---

## Self-hosting

See [docs/deployment.md](docs/deployment.md) for detailed instructions.

The platform runs in two modes:

1. **Local development** (SQLite + in-memory vector store + stub providers)
2. **Production** (PostgreSQL + pgvector + Ollama + Redis/RQ)

---

## License

Apache-2.0
