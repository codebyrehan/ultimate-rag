from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ultimate_rag.db.models import Evidence


class EvidenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, evidence: Evidence) -> Evidence:
        self.session.add(evidence)
        await self.session.flush()
        return evidence

    async def add_many(self, evidences: list[Evidence]) -> None:
        self.session.add_all(evidences)
        await self.session.flush()

    async def list_for_query(self, query_id: str) -> list[Evidence]:
        stmt = select(Evidence).where(Evidence.query_id == query_id).order_by(Evidence.rank)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
