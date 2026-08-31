"""Dense retriever: embeds the query and searches the vector store."""

from __future__ import annotations

from ultimate_rag.embeddings.interface import EmbeddingProvider
from ultimate_rag.retrieval.types import ChunkMetadata, RetrievedChunk
from ultimate_rag.vecstore.interface import ScoredVector, VectorStore


def _scored_to_retrieved(sv: ScoredVector) -> RetrievedChunk:
    p = sv.payload
    return RetrievedChunk(
        chunk_id=p.chunk_id,
        text="",
        score=sv.score,
        metadata=ChunkMetadata(
            document_id=p.document_id,
            tenant_id=p.tenant_id,
            doc_filename=p.doc_filename,
            page_number=p.page_number,
            section=p.section,
            subsection=p.subsection,
            chunk_id=p.chunk_id,
            parent_id=p.parent_id,
            chunk_type=p.chunk_type,
        ),
        source="dense",
    )


class DenseRetriever:
    """Embeds the query and retrieves nearest dense neighbours."""

    def __init__(self, embeddings: EmbeddingProvider, vector_store: VectorStore, settings) -> None:
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.settings = settings

    async def retrieve(self, query: str, tenant_id: str, top_k: int) -> list[RetrievedChunk]:
        qe = await self.embeddings.aembed([query])
        scored = await self.vector_store.asearch(qe[0].tolist(), top_k, tenant_id)
        return [_scored_to_retrieved(sv) for sv in scored]

    async def retrieve_with_vector(
        self, query_vector: list[float], tenant_id: str, top_k: int
    ) -> list[RetrievedChunk]:
        """Retrieve using a pre-computed query embedding (for HyDE)."""
        scored = await self.vector_store.asearch(query_vector, top_k, tenant_id)
        return [_scored_to_retrieved(sv) for sv in scored]
