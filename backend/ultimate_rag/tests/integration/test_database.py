from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ultimate_rag.core.ids import new_id
from ultimate_rag.db.models import (
    Chunk,
    ChunkType,
    DocStatus,
    Document,
    Job,
    JobStatus,
    Tenant,
    User,
)
from ultimate_rag.db.repositories.chunks import ChunkRepository
from ultimate_rag.db.repositories.documents import DocumentRepository
from ultimate_rag.db.repositories.jobs import JobRepository
from ultimate_rag.db.repositories.users import UserRepository


def _hash(path: str) -> str:
    import hashlib

    return hashlib.sha256(path.encode()).hexdigest()


@pytest.fixture
async def sample_tenant(db_session: AsyncSession) -> Tenant:
    from ultimate_rag.db.repositories.tenants import TenantRepository as TR

    repo = TR(db_session)
    t = Tenant(id=new_id(), name="acme")
    await repo.add(t)
    await db_session.commit()
    return t


@pytest.fixture
async def sample_user(db_session: AsyncSession, sample_tenant: Tenant) -> User:
    from ultimate_rag.db.repositories.users import UserRepository as UR

    repo = UR(db_session)
    u = User(
        id=new_id(),
        tenant_id=sample_tenant.id,
        email="alice@acme.example",
        hashed_password="hashed",
    )
    await repo.add(u)
    await db_session.commit()
    return u


async def test_tenant_and_user_lifecycle(db_session: AsyncSession) -> None:
    from ultimate_rag.db.repositories.tenants import TenantRepository as TR

    t_repo = TR(db_session)
    u_repo = UserRepository(db_session)

    tenant = await t_repo.add(Tenant(id=new_id(), name="acme"))
    await db_session.commit()
    assert await t_repo.get(tenant.id) is not None

    user = User(id=new_id(), tenant_id=tenant.id, email="alice@acme.test", hashed_password="h")
    await u_repo.add(user)
    await db_session.commit()
    fetched = await u_repo.get_by_email(tenant.id, "alice@acme.test")
    assert fetched is not None
    assert fetched.tenant_id == tenant.id


async def test_document_crud_and_dedup(
    db_session: AsyncSession, sample_tenant: Tenant, sample_user: User
) -> None:
    d_repo = DocumentRepository(db_session)
    sha = _hash("hello")
    doc = Document(
        id=new_id(),
        tenant_id=sample_tenant.id,
        owner_id=sample_user.id,
        filename="handbook.pdf",
        original_filename="handbook.pdf",
        sha256=sha,
        page_count=12,
        upload_path="/data/handbook.pdf",
        metadata_={"author": "Acme"},
        status=DocStatus.UPLOADED,
        indexing_status=DocStatus.UPLOADED,
    )
    await d_repo.add(doc)
    await db_session.commit()

    dup = await d_repo.get_by_sha(sample_tenant.id, sha)
    assert dup is not None
    assert dup.original_filename == "handbook.pdf"

    retrieved = await d_repo.get(sample_tenant.id, doc.id)
    assert retrieved is not None and retrieved.page_count == 12

    await d_repo.update(sample_tenant.id, doc.id, status=DocStatus.PROCESSING)
    updated = await d_repo.get(sample_tenant.id, doc.id)
    assert updated is not None and updated.status == DocStatus.PROCESSING

    await d_repo.soft_delete(sample_tenant.id, doc.id)
    assert await d_repo.get(sample_tenant.id, doc.id) is None


async def test_tenant_isolation_document(
    db_session: AsyncSession, sample_tenant: Tenant, sample_user: User
) -> None:
    """A document created under one tenant must be invisible to another."""
    from ultimate_rag.db.repositories.tenants import TenantRepository as TR

    t_repo = TR(db_session)
    other_tenant = await t_repo.add(Tenant(id=new_id(), name="evil"))
    await db_session.commit()

    d_repo = DocumentRepository(db_session)
    doc = Document(
        id=new_id(),
        tenant_id=sample_tenant.id,
        owner_id=sample_user.id,
        filename="secret.pdf",
        original_filename="secret.pdf",
        sha256=_hash("tenant-a-doc"),
        page_count=1,
        upload_path="/data/secret.pdf",
        status=DocStatus.UPLOADED,
        indexing_status=DocStatus.UPLOADED,
    )
    await d_repo.add(doc)
    await db_session.commit()

    # other tenant cannot see it
    assert await d_repo.get(other_tenant.id, doc.id) is None
    assert await d_repo.get_by_sha(other_tenant.id, doc.sha256) is None
    # the rightful tenant can
    assert await d_repo.get(sample_tenant.id, doc.id) is not None


