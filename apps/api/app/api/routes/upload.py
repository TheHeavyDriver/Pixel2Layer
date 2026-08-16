from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import UploadServiceDep
from app.services.upload_service import (
    InvalidUploadError,
    UploadTooLargeError,
)

router = APIRouter(prefix="/api/upload", tags=["upload"])


class UploadResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    upload_id: str = Field(alias="uploadId")
    key: str
    url: str
    content_type: str = Field(alias="contentType")
    extension: str
    size_bytes: int = Field(alias="sizeBytes")
    sha256: str


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile, service: UploadServiceDep
) -> UploadResponse:
    """Validate and store an uploaded image; returns the object reference."""
    try:
        result = await service.store(file)
    except InvalidUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    return UploadResponse.model_validate(result.__dict__)