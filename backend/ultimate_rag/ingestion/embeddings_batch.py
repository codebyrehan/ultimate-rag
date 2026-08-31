"""Batch embedding helper for ingestion.

Wraps an :class:`EmbeddingProvider` with batching + retry so large document
ingests never OOM and degrade gracefully on transient provider errors.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

import numpy as np

from ultimate_rag.embeddings.interface import EmbeddingProvider

logger = logging.getLogger("ultimate_rag.ingestion.embeddings_batch")


async def embed_chunks(
    provider: EmbeddingProvider,
    texts: Sequence[str],
    batch_size: int | None = None,
    retries: int = 3,
) -> np.ndarray:
    """Encode texts to embeddings, batching and retrying on failure."""
    if not texts:
        return np.zeros((0, provider.dim), dtype=np.float32)
    bs = batch_size or 32
    results: list[np.ndarray] = []
    for start in range(0, len(texts), bs):
        chunk = list(texts[start : start + bs])
        embs: np.ndarray | None = None
        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                embs = await provider.aembed(chunk)
                break
            except Exception as e:
                last_err = e
                await asyncio.sleep(0.5 * (2**attempt))
        if embs is None:
            logger.error("Embedding failed after %d retries: %s", retries, last_err)
            embs = np.zeros((len(chunk), provider.dim), dtype=np.float32)
        results.append(embs)
    return np.concatenate(results, axis=0) if results else np.zeros((0, provider.dim), dtype=np.float32)
