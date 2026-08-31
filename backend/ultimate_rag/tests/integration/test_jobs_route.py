"""Integration test for /jobs routes (job status polling)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from ultimate_rag.auth.session import create_access_token, hash_password
from ultimate_rag.core.config import get_settings
from ultimate_rag.core.ids import new_id
from ultimate_rag.db.connection import get_session
from ultimate_rag.db.enums import JobStatus
from ultimate_rag.db.models import Job, Tenant, User
from ultimate_rag.db.repositories.jobs import JobRepository
from ultimate_rag.db.repositories.tenants import TenantRepository
from ultimate_rag.db.repositories.users import UserRepository
from ultimate_rag.embeddings.providers.stub import StubEmbeddingProvider
from ultimate_rag.generation.providers.stub import StubProvider
from ultimate_rag.ingestion.ocr import NoOpOCR
from ultimate_rag.main import app
from ultimate_rag.retrieval.bm25 import BM25Retriever
from ultimate_rag.retrieval.reranker import StubReranker
from ultimate_rag.services.container import get_container, reset_container
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
async def _auth_and_job(db_session, _container_stubs):
    t_repo = TenantRepository(db_session)
    u_repo = UserRepository(db_session)
    tenant = await t_repo.add(Tenant(id="tenant_jobs", name="acme"))
    user = User(
        id="u_jobs",
        tenant_id=tenant.id,
        email="a@acme.test",
        hashed_password=hash_password("Sup3rSecret!"),
        is_active=True,
    )
    await u_repo.add(user)
    await db_session.commit()

    j_repo = JobRepository(db_session)
    job = Job(
        id=new_id(),
        tenant_id=tenant.id,
        user_id=user.id,
        kind="ingest",
        status=JobStatus.COMPLETED,
        payload={},
        result={"chunks_indexed": 3, "pages": 2},
        progress=100,
    )
    await j_repo.add(job)
    await db_session.commit()

    token = create_access_token(user_id=user.id, tenant_id=tenant.id, email=user.email)
    return {"token": token, "job_id": job.id, "tenant_id": tenant.id}


@pytest.fixture
async def async_client(db_session, _auth_and_job):
    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {_auth_and_job['token']}"},
    ) as client:
        yield client
    app.dependency_overrides.pop(get_session, None)


@pytest.mark.asyncio
async def test_list_jobs(async_client, _auth_and_job) -> None:
    resp = await async_client.get("/jobs/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["job_id"] == _auth_and_job["job_id"]
    assert data[0]["status"] == "completed"
    assert data[0]["progress"] == 100


@pytest.mark.asyncio
async def test_get_job_by_id(async_client, _auth_and_job) -> None:
    resp = await async_client.get(f"/jobs/{_auth_and_job['job_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == _auth_and_job["job_id"]
    assert data["status"] == "completed"
    assert data["error"] is None
    assert data["result"]["chunks_indexed"] == 3


@pytest.mark.asyncio
async def test_get_job_not_found(async_client) -> None:
    resp = await async_client.get("/jobs/nonexistent-job-id")
    assert resp.status_code == 404
