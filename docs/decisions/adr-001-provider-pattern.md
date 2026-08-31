# Decision Records

## ADR-01: Provider Pattern for Embeddings, Vector Store, and LLM

**Status**: Accepted

**Context**: The platform must support multiple backends (local, OpenAI, Ollama, HuggingFace) without hardcoding dependencies.

**Decision**: Use the Strategy pattern with a base ABC and settings-driven factory functions. Each provider implements the interface; the `ServiceContainer` lazily instantiates and caches the selected provider.

**Consequences**: Swapping providers requires only an environment variable change. Providers are cached per-process to avoid repeated model loading.

## ADR-02: SQLite with PostgreSQL Fallback

**Status**: Accepted

**Context**: The platform must run locally without external services but also scale to production.

**Decision**: Default to SQLite (with `init_db` auto-creating tables) for local/dev. Configuration supports PostgreSQL via `DATABASE_URL`. Alembic handles migrations for production.

**Consequences**: Tests pass with zero external dependencies. Production deploys use PostgreSQL.

## ADR-03: Stub Providers for CI

**Status**: Accepted

**Context**: CI must run without network access or model downloads.

**Decision**: Stub embedding, LLM, and reranker providers produce deterministic outputs. Tests use stubs by default; the same pipeline works identically with real providers.

**Consequences**: All tests are fast, deterministic, and offline. No CI flakiness from model loading or API calls.

## ADR-04: PBKDF2 Instead of bcrypt

**Status**: Accepted

**Context**: bcrypt requires a compiled C extension that may not be available on all platforms.

**Decision**: Use PBKDF2-SHA256 via passlib (pure Python fallback, no binary dependency).

**Consequences**: No special system packages needed. Still secure for password hashing.

## ADR-05: Deterministic Query Transformation

**Status**: Accepted

**Context**: LLM-based query expansion introduces non-determinism and external dependencies.

**Decision**: Use deterministic, regex/synonym-based query rewriting and expansion. This is safe for CI and offline use. Multi-query and HyDE use template-based generation.

**Consequences**: Slightly lower recall improvement than LLM-based expansion, but fully deterministic and dependency-free.
