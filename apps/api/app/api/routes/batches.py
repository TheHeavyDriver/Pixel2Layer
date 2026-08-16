from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserDep, JobQueueDep, StoreDep
from app.services.job_queue import Job
from app.services.store import Batch

router = APIRouter(prefix="/api/batches", tags=["batches"])


class CreateBatchRequest(BaseModel):
    uploadIds: list[str] = Field(..., min_length=1, max_length=50)


class BatchJobResponse(BaseModel):
    id: str
    uploadId: str
    status: str
    stage: str
    progress: float


class BatchResponse(BaseModel):
    id: str
    jobs: list[BatchJobResponse]


def _job_response(job: Job) -> BatchJobResponse:
    return BatchJobResponse(
        id=job.id,
        uploadId=job.upload_id,
        status=job.status.value,
        stage=job.stage,
        progress=job.progress,
    )


@router.post("", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(
    req: CreateBatchRequest,
    user: CurrentUserDep,
    queue: JobQueueDep,
    store: StoreDep,
) -> BatchResponse:
    jobs: list[Job] = []
    for upload_id in req.uploadIds:
        job = Job(id=uuid.uuid4().hex, upload_id=upload_id)
        await queue.enqueue(job)
        jobs.append(job)
    batch = await store.create_batch(owner_id=user.id, job_ids=[j.id for j in jobs])
    return BatchResponse(id=batch.id, jobs=[_job_response(j) for j in jobs])


@router.get("/{batch_id}", response_model=BatchResponse)
async def get_batch(
    batch_id: str,
    user: CurrentUserDep,
    queue: JobQueueDep,
    store: StoreDep,
) -> BatchResponse:
    batch: Batch | None = await store.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="batch not found")
    jobs = [_job_response(j) for j in await queue.get_many(batch.job_ids) if j is not None]
    return BatchResponse(id=batch.id, jobs=jobs)