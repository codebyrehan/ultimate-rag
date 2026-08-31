"""Vector store abstraction (Strategy pattern).

Every implementation is tenant-scoped: vectors are stored with a ``tenant_id``
in their payload, and searches are always filtered by ``tenant_id`` so a tenant
can never retrieve another tenant's vectors.

A result is a ``ScoredVector``: the chunk id, similarity score, and the
payload used to reconstruct a :class:`RetrievedChunk`.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from ultimate_rag.core.config import Settings


@dataclass
class VectorPayload:
    """Payload persisted alongside each vector (mirrors chunk metadata)."""

    chunk_id: str
    document_id: str
    tenant_id: str
    doc_filename: str
    page_number: int = 1
    section: str | None = None
    subsection: str | None = None
    parent_id: str | None = None
    chunk_type: str = "child"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoredVector:
    chunk_id: str
    score: float
    payload: VectorPayload


class VectorStore(abc.ABC):
    """Async vector-store interface."""

    name: str

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abc.abstractmethod
    async def acreate_collection(self) -> None: ...

    @abc.abstractmethod
    async def abatch_insert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[VectorPayload],
    ) -> None: ...

    async def ainsert(self, id: str, vector: list[float], payload: VectorPayload) -> None:
        await self.abatch_insert([id], [vector], [payload])

    @abc.abstractmethod
    async def asearch(
        self,
        query_vector: list[float],
        top_k: int,
        tenant_id: str,
        filter: dict[str, Any] | None = None,
    ) -> list[ScoredVector]: ...

    @abc.abstractmethod
    async def adelete_document(self, document_id: str, tenant_id: str) -> int:
        """Delete all vectors for a document belonging to a tenant."""
        ...

    @abc.abstractmethod
    async def adelete_tenant(self, tenant_id: str) -> int: ...

    @abc.abstractmethod
    async def health_check(self) -> bool: ...

    async def aclose(self) -> None:
        """Default no-op close; providers override to release resources."""
        return None
