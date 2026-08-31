"""Embedding provider abstraction (Strategy pattern).

Resolution is settings-driven via :func:`ultimate_rag.services.factory.build_embedding_provider`.
Implementations return normalized (L2) embeddings as ``np.ndarray`` so the
vector store can use inner-product (a.k.a. cosine) scoring uniformly.
"""

from __future__ import annotations

import abc
import asyncio
from typing import Protocol

import numpy as np


class EmbeddingProvider(Protocol):
    """Interface every embedding provider must implement."""

    name: str
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray:
        """Encode a batch of texts to a (N, dim) float32 array, L2-normalized."""
        ...

    async def aembed(self, texts: list[str]) -> np.ndarray:
        """Async wrapper around :meth:`embed`."""
        return await asyncio.to_thread(self.embed, texts)

    def health(self) -> bool:
        """Return True if the provider can encode a trivial query."""
        raise NotImplementedError


class BaseEmbeddingProvider(abc.ABC):
    name: str

    def __init__(self, dim: int) -> None:
        self.dim = dim

    @abc.abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray: ...

    async def aembed(self, texts: list[str]) -> np.ndarray:
        return await asyncio.to_thread(self.embed, texts)

    def health(self) -> bool:
        try:
            return bool(self.embed(["healthcheck"]).shape == (1, self.dim))
        except Exception:
            return False


def normalize(matrix: np.ndarray) -> np.ndarray:
    """L2-normalize rows of a (N, dim) matrix, guarding against zero vectors."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return (matrix / norms).astype(np.float32)
