from __future__ import annotations

import uuid
from collections.abc import AsyncIterable

from fastapi import APIRouter, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from app.api.deps import JobQueueDep
from app.services.job_queue import Job, JobStatus

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class CreateJobRequest(BaseModel):
    upload_id: str


class JobResponse(BaseModel):
    id: str
    uploadId: str
    status: str
    stage: str
    stageProgress: float
    progress: float
    error: str | None = None
    result: dict | None = None


def _to_response(job: Job) -> JobResponse:
    return JobResponse(
        id=job.id,
        uploadId=job.upload_id,
        status=job.status.value,
        stage=job.stage,
        stageProgress=job.stage_progress,
        progress=job.progress,
        error=job.error,
        result=job.result,
    )


@router.post("", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_job(req: CreateJobRequest, queue: JobQueueDep) -> JobResponse:
    """Enqueue a reconstruction job for a stored upload."""
    job = Job(id=uuid.uuid4().hex, upload_id=req.upload_id)
    await queue.enqueue(job)
    return _to_response(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, queue: JobQueueDep) -> JobResponse:
    job = await queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return _to_response(job)


@router.get("/{job_id}/events", response_class=EventSourceResponse)
async def job_events(
    job_id: str,
    queue: JobQueueDep,
) -> AsyncIterable[ServerSentEvent]:
    """Stream stage/progress updates for a job until it terminates."""
    if await queue.get(job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    event_id = 0
    async for snapshot in queue.subscribe(job_id):
        event_id += 1
        yield ServerSentEvent(data=snapshot, event="update", id=str(event_id))
        # subscribe yields the terminal snapshot itself; stop there.
        if snapshot["status"] in (JobStatus.DONE.value, JobStatus.FAILED.value):
            yield ServerSentEvent(event="done", id=str(event_id))
            return