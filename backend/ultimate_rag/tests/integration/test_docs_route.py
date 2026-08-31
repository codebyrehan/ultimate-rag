"""Integration test for the /documents/* routes (authenticated)."""

from __future__ import annotations

import io

import pytest
from httpx import ASGITransport, AsyncClient

from ultimate_rag.auth.session import create_access_token, hash_password
from ultimate_rag.core.config import get_settings
from ultimate_rag.db.connection import get_session
from ultimate_rag.db.models import Tenant, User
from ultimate_rag.db.repositories.tenants import TenantRepository
from ultimate_rag.db.repositories.users import UserRepository
from ultimate_rag.embeddings.providers.stub import StubEmbeddingProvider
from ultimate_rag.generation.providers.stub import StubProvider
from ultimate_rag.ingestion.ocr import NoOpOCR
from ultimate_rag.main import app
from ultimate_rag.retrieval.bm25 import BM25Retriever
from ultimate_rag.retrieval.reranker import StubReranker
from ultimate_rag.services.container import get_container, reset_container
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
async def async_client(db_session, _container_stubs):
    t_repo = TenantRepository(db_session)
    u_repo = UserRepository(db_session)
    tenant = await t_repo.add(Tenant(id="tenant_docs", name="acme"))
    user = User(
        id="u_docs",
        tenant_id=tenant.id,
        email="a@acme.test",
        hashed_password=hash_password("Sup3rSecret!"),
        is_active=True,
    )
    await u_repo.add(user)
    await db_session.commit()
    token = create_access_token(user_id=user.id, tenant_id=tenant.id, email=user.email)

    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client
    app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_upload_and_ingest(async_client) -> None:
    pdf_bytes = make_sample_pdf()
    resp = await async_client.post(
        "/documents/upload",
        files={"file": ("handbook.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["filename"] == "handbook.pdf"
    assert data["status"] == "processing"


@pytest.mark.asyncio
async def test_upload_duplicate_rejected(async_client) -> None:
    pdf_bytes = make_sample_pdf()
    resp1 = await async_client.post(
        "/documents/upload",
        files={"file": ("handbook.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp1.status_code == 201

    resp2 = await async_client.post(
        "/documents/upload",
        files={"file": ("handbook.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp2.status_code == 409
    assert "already uploaded" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_upload_invalid_content_type(async_client) -> None:
    resp = await async_client.post(
        "/documents/upload",
        files={"file": ("notes.txt", io.BytesIO(b"not a pdf"), "text/plain")},
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_upload_pdf_magic_bytes_mismatch(async_client) -> None:
    resp = await async_client.post(
        "/documents/upload",
        files={"file": ("fake.pdf", io.BytesIO(b"not a real pdf"), "application/pdf")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_requires_auth(db_session, _container_stubs) -> None:
    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/documents/upload",
                files={"file": ("h.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_session, None)
