"""Shared data types used across the retrieval/generation/verification pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChunkMetadata:
    """Metadata carried alongside a chunk for retrieval + citation."""

    document_id: str
    tenant_id: str
    doc_filename: str
    page_number: int
    section: str | None = None
    subsection: str | None = None
    chunk_id: str = ""
    parent_id: str | None = None
    chunk_type: str = "child"
    source: str = "retrieval"


@dataclass
class RetrievedChunk:
    """A chunk returned by a retriever, with its score and metadata."""

    chunk_id: str
    text: str
    score: float
    metadata: ChunkMetadata
    embedding: list[float] | None = None
    rank: int = 0
    source: str = "dense"  # dense | bm25 | rerank

    @property
    def citation_label(self) -> str:
        """Format: [N] document.pdf — Page P — Section."""
        label = self.metadata.doc_filename
        if self.metadata.page_number:
            label += f" — Page {self.metadata.page_number}"
        if self.metadata.section:
            label += f" — {self.metadata.section}"
        return label


@dataclass
class RetrievalContext:
    """Mutable state threaded through the retrieval pipeline stages."""

    tenant_id: str
    query: str
    rewritten_query: str | None = None
    expanded_queries: list[str] = field(default_factory=list)
    multi_queries: list[str] = field(default_factory=list)
    hyde_answer: str | None = None
    dense_candidates: list[RetrievedChunk] = field(default_factory=list)
    bm25_candidates: list[RetrievedChunk] = field(default_factory=list)
    fused_candidates: list[RetrievedChunk] = field(default_factory=list)
    reranked: list[RetrievedChunk] = field(default_factory=list)
    compressed: list[RetrievedChunk] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
