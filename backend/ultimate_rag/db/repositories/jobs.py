from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ultimate_rag.db.enums import JobStatus
from ultimate_rag.db.models import Job


class JobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, tenant_id: str, job_id: str) -> Job | None:
        stmt = select(Job).where(Job.tenant_id == tenant_id, Job.id == job_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, job: Job) -> Job:
        self.session.add(job)
        await self.session.flush()
        return job

    async def list_for_tenant(self, tenant_id: str, limit: int = 50, offset: int = 0) -> list[Job]:
        stmt = (
            select(Job)
            .where(Job.tenant_id == tenant_id)
            .order_by(Job.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        tenant_id: str,
        job_id: str,
        status: JobStatus,
        error: str | None = None,
        result: dict | None = None,
        progress: int | None = None,
    ) -> None:
        vals: dict = {"status": status}
        if error is not None:
            vals["error"] = error
        if result is not None:
            vals["result"] = result
        if progress is not None:
            vals["progress"] = progress
        if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELED):
            vals["finished_at"] = datetime.now(UTC)
        elif status == JobStatus.PROCESSING:
            vals["started_at"] = datetime.now(UTC)
        stmt = (
            update(Job)
            .where(Job.tenant_id == tenant_id, Job.id == job_id)
            .values(**vals)
            .execution_options(synchronize_session="fetch")
        )
        await self.session.execute(stmt)

    async def commit(self) -> None:
        await self.session.commit()
