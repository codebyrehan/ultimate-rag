# Final Audit — Before Changes

**Date**: 2026-08-30
**Repository**: Ultimate RAG Platform
**Method**: Full code inspection + test execution + static analysis (ruff, mypy, pytest)

---

## Executive Summary

The engineering report claims "102 tests passed" with an 8/10 score. I verified:

- **102 tests pass** — VERIFIED (ran `python -m pytest ultimate_rag/tests -q` from `backend/`, result: `102 passed, 1 warning in 15.95s`)
- **50 mypy errors** in 18 files — NOT mentioned in the report
- **ruff: all checks pass, formatting clean** — VERIFIED
- Several features described in `ARCHITECTURE.md` and `docs/` do NOT exist in the actual code

---

## 1. Tests — Status: VERIFIED (102 passed)

### Test inventory (actual):

| File | Tests | Type |
|------|-------|------|
| `tests/unit/test_answer_builder.py` | 6 | unit |
| `tests/unit/test_auth_session.py` | 5 | unit |
| `tests/unit/test_bm25.py` | 4 | unit |
| `tests/unit/test_chunker.py` | 3 | unit |
| `tests/unit/test_embeddings.py` | 4 | unit (1 downloads BGE-small) |
| `tests/unit/test_fusion.py` | 4 | unit |
| `tests/unit/test_query_transform.py` | 13 | unit |
| `tests/unit/test_retrieval.py` | 9 | unit |
| `tests/unit/test_vecstore.py` | 4 | unit |
| `tests/unit/test_verification.py` | 7 | unit |
| `tests/integration/test_auth_route.py` | 5 | integration |
| `tests/integration/test_chat_route.py` | 2 | integration |
| `tests/integration/test_database.py` | 5 | integration |
| `tests/integration/test_docs_route.py` | 4 | integration |
| `tests/integration/test_ingestion.py` | 4 | integration |
| `tests/integration/test_jobs_route.py` | 3 | integration |
| `tests/integration/test_query_service.py` | 1 | integration |
| `tests/integration/test_rate_limit.py` | 5 | integration |
| `tests/integration/test_retrieval_pipeline.py` | 1 | integration |
| `tests/integration/test_search_route.py` | 2 | integration |
| `tests/integration/test_security.py` | 10 | integration |
| **Total** | **102** | |

### What's missing:
- No e2e tests directory exists
- No browser/Playwright tests
- No negative/abstention tests (unanswerable questions)
- No prompt injection defense tests on document content
- No NLI-based verification tests (only Jaccard tests)

---

## 2. Architecture — Discrepancies Found

### Claim: "Query understanding via router"
- **Claimed**: `retrieval/router.py` exists for query classification
- **Actual**: No `router.py` in `retrieval/`. Only `query_transform/transformer.py`
- **Status**: NOT VERIFIED

### Claim: "Auth middleware: tenant/jwt enforcement"
- **Claimed**: `auth/password.py`, `auth/jwt.py`, `auth/middleware.py` exist
- **Actual**: Only `auth/session.py` (hashing + JWT) and `auth/dependencies.py` (FastAPI dependency) exist
- **Status**: NOT VERIFIED

### Claim: "Prompt templates + security"
- **Claimed**: `generation/templates.py`, `generation/security.py` exist
- **Actual**: No `templates.py` or `security.py` in `generation/`. The system prompt is a hardcoded constant `DEFAULT_SYSTEM_PROMPT` in `answer_builder.py`
- **Status**: NOT VERIFIED

### Claim: "Verification: claims, citation, faithfulness, relevance, confidence"
- **Claimed**: `verification/claims.py`, `verification/citation.py`, `verification/faithfulness.py`, `verification/relevance.py`, `verification/confidence.py`
- **Actual**: Only `verification/guard.py` exists, which combines all of the above into a single class. No separate modules.
- **Status**: NOT VERIFIED

### Claim: "Streamlit admin/dev quickview"
- **Claimed**: Streamlit frontend exists
- **Actual**: No Streamlit code. Only React/Vite frontend
- **Status**: NOT VERIFIED

### Claim: "Next.js frontend"
- **Claimed**: Next.js app in `frontend/`
- **Actual**: React + Vite + TypeScript + Tailwind (not Next.js)
- **Status**: NOT VERIFIED

