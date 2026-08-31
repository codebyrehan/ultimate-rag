"""Integration tests for /chat and /chat/stream routes."""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from ultimate_rag.auth.session import create_access_token, hash_password
from ultimate_rag.core.config import get_settings
from ultimate_rag.db.connection import get_session
from ultimate_rag.db.models import Document, Tenant, User
from ultimate_rag.db.repositories.documents import DocumentRepository
from ultimate_rag.db.repositories.tenants import TenantRepository
from ultimate_rag.db.repositories.users import UserRepository
from ultimate_rag.embeddings.providers.stub import StubEmbeddingProvider
from ultimate_rag.generation.providers.stub import StubProvider
from ultimate_rag.ingestion.ocr import NoOpOCR
from ultimate_rag.ingestion.pipeline import build_ingestion_pipeline
from ultimate_rag.main import app
from ultimate_rag.retrieval.bm25 import BM25Retriever
from ultimate_rag.retrieval.reranker import StubReranker
from ultimate_rag.services.container import get_container, reset_container
from ultimate_rag.services.factory import build_storage
from ultimate_rag.tests._fixtures import make_sample_pdf
from ultimate_rag.vecstore.providers.in_memory import InMemoryVectorStore


@pytest.fixture
def _container_stubs():
    s = get_settings()
    reset_container()
    c = get_container()
    c.register_factory("embeddings", lambda: StubEmbeddingProvider(s))
    c.register_factory("vector_store", lambda: InMemoryVectorStore(s))
    c.register_factory("bm25", lambda: BM25Retriever(s))
    c.register_factory("llm", lambda: StubProvider(s))
    c.register_factory("reranker", lambda: StubReranker(s))
    c.register_factory("ocr", lambda: NoOpOCR(s))
    return c


@pytest.fixture
async def _auth_setup(db_session, _container_stubs):
    import hashlib

    s = get_settings()
    container = _container_stubs
    t_repo = TenantRepository(db_session)
    u_repo = UserRepository(db_session)
    tenant = await t_repo.add(Tenant(id="tenant_chat", name="acme"))
    user = User(
        id="u_chat",
        tenant_id=tenant.id,
        email="a@acme.test",
        hashed_password=hash_password("Sup3rSecret!"),
        is_active=True,
    )
    await u_repo.add(user)

    storage = build_storage(s)
    pdf = make_sample_pdf()
    stored = await storage.save("handbook.pdf", pdf)
    d_repo = DocumentRepository(db_session)
    doc = Document(
        id="doc_chat",
        tenant_id=tenant.id,
        owner_id=user.id,
        filename=stored.filename,
        original_filename=stored.filename,
        sha256=hashlib.sha256(pdf).hexdigest(),
        page_count=2,
        upload_path=stored.path,
        file_id=stored.file_id,
        status="uploaded",
        indexing_status="uploaded",
    )
    await d_repo.add(doc)
    await db_session.commit()

    ingest = await build_ingestion_pipeline(container)
    await ingest.process(doc.id, tenant.id, db_session)

    token = create_access_token(user_id=user.id, tenant_id=tenant.id, email=user.email)
    return {"token": token, "tenant_id": tenant.id}


@pytest.fixture
async def async_client(db_session, _auth_setup):
    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {_auth_setup['token']}"},
    ) as client:
        yield client
    app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_chat_sync(async_client) -> None:
    resp = await async_client.post(
        "/chat/",
        json={"query": "annual leave entitlement"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"]
    assert len(data["citations"]) > 0
    assert data["confidence"] >= 0.0


@pytest.mark.asyncio
async def test_chat_stream(async_client) -> None:
    resp = await async_client.post(
        "/chat/stream",
        json={"query": "annual leave entitlement"},
    )
    assert resp.status_code == 200
    lines = [line for line in resp.text.strip().splitlines() if line]
    assert len(lines) >= 2
    events = [json.loads(line) for line in lines]
    done = [e for e in events if e["type"] == "done"]
    tokens = [e for e in events if e["type"] == "token"]
    assert len(done) == 1
    assert len(tokens) >= 1
    assert done[0]["citations"]
    assert "query_id" in done[0]
