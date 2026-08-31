# Architecture — Ultimate RAG Platform

## 0. Phase 0 — Design

### 0.1 Requirements analysis

The platform must deliver a **modular, open-source-first, locally-runnable** document-intelligence + RAG system with:

- Multi-user / multi-tenant document isolation
- Robust ingestion (PDF text + OCR + tables + semantic chunking + parent/child)
- Pluggable local embeddings (Sentence Transformers / BGE) and vector stores
- Hybrid dense + BM25 retrieval with Reciprocal Rank Fusion
- Query understanding, rewriting, expansion, optional HyDE
- Cross-encoder reranking + context compression
- LLM generation via Ollama (default) with optional OpenAI-compatible / local-HF providers, streaming
- Grounded generation with citations, claim extraction, faithfulness & citation verification, confidence estimation
- Async background processing (job queue)
- AuthN (JWT) + AuthZ (tenant isolation) + rate limiting
- Observability (request IDs, structured logging, latency metrics)
- Evaluation framework + sample dataset
- Full test suite (unit / integration / retrieval / e2e)
- Docker + local-dev + cloud deployment (Render / HuggingFace Spaces)

### 0.2 Technology choices & alternatives

| Capability | Primary (production) | Local-test fallback | Rationale |
|---|---|---|---|
| API | FastAPI | — | Async, auto OpenAPI, DI, typed |
| DB | PostgreSQL + pgvector | SQLite (in-memory when possible) | Postgres scales; SQLite lets tests run with **zero external services**. Models written generically over SQLAlchemy so the dialect swaps transparently. |
| Vector store | Qdrant | In-memory numpy store | Qdrant is purpose-built; the in-memory store performs **real** cosine/dot search (no fake stubs) so retrieval is genuinely testable offline. |
| Embeddings | Sentence Transformers (BGE) | same | Local, no paid API. BGE-M3 preferred when RAM allows; BGE-small otherwise. |
| Reranker | cross-encoder (BGE-reranker) | — | Local, MS-MARCO compatible. Made optional/configurable. |
| BM25 | In-store (Qdrant sparse) or sklearn TfidfVectorizer fallback | sklearn BM25 implementation | Keyword retrieval must be independent of the vector store when possible; sklearn-backed BM25 guarantees a working path everywhere. |
| LLM | Ollama | HuggingFace transformers (small local model) + test-only provider | Ollama is the documented default. A real HF-provider exists for local inference; a clearly-test-only provider is used only inside tests to keep the suite fast/deterministic. |
| OCR | Tesseract (pytesseract) | pytesseract (binary optional) | Real OCR when Tesseract binary present; graceful degraded path otherwise. |
| Queue | Redis + RQ | In-process queue (threaded) | RQ is simpler than Celery and reliable. In-process executor lets the full pipeline run with **no external services** for tests/dev. |
| Auth | JWT + passlib bcrypt | — | Industry-standard. Refresh tokens optional. |
| Frontend | Next.js (React) | Streamlit (admin/dev quickview) | Next.js is the production UI; Streamlit is a bonus dev surface. |

### 0.3 Environment constraints (discovered)

- **No Docker, PostgreSQL, Redis, Ollama, or Tesseract binary** in this dev sandbox.
- Available: Python 3.14, Node 24, torch 2.13 CPU, sentence-transformers, scikit-learn, pymupdf/pypdf/pdfplumber, fastapi/sqlalchemy/alembic/uvicorn, qdrant-client, redis/rq, transformers 5.16, HuggingFace model download (BGE-small verified).
- ~16 GB RAM total, ~4.7 GB free.

**Design consequence**: every external dependency is behind a *provider interface* with a genuine in-process fallback, so the system is **runnable and testable in this sandbox** while remaining production-deployable to Docker/Render/HF Spaces. No "fake" implementations: fallbacks perform real computation (numpy search, real TF-IDF/BM25, real local model inference where feasible).

### 0.4 Key architectural decisions

1. **Provider interfaces (Strategy + Factory).** `EmbeddingProvider`, `VectorStore`, `LLMProvider`, `OCRProvider`, `Chunker`, `Reranker`, `FileStorage`. Resolution is configuration-driven (`settings.*_PROVIDER`), so swapping a provider never touches business logic.

2. **Service container + DI.** A single `ServiceContainer` wires concrete providers from a `ProviderFactory`. FastAPI routes receive services via `Depends`. Tests inject fakes/mocks at the container level.

3. **Async-first.** API layer is async (FastAPI). Ingestion and retrieval are CPU/IO-bound; heavy work is offloaded to workers, but an in-process executor mirrors the same task graph so the pipeline is identical in dev and prod.

