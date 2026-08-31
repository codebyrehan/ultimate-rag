from __future__ import annotations

import asyncio
import hashlib

import numpy as np
import pytest

from ultimate_rag.core.config import get_settings
from ultimate_rag.db.enums import DocStatus
from ultimate_rag.db.models import Document, Tenant, User
from ultimate_rag.db.repositories.documents import DocumentRepository
from ultimate_rag.db.repositories.evidence import EvidenceRepository
from ultimate_rag.db.repositories.queries import QueryRepository
from ultimate_rag.db.repositories.tenants import TenantRepository
from ultimate_rag.db.repositories.users import UserRepository
from ultimate_rag.generation.answer_builder import AnswerBuilder
from ultimate_rag.generation.providers.stub import StubProvider
from ultimate_rag.generation.query_service import QueryService
from ultimate_rag.ingestion.chunker import SemanticChunker
from ultimate_rag.ingestion.ocr import NoOpOCR
from ultimate_rag.ingestion.pipeline import IngestionPipeline
from ultimate_rag.retrieval.bm25 import BM25Retriever
from ultimate_rag.retrieval.pipeline import RetrievalPipeline
from ultimate_rag.retrieval.reranker import StubReranker
from ultimate_rag.services.factory import build_storage
from ultimate_rag.tests._fixtures import make_sample_pdf
from ultimate_rag.vecstore.providers.in_memory import InMemoryVectorStore


class _StubEmbeddings:
    name = "stub"
    dim = 8

    def __init__(self, settings) -> None:
        self.settings = settings

    def embed(self, texts):
        return np.zeros((len(texts), self.dim), dtype=np.float32)

    async def aembed(self, texts):
        return await asyncio.to_thread(self.embed, texts)

    def health(self) -> bool:
        return True


@pytest.fixture
async def _svc(db_session):
    s = get_settings()
    embeddings_stub = _StubEmbeddings(s)
    vs = InMemoryVectorStore(s)
    bm25 = BM25Retriever(s)
    chunker = SemanticChunker(s)
    ocr = NoOpOCR(s)
    storage = build_storage(s)

    t_repo = TenantRepository(db_session)
    u_repo = UserRepository(db_session)
    tenant = await t_repo.add(Tenant(id="tenant_e2e", name="acme"))
    user = User(id="u_e2e", tenant_id=tenant.id, email="a@acme.test", hashed_password="h")
    await u_repo.add(user)
    pdf = make_sample_pdf()
    stored = await storage.save("handbook.pdf", pdf)

    d_repo = DocumentRepository(db_session)
    doc = Document(
        id="doc_e2e",
        tenant_id=tenant.id,
        owner_id=user.id,
        filename=stored.filename,
        original_filename=stored.filename,
        sha256=hashlib.sha256(pdf).hexdigest(),
        page_count=2,
        upload_path=stored.path,
        file_id=stored.file_id,
        status=DocStatus.UPLOADED,
        indexing_status=DocStatus.UPLOADED,
    )
    await d_repo.add(doc)
    await db_session.commit()

    ingest = IngestionPipeline(
        embeddings=embeddings_stub,
        vector_store=vs,
        bm25=bm25,
        chunker=chunker,
        ocr=ocr,
        storage=storage,
        settings=s,
    )
    await ingest.process(doc.id, tenant.id, db_session)

    retrieval = RetrievalPipeline(
        embeddings=embeddings_stub,
        vector_store=vs,
        bm25=bm25,
        reranker=StubReranker(s),
        settings=s,
    )
    answer_builder = AnswerBuilder(llm=StubProvider(s), settings=s)
    svc = QueryService(retrieval=retrieval, answer_builder=answer_builder, settings=s)
    return svc, tenant, db_session


@pytest.mark.asyncio
async def test_query_service_answer_with_evidence(_svc) -> None:
    svc, tenant, session = _svc
    answer, query_id, report, _conv_id = await svc.answer(
        "annual leave entitlement", tenant.id, session, user_id="u_e2e"
    )
    assert answer.text
    assert len(answer.citations) > 0
    assert answer.confidence >= 0.0
    assert report is not None

    q_repo = QueryRepository(session)
    q = await q_repo.get(tenant.id, query_id)
    assert q is not None
    assert q.query == "annual leave entitlement"
    assert q.latency_ms >= 0

    ev_repo = EvidenceRepository(session)
    evs = await ev_repo.list_for_query(query_id)
    assert len(evs) == len(answer.citations)
    assert evs[0].rank == 0
    assert all(e.score >= 0.0 for e in evs)
