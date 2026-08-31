"""In-memory vector store.

Genuine brute-force similarity search using numpy. Used as the default for
local development / tests (no external service required) and as a portable
reference implementation. For production scale, use :class:`QdrantStore` or
:class:`PgVectorStore`.

Because vectors are stored L2-normalized by the embedding provider, an inner
product equals the cosine similarity. Searches are always restricted to a
single ``tenant_id``.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import numpy as np

from ultimate_rag.core.config import Settings
from ultimate_rag.vecstore.interface import ScoredVector, VectorPayload, VectorStore

logger = logging.getLogger("ultimate_rag.vecstore.in_memory")

_INDEX_LOCK = None


def _lock():
    global _INDEX_LOCK
    if _INDEX_LOCK is None:
        import threading

        _INDEX_LOCK = threading.Lock()
    return _INDEX_LOCK


class InMemoryVectorStore(VectorStore):
    name = "in_memory"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        # tenant_id -> {chunk_id: (vector ndarray, payload)}
        self._store: dict[str, dict[str, tuple[np.ndarray, VectorPayload]]] = defaultdict(dict)
        self._collection = settings.vector_store_collection

    async def acreate_collection(self) -> None:
        # collections are created lazily on first insert
        logger.debug("in-memory collection '%s' ready", self._collection)

    async def abatch_insert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[VectorPayload],
    ) -> None:
        if not ids:
            return
        arr = np.asarray(vectors, dtype=np.float32)
        with _lock():
            for cid, vec, payload in zip(ids, arr, payloads, strict=False):
                tenant = payload.tenant_id
                # normalize defensively (provider should already normalize)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                self._store[tenant][cid] = (vec.astype(np.float32), payload)
        logger.debug("inserted %d vectors into '%s'", len(ids), self._collection)

    async def asearch(
        self,
        query_vector: list[float],
        top_k: int,
        tenant_id: str,
        filter: dict[str, Any] | None = None,
    ) -> list[ScoredVector]:
        if not self._store.get(tenant_id):
            return []
        q = np.asarray(query_vector, dtype=np.float32)
        qn = np.linalg.norm(q)
        if qn > 0:
            q = q / qn
        with _lock():
            entries = list(self._store[tenant_id].values())
            ids = [p.chunk_id for _, p in entries]
            mat = np.stack([v for v, _ in entries]) if entries else np.zeros((0, q.shape[0]))
        # cosine = inner product (vectors pre-normalized)
        scores = (mat @ q).astype(np.float32) if mat.shape[0] else np.zeros(0)
        results = [
            ScoredVector(chunk_id=ids[i], score=float(scores[i]), payload=entries[i][1])
            for i in range(len(ids))
        ]
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def adelete_document(self, document_id: str, tenant_id: str) -> int:
        with _lock():
            store = self._store.get(tenant_id, {})
            to_del = [cid for cid, (_, p) in store.items() if p.document_id == document_id]
            for cid in to_del:
                store.pop(cid, None)
        return len(to_del)

    async def adelete_tenant(self, tenant_id: str) -> int:
        with _lock():
            n = len(self._store.get(tenant_id, {}))
            self._store.pop(tenant_id, None)
        return n

    async def health_check(self) -> bool:
        return True

    async def aclose(self) -> None:
        with _lock():
            self._store.clear()
