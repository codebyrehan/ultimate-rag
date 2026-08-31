"""RQ-backed job runner (used when ``inline_worker=False`` and Redis is up).

This runner is lazy: it only connects to Redis when enqueued a job, so the
package imports cleanly in offline/CI environments where Redis is absent.
The inline runner is the default fallback.
"""

from __future__ import annotations

import logging

from rq import Queue

from ultimate_rag.jobs.runner import JobRunner

logger = logging.getLogger("ultimate_rag.jobs.queue")


class QueueJobRunner(JobRunner):
    """Dispatch ingestion jobs to an RQ worker via Redis."""

    name = "rq"

    def __init__(self, settings) -> None:
        self.settings = settings
        self._queue: Queue | None = None
        self._redis_url = settings.redis_url

    def _get_queue(self):
        if self._queue is None:
            import redis
            from rq import Queue

            conn = redis.from_url(self._redis_url)
            self._queue = Queue("ingest", connection=conn)
        return self._queue

    async def enqueue_ingestion(
        self,
        document_id: str,
        tenant_id: str,
        session,
        container,
    ) -> str:
        q = self._get_queue()
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
            kind="ingest",
            status=JobStatus.PENDING,
            payload={"document_id": document_id, "redis_url": self._redis_url},
        )
        await j_repo.add(job)
        await session.commit()

        q.enqueue(
            "ultimate_rag.jobs.worker.process_ingestion",
            args=(document_id, tenant_id, job_id, self._redis_url),
            job_timeout="1h",
        )
        return job_id
