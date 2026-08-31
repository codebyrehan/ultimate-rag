from __future__ import annotations

import numpy as np
import pytest

from ultimate_rag.core.config import Settings
from ultimate_rag.embeddings.providers.stub import StubEmbeddingProvider


def _settings(dim: int = 128) -> Settings:
    s = Settings.model_construct()
    s.embedding_dim = dim
    return s


def test_stub_embedding_shape_and_normalization():
    prov = StubEmbeddingProvider(_settings(128))
    embs = prov.embed(["hello world", "leave policy"])
    assert embs.shape == (2, 128)
    norms = np.linalg.norm(embs, axis=1)
    assert np.allclose(norms, 1.0)


def test_stub_embedding_deterministic():
    prov = StubEmbeddingProvider(_settings(64))
    a = prov.embed(["leave policy"])
    b = prov.embed(["leave policy"])
    assert np.allclose(a, b)


def test_stub_embedding_similar_terms():
    prov = StubEmbeddingProvider(_settings(128))
    a = prov.embed(["leave policy"])[0]
    b = prov.embed(["leave policy"])[0]
    sim = float(a @ b)
    assert sim > 0.99


@pytest.mark.asyncio
async def test_local_embedding_real_model():
    """Real BGE-small embedding (downloads once, cached)."""
    from ultimate_rag.embeddings.providers.sentence_transformers import SentenceTransformersProvider

    s = Settings.model_construct()
    prov = SentenceTransformersProvider(s)
    embs = await prov.aembed(["employee leave policy", "cafeteria menu"])
    assert embs.shape == (2, s.embedding_dim)
    norms = np.linalg.norm(embs, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-4)
