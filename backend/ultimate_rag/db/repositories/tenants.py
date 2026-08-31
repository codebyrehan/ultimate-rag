from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ultimate_rag.db.models import Tenant


class TenantRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, tenant_id: str) -> Tenant | None:
        return await self.session.get(Tenant, {"id": tenant_id})

    async def add(self, tenant: Tenant) -> Tenant:
        self.session.add(tenant)
        await self.session.flush()
        return tenant

    async def commit(self) -> None:
        await self.session.commit()
