"""Conversation management routes.

List, retrieve, and delete conversations.  Messages are persisted as part of
the chat lifecycle; this route surface lets clients enumerate their
conversations and inspect message history.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ultimate_rag.auth.dependencies import CurrentUser
from ultimate_rag.db.connection import get_session
from ultimate_rag.db.repositories.conversations import ConversationRepository, MessageRepository

router = APIRouter()


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class ConversationResponse(BaseModel):
    id: str
    title: str | None = None
    created_at: str
    updated_at: str
    messages: list[MessageResponse] = []


@router.get("/", response_model=list[ConversationResponse], status_code=status.HTTP_200_OK)
async def list_conversations(
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[ConversationResponse]:
    tenant_id = current_user.tenant_id
    conv_repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)
    conversations = await conv_repo.list(tenant_id, user_id=current_user.id, limit=limit, offset=offset)
    result: list[ConversationResponse] = []
    for conv in conversations:
        msgs = await msg_repo.list_for_conversation(tenant_id, conv.id)
        result.append(
            ConversationResponse(
                id=conv.id,
                title=conv.title,
                created_at=str(conv.created_at),
                updated_at=str(conv.updated_at),
                messages=[
                    MessageResponse(
                        id=m.id,
                        role=m.role,
                        content=m.content,
                        created_at=str(m.created_at),
                    )
                    for m in msgs
                ],
            )
        )
    return result


@router.get("/{conversation_id}", response_model=ConversationResponse, status_code=status.HTTP_200_OK)
async def get_conversation(
    conversation_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ConversationResponse:
    tenant_id = current_user.tenant_id
    conv_repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)
    conv = await conv_repo.get(tenant_id, conversation_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return ConversationResponse(
            id="",
            created_at="",
            updated_at="",
        )
    msgs = await msg_repo.list_for_conversation(tenant_id, conv.id)
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        created_at=str(conv.created_at),
        updated_at=str(conv.updated_at),
        messages=[
            MessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=str(m.created_at),
            )
            for m in msgs
        ],
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    tenant_id = current_user.tenant_id
    conv_repo = ConversationRepository(session)
    conv = await conv_repo.get(tenant_id, conversation_id)
    if conv is not None and conv.user_id == current_user.id:
        await session.delete(conv)
        await session.commit()
