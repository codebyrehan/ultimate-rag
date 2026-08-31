"""Reciprocal Rank Fusion (weighted) for hybrid dense + BM25 retrieval.

RRF does NOT simply concatenate lists — it fuses ranked lists by reciprocal
rank, which is robust to score-scale differences between dense and lexical
retrieval. Dense and lexical weights are configurable.
"""

from __future__ import annotations

from collections import defaultdict

from ultimate_rag.retrieval.types import RetrievedChunk


class RRFusioner:
    """Weighted Reciprocal Rank Fusion of dense and BM25 candidate lists."""

    def __init__(self, k: int = 60, dense_weight: float = 0.6, lexical_weight: float = 0.4) -> None:
        self.k = k
        self.dense_weight = dense_weight
        self.lexical_weight = lexical_weight

    def fuse(
        self,
        dense: list[RetrievedChunk],
        bm25: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Merge two ranked lists with weighted RRF, deduplicating by chunk_id."""
        scores: dict[str, float] = defaultdict(float)
        best: dict[str, RetrievedChunk] = {}

        for rank, chunk in enumerate(dense):
            rrf = self.dense_weight / (self.k + rank + 1)
            scores[chunk.chunk_id] += rrf
            best[chunk.chunk_id] = self._best(best.get(chunk.chunk_id), chunk)

        for rank, chunk in enumerate(bm25):
            rrf = self.lexical_weight / (self.k + rank + 1)
            scores[chunk.chunk_id] += rrf
            best[chunk.chunk_id] = self._best(best.get(chunk.chunk_id), chunk)

        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        out: list[RetrievedChunk] = []
        for cid, score in ordered[:top_k]:
            chunk = best[cid]
            chunk.score = score
            chunk.source = f"{chunk.source}+rrf"
            out.append(chunk)
        return out

    @staticmethod
    def _best(a: RetrievedChunk | None, b: RetrievedChunk) -> RetrievedChunk:
        if a is None or b.score > a.score:
            return b
        return a
