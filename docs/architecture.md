# Architecture

## Overview

The Ultimate RAG Platform is a modular, multi-tenant document intelligence system built on FastAPI.

## Layers

### 1. API Layer (`api/`)
- **Routes**: auth, documents, chat, search, conversations, jobs, health
- **Dependencies**: tenant-scoped sessions, JWT-protected `CurrentUser`
- **Models**: Pydantic schemas for request/response validation

### 2. Core (`core/`)
- `config.py`: Pydantic-settings based configuration (all env-driven)
- `errors.py`: Custom `RAGError` exception + structured error handlers
- `rate_limit.py`: Sliding-window per-route rate limiting
- `metrics.py`: In-process counters, gauges, latency histograms
- `security.py`: Filename sanitization, password constants, SHA-256
- `logging.py`: Structured JSON logging with request IDs

### 3. Database (`db/`)
- **Models**: SQLAlchemy 2.0 ORM (Tenant → User → Document → Chunk → Conversation → Message → Query → Evidence)
- **Repositories**: Tenant-scoped data access (tenant_id mandatory)
- **Alembic**: Migrations for schema evolution
- **Connection**: Async engine with SQLite/PostgreSQL support

### 4. Retrieval (`retrieval/`)
- `pipeline.py`: Orchestrates the full retrieval pipeline
- `dense.py`: Dense retrieval via embedding provider + vector store
- `bm25.py`: From-scratch Okapi BM25 (sklearn TF-IDF based)
- `fusion.py`: Weighted RRF fusion
- `reranker.py`: Cross-encoder or stub reranker
- `dedup.py`: Chunk deduplication
- `compression.py`: Context compression for final top-K
- `types.py`: Retrieval context dataclass
- `query_transform/`: Query rewriting, expansion, multi-query, HyDE

### 5. Ingestion (`ingestion/`)
- `pipeline.py`: Validate → extract → OCR → chunk → embed → index → persist
- `extractor.py`: PDF text + table extraction (PyMuPDF)
- `ocr.py`: Tesseract or NoOp fallback
- `chunker.py`: Semantic chunking with parent/child structure
- `validator.py`: SHA-256, MIME type, file size validation
- `embeddings_batch.py`: Batch embedding with bounded concurrency

### 6. Generation (`generation/`)
- `interface.py`: LLM provider ABC, Answer, Citation dataclasses
- `answer_builder.py`: Prompt construction, grounded generation
- `query_service.py`: End-to-end orchestration (retrieve → generate → verify)
- **Providers**: Ollama, OpenAI, HuggingFace, Stub

### 7. Embeddings (`embeddings/`)
- `interface.py`: EmbeddingProvider ABC
- **Providers**: sentence_transformers (BGE-small), OpenAI-compatible, Stub

### 8. Vector Store (`vecstore/`)
- `interface.py`: VectorStore ABC (tenant-scoped)
- **Providers**: InMemory (numpy), Qdrant, PgVector

### 9. Verification (`verification/`)
- `guard.py`: Claim extraction, faithfulness check (Jaccard), confidence scoring

### 10. Storage (`storage/`)
- `interface.py`: Storage ABC
- **Providers**: LocalStorage, S3

### 11. Jobs (`jobs/`)
- `runner.py`: Inline and RQ-backed job dispatch
- `queue_runner.py`: RQ worker integration
- `worker.py`: RQ worker entry point for ingestion

### 12. Services (`services/`)
- `container.py`: Lazy, cached provider container (dependency injection)
- `factory.py`: Provider factory functions

### 13. Frontend (`frontend/`)
- React + Vite + TypeScript + Tailwind CSS
- Pages: Login, Register, Dashboard, Chat, Conversations, Documents, Settings

## Multi-tenancy

```
Tenant
  ├── User (JWT contains tenant_id)
  ├── Document (tenant_id scope)
  ├── Chunk (tenant_id scope)
  ├── Conversation (tenant_id scope)
  ├── Message (tenant_id scope)
  ├── Query (tenant_id scope)
  └── Evidence (via Query)
```

Every repository method enforces `tenant_id`. Every route extracts `tenant_id` from the JWT.

## Deployment modes

### Development (default)
- SQLite in-memory
- In-memory vector store
- Stub embedding provider
- Stub LLM provider

### Local (no Docker)
- SQLite file
- In-memory vector store
- BGE-small embeddings (CPU)
- Ollama LLM

### Production (Docker Compose)
- PostgreSQL + pgvector
- Redis (RQ worker)
- Ollama
- Qdrant (optional vector store alternative)
