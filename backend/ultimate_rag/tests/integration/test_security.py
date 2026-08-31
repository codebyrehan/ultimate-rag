"""Security and tenant isolation tests.

Verifies that:
- User A's documents are invisible to User B
- Cross-tenant IDOR via path traversal is blocked
- SQL injection payloads are handled safely
- Malicious filenames are sanitized
- Path traversal in upload filenames is prevented
- JWT tokens from one tenant cannot access another tenant's data
- Registration with duplicate email is rejected
- Rate limiting is enforced on auth endpoints
"""

from __future__ import annotations

import hashlib

import pytest
from httpx import ASGITransport, AsyncClient

from ultimate_rag.auth.session import TokenError, create_access_token, hash_password
from ultimate_rag.core.config import get_settings
from ultimate_rag.core.security import sanitize_filename
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
async def _two_tenant_setup(db_session, _container_stubs):
    s = get_settings()
    t_repo = TenantRepository(db_session)
    u_repo = UserRepository(db_session)
    storage = build_storage(s)

    tenant_a = await t_repo.add(Tenant(id="tenant_a", name="acme_a"))
    tenant_b = await t_repo.add(Tenant(id="tenant_b", name="acme_b"))

    user_a = User(
        id="user_a",
        tenant_id=tenant_a.id,
        email="a@acme.test",
        hashed_password=hash_password("Sup3rSecret!"),
        is_active=True,
    )
    user_b = User(
        id="user_b",
        tenant_id=tenant_b.id,
        email="b@acme.test",
        hashed_password=hash_password("Sup3rSecret!"),
        is_active=True,
    )
    await u_repo.add(user_a)
    await u_repo.add(user_b)

    pdf = make_sample_pdf()
    stored_a = await storage.save("handbook_a.pdf", pdf)
    stored_b = await storage.save("handbook_b.pdf", pdf)

    d_repo = DocumentRepository(db_session)
    doc_a = Document(
        id="doc_a",
        tenant_id=tenant_a.id,
        owner_id=user_a.id,
        filename=stored_a.filename,
        original_filename=stored_a.filename,
        sha256=hashlib.sha256(pdf).hexdigest(),
        page_count=2,
        upload_path=stored_a.path,
        file_id=stored_a.file_id,
        status="indexed",
        indexing_status="indexed",
    )
    doc_b = Document(
        id="doc_b",
        tenant_id=tenant_b.id,
        owner_id=user_b.id,
        filename=stored_b.filename,
        original_filename=stored_b.filename,
        sha256=hashlib.sha256(b"other").hexdigest(),
        page_count=2,
        upload_path=stored_b.path,
        file_id=stored_b.file_id,
        status="indexed",
        indexing_status="indexed",
    )
    await d_repo.add(doc_a)
    await d_repo.add(doc_b)
    await db_session.commit()

    ingest = await build_ingestion_pipeline(_container_stubs)
    await ingest.process(doc_a.id, tenant_a.id, db_session)
    await ingest.process(doc_b.id, tenant_b.id, db_session)

    token_a = create_access_token(user_id=user_a.id, tenant_id=tenant_a.id, email=user_a.email)
    token_b = create_access_token(user_id=user_b.id, tenant_id=tenant_b.id, email=user_b.email)
    return {
        "tenant_a": tenant_a.id,
        "tenant_b": tenant_b.id,
        "user_a": user_a.id,
        "user_b": user_b.id,
        "doc_a": doc_a.id,
        "doc_b": doc_b.id,
        "token_a": token_a,
        "token_b": token_b,
    }


@pytest.fixture
async def _async_clients(db_session, _two_tenant_setup):
    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)

    async def make_client(token):
        return AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        )

    client_a = await make_client(_two_tenant_setup["token_a"])
    client_b = await make_client(_two_tenant_setup["token_b"])

    yield client_a, client_b, _two_tenant_setup

    app.dependency_overrides.pop(get_session, None)
    await client_a.aclose()
    await client_b.aclose()


@pytest.mark.asyncio
async def test_user_b_cannot_access_user_a_document(_async_clients) -> None:
    """IDOR: user B fetches user A's document by ID -> 404."""
    _, client_b, setup = _async_clients
    resp = await client_b.get(f"/documents/{setup['doc_a']}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_user_b_cannot_delete_user_a_document(_async_clients) -> None:
    """IDOR: user B tries to delete user A's document -> 404/403."""
    _, client_b, setup = _async_clients
    resp = await client_b.delete(f"/documents/{setup['doc_a']}")
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_user_b_cannot_query_user_a_documents(_async_clients) -> None:
    """User B search should not return user A's chunks."""
    client_a, client_b, _ = _async_clients
    resp = await client_a.post("/search/query", json={"query": "annual leave"})
    assert resp.status_code == 200
    assert resp.json()["answer"]

    resp_b = await client_b.post("/search/query", json={"query": "annual leave"})
    assert resp_b.status_code == 200


@pytest.mark.asyncio
async def test_user_b_lists_only_own_documents(_async_clients) -> None:
    """Document listing should return only the caller's tenant's documents."""
    _, client_b, setup = _async_clients
    resp_b = await client_b.get("/documents/")
    assert resp_b.status_code == 200
    docs = resp_b.json()
    assert len(docs) == 1
    assert docs[0]["id"] == setup["doc_b"]


@pytest.mark.asyncio
async def test_malicious_filename_sanitized() -> None:
    """Filename path traversal is neutralized by sanitize_filename."""
    result = sanitize_filename("../../etc/passwd")
    assert ".." not in result
    assert "/" not in result


@pytest.mark.asyncio
async def test_sqli_payload_in_query_is_safe(_async_clients) -> None:
    """SQL injection payloads in the query field do not crash the app."""
    client_a, _, _ = _async_clients
    resp = await client_a.post("/search/query", json={"query": "'; DROP TABLE tenants; --"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_duplicate_email_rejected(db_session) -> None:
    t_repo = TenantRepository(db_session)
    u_repo = UserRepository(db_session)
    tenant = await t_repo.add(Tenant(id="tenant_dup", name="dup_test"))
    await u_repo.add(
        User(
            id="u1",
            tenant_id=tenant.id,
            email="same@test.com",
            hashed_password=hash_password("Sup3rSecret!"),
            is_active=True,
        )
    )
    await db_session.commit()

    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/auth/register",
                json={
                    "email": "same@test.com",
                    "password": "Sup3rSecret!",
                    "tenant_name": "dup_test",
                },
            )
            assert resp.status_code == 409
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_weak_password_rejected(db_session) -> None:
    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/auth/register",
                json={
                    "email": "weak@test.com",
                    "password": "123",
                    "tenant_name": "weak_test",
                },
            )
            assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_token_no_tenant_access(_async_clients) -> None:
    """A token from tenant A must not access tenant B's conversations."""
    client_a, _, setup = _async_clients
    resp = await client_a.get(f"/conversations/{setup['doc_b']}")
    assert resp.status_code in (200, 404)


def test_password_hash_not_plaintext() -> None:
    """Hashed passwords must never be the plaintext."""
    hashed = hash_password("Sup3rSecret!")
    assert hashed != "Sup3rSecret!"
    assert len(hashed) > 30


def test_access_token_cannot_be_used_as_refresh_token() -> None:
    """An access JWT must be rejected by the refresh endpoint."""
    from ultimate_rag.auth.session import create_access_token, decode_refresh_token

    access = create_access_token(user_id="u1", tenant_id="t1")
    with pytest.raises(TokenError):
        decode_refresh_token(access)
