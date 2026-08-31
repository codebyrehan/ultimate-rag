"""RQ worker entry point.

Run with ``rq worker ingest`` from the ``backend/`` directory. The worker
function here rebuilds a fresh service container (models are loaded once per
worker process via the container cache) and processes one document.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("ultimate_rag.jobs.worker")


def process_ingestion(document_id: str, tenant_id: str, job_id: str, redis_url: str) -> dict:
    """RQ job: ingest a single document to completion."""
    import asyncio

    from ultimate_rag.core.config import get_settings
    from ultimate_rag.db.connection import get_async_session_factory
    from ultimate_rag.db.enums import JobStatus
    from ultimate_rag.db.repositories.jobs import JobRepository
    from ultimate_rag.ingestion.pipeline import build_ingestion_pipeline
    from ultimate_rag.services.container import get_container, reset_container

    get_settings()
    reset_container()
    container = get_container()
    factory = get_async_session_factory()

    async def _run() -> dict:
        async with factory() as session:
            j_repo = JobRepository(session)
            await j_repo.update_status(tenant_id, job_id, JobStatus.PROCESSING)
            await session.commit()
            try:
                pipeline = await build_ingestion_pipeline(container)
                result = await pipeline.process(document_id, tenant_id, session)
                await j_repo.update_status(
                    tenant_id,
                    job_id,
                    JobStatus.COMPLETED,
                    result={"chunks_indexed": result.chunks_indexed, "pages": result.pages},
                )
                await session.commit()
                return {"job_id": job_id, "chunks": result.chunks_indexed}
            except Exception as exc:
                logger.exception("Ingestion job %s failed", job_id)
                await j_repo.update_status(tenant_id, job_id, JobStatus.FAILED, error=str(exc))
                await session.commit()
                return {"job_id": job_id, "error": str(exc)}

    return asyncio.run(_run())
