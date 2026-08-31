from __future__ import annotations

from sqlalchemy import select

from ultimate_rag.db.models import Query


class QueryRepository:
    def __init__(self, session):
        self.session = session

    async def add(self, query: Query) -> Query:
        self.session.add(query)
        await self.session.flush()
        return query

    async def get(self, tenant_id: str, query_id: str) -> Query | None:
        stmt = select(Query).where(Query.tenant_id == tenant_id, Query.id == query_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_latency(self, tenant_id: str, query_id: str, latency_ms: int) -> None:
        from sqlalchemy import update

        stmt = (
            update(Query)
            .where(Query.tenant_id == tenant_id, Query.id == query_id)
            .values(latency_ms=latency_ms)
            .execution_options(synchronize_session="fetch")
        )
        await self.session.execute(stmt)

    async def commit(self) -> None:
        await self.session.commit()
