"""Qdrant vector store provider.

A production-grade, horizontally-scalable vector DB. Uses the synchronous
``qdrant-client`` wrapped to run in a worker thread so the async interface
is preserved. All searches are filtered by ``tenant_id``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from ultimate_rag.core.config import Settings
from ultimate_rag.vecstore.interface import ScoredVector, VectorPayload, VectorStore

logger = logging.getLogger("ultimate_rag.vecstore.qdrant")

_STANDARD_PAYLOAD_KEYS = {
    "chunk_id",
    "document_id",
    "tenant_id",
    "doc_filename",
    "page_number",
    "section",
    "subsection",
    "parent_id",
    "chunk_type",
}


class QdrantStore(VectorStore):
    name = "qdrant"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._collection = settings.vector_store_collection
        self._host, self._port = self._parse_url(settings.qdrant_url)
        self._client: QdrantClient | None = None

    @staticmethod
    def _parse_url(url: str) -> tuple[str, int]:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6333
        return host, port

    def _get_client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(host=self._host, port=self._port)
        return self._client

    async def acreate_collection(self) -> None:
        def _create() -> None:
            c = self._get_client()
            if not c.collection_exists(self._collection):
                c.recreate_collection(
                    collection_name=self._collection,
                    vectors_config=qmodels.VectorParams(
                        size=self.settings.embedding_dim,
                        distance=qmodels.Distance.COSINE,
                    ),
                )
            logger.info("qdrant collection '%s' ready", self._collection)

        await asyncio.to_thread(_create)

    async def abatch_insert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[VectorPayload],
    ) -> None:
        if not ids:
            return
        points = [
            qmodels.PointStruct(
                id=ids[i],
                vector=vectors[i],
                payload=_payload_to_dict(payloads[i]),
            )
            for i in range(len(ids))
        ]
        await asyncio.to_thread(
            self._get_client().upsert, collection_name=self._collection, points=points, wait=False
        )

    async def asearch(
        self,
        query_vector: list[float],
        top_k: int,
        tenant_id: str,
        filter: dict[str, Any] | None = None,
    ) -> list[ScoredVector]:
        c = self._get_client()
        flt = self._build_filter(tenant_id, filter)
        search_params = qmodels.SearchParams(hnsw_ef=self.settings.hnsw_ef)

        def _search() -> Any:
            kwargs: dict[str, Any] = {
                "collection_name": self._collection,
                "query": query_vector,
                "with_payload": True,
                "with_vectors": False,
                "limit": top_k,
                "search_params": search_params,
            }
            if flt is not None:
                kwargs["query_filter"] = flt
            return c.query_points(**kwargs)

        response = await asyncio.to_thread(_search)
        hits = response.points
        return [_hit_to_scored(h) for h in hits]

    async def adelete_document(self, document_id: str, tenant_id: str) -> int:
        c = self._get_client()
        flt = qmodels.Filter(
            must=[self._match("tenant_id", tenant_id), self._match("document_id", document_id)]
        )
        res = await asyncio.to_thread(
            c.delete, collection_name=self._collection, points_selector=qmodels.FilterSelector(filter=flt)
        )
        return int(res.operation_id) if res.operation_id else 0

    async def adelete_tenant(self, tenant_id: str) -> int:
        c = self._get_client()
        flt = qmodels.Filter(must=[self._match("tenant_id", tenant_id)])
        res = await asyncio.to_thread(
            c.delete, collection_name=self._collection, points_selector=qmodels.FilterSelector(filter=flt)
        )
        return int(res.operation_id) if res.operation_id else 0

    async def health_check(self) -> bool:
        try:
            return await asyncio.to_thread(self._get_client().collection_exists, self._collection)
        except Exception as e:
            logger.warning("qdrant healthcheck failed: %s", e)
            return False

    async def aclose(self) -> None:
        if self._client is not None:
            await asyncio.to_thread(self._client.close)
            self._client = None

    # ---- helpers ----
    def _build_filter(self, tenant_id: str, extra: dict[str, Any] | None) -> qmodels.Filter | None:
        must: list[Any] = [self._match("tenant_id", tenant_id)]
        if extra:
            for k, v in extra.items():
                if v is not None:
                    must.append(self._match(k, v))
        return qmodels.Filter(must=must)

    @staticmethod
    def _match(key: str, value: Any) -> qmodels.FieldCondition:
        return qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value))


def _payload_to_dict(p: VectorPayload) -> dict[str, Any]:
    d: dict[str, Any] = {
        "chunk_id": p.chunk_id,
        "document_id": p.document_id,
        "tenant_id": p.tenant_id,
        "doc_filename": p.doc_filename,
        "page_number": p.page_number,
        "section": p.section,
        "subsection": p.subsection,
        "parent_id": p.parent_id,
        "chunk_type": p.chunk_type,
    }
    d.update(p.extra or {})
    return d


def _hit_to_scored(hit: Any) -> ScoredVector:
    p = hit.payload or {}
    extra = {k: v for k, v in p.items() if k not in _STANDARD_PAYLOAD_KEYS}
    return ScoredVector(
        chunk_id=str(getattr(hit, "id", p.get("chunk_id", ""))),
        score=float(getattr(hit, "score", 0.0)),
        payload=VectorPayload(
            chunk_id=str(p.get("chunk_id", getattr(hit, "id", ""))),
            document_id=str(p.get("document_id", "")),
            tenant_id=str(p.get("tenant_id", "")),
            doc_filename=p.get("doc_filename", ""),
            page_number=int(p.get("page_number", 1) or 1),
            section=p.get("section"),
            subsection=p.get("subsection"),
            parent_id=p.get("parent_id"),
            chunk_type=p.get("chunk_type", "child"),
            extra=extra,
        ),
    )
