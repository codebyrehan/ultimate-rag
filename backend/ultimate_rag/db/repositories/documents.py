from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ultimate_rag.db.enums import DocStatus
from ultimate_rag.db.models import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, tenant_id: str, doc_id: str) -> Document | None:
        stmt = select(Document).where(
            Document.tenant_id == tenant_id,
            Document.id == doc_id,
            Document.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_sha(self, tenant_id: str, sha256: str) -> Document | None:
        stmt = select(Document).where(
            Document.tenant_id == tenant_id,
            Document.sha256 == sha256,
            Document.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self, tenant_id: str, statuses: list[DocStatus] | None = None, limit: int = 100, offset: int = 0
    ) -> list[Document]:
        stmt = (
            select(Document)
            .where(Document.tenant_id == tenant_id, Document.deleted_at.is_(None))
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if statuses:
            stmt = stmt.where(Document.status.in_(statuses))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, document: Document) -> Document:
        self.session.add(document)
        await self.session.flush()
        return document

    async def update(self, tenant_id: str, doc_id: str, **fields: Any) -> Document:
        stmt = (
            update(Document)
            .where(
                Document.tenant_id == tenant_id,
                Document.id == doc_id,
                Document.deleted_at.is_(None),
            )
            .values(**fields)
            .execution_options(synchronize_session="fetch")
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get(tenant_id, doc_id)  # type: ignore[return-value]

    async def soft_delete(self, tenant_id: str, doc_id: str) -> None:
        stmt = (
            update(Document)
            .where(
                Document.tenant_id == tenant_id,
                Document.id == doc_id,
                Document.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now(UTC))
        )
        await self.session.execute(stmt)

    async def delete_all_tenant(self, tenant_id: str) -> int:
        stmt = delete(Document).where(Document.tenant_id == tenant_id, Document.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0) if isinstance(result, CursorResult) else 0

    async def commit(self) -> None:
        await self.session.commit()