### Claim: `embeddings/base.py`
- **Claimed**: Import in `pipeline.py:26`: `from ultimate_rag.embeddings.base import EmbeddingProvider`
- **Actual**: No `embeddings/base.py` exists. The interface is in `embeddings/interface.py`. This is a TYPE_CHECKING import so it doesn't fail at runtime, but it's incorrect.
- **Status**: NOT VERIFIED — BUG (latent import error under TYPE_CHECKING)

---

## 3. Faithfulness / Verification — Status: NEEDS UPGRADE

### Claim: "NLI-style (local cross-encoder OR token-overlap fallback) support check"
- **Actual**: `FaithfulnessChecker` in `guard.py:79-124` uses **only Jaccard token-overlap similarity**. The docstring says "a real deployment would swap in an NLI model here."
- The `nli_similarity_threshold` setting defaults to 0.65 but is used as `threshold` for Jaccard in `VerificationGuard.__init__` (line 202): `self.faithfulness = FaithfulnessChecker(threshold=getattr(settings, "nli_similarity_threshold", 0.3))`
- **No NLI model, no cross-encoder entailment, no contradiction detection**
- The `FaithfulnessResult.contradicted` field is always `False`
- **Status**: NOT VERIFIED — CRITICAL GAP

### Claim: "SUPPORTED / CONTRADICTED / UNKNOWN structured output"
- **Actual**: Returns `supported: bool` only. No ternary status. No contradiction detection.
- **Status**: NOT VERIFIED — CRITICAL GAP

---

## 4. Ollama Streaming — Status: BROKEN

### Claim: "True streaming via Ollama's streaming API"
- **Actual**: `OllamaProvider` in `generation/providers/ollama.py` does NOT implement `stream()`. It only implements `generate()` with `"stream": False` in the Ollama API payload.
- The `LLMProvider.stream()` default implementation (interface.py:77-90) calls `self.generate()` and emits the entire response as a single chunk.
- The `StubProvider.stream()` (stub.py:63-68) splits response into words, but this is still non-streaming generation split post-hoc.
- **Status**: NOT VERIFIED — CRITICAL BUG

### Claim: "SSE streaming with event protocol"
- **Actual**: `/chat/stream` returns `application/x-ndjson`, not SSE. The frontend uses `responseType: 'stream'` in axios but processes as NDJSON lines.
- **Status**: NOT VERIFIED (uses NDJSON, not SSE)

---

## 5. PDF Citation Navigation — Status: NOT IMPLEMENTED

### Claim: "PDF.js / react-pdf viewer with page navigation"
- **Actual**: `frontend/src/pages/DocumentDetail.tsx` only shows metadata (status, page count, chunks). No PDF viewer. Citations in chat show text like `[1] handbook.pdf — Page 2` but clicking does nothing.
- No backend endpoint for authenticated PDF serving.
- **Status**: NOT VERIFIED — GAP

---

## 6. Redis Cache — Status: NOT IMPLEMENTED

### Claim: "Tenant-safe cache for query/embedding results"
- **Actual**: No Redis cache layer. `redis_url` is configured but only used for the RQ job queue (when `INLINE_WORKER=0`). No caching of queries, embeddings, or retrieval results.
- **Status**: NOT VERIFIED — GAP

---

## 7. Document Versioning — Status: NOT IMPLEMENTED

### Claim: "Document logical ID, version ID, version number, hash, upload time, active version"
- **Actual**: No versioning fields in `Document` model. SHA-256 dedup globally prevents re-upload of same content, but no version history.
- **Status**: NOT VERIFIED — GAP

---

## 8. Multi-Document Reasoning — Status: NOT IMPLEMENTED

### Claim: "Compare documents, find contradictions, summarize common requirements"
- **Actual**: Retrieval searches across all chunks for a tenant. No document-aware filtering, no comparison features in the API or frontend. Citations include `doc_filename` but no multi-doc comparison logic.
- **Status**: NOT VERIFIED — GAP

---

## 9. Adaptive Query Transformation — Status: NOT IMPLEMENTED