4. **Tenant isolation everywhere.** `tenant_id`/`owner_id` are mandatory params on *every* repository, vector-store, and BM25 operation. The API layer derives them from the JWT and the DB models enforce FK constraints (production) / app-layer checks (SQLite fallback). There is no code path that can retrieve another tenant's data.

5. **Security by construction.**
   - Filenames sanitized; uploads stored by generated ULID, never user-supplied paths (no path traversal).
   - File-size + magic-byte validation; PDF-only ingestion gate.
   - Documents treated as **untrusted**: prompt templates wrap retrieved content in explicit delimiters and carry a hardened system message that outranks document text. No document content is ever interpolated into system instructions.
   - Parameterized SQL (SQLAlchemy 2.0 style) — no string-built queries.
   - Secrets never logged; request IDs propagated through async tasks.

6. **Idempotent ingestion.** SHA-256 dedup at the document level; re-uploading the same file/content is a no-op or re-index that replaces vectors atomically. Failed jobs leave the index untouched (processing status tracked, not the document index).

7. **Chunking.** Semantic chunking on heading/paragraph boundaries with overlap, producing parent + child chunks. Child chunks carry `parent_id` for parent-child retrieval. Metadata preserves doc id, tenant, page, section, chunk type.

8. **Hybrid retrieval = dense + BM25 → RRF → dedup → rerank → compress → generate → verify.** Each stage is a pure function on a shared `RetrievalContext` object, making it testable in isolation and composable.

9. **Claims > citations > verification > confidence.** Generation emits claims; each claim is matched to retrieved evidence; an NLI-style (local cross-encoder OR token-overlap fallback) support check scores faithfulness; a multi-signal aggregator yields HIGH/MEDIUM/LOW confidence.

10. **Observability.** Structlog-style JSON logs with request_id, tenant_id, doc_id, latencies per stage. Metrics counters are exposed on `/health` and `/metrics` (in-process). No external telemetry dependency required.

### 0.5 Final folder structure

```
ultimate-rag/
├─ backend/
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ main.py                    # FastAPI app factory
│  │  ├─ api/
│  │  │  ├─ routes/{auth,docs,chat,search,jobs,health}.py
│  │  │  └─ deps.py                # FastAPI dependency providers
│  │  ├─ core/
│  │  │  ├─ config.py              # Pydantic-settings (all env-driven)
│  │  │  ├─ security.py            # password hashing, token utils
│  │  │  ├─ errors.py              # exception hierarchy
│  │  │  ├─ logging.py
│  │  │  ├─ ids.py                 # ULID generation
│  │  │  └─ rate_limit.py          # token-bucket rate limiter
│  │  ├─ db/
│  │  │  ├─ connection.py          # async engine + sync session
│  │  │  ├─ models.py              # SQLAlchemy ORM (tenant-scoped)
│  │  │  └─ repositories/           # {users,tenants,documents,chunks,conversations,queries,jobs,evidence}
│  │  ├─ auth/
│  │  │  ├─ password.py
│  │  │  ├─ jwt.py
│  │  │  └─ middleware.py          # tenant/jwt enforcement
│  │  ├─ storage/                  # file storage abstraction (local/s3)
│  │  ├─ ingestion/
│  │  │  ├─ pipeline.py            # orchestrator (async jobs)
│  │  │  ├─ validator.py           # size/magic-byte/PDF checks
│  │  │  ├─ extractor.py          # PyMuPDF text + table extraction
│  │  │  ├─ ocr.py                # pytesseract OCR fallback
│  │  │  ├─ chunker.py            # semantic + parent/child chunking
│  │  │  └─ embeddings_batch.py
│  │  ├─ embeddings/
│  │  │  ├─ interface.py
│  │  │  └─ providers/{sentence_transformers,openai,stub}.py
│  │  ├─ vecstore/
│  │  │  ├─ interface.py
│  │  │  └─ providers/{qdrant,in_memory}.py
│  │  ├─ retrieval/
│  │  │  ├── pipeline.py          # staged retriever orchestration
│  │  │  ├── router.py            # query classification
│  │  │  ├── rewrite.py           # query rewriting
│  │  │  ├── expand.py            # multi-query generation
│  │  │  ├── hyde.py
│  │  │  ├── fusion.py            # RRF
│  │  │  ├── dedup.py
│  │  │  ├── reranker.py
│  │  │  ├── compression.py
│  │  │  └── bm25.py              # keyword retriever (sklearn)
│  │  ├─ generation/
│  │  │  ├─ provider.py
│  │  │  ├─ providers/{ollama,hf_transformers,stub}.py
│  │  │  ├─ templates.py          # hardened prompt templates
│  │  │  └─ security.py           # injection guards
│  │  ├─ verification/
│  │  │  ├─ claims.py            # claim extraction
│  │  │  ├─ citation.py          # claim→evidence matching
│  │  │  ├─ faithfulness.py
│  │  │  ├── relevance.py
│  │  │  └── confidence.py
│  │  ├─ services/            # ServiceContainer + ProviderFactory
│  │  ├─ workers/             # RQ + in-process executor
│  │  ├─ evaluation/          # dataset, metrics, runner
│  │  └─ tests/ ...
│  ├─ alembic/ + versions/
│  ├─ Dockerfile
│  └─ requirements.txt
├─ frontend/                  # Next.js app
├─ evaluation/                # datasets + sample docs + results
├─ scripts/                   # setup/migration/dev helpers
├─ docker/                    # compose, render.yaml, init scripts
├─ .env.example
├─ pyproject.toml
└─ README.md
```

