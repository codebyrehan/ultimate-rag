"""Cached embedding provider wrapper.

Wraps any :class:`EmbeddingProvider` with a tenant-scoped cache for embedding
results. Cache keys include the input text hash, tenant_id, model version, and
embedding dimension to prevent cache poisoning across tenants or model changes.
"""

from __future__ import annotations

import hashlib
import logging

import numpy as np

from ultimate_rag.cache import CacheProvider, make_cache_key
from ultimate_rag.embeddings.interface import EmbeddingProvider

logger = logging.getLogger("ultimate_rag.embeddings.cached")


class CachedEmbeddingProvider(EmbeddingProvider):
    """Decorator that caches embedding results per-tenant."""

    name = "cached"

    def __init__(
        self,
        inner: EmbeddingProvider,
        cache: CacheProvider,
        tenant_id: str | None = None,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._tenant_id = tenant_id or ""
        self.dim = inner.dim

    def embed(self, texts: list[str]) -> np.ndarray:
        return self._inner.embed(texts)

    async def aembed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        cached: list[np.ndarray | None] = [None] * len(texts)
        missed_idx: list[int] = []
        missed_texts: list[str] = []
        version = f"v1:dim={self.dim}"
        for i, text in enumerate(texts):
            text_hash = hashlib.sha256(text.encode()).hexdigest()[:32]
            key = make_cache_key("embed", self._tenant_id, text_hash, version=version)
            cached_bytes = await self._cache.get(key)
            if cached_bytes is not None:
                try:
                    embs = np.frombuffer(cached_bytes, dtype=np.float32).reshape(1, -1)
                    cached[i] = embs
                except Exception:
                    cached[i] = None
            if cached[i] is None:
                missed_idx.append(i)
                missed_texts.append(text)

        if missed_texts:
            results = await self._inner.aembed(missed_texts)
            for j, idx in enumerate(missed_idx):
                emb = results[j]
                cached[idx] = emb
                text_hash = hashlib.sha256(missed_texts[j].encode()).hexdigest()[:32]
                key = make_cache_key("embed", self._tenant_id, text_hash, version=version)
                await self._cache.set(key, emb.tobytes(), ttl=3600)

        return (
            np.stack([c for c in cached if c is not None])
            if cached
            else np.zeros((0, self.dim), dtype=np.float32)
        )

    def health(self) -> bool:
        return self._inner.health()

    async def aclose(self) -> None:
        if hasattr(self._inner, "aclose"):
            await self._inner.aclose()