### Claim: "Simple query shouldn't trigger HyDE, multi-query, or LLM calls"
- **Actual**: `QueryTransformer` always runs the rewriter (deterministic, cheap). Expansion, multi-query, and HyDE are settings-driven (all disabled by default). There's no **adaptive** logic — it's a simple on/off per feature, not based on query complexity.
- All transformations are deterministic (no LLM calls), but there's no adaptive routing.
- **Status**: PARTIALLY VERIFIED — no adaptive behavior

---

## 10. Rate Limiting — Status: IN-PROCESS ONLY

### Claim: "Process-local or Redis-backed"
- **Actual**: Only `_InMemoryStore` exists (process-local). The `RateLimitStore` Protocol is defined but no Redis implementation. The report mentions "For multi-process scaling, swap in a Redis-backed store" but this swap was never implemented.
- **Status**: NOT VERIFIED (no Redis backend)

### Bug: Rate limit key mapping
- `_route_key()` in `rate_limit.py:108-120` maps both `/documents` and `/jobs` to the "query" bucket (same as `/search/query` and `/chat`). Upload has its own "upload" bucket, but listing documents and jobs share the query rate limit.

---

## 11. Database — Issues Found

### Alembic migration
- `alembic.ini` has `script_location = alembic` but the alembic directory is at `backend/alembic/`. The `prepend_sys.path = backend` entry helps when running from the root, but the Dockerfile runs from `/app` (WORKDIR), so `backend/` won't be on the path.
- **Risk**: Migrations may fail in Docker.
- **Status**: RISK

### Missing indexes
- `Query` table has no unique constraint on `id` (PK handles this)
- `Evidence` table has no tenant_id column — evidence is linked via query_id but query_id doesn't include tenant in the model. The `_persist_evidence` method doesn't filter by tenant.
- **Status**: RISK — Evidence records are not tenant-scoped

### Transactions
- `DocumentRepository.update()` uses `execution_options(synchronize_session="fetch")` — this can be slow on large datasets
- **Status**: MINOR

---

## 12. Security — Issues Found

### JWT validation
- `decode_access_token` correctly decodes and validates expiration
- BUT: `extract_token` (dependencies.py:18-27) does not validate token format before passing to `decode_access_token`. A malformed token will raise `TokenError` which is caught, but the error handling is correct.
- JWT does not include `nbf` (not-before) claim
- **Status**: OK (minor: no nbf claim)

### Password policy
- Minimum 8 characters, no complexity requirements
- **Status**: MINOR — could require more complexity

### Missing security:
- No CSRF protection (JWT bearer tokens in header, so CSRF risk is low)
- No security headers (CSP, X-Frame-Options, X-Content-Type-Options)
- No HSTS
- **Status**: GAP

### Prompt injection defense
- System prompt instructs the LLM to use only context passages, but there's no explicit delimiter wrapping or injection-resistant prompt structure
- The test `test_prompt_security_document_content_isolation` only checks that system prompt is preserved — it doesn't test if the model would actually follow injected instructions
- **Status**: PARTIALLY VERIFIED

### Path traversal
- `sanitize_filename` in `security.py:12-18` strips directory components via `Path.name` and restricts charset
- `LocalFileStorage._path_for` calls `sanitize_filename` and validates `relative_to`
- **Status**: VERIFIED

### File upload
- Magic byte check for `%PDF-` — VERIFIED
- Size limit — VERIFIED
- MIME type whitelist — VERIFIED (but `file.content_type` is client-supplied and can be spoofed)
- **Status**: VERIFIED (with caveat: MIME type from client is spoofable, but magic bytes are checked)

---

## 13. Citation Reliability — Issues Found

### Claim: "Citations point back to source chunks; LLM cannot invent"
- **Verified**: Citations are constructed from `RetrievedChunk` metadata in `AnswerBuilder._citation()` (answer_builder.py:125-133). The LLM only receives text passages; chunk_id, page_number, doc_filename come from the backend.
- **NOT VERIFIED**: No tests prove the LLM cannot fabricate citation metadata. All existing tests check structure, not fabrication resistance.
- **Status**: PARTIALLY VERIFIED

### Missing:
- No citation precision/recall/coverage metrics
- No unsupported claim ratio
- No automatic removal of unsupported claims
- **Status**: GAP