### 0.6 Implementation roadmap (phases)

Phases 1→22 follow the build prompt's sequence with internal phase gates (write → explain → test → fix → check imports/config/integration → report → advance). A summary of each:

1. **Repo + config**: pyproject, .env.example, package setup, logging scaffold.
2. **DB**: models (tenant-scoped), async/sync sessions, Alembic, SQLite fallback, repositories.
3. **Ingestion**: validator, extractor (PyMuPDF text+tables), OCR fallback, chunker (semantic+parent/child), hashing/dedup, status tracking.
4. **Embeddings**: interface + Sentence Transformers (BGE) + OpenAI-compat + test stub.
5. **Vector store**: interface + Qdrant + real in-memory numpy store.
6. **BM25**: sklearn-backed, tenant-scoped.
7. **Hybrid RRF**: fusion + dedup.
8. **Reranker**: cross-encoder interface + BGE reranker.
9. **(chunking completed in 3)**
10. **Query understanding**: router, rewrite, expand, HyDE.
11. **Generation**: Ollama + HF-transformers providers, streaming via SSE.
12. **Prompt security**: hardened templates, injection defenses, groundedness.
13. **Citations**: page/section metadata, clickable mapping, verification.
14. **Verification**: claims, faithfulness, relevance, confidence aggregation.
15. **Async workers**: RQ + in-process executor, job model, status API.
16. **Auth**: JWT, bcrypt, tenant middleware, rate limiting.
17. **API routes**: auth/docs/chat/search/jobs/health + OpenAPI schemas.
18. **Frontend**: Next.js dashboard, document manager, chat with citations/sources/streaming.
19. **Evaluation**: dataset format, metrics (Recall@K, MRR, nDCG, faithfulness, citation P/R), runner.
20. **Tests**: unit/integration/retrieval/e2e covering all acceptance items.
21. **Docker + deployment**: compose, Render, HF Spaces, Windows/local setup.
22. **README + audit**: docs, security review, performance review.

### 0.7 Phase acceptance criteria (Phase 0)

- [x] Requirements analyzed
- [x] Final architecture designed
- [x] Technology choices justified (incl. test fallbacks)
- [x] Bottlenecks identified (model load latency, vector search dim)
- [x] Security risks enumerated (path traversal, injection, tenant isolation, secrets, unsafe deserialization)
- [x] Free/OSS constraints satisfied (no paid API by default)
- [x] Final folder structure produced
- [x] Implementation roadmap + phase acceptance criteria defined
- [ ] (handoff) Proceed to Phase 1 on instruction

### 0.8 Security risk register (preview)

| Risk | Mitigation |
|---|---|
| Path traversal in uploads | Store by ULID; sanitize filename; reject `..`, absolute paths, null bytes |
| Malicious PDFs / zip bombs | Size cap, magic-byte check, PyMuPDF page limit, resource timeout |
| Prompt injection from docs | Hardened system prompt; document text only in `<retrieved>` delimiters; never interpolated into system msg |
| Fake/missing citations | Citations derived only from trusted retrieval metadata; LLM cannot invent page/doc ids |
| SQL injection | SQLAlchemy 2.0 core/ORM, parameterized, no string concatenation |
| Tenant isolation bypass | tenant_id on every query + FK; middleware asserts ownership |
| Insecure CORS | Explicit allowlist from settings |
| Exposed secrets | .env not committed; logging redacts keys/tokens; errors scrubbed |
| Unsafe deserialization | No pickle for untrusted data; only structured formats |
