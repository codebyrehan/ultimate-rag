"""End-to-end ingestion -> retrieval test.

Real PDF fixture -> extraction -> semantic chunking -> embedding (stub, no
download) -> vector store + BM25 indexing -> chunk persistence -> hybrid
retrieval (dense + BM25 -> RRF -> rerank -> compress).

Uses the :class:`StubEmbeddingProvider` and :class:`StubReranker` so the test
runs offline without downloading models, while exercising the real
``InMemoryVectorStore``, ``BM25Retriever``, ``SemanticChunker``,
``IngestionPipeline``, and ``RetrievalPipeline``.
"""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ultimate_rag.core.config import get_settings
from ultimate_rag.core.ids import new_id
from ultimate_rag.db.enums import DocStatus
from ultimate_rag.db.models import Chunk, Document, Tenant, User
from ultimate_rag.db.repositories.chunks import ChunkRepository
from ultimate_rag.db.repositories.documents import DocumentRepository
from ultimate_rag.db.repositories.tenants import TenantRepository
from ultimate_rag.db.repositories.users import UserRepository
from ultimate_rag.embeddings.providers.stub import StubEmbeddingProvider
from ultimate_rag.ingestion.chunker import SemanticChunker
from ultimate_rag.ingestion.ocr import NoOpOCR
from ultimate_rag.ingestion.pipeline import IngestionPipeline
from ultimate_rag.retrieval.bm25 import BM25Retriever
from ultimate_rag.retrieval.pipeline import RetrievalPipeline
from ultimate_rag.retrieval.reranker import StubReranker
from ultimate_rag.services.factory import build_storage
from ultimate_rag.tests._fixtures import make_sample_pdf
from ultimate_rag.vecstore.providers.in_memory import InMemoryVectorStore


@pytest.fixture
async def _e2e_env(db_session: AsyncSession):
    s = get_settings()
    embeddings = StubEmbeddingProvider(s)
    vs = InMemoryVectorStore(s)
    bm25 = BM25Retriever(s)
    chunker = SemanticChunker(s)
    ocr = NoOpOCR(s)
    storage = build_storage(s)
    retriever_reranker = StubReranker(s)
    return {
        "settings": s,
        "embeddings": embeddings,
        "vector_store": vs,
        "bm25": bm25,
        "chunker": chunker,
        "ocr": ocr,
        "storage": storage,
        "reranker": retriever_reranker,
        "session": db_session,
    }


@pytest.mark.asyncio
async def test_ingest_then_retrieve_leave_policy(_e2e_env) -> None:
    s = _e2e_env["settings"]
    session: AsyncSession = _e2e_env["session"]

    # tenant + user
    t_repo = TenantRepository(session)
    u_repo = UserRepository(session)
    tenant = await t_repo.add(Tenant(id=new_id(), name="acme"))
    user = User(
        id=new_id(),
        tenant_id=tenant.id,
        email="alice@acme.test",
        hashed_password="h",
    )
    await u_repo.add(user)

    # store the sample PDF
    pdf_bytes = make_sample_pdf()
    stored = await _e2e_env["storage"].save("handbook.pdf", pdf_bytes)
    sha = hashlib.sha256(pdf_bytes).hexdigest()

    # create the document row
    d_repo = DocumentRepository(session)
    doc = Document(
        id=new_id(),
        tenant_id=tenant.id,
        owner_id=user.id,
        filename=stored.filename,
        original_filename=stored.filename,
        sha256=sha,
        page_count=2,
        upload_path=stored.path,
        file_id=stored.file_id,
        status=DocStatus.UPLOADED,
        indexing_status=DocStatus.UPLOADED,
    )
    await d_repo.add(doc)
    await session.commit()

    # run ingestion
    ingest = IngestionPipeline(
        embeddings=_e2e_env["embeddings"],
        vector_store=_e2e_env["vector_store"],
        bm25=_e2e_env["bm25"],
        chunker=_e2e_env["chunker"],
        ocr=_e2e_env["ocr"],
        storage=_e2e_env["storage"],
        settings=s,
    )
    result = await ingest.process(doc.id, tenant.id, session)
    assert result.status == "indexed"
    assert result.chunks_indexed > 0

    # chunks persisted to DB
    chunk_repo = ChunkRepository(session)
    db_chunks = await chunk_repo.list_for_document(tenant.id, doc.id)
    assert len(db_chunks) == result.chunks_indexed
    assert all(isinstance(c, Chunk) for c in db_chunks)

    # vectors indexed in the dense store
    dense_hits = await _e2e_env["vector_store"].asearch(
        (await _e2e_env["embeddings"].aembed(["annual leave"])).tolist()[0],
        top_k=5,
        tenant_id=tenant.id,
    )
    assert len(dense_hits) > 0

    # bm25 indexed
    bm25_hits = _e2e_env["bm25"].search("leave entitlement", tenant.id, top_k=5)
    assert len(bm25_hits) > 0

    # retrieval pipeline with DB-backed text hydration
    async def text_loader(chunk_ids: list[str]) -> dict[str, str]:
        rows = await chunk_repo.get_by_ids(tenant.id, chunk_ids)
        return {cid: row.text for cid, row in rows.items()}

    retrieval = RetrievalPipeline(
        embeddings=_e2e_env["embeddings"],
        vector_store=_e2e_env["vector_store"],
        bm25=_e2e_env["bm25"],
        reranker=_e2e_env["reranker"],
        settings=s,
    )
    ctx = await retrieval.retrieve("annual leave entitlement", tenant.id, text_loader=text_loader)

    assert ctx.tenant_id == tenant.id
    assert len(ctx.dense_candidates) > 0
    assert len(ctx.bm25_candidates) > 0
    assert len(ctx.fused_candidates) > 0
    assert len(ctx.reranked) > 0
    assert len(ctx.compressed) > 0
    assert len(ctx.compressed) <= s.final_top_k

    # reranked text is hydrated (non-empty)
    assert all(c.text for c in ctx.compressed)
