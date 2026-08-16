from __future__ import annotations

import asyncio

import pytest

from app.core.config import Settings
from app.services.job_queue import (
    JOB_STAGES,
    Job,
    JobQueue,
    JobStatus,
    MemoryJobRepository,
)


@pytest.fixture()
def settings() -> Settings:
    return Settings(job_backend="memory", environment="test")


@pytest.fixture()
def queue(settings: Settings) -> JobQueue:
    return JobQueue(MemoryJobRepository(), settings)


async def _fast_worker(job: Job, progress) -> dict:
    for index, stage in enumerate(JOB_STAGES):
        await progress(stage, 0.5 + index, overall=(index + 1) / len(JOB_STAGES))
    return {"ok": True, "stages": JOB_STAGES}


async def _boom_worker(job: Job, progress) -> dict:
    await progress("analyzing", 0.4)
    raise RuntimeError("worker exploded")


async def test_lifecycle_queued_to_done(queue: JobQueue) -> None:
    queue._worker = _fast_worker
    queue.start()
    await queue.enqueue(Job(id="j1", upload_id="u1"))

    start = await queue.get("j1")
    assert start.status is JobStatus.QUEUED

    # give the worker a moment to run
    for _ in range(200):
        current = await queue.get("j1")
        if current and current.status == JobStatus.DONE:
            break
        await asyncio.sleep(0.005)

    done = await queue.get("j1")
    assert done is not None
    assert done.status is JobStatus.DONE
    assert done.progress == 1.0
    assert done.result == {"ok": True, "stages": JOB_STAGES}
    await queue.stop()


async def test_failure_sets_failed_state(queue: JobQueue) -> None:
    queue._worker = _boom_worker
    queue.start()
    await queue.enqueue(Job(id="j2", upload_id="u2"))

    for _ in range(200):
        current = await queue.get("j2")
        if current and current.status == JobStatus.FAILED:
            break
        await asyncio.sleep(0.005)

    failed = await queue.get("j2")
    assert failed is not None
    assert failed.status is JobStatus.FAILED
    assert "worker exploded" in (failed.error or "")
    await queue.stop()


async def test_progress_callbacks_surface_stages(queue: JobQueue) -> None:
    seen: list[str] = []

    async def recording_worker(job: Job, progress) -> dict:
        for stage in JOB_STAGES:
            await progress(stage, 1.0)
            seen.append(stage)
        return {}

    queue._worker = recording_worker
    queue.start()
    await queue.enqueue(Job(id="j3", upload_id="u3"))

    for _ in range(200):
        current = await queue.get("j3")
        if current and current.status == JobStatus.DONE:
            break
        await asyncio.sleep(0.005)

    assert seen == JOB_STAGES
    await queue.stop()


async def test_enqueue_and_get_roundtrip(queue: JobQueue) -> None:
    job = Job(id="j4", upload_id="u4")
    await queue.enqueue(job)
    assert await queue.get("j4") is not None
    await queue.repository.delete("j4")
    assert await queue.get("j4") is None


async def test_sse_subscribe_streams_to_terminal(queue: JobQueue) -> None:
    queue._worker = _fast_worker
    queue.start()
    await queue.enqueue(Job(id="j5", upload_id="u5"))

    snapshots = []
    async for snapshot in queue.subscribe("j5"):
        snapshots.append(snapshot)
        if snapshot["status"] == JobStatus.DONE.value:
            break

    assert len(snapshots) >= 1
    assert snapshots[-1]["status"] == JobStatus.DONE.value
    await queue.stop()