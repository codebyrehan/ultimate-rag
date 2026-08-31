"""Candidate deduplication during retrieval."""

from __future__ import annotations

from ultimate_rag.retrieval.types import RetrievedChunk


def dedup_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Deduplicate by chunk_id, keeping the highest-scoring occurrence."""
    best: dict[str, RetrievedChunk] = {}
    order: list[str] = []
    for chunk in chunks:
        cid = chunk.chunk_id
        if cid not in best:
            order.append(cid)
            best[cid] = chunk
        elif chunk.score > best[cid].score:
            best[cid] = chunk
    return [best[cid] for cid in order]