---

## 14. Async Jobs — Issues

### Inline worker
- `InlineJobRunner` (runner.py:35-84) runs ingestion synchronously. When the API receives an upload, it creates a job row, then calls `pipeline.process()` inline. The upload endpoint returns immediately with `status: "processing"` but the job is actually completed by the time the response is sent (for small docs) or the inline processing blocks the API thread.
- **Status**: WORKS but blocks API thread

### Queue runner
- `QueueJobRunner` (queue_runner.py) uses RQ. The `process_ingestion` worker function (worker.py:15) rebuilds a fresh container. This is correct.
- **Status**: VERIFIED (code review, not runtime tested)

### Worker failure handling
- Both `InlineJobRunner` and `worker.py` catch exceptions and update job status to FAILED with error message. Retry is not implemented.
- **Status**: PARTIALLY VERIFIED

---

## 15. Document Delete / Reindex — Issues Found

### Delete flow
- `docs.py:delete_document` calls `repo.soft_delete()` which sets `deleted_at`. But:
  - Does NOT delete vectors from the vector store
  - Does NOT delete chunks from BM25
  - Does NOT delete physical files from storage
  - Only marks the DB record as deleted
- **CRITICAL BUG**: Soft delete leaves orphaned vectors in the vector store and orphaned BM25 entries

### Reindex
- `IngestionPipeline._embed_and_index` deletes old chunks from DB (`chunk_repo.delete_document`) and re-inserts. It does NOT delete old vectors from the vector store. Vectors accumulate.
- **CRITICAL BUG**: Vector store is not cleaned on reindex

---

## 16. Frontend — Issues Found

### Chat streaming
- `useChat.ts` uses axios with `responseType: 'stream'` and `onResponse` callback
- **BUG**: After the stream callback fires, `resp.data` is a ReadableStream, not a ChatResponse. The code `const data = resp.data as ChatResponse;` on line 90 is unreachable/misleading — the entire response is consumed by the stream callback.
- **Bug**: `processStream()` is called without `await` (line 86), so errors during streaming may not be caught properly by the try/catch
- **Status**: BUG

### Citation display
- Citations are shown as text: `[1] handbook.pdf — Page 2 — Section`
- No click-to-navigate functionality
- **Status**: GAP

### Authentication persistence
- Token stored in localStorage, JWT decoded client-side
- No token refresh mechanism
- 401 on API response removes token and redirects to login
- **Status**: OK

### No PDF viewer
- `DocumentDetail.tsx` does not render PDFs
- **Status**: GAP

---

## 17. Docker — Issues Found

### Root-level stale files
- The repository root contains stale duplicate files: `package.json`, `index.html`, `vite.config.ts`, `tsconfig.json`, `tailwind.config.cjs`, `postcss.config.cjs`, `Dockerfile` (349 bytes), `nginx.conf`, `README.md` (666 bytes), `conftest.py`, `pyproject.toml` (1816 bytes), `alembic.ini`, `architecture.md`, `rag-pipeline.md`, `security.md`, `deployment.md`, `performance.md`, `evaluation.md`, `decisions/`, `datasets/`, `results/`, `sample_docs/`, `uploads/`
- These appear to be from a previous build phase that used the root directory structure (as described in ARCHITECTURE.md). They should be cleaned up.
- **Status**: CLUTTER / RISK

### Dockerfile
- Root `Dockerfile` (674 bytes) builds from root — references `backend/pyproject.toml` and `backend/ultimate_rag/`
- `frontend/Dockerfile` (349 bytes) builds from `frontend/`
- The root `Dockerfile` at `E:\ultimate rag p1\Dockerfile` (674 bytes) is the main backend Dockerfile
- **Status**: VERIFIED (code review)

### docker-compose.yml
- Services: api, worker, frontend, postgres, redis, ollama
- API depends on postgres, redis, ollama
- Worker depends on api, postgres, redis, ollama
- Volumes: pg_data, redis_data, ollama_data
- **Status**: VERIFIED

---

## 18. Configuration Validation — Issues Found

