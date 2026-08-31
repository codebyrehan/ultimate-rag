"""OpenAI-compatible embedding provider.

Used only when ``EMBEDDING_PROVIDER=openai``. Requires ``OPENAI_API_KEY``.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import numpy as np

from ultimate_rag.core.config import Settings
from ultimate_rag.embeddings.interface import BaseEmbeddingProvider, normalize

logger = logging.getLogger("ultimate_rag.embeddings.openai")


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        super().__init__(dim=settings.embedding_dim)
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.openai_base_url or "https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}"},
            timeout=60.0,
        )

    def embed(self, texts: list[str]) -> np.ndarray:
        raise RuntimeError("OpenAI provider is async-only; use aembed()")

    async def aembed(self, texts: list[str]) -> np.ndarray:
        embs: list[list[float]] = []
        batch = self._settings.embedding_batch_size
        for i in range(0, len(texts), batch):
            chunk = texts[i : i + batch]
            resp = await self._client.post(
                "embeddings", json={"model": self._settings.embedding_model, "input": chunk}
            )
            resp.raise_for_status()
            data: Any = resp.json()
            embs.extend([d["embedding"] for d in data["data"]])
        return normalize(np.asarray(embs, dtype=np.float32))

    async def aclose(self) -> None:
        await self._client.aclose()
