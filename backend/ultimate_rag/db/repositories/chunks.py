from __future__ import annotations

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ultimate_rag.db.models import Chunk


class ChunkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, chunk: Chunk) -> Chunk:
        self.session.add(chunk)
        await self.session.flush()
        return chunk

    async def add_many(self, chunks: list[Chunk]) -> None:
        self.session.add_all(chunks)
        await self.session.flush()

    async def list_for_document(self, tenant_id: str, document_id: str) -> list[Chunk]:
        stmt = (
            select(Chunk)
            .where(
                Chunk.tenant_id == tenant_id,
                Chunk.document_id == document_id,
            )
            .order_by(Chunk.chunk_index)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ids(self, tenant_id: str, chunk_ids: list[str]) -> dict[str, Chunk]:
        """Return chunks by id, tenant-scoped (for text hydration / parent expansion)."""
        if not chunk_ids:
            return {}
        stmt = select(Chunk).where(Chunk.tenant_id == tenant_id, Chunk.id.in_(chunk_ids))
        result = await self.session.execute(stmt)
        return {c.id: c for c in result.scalars().all()}

    async def get_parents(self, tenant_id: str, chunk_ids: list[str]) -> dict[str, Chunk]:
        """Return parent chunks for the given child chunk ids."""
        from ultimate_rag.db.models import Chunk as C

        # Resolve parent ids of the given child chunks first.
        stmt = select(C.parent_id).where(
            C.tenant_id == tenant_id, C.id.in_(chunk_ids), C.chunk_type == "child"
        )
        result = await self.session.execute(stmt)
        parent_ids = [r for (r,) in result if r]
        if not parent_ids:
            return {}
        parent_stmt = select(C).where(C.tenant_id == tenant_id, C.id.in_(parent_ids))
        parent_result = await self.session.execute(parent_stmt)
        parents = {c.id: c for c in parent_result.scalars().all()}
        return parents

    async def delete_document(self, tenant_id: str, document_id: str) -> int:
        stmt = delete(Chunk).where(Chunk.tenant_id == tenant_id, Chunk.document_id == document_id)
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0) if isinstance(result, CursorResult) else 0

    async def delete_tenant(self, tenant_id: str) -> int:
        stmt = delete(Chunk).where(Chunk.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0) if isinstance(result, CursorResult) else 0

    async def commit(self) -> None:
        await self.session.commit()
