"""Job status routes.

Exposes ingestion job state (pending/processing/completed/failed) and allows
listing recent jobs for the authenticated tenant. Tenant scoping is enforced
server-side via the JWT-derived ``CurrentUser``.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ultimate_rag.auth.dependencies import CurrentUser
from ultimate_rag.db.connection import get_session
from ultimate_rag.db.enums import JobStatus
from ultimate_rag.db.repositories.jobs import JobRepository

router = APIRouter()


class JobResponse(BaseModel):
    job_id: str
    kind: str
    status: str
    progress: int
    error: str | None = None
    result: dict = {}
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    current_user: CurrentUser,
    session=Depends(get_session),  # noqa: B008
) -> JobResponse:
    repo = JobRepository(session)
    job = await repo.get(current_user.tenant_id, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobResponse(
        job_id=job.id,
        kind=job.kind,
        status=job.status.value if hasattr(job.status, "value") else job.status,
        progress=job.progress,
        error=job.error,
        result=job.result or {},
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@router.get("/", response_model=list[JobResponse])
async def list_jobs(
    current_user: CurrentUser,
    session=Depends(get_session),  # noqa: B008
) -> list[JobResponse]:
    repo = JobRepository(session)
    jobs = await repo.list_for_tenant(current_user.tenant_id)
    return [
        JobResponse(
            job_id=j.id,
            kind=j.kind,
            status=j.status.value if hasattr(j.status, "value") else j.status,
            progress=j.progress,
            error=j.error,
            result=j.result or {},
            created_at=j.created_at,
            started_at=j.started_at,
            finished_at=j.finished_at,
        )
        for j in jobs
    ]


@router.delete("/{job_id}", response_model=dict)
async def cancel_job(
    job_id: str,
    current_user: CurrentUser,
    session=Depends(get_session),  # noqa: B008
) -> dict:
    repo = JobRepository(session)
    job = await repo.get(current_user.tenant_id, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status not in (JobStatus.PENDING, JobStatus.PROCESSING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job cannot be canceled (current status: {job.status})",
        )
    await repo.update_status(current_user.tenant_id, job_id, JobStatus.CANCELED)
    await session.commit()
    return {"job_id": job_id, "canceled": True}
