"""Cache abstraction for deterministic, tenant-scoped results.

Strategy pattern: resolution is settings-driven. Supports in-memory (for
single-instance dev/test) and Redis/Valkey (for multi-process production).

Cache keys are namespaced by:
  - cache namespace prefix
  - tenant_id
  - user scope (when applicable)
  - document scope (when applicable)
  - model/config version hash

Only deterministic, non-sensitive operations are cacheable:
  - embeddings (input text + model version → embedding vector)
  - query transformations (rewritten query → transformed query)
  - retrieval results (for repeated identical queries within a TTL window)

Never cache raw document content, user PII, or secrets.
"""

from __future__ import annotations

from typing import Protocol


class CacheProvider(Protocol):
    """Minimal async cache interface."""

    async def get(self, key: str) -> bytes | None: ...
    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None: ...
    async def delete(self, key: str) -> bool: ...
    async def exists(self, key: str) -> bool: ...
    async def close(self) -> None: ...


def make_cache_key(
    namespace: str,
    tenant_id: str,
    *parts: str,
    user_id: str | None = None,
    doc_id: str | None = None,
    version: str | None = None,
) -> str:
    """Build a namespaced, tenant-scoped cache key.

    Parts are joined with ':', and each component is hashed to avoid
    delimiter collisions in user-supplied input.
    """
    import hashlib

    segments = [namespace, tenant_id]
    if user_id:
        segments.append(f"u:{user_id}")
    if doc_id:
        segments.append(f"d:{doc_id}")
    for p in parts:
        if p:
            h = hashlib.sha256(p.encode()).hexdigest()[:16]
            segments.append(h)
    if version:
        segments.append(version)
    return ":".join(segments)
