"""Local embedding provider backed by Sentence Transformers (BGE family).

Downloads model weights on first use (cached under HF_HOME). Encoding is
CPU-only and runs synchronously inside a thread (see ``aembed``).
"""

from __future__ import annotations

import logging
import os

import numpy as np
from sentence_transformers import SentenceTransformer

from ultimate_rag.core.config import Settings
from ultimate_rag.embeddings.interface import BaseEmbeddingProvider, normalize

logger = logging.getLogger("ultimate_rag.embeddings.local")

os.environ.setdefault("TRANSFORMERS_VERBOSITY", "ERROR")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


class SentenceTransformersProvider(BaseEmbeddingProvider):
    name = "sentence_transformers"

    def __init__(self, settings: Settings) -> None:
        super().__init__(dim=settings.embedding_dim)
        self._settings = settings
        self._model: SentenceTransformer | None = None

    def _load(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading embedding model %s", self._settings.embedding_model)
            device = getattr(self._settings, "embedding_device", None) or "cpu"
            self._model = SentenceTransformer(self._settings.embedding_model, device=device)
            try:
                dim = self._model.get_embedding_dimension()
            except AttributeError:
                dim = self._model.get_sentence_embedding_dimension() or self.dim
            self.dim = dim or self.dim
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        model = self._load()
        embs = model.encode(
            texts,
            batch_size=self._settings.embedding_batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        arr = np.asarray(embs, dtype=np.float32)
        return normalize(arr)

    def health(self) -> bool:
        try:
            return bool(self.embed(["healthcheck"]).shape == (1, self.dim))
        except Exception as e:  # pragma: no cover - model unavailable
            logger.warning("Embedding health check failed: %s", e)
            return False