### Settings validation
- Pydantic `Field(pattern=...)` validates provider names — VERIFIED
- `database_url` validator converts `sqlite:` to `sqlite+aiosqlite:` — VERIFIED
- No validation for negative `top_k`, invalid chunk size, etc.
- **Status**: PARTIALLY VERIFIED

### Default secret key
- `secret_key` defaults to `"dev-only-change-me-in-production-7f3a9c1e"` — the `.env` file uses this default
- `is_default_secret` property exists but is not used for any enforcement or warning
- **Status**: GAP — no warning when default secret is used in production

---

## 19. Observability — Issues Found

### Request IDs
- `X-Request-ID` header or generated UUID — VERIFIED
- Logged in structured JSON format with request_id filter — VERIFIED
- `X-Response-Time-ms` header added — VERIFIED

### Latency tracing
- `measure()` context manager records latencies: `retrieval.total_latency_ms`, `retrieval.bm25_latency_ms`, `retrieval.rerank_latency_ms`, `generation.llm_latency_ms`, `ingestion.total_latency_ms`
- Missing: `retrieval.rrf_fusion_ms`, `retrieval.hyde_embed_ms`
- Actually present: `retrieval.rrf_fusion_ms` is there (pipeline.py:103)
- **Status**: PARTIALLY VERIFIED

### Missing:
- No trace/span IDs for distributed tracing
- No structured query tracking with full pipeline breakdown
- **Status**: GAP

---

## 20. Mypy Errors (50 errors in 18 files)

### Pre-existing errors in production code:
1. `core/config.py` — `secret_key` `min_length=16` but Field doesn't enforce it the way expected
2. `storage/providers/s3.py` — Missing `acl` parameter type hints
3. `vecstore/providers/pgvector.py` — `adelete_document` uses sync `with` instead of `async`
4. `vecstore/providers/qdrant.py` — Type annotation issues
5. `embeddings/providers/sentence_transformers.py:39` — `int | None` assigned to `int`
6. `ingestion/pipeline.py:121` — `doc.file_id` type `str | None` passed to `storage.read()` which expects `str`
7. `jobs/queue_runner.py:33` — `Queue` assigned to `None` typed variable
8. `main.py:76` — Exception handler type mismatch

### Pre-existing errors in test code:
9. `tests/unit/test_embeddings.py:44` — `Settings()` without required args (uses `Settings()` instead of `get_settings()`)
10. `tests/integration/test_ingestion.py:21` — Same `Settings()` issue
11. `tests/integration/test_ingestion.py:116` — `doc.status` None check missing
12. `tests/integration/test_rate_limit.py` — `_FakeRequest` type mismatch
13. `tests/unit/test_answer_builder.py:154-157` — `llm.messages` None issues
14. `tests/unit/test_retrieval.py:130` — `_FakeDense.asearch` signature mismatch

### Assessment: mypy uses `python_version = "3.11"` in config but the environment is Python 3.14. Some errors are due to newer Python type strictness.

---

## 3. Bug Summary

| # | Bug | File | Severity |
|---|-----|------|----------|
| 1 | TYPE_CHECKING import of nonexistent `embeddings/base` | `pipeline.py:26` | Medium (latent) |
| 2 | `adelete_document` / `adelete_tenant` in pgvector use sync `with` (missing `async`) | `pgvector.py:180-190` | Medium |
| 3 | Soft delete doesn't clean vector store or BM25 | `docs.py:169` | **Critical** |
| 4 | Reindex doesn't clean old vectors from vector store | `ingestion/pipeline.py:216-224` | **Critical** |
| 5 | `doc.file_id` can be None but passed to `storage.read()` | `ingestion/pipeline.py:121` | Medium |
| 6 | Conversations `get_conversation` returns empty response instead of 404 | `conversations.py:78-83` | Medium |
| 7 | Frontend `useChat.ts` stream handling: `processStream()` not awaited, `resp.data` misused | `useChat.ts:86,90` | High |
| 8 | `OllamaProvider` does not implement `stream()` | `ollama.py` | **Critical** |
| 9 | `HydeGenerator._PREFIXES` has `re.IGNORECASE | re.IGNORECASE` (duplicate flag) | `transformer.py:221` | Low |
| 10 | Rate limit maps `/documents` and `/jobs` to "query" bucket | `rate_limit.py:118-119` | Low |
| 11 | Evidence table has no tenant_id; `_persist_evidence` doesn't filter by tenant | `models.py:196-204` | Medium |
| 12 | `embeddings_batch.py` imports `Sequence` from `collections.abc` but uses it as a type hint that doesn't match the actual usage | `embeddings_batch.py:11` | Low |
| 13 | `BM25Retriever.search` has a redundant `_idf` call on line 174 before `_idf_recompute` on line 175 | `bm25.py:174-175` | Low |
| 14 | `embeddings/__init__.py` is empty but `pipeline.py` tries to import `from ultimate_rag.embeddings.base` | — | Medium |