async def test_chunk_parent_child_and_repo_delete(
    db_session: AsyncSession, sample_tenant: Tenant, sample_user: User
) -> None:
    d_repo = DocumentRepository(db_session)
    c_repo = ChunkRepository(db_session)
    doc = Document(
        id=new_id(),
        tenant_id=sample_tenant.id,
        owner_id=sample_user.id,
        filename="d.pdf",
        original_filename="d.pdf",
        sha256=_hash("chunk-doc"),
        page_count=3,
        upload_path="/data/d.pdf",
        status=DocStatus.UPLOADED,
        indexing_status=DocStatus.UPLOADED,
    )
    await d_repo.add(doc)
    await db_session.commit()

    parent = Chunk(
        id=new_id(),
        document_id=doc.id,
        tenant_id=sample_tenant.id,
        parent_id=None,
        chunk_index=0,
        page_number=1,
        chunk_type=ChunkType.PARENT,
        text="PARENT TEXT",
        token_count=2,
    )
    child = Chunk(
        id=new_id(),
        document_id=doc.id,
        tenant_id=sample_tenant.id,
        parent_id=parent.id,
        chunk_index=1,
        page_number=1,
        chunk_type=ChunkType.CHILD,
        text="child text",
        token_count=2,
        section="Introduction",
    )
    await c_repo.add_many([parent, child])
    await db_session.commit()

    chunk_list = await c_repo.list_for_document(sample_tenant.id, doc.id)
    assert len(chunk_list) == 2
    parents = await c_repo.get_parents(sample_tenant.id, [child.id])
    assert parent.id in parents

    count = await c_repo.delete_document(sample_tenant.id, doc.id)
    assert count == 2


async def test_job_lifecycle(db_session: AsyncSession, sample_tenant: Tenant, sample_user: User) -> None:
    j_repo = JobRepository(db_session)
    job = Job(
        id=new_id(),
        tenant_id=sample_tenant.id,
        user_id=sample_user.id,
        kind="ingest",
        status=JobStatus.PENDING,
        payload={"document_id": "abc"},
    )
    await j_repo.add(job)
    await db_session.commit()

    await j_repo.update_status(sample_tenant.id, job.id, JobStatus.PROCESSING, progress=10)
    fetched = await j_repo.get(sample_tenant.id, job.id)
    assert fetched is not None
    assert fetched.status == JobStatus.PROCESSING
    assert fetched.started_at is not None

    await j_repo.update_status(sample_tenant.id, job.id, JobStatus.FAILED, error="boom", progress=100)
    fetched = await j_repo.get(sample_tenant.id, job.id)
    assert fetched is not None
    assert fetched.error == "boom"
    assert fetched.finished_at is not None


async def test_document_versioning(
    db_session: AsyncSession, sample_tenant: Tenant, sample_user: User
) -> None:
    d_repo = DocumentRepository(db_session)
    sha = _hash("versioned-doc")
    doc = Document(
        id=new_id(),
        tenant_id=sample_tenant.id,
        owner_id=sample_user.id,
        filename="handbook_v1.pdf",
        original_filename="handbook.pdf",
        sha256=sha,
        page_count=12,
        upload_path="/data/handbook.pdf",
        metadata_={"author": "Acme"},
        status=DocStatus.UPLOADED,
        indexing_status=DocStatus.UPLOADED,
    )
    await d_repo.add(doc)
    await db_session.commit()
    assert doc.version == 1

    await d_repo.update(sample_tenant.id, doc.id, version=2, status=DocStatus.PROCESSING)
    updated = await d_repo.get(sample_tenant.id, doc.id)
    assert updated is not None
    assert updated.version == 2
    assert updated.status == DocStatus.PROCESSING
