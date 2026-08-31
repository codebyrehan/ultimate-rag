from __future__ import annotations

from ultimate_rag.core.config import get_settings
from ultimate_rag.retrieval.bm25 import BM25Retriever
from ultimate_rag.retrieval.types import ChunkMetadata


def _mk(tid: str, cid: str, doc: str, text: str) -> tuple[str, str, ChunkMetadata]:
    return (
        cid,
        text,
        ChunkMetadata(
            document_id=doc,
            tenant_id=tid,
            doc_filename="handbook.pdf",
            page_number=1,
            section=None,
            subsection=None,
            chunk_id=cid,
            parent_id=None,
            chunk_type="child",
        ),
    )


def test_bm25_ranks_exact_term_match():
    s = get_settings()
    bm25 = BM25Retriever(s)
    tid = "t1"
    bm25.add_chunks(
        tid,
        [
            _mk(tid, "c1", "d1", "employees accrue annual leave entitlement"),
            _mk(tid, "c2", "d1", "the cafeteria serves pizza for lunch"),
        ],
    )
    res = bm25.search("leave entitlement", tid, top_k=5)
    assert [r.chunk_id for r in res] == ["c1"]
    assert res[0].score > 0
    # a query matching the second doc returns it
    res2 = bm25.search("pizza", tid, top_k=5)
    assert res2[0].chunk_id == "c2"


def test_bm25_tenant_isolation():
    s = get_settings()
    bm25 = BM25Retriever(s)
    bm25.add_chunks("tenantA", [_mk("tenantA", "c1", "d1", "secret leave policy")])
    res = bm25.search("leave policy", "tenantB", top_k=5)
    assert res == []


def test_bm25_delete_document():
    s = get_settings()
    bm25 = BM25Retriever(s)
    bm25.add_chunks(
        "t",
        [
            _mk("t", "c1", "d1", "leave policy"),
            _mk("t", "c2", "d2", "salary details"),
        ],
    )
    n = bm25.delete_document("d1", "t")
    assert n == 1
    res = bm25.search("leave policy", "t", top_k=5)
    assert res == []


def test_bm25_delete_tenant():
    s = get_settings()
    bm25 = BM25Retriever(s)
    bm25.add_chunks("t", [_mk("t", "c1", "d1", "leave policy")])
    n = bm25.delete_tenant("t")
    assert n == 1
    assert bm25.search("leave policy", "t", top_k=5) == []
