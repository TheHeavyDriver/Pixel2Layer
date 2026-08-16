from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

import redis.asyncio as aioredis

from app.core.config import Settings


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


# From architecture.md §4.3
JOB_STAGES = [
    "uploading",
    "analyzing",
    "text",
    "shapes",
    "colors",
    "segmenting",
    "vectorizing",
    "building",
    "exporting",
]


@dataclass
class Job:
    id: str
    upload_id: str
    status: JobStatus = JobStatus.QUEUED
    stage: str = "uploading"
    stage_progress: float = 0.0  # 0..1 within the current stage
    progress: float = 0.0  # overall 0..1
    error: str | None = None
    result: dict[str, Any] | None = None
    retries: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class JobRepository:
    """Abstract job state store."""

    async def create(self, job: Job) -> None: ...
    async def get(self, job_id: str) -> Job | None: ...
    async def update(self, job: Job) -> None: ...
    async def delete(self, job_id: str) -> None: ...


class MemoryJobRepository(JobRepository):
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    async def create(self, job: Job) -> None:
        self._jobs[job.id] = job

    async def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def update(self, job: Job) -> None:
        self._jobs[job.id] = job

    async def delete(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)


class RedisJobRepository(JobRepository):
    """Redis-backed store; job JSON under `p2l:job:{id}` with no TTL (jobs must persist)."""

    KEY_PREFIX = "p2l:job:"

    def __init__(self, redis_url: str) -> None:
        self._redis: aioredis.Redis = aioredis.from_url(redis_url, decode_responses=True)

    async def create(self, job: Job) -> None:
        await self._redis.set(self.KEY_PREFIX + job.id, json.dumps(job.to_dict()))

    async def get(self, job_id: str) -> Job | None:
        raw = await self._redis.get(self.KEY_PREFIX + job_id)
        if raw is None:
            return None
        return Job(**json.loads(raw))

    async def update(self, job: Job) -> None:
        await self._redis.set(self.KEY_PREFIX + job.id, json.dumps(job.to_dict()))

    async def delete(self, job_id: str) -> None:
        await self._redis.delete(self.KEY_PREFIX + job_id)


class JobQueue:
    """Orchestrates async reconstruction jobs with progress broadcast to SSE listeners."""

    def __init__(
        self,
        repository: JobRepository,
        settings: Settings,
        worker_impl=None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        # do_work receives (job, progress_callback); returns result dict or raises
        self._worker = worker_impl or self._default_worker
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._events: dict[str, list[asyncio.Queue]] = {}
        self._worker_task: asyncio.Task | None = None

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._run_worker())

    async def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            await asyncio.gather(self._worker_task, return_exceptions=True)
            self._worker_task = None

    async def enqueue(self, job: Job) -> Job:
        await self.repository.create(job)
        await self._bump(job)
        await self._queue.put(job.id)
        return job

    async def get(self, job_id: str) -> Job | None:
        return await self.repository.get(job_id)

    async def get_many(self, job_ids: list[str]) -> list[Job | None]:
        return [await self.repository.get(job_id) for job_id in job_ids]

    # -- internal processing ------------------------------------------------
    async def _run_worker(self) -> None:
        while True:
            job_id = await self._queue.get()
            job = await self.repository.get(job_id)
            if job is None:
                continue
            try:
                await self._process(job)
            except Exception as exc:  # noqa: BLE001 - worker must not die
                await self._fail(job, str(exc))
            finally:
                self._queue.task_done()

    async def _process(self, job: Job) -> None:
        job.status = JobStatus.RUNNING
        await self._bump(job)

        async def progress(stage: str, stage_progress: float, overall: float | None = None) -> None:
            job.stage = stage
            job.stage_progress = stage_progress
            job.progress = overall if overall is not None else job.progress
            await self._bump(job)

        job.result = await self._worker(job, progress)
        job.status = JobStatus.DONE
        job.progress = 1.0
        await self._bump(job)

    async def _fail(self, job: Job, message: str) -> None:
        job.status = JobStatus.FAILED
        job.error = message
        await self._bump(job)

    async def _bump(self, job: Job) -> None:
        await self.repository.update(job)
        await self._publish(job.id, job.to_dict())

    # -- SSE event streaming ------------------------------------------------
    async def subscribe(self, job_id: str) -> AsyncIterator[dict[str, Any]]:
        """Yield job snapshots until the job reaches a terminal state and the backlog drains."""
        q: asyncio.Queue = asyncio.Queue(maxsize=128)
        self._events.setdefault(job_id, []).append(q)
        try:
            job = await self.repository.get(job_id)
            if job is not None:
                await q.put(job.to_dict())
            while True:
                snapshot = await q.get()
                yield snapshot
                if snapshot["status"] in (JobStatus.DONE.value, JobStatus.FAILED.value):
                    break
        finally:
            listeners = self._events.get(job_id)
            if listeners:
                listeners.remove(q)
                if not listeners:
                    self._events.pop(job_id, None)

    async def _publish(self, job_id: str, snapshot: dict[str, Any]) -> None:
        for q in list(self._events.get(job_id, [])):
            try:
                q.put_nowait(snapshot)
            except asyncio.QueueFull:
                pass  # slow consumer: drop snapshot, next poll event covers it

    # -- default no-op worker for v0.1 (pipeline impl lands in v0.2) --------
    async def _default_worker(self, job: Job, progress) -> dict[str, Any]:
        # Simulated stages so the full upload→progress→result flow works end to end.
        for index, stage in enumerate(JOB_STAGES):
            await asyncio.sleep(0.05)
            await progress(stage, 1.0, overall=(index + 1) / len(JOB_STAGES))
        return {"message": "reconstruction pipeline stub", "upload_id": job.upload_id}


def build_repository(settings: Settings) -> JobRepository:
    if settings.job_backend == "redis":
        return RedisJobRepository(settings.redis_url)
    return MemoryJobRepository()