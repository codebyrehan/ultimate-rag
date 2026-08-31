from __future__ import annotations

import pytest

from ultimate_rag.retrieval.fusion import RRFusioner
from ultimate_rag.retrieval.types import ChunkMetadata, RetrievedChunk


def _mk(
    tid: str,
    cid: str,
    text: str = "sample text",
    score: float = 1.0,
    source: str = "dense",
) -> RetrievedChunk:
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


def test_fuse_ranks_chunk_in_both_lists_first():
    rrf = RRFusioner(k=60, dense_weight=0.6, lexical_weight=0.4)
    dense = [_mk("t", "c1"), _mk("t", "c2")]
    bm25 = [_mk("t", "c1", source="bm25"), _mk("t", "c3", source="bm25")]
    out = rrf.fuse(dense, bm25, top_k=3)
    # c1 is rank 0 in both -> combined score 0.6/61 + 0.4/61 = 1.0/61
    assert out[0].chunk_id == "c1"
    assert out[0].score == pytest.approx(1.0 / 61)
    assert [c.chunk_id for c in out] == ["c1", "c2", "c3"]


def test_fuse_weight_skews_result():
    rrf_dense = RRFusioner(k=60, dense_weight=1.0, lexical_weight=0.0)
    dense = [_mk("t", "only_dense")]
    bm25 = [_mk("t", "only_bm25", source="bm25")]
    out_d = rrf_dense.fuse(dense, bm25, top_k=2)
    assert out_d[0].chunk_id == "only_dense"

    rrf_lex = RRFusioner(k=60, dense_weight=0.0, lexical_weight=1.0)
    out_l = rrf_lex.fuse(dense, bm25, top_k=2)
    assert out_l[0].chunk_id == "only_bm25"


def test_fuse_top_k_truncates():
    rrf = RRFusioner(k=60)
    dense = [_mk("t", f"c{i}") for i in range(5)]
    bm25 = [_mk("t", f"c{i}", source="bm25") for i in range(5, 10)]
    out = rrf.fuse(dense, bm25, top_k=3)
    assert len(out) == 3


def test_fuse_empty_inputs():
    rrf = RRFusioner(k=60)
    assert rrf.fuse([], [], top_k=5) == []
    single = rrf.fuse([_mk("t", "c1")], [], top_k=5)
    assert len(single) == 1 and single[0].chunk_id == "c1"
