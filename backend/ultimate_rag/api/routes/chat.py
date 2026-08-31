"""Chat / conversational RAG routes.

``/chat`` returns a complete answer synchronously.
``/chat/stream`` streams answer tokens (NDJSON) as they are generated and
emits a final ``done`` message with citations + confidence.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ultimate_rag.auth.dependencies import CurrentUser
from ultimate_rag.core.metrics import inc, measure
from ultimate_rag.db.connection import get_session
from ultimate_rag.db.repositories.chunks import ChunkRepository
from ultimate_rag.generation.query_service import QueryService, build_query_service
from ultimate_rag.services.container import get_container

router = APIRouter()


async def make_text_loader(tenant_id: str, session):
    chunk_repo = ChunkRepository(session)

    async def _load(chunk_ids: list[str]) -> dict[str, str]:
        chunks_map = await chunk_repo.get_by_ids(tenant_id, chunk_ids)
        return {cid: (c.text or "") for cid, c in chunks_map.items()}

    return _load


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    query_id: str
    conversation_id: str | None = None
    answer: str
    confidence: float
    model: str
    citations: list[dict]


@router.post("/")
async def chat(
    payload: ChatRequest,
    current_user: CurrentUser,
    session=Depends(get_session),  # noqa: B008
) -> ChatResponse:
    tenant_id = current_user.tenant_id
    container = get_container()
    query_service: QueryService = await build_query_service(container)
    text_loader = await make_text_loader(tenant_id, session)
    with measure("chat.latency_ms"):
        inc("chat.requests")
        answer, query_id, _, conv_id = await query_service.answer(
            query=payload.query,
            tenant_id=tenant_id,
            session=session,
            user_id=current_user.id,
            conversation_id=payload.conversation_id,
            text_loader=text_loader,
        )
    inc("chat.responses.total", len(answer.citations))
    return ChatResponse(
        query_id=query_id,
        conversation_id=conv_id,
        answer=answer.text,
        confidence=answer.confidence,
        model=answer.model,
        citations=[c.to_dict() for c in answer.citations],
    )


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    current_user: CurrentUser,
    session=Depends(get_session),  # noqa: B008
) -> StreamingResponse:
    tenant_id = current_user.tenant_id
    container = get_container()
    query_service: QueryService = await build_query_service(container)
    text_loader = await make_text_loader(tenant_id, session)

    async def _event_stream():
        async for event in query_service.stream_answer(
            query=payload.query,
            tenant_id=tenant_id,
            session=session,
            user_id=current_user.id,
            conversation_id=payload.conversation_id,
            text_loader=text_loader,
        ):
            yield (json.dumps(event) + "\n").encode("utf-8")
            await asyncio.sleep(0)

    return StreamingResponse(_event_stream(), media_type="application/x-ndjson")
