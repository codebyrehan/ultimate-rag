"""Context compression: trim redundant/irrelevant chunks before generation.

After reranking we keep the top-N chunks, drop near-duplicate text, and
always preserve citation metadata (page/section/doc).
"""

from __future__ import annotations

from ultimate_rag.retrieval.types import RetrievedChunk


def compress(chunks: list[RetrievedChunk], top_k: int, min_score: float = -10.0) -> list[RetrievedChunk]:
    """Return up to ``top_k`` chunks, filtering by score and de-duplicating text."""
    filtered = [c for c in chunks if c.score >= min_score]
    filtered.sort(key=lambda c: c.score, reverse=True)
    seen_text: set[str] = set()
    kept: list[RetrievedChunk] = []
    for c in filtered:
        key = c.text.strip()[:80].lower() if c.text else c.chunk_id
        if key in seen_text and c.text:
            continue
        seen_text.add(key)
        kept.append(c)
        if len(kept) >= top_k:
            break
    return kept
