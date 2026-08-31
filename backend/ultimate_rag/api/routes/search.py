"""Search / query routes.

Exposes the end-to-end RAG query endpoint: retrieval (dense + BM25 -> RRF ->
rerank -> compress) -> answer synthesis -> evidence persistence. Tenant is
resolved from a query parameter or defaults to the configured tenant.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ultimate_rag.auth.dependencies import CurrentUser
from ultimate_rag.db.connection import get_session
from ultimate_rag.db.repositories.chunks import ChunkRepository
from ultimate_rag.generation.query_service import QueryService, build_query_service
from ultimate_rag.services.container import get_container

router = APIRouter()


async def make_text_loader(tenant_id: str, session: AsyncSession):
    chunk_repo = ChunkRepository(session)

    async def _load(chunk_ids: list[str]) -> dict[str, str]:
        chunks_map = await chunk_repo.get_by_ids(tenant_id, chunk_ids)
        return {cid: (c.text or "") for cid, c in chunks_map.items()}

    return _load


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    conversation_id: str | None = None


class CitationResponse(BaseModel):
    chunk_id: str
    label: str
    score: float
    doc_filename: str
    page_number: int

    verified: bool = False
    supported_fraction: float = 0.0


class SearchResponse(BaseModel):
    query_id: str
    conversation_id: str | None = None
    answer: str
    confidence: float
    model: str
    citations: list[CitationResponse]
    verified: bool = False
    supported_fraction: float = 0.0


@router.post("/query", response_model=SearchResponse, status_code=status.HTTP_200_OK)
async def search_query(
    payload: SearchRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> SearchResponse:
    tenant_id = current_user.tenant_id
    container = get_container()
    query_service: QueryService = await build_query_service(container)
    text_loader = await make_text_loader(tenant_id, session)
    answer, query_id, report, conv_id = await query_service.answer(
        query=payload.query,
        tenant_id=tenant_id,
        session=session,
        user_id=current_user.id,
        conversation_id=payload.conversation_id,
        text_loader=text_loader,
    )
    verified = report is not None
    supported_fraction = report.supported_fraction if report else 0.0
    return SearchResponse(
        query_id=query_id,
        conversation_id=conv_id,
        answer=answer.text,
        confidence=answer.confidence,
        model=answer.model,
        citations=[
            CitationResponse(
                chunk_id=c.chunk_id,
                label=c.label,
                score=c.score,
                doc_filename=c.doc_filename,
                page_number=c.page_number,
            )
            for c in answer.citations
        ],
        verified=verified,
        supported_fraction=round(supported_fraction, 4) if report else 0.0,
    )
