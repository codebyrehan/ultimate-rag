"""Tenant-scoped repository layer.

Every repository method that scopes by tenant/user takes a ``tenant_id``
argument and applies it as a hard filter, so tenant isolation cannot be
bypassed at the call site.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model: type[T]):
        self.session = session
        self.model = model

    async def add(self, obj: T) -> T:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get_by_id(self, id: str) -> T | None:
        return await self.session.get(self.model, {"id": id})

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def refresh(self, obj: T) -> None:
        await self.session.refresh(obj)
