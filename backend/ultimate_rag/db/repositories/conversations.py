from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ultimate_rag.db.models import Conversation, Message


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, tenant_id: str, conv_id: str) -> Conversation | None:
        stmt = select(Conversation).where(Conversation.tenant_id == tenant_id, Conversation.id == conv_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self, tenant_id: str, user_id: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.tenant_id == tenant_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if user_id:
            stmt = stmt.where(Conversation.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, conversation: Conversation) -> Conversation:
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def commit(self) -> None:
        await self.session.commit()


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, message: Message) -> Message:
        self.session.add(message)
        await self.session.flush()
        return message

    async def list_for_conversation(self, tenant_id: str, conversation_id: str) -> list[Message]:
        stmt = (
            select(Message)
            .where(
                Message.tenant_id == tenant_id,
                Message.conversation_id == conversation_id,
            )
            .order_by(Message.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
