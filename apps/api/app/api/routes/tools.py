from __future__ import annotations

import io
import uuid

import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, status
from PIL import Image
from pydantic import BaseModel, Field

from app.api.deps import UploadServiceDep
from app.schemas.scene_graph import SceneGraph
from app.services.grouping import LayerGrouper
from app.services.image_utils import load_image
from app.services.segmenter import build_segmenter

router = APIRouter(prefix="/api/tools", tags=["tools"])


class BackgroundRemovalResponse(BaseModel):
    url: str
    key: str
    width: int
    height: int


@router.post("/background-removal", response_model=BackgroundRemovalResponse)
async def background_removal(
    file: UploadFile,
    upload_service: UploadServiceDep,
) -> BackgroundRemovalResponse:
    """First-class background removal (backlog).

    Returns a masked PNG cutout of the foreground, stored under `assets/`.
    Uses the same pluggable segmenter as the pipeline, so results are
    labelled approximate in the associated metadata.
    """
    data = await file.read()
    try:
        image = load_image(data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="could not decode image"
        ) from exc

    segmenter = build_segmenter()
    regions = segmenter.segment(image)
    if not regions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="no foreground regions detected",
        )

    mask = np.zeros((image.height, image.width), dtype=np.uint8)
    for region in regions:
        top, left = region.y, region.x
        bottom, right = top + region.height, left + region.width
        sub = mask[top:bottom, left:right]
        region_mask = region.mask[top:bottom, left:right]
        mask[top:bottom, left:right] = np.maximum(sub, region_mask)

    rgba = image.rgba.copy()
    rgba[:, :, 3] = mask

    key = f"assets/bg-removal-{uuid.uuid4().hex}.png"
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG")
    await upload_service.storage.put(key, buf.getvalue(), "image/png")

    return BackgroundRemovalResponse(
        url=f"/api/storage/{key}",
        key=key,
        width=image.width,
        height=image.height,
    )


class GroupingRequest(BaseModel):
    scene: SceneGraph


class GroupSuggestionResponse(BaseModel):
    name: str
    elementIds: list[str] = Field(..., alias="elementIds")


class GroupingResponse(BaseModel):
    groups: list[GroupSuggestionResponse]


@router.post("/grouping", response_model=GroupingResponse)
async def suggest_groups(req: GroupingRequest) -> GroupingResponse:
    """Smart layer grouping suggestions for a reconstructed scene (backlog)."""
    suggestions = LayerGrouper().suggest(req.scene)
    return GroupingResponse(
        groups=[
            GroupSuggestionResponse(name=s.name, elementIds=s.element_ids)
            for s in suggestions
        ]
    )