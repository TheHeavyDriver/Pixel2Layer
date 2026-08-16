from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.services.job_queue import JobQueue
from app.services.upload_service import UploadService


def get_upload_service(request: Request) -> UploadService:
    return request.app.state.upload_service


def get_job_queue(request: Request) -> JobQueue:
    return request.app.state.job_queue


UploadServiceDep = Annotated[UploadService, Depends(get_upload_service)]
JobQueueDep = Annotated[JobQueue, Depends(get_job_queue)]