"""Regression tests for inline ingestion concurrency limiting."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ultimate_rag.core.config import Settings
from ultimate_rag.jobs.runner import InlineJobRunner


def _make_runner(concurrency: int = 2):
    settings = Settings(inline_ingestion_concurrency=concurrency, inline_worker=True)
    return InlineJobRunner(settings)


@pytest.fixture
def _patch_job_repository():
    """Patch JobRepository with a mock that records adds."""
    import ultimate_rag.jobs.runner as runner_mod
    from ultimate_rag.db.repositories.jobs import JobRepository as RealJR

    repo_mock = MagicMock()
    repo_mock.add = AsyncMock()
    repo_mock.update_status = AsyncMock()
    runner_mod.JobRepository = lambda s: repo_mock
    yield repo_mock
    runner_mod.JobRepository = RealJR


def _make_session():
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    return session


def _get_background_task(runner):
    """Return the single active background task, or None."""
    tasks = list(runner._active_tasks)
    assert len(tasks) <= 1, "Expected at most one active background task"
    return tasks[0] if tasks else None


@pytest.mark.asyncio
async def test_concurrency_limit_is_respected(_patch_job_repository):
    """Only N ingestion jobs may execute concurrently; extras wait."""
    runner = _make_runner(concurrency=2)
    import ultimate_rag.jobs.runner as runner_mod

    original = runner_mod._execute_ingestion_job
    start_gates = [asyncio.Event() for _ in range(4)]
    release_gate = asyncio.Event()
    execution_order: list[str] = []
    call_count = 0

    async def side_effect(job_id, tenant_id, document_id, container):
        nonlocal call_count
        idx = call_count
        call_count += 1
        execution_order.append(f"start-{idx}")
        start_gates[idx].set()
        await release_gate.wait()
        execution_order.append(f"end-{idx}")

    runner_mod._execute_ingestion_job = side_effect
    try:
        session = _make_session()
        tasks = [
            asyncio.create_task(runner.enqueue_ingestion(f"doc-{i}", "t1", session, None))
            for i in range(4)
        ]
        # Wait for first two tasks to start (concurrency=2)
        await asyncio.wait_for(start_gates[0].wait(), timeout=2.0)
        await asyncio.wait_for(start_gates[1].wait(), timeout=2.0)
        # The third and fourth should NOT have started yet
        assert not start_gates[2].is_set()
        assert not start_gates[3].is_set()

        # Release the semaphore slots
        release_gate.set()
        await asyncio.sleep(0.05)
        await asyncio.gather(*tasks)
        await asyncio.sleep(0.05)
        assert len(execution_order) == 8  # 4 starts + 4 ends
    finally:
        runner_mod._execute_ingestion_job = original


@pytest.mark.asyncio
async def test_semaphore_released_on_success(_patch_job_repository):
    """Semaphore slot is released after successful ingestion."""
    runner = _make_runner(concurrency=1)
    import ultimate_rag.jobs.runner as runner_mod

    original = runner_mod._execute_ingestion_job
    started = asyncio.Event()

    async def mock_execute(job_id, tenant_id, document_id, container):
        started.set()
        await asyncio.sleep(0.1)

    runner_mod._execute_ingestion_job = mock_execute
    try:
        session = _make_session()
        assert runner._semaphore.locked() is False
        await runner.enqueue_ingestion("doc-1", "t1", session, None)
        bg = _get_background_task(runner)
        assert bg is not None
        await asyncio.wait_for(started.wait(), timeout=2.0)
        assert runner._semaphore.locked() is True
        await bg
        assert runner._semaphore.locked() is False
    finally:
        runner_mod._execute_ingestion_job = original


@pytest.mark.asyncio
async def test_semaphore_released_on_failure(_patch_job_repository):
    """Semaphore slot is released after failed ingestion."""
    runner = _make_runner(concurrency=1)
    import ultimate_rag.jobs.runner as runner_mod

    original = runner_mod._execute_ingestion_job
    started = asyncio.Event()

    async def mock_execute(job_id, tenant_id, document_id, container):
        started.set()
        await asyncio.sleep(0.01)
        raise RuntimeError("ingestion boom")

    runner_mod._execute_ingestion_job = mock_execute
    try:
        session = _make_session()
        await runner.enqueue_ingestion("doc-1", "t1", session, None)
        bg = _get_background_task(runner)
        assert bg is not None
        await asyncio.wait_for(started.wait(), timeout=2.0)
        assert runner._semaphore.locked() is True
        with pytest.raises(RuntimeError):
            await bg
        assert runner._semaphore.locked() is False
    finally:
        runner_mod._execute_ingestion_job = original


@pytest.mark.asyncio
async def test_semaphore_released_on_cancellation(_patch_job_repository):
    """Semaphore slot is released if the background task is cancelled."""
    runner = _make_runner(concurrency=1)
    import ultimate_rag.jobs.runner as runner_mod

    original = runner_mod._execute_ingestion_job
    started = asyncio.Event()

    async def mock_execute(job_id, tenant_id, document_id, container):
        started.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            raise

    runner_mod._execute_ingestion_job = mock_execute
    try:
        session = _make_session()
        await runner.enqueue_ingestion("doc-1", "t1", session, None)
        bg = _get_background_task(runner)
        assert bg is not None
        await asyncio.wait_for(started.wait(), timeout=2.0)
        assert runner._semaphore.locked() is True
        bg.cancel()
        with pytest.raises(asyncio.CancelledError):
            await bg
        await asyncio.sleep(0.01)
        assert runner._semaphore.locked() is False
    finally:
        runner_mod._execute_ingestion_job = original


@pytest.mark.asyncio
async def test_task_references_are_cleaned_up(_patch_job_repository):
    """Active task set does not retain completed tasks."""
    runner = _make_runner(concurrency=1)
    import ultimate_rag.jobs.runner as runner_mod

    original = runner_mod._execute_ingestion_job
    started = asyncio.Event()

    async def mock_execute(job_id, tenant_id, document_id, container):
        started.set()
        await asyncio.sleep(0.05)

    runner_mod._execute_ingestion_job = mock_execute
    try:
        session = _make_session()
        await runner.enqueue_ingestion("doc-1", "t1", session, None)
        bg = _get_background_task(runner)
        assert bg is not None
        await asyncio.wait_for(started.wait(), timeout=2.0)
        assert len(runner._active_tasks) == 1
        await bg
        # Allow done callback to fire
        await asyncio.sleep(0.05)
        assert len(runner._active_tasks) == 0
    finally:
        runner_mod._execute_ingestion_job = original


@pytest.mark.asyncio
async def test_chat_retrieval_not_blocked_by_ingestion():
    """Chat retrieval to_thread() calls are not starved by bounded ingestion."""
    runner = _make_runner(concurrency=1)
    import ultimate_rag.jobs.runner as runner_mod

    original = runner_mod._execute_ingestion_job
    started = asyncio.Event()

    async def slow_ingestion(job_id, tenant_id, document_id, container):
        started.set()
        await asyncio.sleep(0.2)

    runner_mod._execute_ingestion_job = slow_ingestion
    try:
        session = _make_session()
        await runner.enqueue_ingestion("doc-1", "t1", session, None)
        bg = _get_background_task(runner)
        assert bg is not None
        await asyncio.wait_for(started.wait(), timeout=2.0)

        chat_result = await asyncio.to_thread(lambda: "chat-ok")
        assert chat_result == "chat-ok"
    finally:
        runner_mod._execute_ingestion_job = original
        if bg is not None:
            bg.cancel()
            with pytest.raises(asyncio.CancelledError):
                await bg


def test_default_concurrency_is_one():
    """Default inline_ingestion_concurrency should be conservative."""
    settings = Settings()
    assert settings.inline_ingestion_concurrency == 1
