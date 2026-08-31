"""Deterministic, dependency-free embedding provider used ONLY in tests.

Real retrieval/ingestion code uses local (Sentence Transformers) or OpenAI
providers; this stub exists so the pipeline can be exercised in CI/sandbox
without downloading a model, while still producing real-valued, deterministic
embeddings (hashed feature projection) rather than random or empty vectors.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

from ultimate_rag.core.config import Settings
from ultimate_rag.embeddings.interface import BaseEmbeddingProvider, normalize

_TOKEN = re.compile(r"[a-z0-9]+")


class StubEmbeddingProvider(BaseEmbeddingProvider):
    name = "stub"

    def __init__(self, settings: Settings) -> None:
        super().__init__(dim=settings.embedding_dim)
        self._dim = settings.embedding_dim

    def _vec(self, seed: str) -> np.ndarray:
        """Deterministic float vector of length ``dim`` in [-1, 1] derived from a seed.

        Bytes are interpreted as uint8 and rescaled (never reinterpreted as
        float32, which would overflow when many tokens are summed).
        """
        digest = hashlib.sha256(seed.encode()).digest()
        full = digest
        while len(full) < self._dim:
            digest = hashlib.sha256(digest).digest()
            full += digest
        arr = np.frombuffer(full[: self._dim], dtype=np.uint8).astype(np.float32)
        return (arr - 127.5) / 127.5

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self._dim), dtype=np.float32)
        for i, text in enumerate(texts):
            tokens = _TOKEN.findall(text.lower())
            vec = np.zeros(self._dim, dtype=np.float32)
            if not tokens:
                vec += self._vec(text)
            else:
                for tok in tokens:
                    vec += self._vec(tok)
            out[i] = vec
        return normalize(out)
