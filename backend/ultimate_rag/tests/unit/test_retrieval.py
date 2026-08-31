from __future__ import annotations

import asyncio

import numpy as np
import pytest

from ultimate_rag.core.config import get_settings
from ultimate_rag.retrieval.compression import compress
from ultimate_rag.retrieval.dedup import dedup_chunks
from ultimate_rag.retrieval.pipeline import RetrievalPipeline
from ultimate_rag.retrieval.reranker import StubReranker
from ultimate_rag.retrieval.types import ChunkMetadata, RetrievedChunk
from ultimate_rag.vecstore.interface import ScoredVector, VectorStore


def _mk(tid: str, cid: str, text: str, score: float = 1.0, source: str = "dense") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=cid,
        text=text,
        score=score,
        metadata=ChunkMetadata(
            document_id="d1",
            tenant_id=tid,
            doc_filename="doc.pdf",
            page_number=1,
            chunk_id=cid,
        ),
        source=source,
    )


# --- dedup ---


def test_dedup_keeps_highest_score():
    chunks = [
        _mk("t", "c1", "text A", score=0.5),
        _mk("t", "c1", "text A", score=0.9),
    ]
    out = dedup_chunks(chunks)
    assert len(out) == 1
    assert out[0].score == 0.9


def test_dedup_preserves_first_seen_order():
    chunks = [
        _mk("t", "c1", "a"),
        _mk("t", "c2", "b"),
        _mk("t", "c1", "a dup", score=1.5),
    ]
    out = dedup_chunks(chunks)
    assert [c.chunk_id for c in out] == ["c1", "c2"]
    assert out[0].score == 1.5


def test_dedup_empty():
    assert dedup_chunks([]) == []


# --- compress ---


def test_compress_limits_to_top_k():
    chunks = [_mk("t", f"c{i}", f"text {i}", score=10 - i) for i in range(5)]
    out = compress(chunks, top_k=3)
    assert len(out) == 3
    assert out[0].chunk_id == "c0"


def test_compress_drops_near_duplicates():
    chunks = [
        _mk("t", "c1", "The leave policy grants 20 days", score=0.9),
        _mk("t", "c2", "the leave policy grants 20 days", score=0.8),
        _mk("t", "c3", "Salary review happens yearly", score=0.7),
    ]
    out = compress(chunks, top_k=5)
    assert len(out) == 2
    assert {c.chunk_id for c in out} == {"c1", "c3"}


def test_compress_filters_by_min_score():
    chunks = [_mk("t", "c1", "x", score=-5.0), _mk("t", "c2", "y", score=0.5)]
    out = compress(chunks, top_k=5, min_score=0.0)
    assert [c.chunk_id for c in out] == ["c2"]


# --- stub reranker ---


@pytest.mark.asyncio
async def test_stub_reranker_orders_by_token_overlap():
    s = get_settings()
    rr = StubReranker(s)
    chunks = [
        _mk("t", "c1", "cafeteria serves pizza"),
        _mk("t", "c2", "leave entitlement and pizza"),
        _mk("t", "c3", "salary details"),
    ]
    out = await rr.rerank("pizza leave", chunks, top_k=2)
    assert [c.chunk_id for c in out] == ["c2", "c1"]
    assert out[0].score > out[1].score


@pytest.mark.asyncio
async def test_stub_reranker_empty():
    s = get_settings()
    rr = StubReranker(s)
    out = await rr.rerank("query", [], top_k=5)
    assert out == []


# --- pipeline integration (StubReranker + in-memory vector store) ---


class _FakeDense(VectorStore):
    """Minimal in-memory vector store for pipeline tests."""

    name = "fake"
    _TID = "tenant_x"

    def __init__(self) -> None:
        super().__init__(get_settings())
        self._index: list[ScoredVector] = []

    async def acreate_collection(self) -> None: ...

    async def abatch_insert(self, ids, vectors, payloads) -> None: ...

    async def asearch(
        self, query_vector: list, top_k: int, tenant_id: str, filter: dict | None = None
    ) -> list[ScoredVector]:
        del query_vector, tenant_id, filter
        return list(self._index[:top_k])

    async def adelete_document(self, document_id, tenant_id) -> int:
        del document_id, tenant_id
        return 0

    async def adelete_tenant(self, tenant_id) -> int:
        del tenant_id
        return 0

    async def health_check(self) -> bool:
        return True


class _FakeEmbeddings:
    """Returns a tiny fixed vector so the dense path runs without a model."""

    name = "fake"
    dim = 8

    def embed(self, texts):
        return np.zeros((len(texts), self.dim), dtype=np.float32)

    async def aembed(self, texts):
        return await asyncio.to_thread(self.embed, texts)

    def health(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_pipeline_stages_execute():
    s = get_settings()
    from ultimate_rag.retrieval.bm25 import BM25Retriever

    bm25 = BM25Retriever(s)
    tid = "tenant_x"
    chunks = [
        _mk(tid, "c1", "employees accrue annual leave entitlement", source="dense"),
        _mk(tid, "c2", "the cafeteria serves pizza for lunch", source="bm25"),
    ]
    bm25.add_chunks(tid, [(c.chunk_id, c.text, c.metadata) for c in chunks])

    pipeline = RetrievalPipeline(
        embeddings=_FakeEmbeddings(),
        vector_store=_FakeDense(),
        bm25=bm25,
        reranker=StubReranker(s),
        settings=s,
    )
    ctx = await pipeline.retrieve("leave entitlement pizza", tid)
    assert ctx.tenant_id == tid
    assert ctx.query == "leave entitlement pizza"
    assert len(ctx.bm25_candidates) >= 1
    assert len(ctx.reranked) <= s.reranker_top_k
    assert len(ctx.compressed) <= s.final_top_k
