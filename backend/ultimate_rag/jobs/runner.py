"""Job runner: inline vs queued ingestion dispatch.

When ``inline_worker`` is enabled (the default, and the only mode available
without Redis), ingestion runs in a background task so the API request
returns immediately. Otherwise a real RQ worker would dequeue and process
the job; the queue-backed path is a thin envelope here so the API route is
decoupled from the execution strategy.
"""

from __future__ import annotations

import asyncio
import logging

from ultimate_rag.core.config import get_settings
from ultimate_rag.db.connection import get_async_session_factory

logger = logging.getLogger("ultimate_rag.jobs")


class JobRunner:
    """Dispatches ingestion jobs. Implementations are settings-driven."""

    name = str("base")

    async def enqueue_ingestion(
        self,
        document_id: str,
        tenant_id: str,
        session,
        container,
    ) -> str:
        """Schedule an ingestion job and return its job id."""
        raise NotImplementedError


async def _execute_ingestion_job(job_id: str, tenant_id: str, document_id: str, container) -> None:
    """Run ingestion in a background task with its own DB session."""
    from ultimate_rag.core.ids import new_id
    from ultimate_rag.db.enums import JobStatus
    from ultimate_rag.db.repositories.jobs import JobRepository
    from ultimate_rag.ingestion.pipeline import build_ingestion_pipeline

    factory = get_async_session_factory()
    async with factory() as session:
        try:
            j_repo = JobRepository(session)
            await j_repo.update_status(tenant_id, job_id, JobStatus.PROCESSING)
            await session.commit()

            pipeline = await build_ingestion_pipeline(container)
            result = await pipeline.process(document_id, tenant_id, session)
            await j_repo.update_status(
                tenant_id,
                job_id,
                JobStatus.COMPLETED,
                result={"chunks_indexed": result.chunks_indexed, "pages": result.pages},
            )
        except Exception as exc:
            logger.exception("Ingestion job failed: %s", job_id)
            try:
                j_repo = JobRepository(session)
                await j_repo.update_status(tenant_id, job_id, JobStatus.FAILED, error=str(exc))
            except Exception:
                logger.exception("Failed to update job status for %s", job_id)
        finally:
            try:
                await session.commit()
            except Exception:
                logger.exception("Final commit failed for job %s", job_id)


class InlineJobRunner(JobRunner):
    """Runs ingestion in a bounded number of background tasks."""

    name = str("inline")

    def __init__(self, settings) -> None:
        self.settings = settings
        self._limit = max(1, int(getattr(settings, "inline_ingestion_concurrency", 1)))
        self._semaphore = asyncio.Semaphore(self._limit)
        self._active_tasks: set[asyncio.Task] = set()

    def _on_task_done(self, task: asyncio.Task) -> None:
        self._active_tasks.discard(task)

    async def _run_with_limit(self, job_id: str, tenant_id: str, document_id: str, container) -> None:
        async with self._semaphore:
            await _execute_ingestion_job(job_id, tenant_id, document_id, container)

    async def enqueue_ingestion(
        self,
        document_id: str,
        tenant_id: str,
        session,
        container,
    ) -> str:
        from ultimate_rag.core.ids import new_id
        from ultimate_rag.db.enums import JobStatus
        from ultimate_rag.db.models import Job
        from ultimate_rag.db.repositories.jobs import JobRepository

        job_id = new_id()
        j_repo = JobRepository(session)
        job = Job(
            id=job_id,
            tenant_id=tenant_id,
            user_id=None,
            kind=str("ingest"),
            status=JobStatus.PENDING,
            payload={"document_id": document_id},
        )
        await j_repo.add(job)
        await session.commit()

        task = asyncio.create_task(self._run_with_limit(job_id, tenant_id, document_id, container))
        self._active_tasks.add(task)
        task.add_done_callback(self._on_task_done)
        return job_id


def build_job_runner(settings):
    """Pick an inline or queue-backed runner based on settings."""
    if settings.inline_worker:
        return InlineJobRunner(settings)
    try:
        from ultimate_rag.jobs.queue_runner import QueueJobRunner

        return QueueJobRunner(settings)
    except ImportError:
        logger.warning("Queue worker requested but rq/redis unavailable; falling back to inline")
        return InlineJobRunner(settings)
    try:
        from ultimate_rag.jobs.queue_runner import QueueJobRunner

        return QueueJobRunner(settings)
    except ImportError:
        logger.warning("Queue worker requested but rq/redis unavailable; falling back to inline")
        return InlineJobRunner(settings)
    try:
        from ultimate_rag.jobs.queue_runner import QueueJobRunner

        return QueueJobRunner(settings)
    except ImportError:
        logger.warning("Queue worker requested but rq/redis unavailable; falling back to inline")
        return InlineJobRunner(settings)
