"""Document management routes.

Upload a validated PDF -> store it (opaque server id) -> create a Document
row -> enqueue ingestion (inline or via RQ). List and get endpoints expose
status. Files are never written under user-supplied names.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ultimate_rag.auth.dependencies import CurrentUser
from ultimate_rag.core.config import get_settings
from ultimate_rag.core.ids import new_id
from ultimate_rag.core.security import sanitize_filename, sha256_bytes
from ultimate_rag.db.connection import get_session
from ultimate_rag.db.enums import DocStatus
from ultimate_rag.db.models import Document
from ultimate_rag.db.repositories.chunks import ChunkRepository
from ultimate_rag.db.repositories.documents import DocumentRepository
from ultimate_rag.jobs.runner import build_job_runner
from ultimate_rag.services.container import get_container
from ultimate_rag.services.factory import build_storage

logger = logging.getLogger("ultimate_rag.api.routes.docs")
router = APIRouter()


class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    page_count: int
    sha256: str
    version: int
    status: str
    indexing_status: str
    created_at: str | None = None
    chunks: list[dict] = []


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    current_user: CurrentUser,
    file: UploadFile = File(...),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> DocumentResponse:
    settings = get_settings()
    tenant_id = current_user.tenant_id
    if file.content_type and file.content_type not in settings.allowed_mime_list():
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}",
        )
    data = await file.read()
    if len(data) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds maximum allowed size",
        )
    if not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is not a valid PDF")

    storage = build_storage(settings)
    stored = await storage.save(file.filename or "upload.pdf", data)
    sha = sha256_bytes(data)

    d_repo = DocumentRepository(session)
    existing = await d_repo.get_by_sha(tenant_id, sha)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document already uploaded: {existing.id}",
        )

    doc = Document(
        id=new_id(),
        tenant_id=tenant_id,
        owner_id=current_user.id,
        filename=stored.filename,
        original_filename=sanitize_filename(file.filename or "upload.pdf"),
        sha256=sha,
        page_count=0,
        upload_path=stored.path,
        file_id=stored.file_id,
        status=DocStatus.UPLOADED,
        indexing_status=DocStatus.UPLOADED,
    )
    await d_repo.add(doc)
    await session.commit()

    runner = build_job_runner(settings)
    job_id = await runner.enqueue_ingestion(doc.id, tenant_id, session, get_container())
    doc.metadata_ = {"job_id": job_id}
    await session.commit()
    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        page_count=0,
        sha256=sha,
        version=1,
        status="processing",
        indexing_status="processing",
        created_at=None,
        chunks=[],
    )


class DocumentDetailResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    page_count: int
    sha256: str
    version: int
    status: str
    indexing_status: str
    created_at: str | None = None
    chunks: list[dict] = []


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[DocumentResponse]:
    repo = DocumentRepository(session)
    chunk_repo = ChunkRepository(session)
    docs = await repo.list(current_user.tenant_id, limit=limit, offset=offset)
    result: list[DocumentResponse] = []
    for d in docs:
        chunks = await chunk_repo.list_for_document(current_user.tenant_id, d.id)
        result.append(
            DocumentResponse(
                id=d.id,
                filename=d.filename,
                original_filename=d.original_filename,
                page_count=d.page_count,
                sha256=d.sha256,
                version=d.version,
                status=d.status.value if hasattr(d.status, "value") else d.status,
                indexing_status=d.indexing_status.value
                if hasattr(d.indexing_status, "value")
                else d.indexing_status,
                created_at=d.created_at.isoformat() if d.created_at else None,
                chunks=[{"id": c.id, "page_number": c.page_number, "section": c.section} for c in chunks],
            )
        )
    return result


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> DocumentDetailResponse:
    repo = DocumentRepository(session)
    d = await repo.get(current_user.tenant_id, document_id)
    if d is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    chunk_repo = ChunkRepository(session)
    chunks = await chunk_repo.list_for_document(current_user.tenant_id, d.id)
    return DocumentDetailResponse(
        id=d.id,
        filename=d.filename,
        original_filename=d.original_filename,
        page_count=d.page_count,
        sha256=d.sha256,
        version=d.version,
        status=d.status.value if hasattr(d.status, "value") else d.status,
        indexing_status=d.indexing_status.value
        if hasattr(d.indexing_status, "value")
        else d.indexing_status,
        created_at=d.created_at.isoformat() if d.created_at else None,
        chunks=[{"id": c.id, "page_number": c.page_number, "section": c.section} for c in chunks],
    )


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    settings = get_settings()
    repo = DocumentRepository(session)
    d = await repo.get(current_user.tenant_id, document_id)
    if d is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not d.file_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file not found")
    storage = build_storage(settings)
    data = await storage.read(d.file_id)
    return StreamingResponse(
        iter([data]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{d.original_filename}"'},
    )


@router.delete("/{document_id}", response_model=dict)
async def delete_document(
    document_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict:
    settings = get_settings()
    tenant_id = current_user.tenant_id
    repo = DocumentRepository(session)
    d = await repo.get(tenant_id, document_id)
    if d is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    container = get_container()
    vector_store = container.get("vector_store")
    bm25 = container.get("bm25")
    storage = build_storage(settings)

    await vector_store.adelete_document(d.id, tenant_id)
    bm25.delete_document(d.id, tenant_id)
    if d.file_id:
        await storage.delete(d.file_id)

    await repo.soft_delete(tenant_id, d.id)
    await session.commit()
    logger.info("Deleted document %s for tenant %s", d.id, tenant_id)
    return {"document_id": document_id, "deleted": True}
