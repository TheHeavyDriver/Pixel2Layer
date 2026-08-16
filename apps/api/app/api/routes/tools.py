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
from app.services.image_edit import (
    crop_to_region,
    keep_region,
    remove_region,
    select_region,
)
from app.services.image_utils import LoadedImage, load_image
from app.services.segmenter import SegmentedRegion, build_segmenter

router = APIRouter(prefix="/api/tools", tags=["tools"])


def _decode_image(data: bytes) -> LoadedImage:
    try:
        return load_image(data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="could not decode image"
        ) from exc


class BackgroundRemovalResponse(BaseModel):
    url: str
    key: str
    width: int
    height: int


async def _store_png(
    upload_service: UploadServiceDep, rgba: np.ndarray, kind: str
) -> BackgroundRemovalResponse:
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG")
    key = f"assets/{kind}-{uuid.uuid4().hex}.png"
    await upload_service.storage.put(key, buf.getvalue(), "image/png")
    return BackgroundRemovalResponse(
        url=f"/api/storage/{key}",
        key=key,
        width=rgba.shape[1],
        height=rgba.shape[0],
    )


@router.post("/background-removal", response_model=BackgroundRemovalResponse)
async def background_removal(
    file: UploadFile,
    upload_service: UploadServiceDep,
) -> BackgroundRemovalResponse:
    """Masked PNG cutout of the foreground, stored under `assets/`.

    Uses the same pluggable segmenter as the pipeline, so results are
    labelled approximate in the associated metadata.
    """
    data = await file.read()
    image = _decode_image(data)

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

    return await _store_png(upload_service, rgba, "bg-removal")


class RegionInfoResponse(BaseModel):
    x: int
    y: int
    width: int
    height: int
    label: str
    confidence: float


class RegionsResponse(BaseModel):
    width: int
    height: int
    regions: list[RegionInfoResponse]


@router.post("/regions", response_model=RegionsResponse)
async def detect_regions(
    file: UploadFile,
) -> RegionsResponse:
    """Detect and return the foreground regions of an uploaded image.

    Region bounds are in the source image's pixel space (0,0 = top-left),
    so the editor can offer per-region keep/remove/crop actions.
    """
    data = await file.read()
    image = _decode_image(data)
    regions = build_segmenter().segment(image)
    return RegionsResponse(
        width=image.width,
        height=image.height,
        regions=[
            RegionInfoResponse(
                x=r.x, y=r.y, width=r.width, height=r.height, label=r.label, confidence=r.confidence
            )
            for r in regions
        ],
    )


class RegionCropResponse(BaseModel):
    url: str
    key: str
    width: int
    height: int


def _resolve_region_or_error(
    regions: list[SegmentedRegion], index: int
) -> SegmentedRegion:
    try:
        return select_region(regions, index)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@router.post("/region-crop", response_model=RegionCropResponse)
async def region_crop(
    file: UploadFile,
    index: int,
    upload_service: UploadServiceDep,
) -> RegionCropResponse:
    """Crop an image to a single detected region's bounding box.

    Pass `index` to select which detected foreground region to crop to
    (0-based, as returned by `/api/tools/regions`).
    """
    data = await file.read()
    image = _decode_image(data)
    regions = build_segmenter().segment(image)
    region = _resolve_region_or_error(regions, index)
    rgba = crop_to_region(image.rgba, region)
    return await _store_png(upload_service, rgba, "region-crop")


class RegionMaskResponse(BaseModel):
    url: str
    key: str
    width: int
    height: int


@router.post("/region-mask", response_model=RegionMaskResponse)
async def region_mask(
    file: UploadFile,
    upload_service: UploadServiceDep,
    index: int,
    mode: str = "keep",
) -> RegionMaskResponse:
    """Mask an image with a single detected region.

    - `mode=keep` keeps only the chosen region's foreground pixels.
    - `mode=remove` transparents out the chosen region's pixels.
    `index` is 0-based as returned by `/api/tools/regions`.
    """
    if mode not in ("keep", "remove"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="mode must be 'keep' or 'remove'",
        )
    data = await file.read()
    image = _decode_image(data)
    regions = build_segmenter().segment(image)
    region = _resolve_region_or_error(regions, index)
    rgba = keep_region(image.rgba, region) if mode == "keep" else remove_region(
        image.rgba, region
    )
    return await _store_png(upload_service, rgba, "region-mask")


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