---

## 4. Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Faithfulness uses Jaccard, not NLI | **High** | Replace with semantic entailment checker (cross-encoder or local NLI) |
| Ollama streaming is fake (single chunk) | **High** | Implement real SSE streaming via Ollama's `/api/chat` with `stream: true` |
| Soft delete leaves orphaned vectors | **High** | Add vector store + BM25 cleanup to delete flow |
| Reindex doesn't clean old vectors | **High** | Delete old vectors by document_id before re-indexing |
| Frontend streaming has unhandled async bug | **High** | Fix `useChat.ts` stream processing |
| No PDF viewer for citation navigation | Medium | Add PDF.js / react-pdf integration |
| No Redis cache layer | Medium | Add tenant-keyed caching for query/embedding results |
| 50 mypy errors in existing code | Medium | Fix all type errors |
| No document versioning | Low | Document limitation, create ADR |
| No multi-document reasoning | Medium | Add document-aware retrieval filtering |
| Evidence table not tenant-scoped | Medium | Add tenant_id to Evidence model or filter via query_id → query → tenant |
| Alembic `script_location` may fail in Docker | Medium | Fix path resolution in Dockerfile/alembic.ini |
| Stale duplicate files at repository root | Low | Clean up root-level duplicates |
| No security headers (CSP, HSTS, X-Frame-Options) | Medium | Add security headers middleware |
| No token refresh mechanism | Medium | Implement refresh token flow |
| Default secret key not enforced warning | Medium | Add startup warning when default secret detected |
| No adaptive query transformation | Low | Add query complexity detection to route transformations |
| No negative/abstention tests | Medium | Add tests for unanswerable/misleading questions |
| No prompt injection tests on document content | Medium | Add tests with malicious document text |

---

## 5. Recommended Fixes (Prioritized)

### P0 — Correctness
1. Fix `adelete_document` / `adelete_tenant` async bug in pgvector.py
2. Fix soft delete to clean vector store + BM25 + storage
3. Fix reindex to delete old vectors before re-inserting
4. Fix `doc.file_id` None type issue in pipeline.py
5. Fix conversations route to return 404 for non-owned/non-existent
6. Fix frontend `useChat.ts` stream handling

### P0 — Security
7. Add security headers middleware
8. Add prompt injection defense tests
9. Add negative/abstention tests
10. Add startup warning for default secret key

### P0 — Citation reliability
11. Add tests proving LLM cannot fabricate citation metadata
12. Add citation precision/recall/coverage metrics
13. Implement automatic claim-to-citation mapping verification

### P1 — RAG quality
14. Replace Jaccard faithfulness with NLI-based verification
15. Implement true Ollama streaming via `/api/chat` with `stream: true`
16. Add adaptive query transformation (simple queries skip expansion/HyDE)

### P1 — Streaming
17. Implement real SSE endpoint for streaming
18. Add proper event protocol: `token`, `citation`, `verification`, `done`

### P1 — Evaluation
19. Create expanded evaluation dataset (20+ cases)
20. Run ablation study and generate report
21. Create `evaluation/results/final-report.json` and `.md`

### P1 — Production persistence
22. Add tenant_id to Evidence model
23. Fix alembic path resolution for Docker

### P2 — UX
24. Add PDF viewer with page navigation for citations
25. Add loading/empty states to frontend pages

### P2 — Observability
26. Fix all 50 mypy errors

### P3 — Nice-to-have
27. Add Redis cache layer
28. Add document versioning (or ADR documenting limitation)
29. Add multi-document reasoning features
30. Clean up stale root-level duplicate files
