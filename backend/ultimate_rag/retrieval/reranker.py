"""Cross-encoder reranker abstraction.

Reranking happens over the fused candidate set: the cross-encoder scores
(query, document) pairs jointly, which is far more accurate than bi-encoder
similarity alone. A :class:`StubReranker` provides a deterministic
token-overlap reranker for CI/sandbox (no model download) — it is a real
reranker, not a no-op.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Protocol

from ultimate_rag.core.config import Settings
from ultimate_rag.retrieval.types import RetrievedChunk

logger = logging.getLogger("ultimate_rag.retrieval.reranker")

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class Reranker(Protocol):
    def __init__(self, settings: Settings) -> None: ...

    async def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]: ...


def _token_overlap(query: str, text: str) -> float:
    qt = set(_TOKEN_RE.findall(query.lower()))
    dt = set(_TOKEN_RE.findall(text.lower()))
    if not qt:
        return 0.0
    return len(qt & dt) / len(qt)


class StubReranker:
    """Deterministic token-overlap reranker (no model required)."""

    name = "stub"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        scored = []
        for c in chunks:
            c.score = _token_overlap(query, c.text)
            scored.append(c)
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]


class CrossEncoderReranker:
    """Reranker backed by a HuggingFace cross-encoder model (CPU)."""

    name = "cross_encoder"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = None
        self._model_name = settings.reranker_model

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("Loading reranker %s", self._model_name)
            self._model = CrossEncoder(self._model_name, max_length=512)
        return self._model

    async def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        if not chunks:
            return []
        model = self._load()
        pairs = [(query, c.text) for c in chunks]
        scores = await asyncio.to_thread(model.predict, pairs)
        for c, sc in zip(chunks, scores, strict=False):
            c.score = float(sc)
        chunks.sort(key=lambda c: c.score, reverse=True)
        return chunks[:top_k]


class RerankerFactory:
    """Build a reranker from settings (kept for explicit construction)."""

    @staticmethod
    def build(settings: Settings):
        provider = settings.reranker_provider
        if provider == "cross_encoder":
            return CrossEncoderReranker(settings)
        if provider == "stub":
            return StubReranker(settings)
        raise ValueError(f"Unknown reranker provider: {provider}")
