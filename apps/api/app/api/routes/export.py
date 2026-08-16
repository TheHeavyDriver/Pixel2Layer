from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.schemas.scene_graph import SceneGraph
from app.services.export_service import ExportError, ExportService

router = APIRouter(prefix="/api/export", tags=["export"])

_service = ExportService()


class ExportRequest(BaseModel):
    format: Literal["png", "jpg", "svg", "pdf"]
    scan: float = Field(1.0, ge=0.1, le=4.0)
    scene: SceneGraph


class P2lRequest(BaseModel):
    scene: SceneGraph
    name: str | None = None
    metadata: dict | None = None


_CONTENT_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "svg": "image/svg+xml",
    "pdf": "application/pdf",
}


@router.post("", response_class=Response)
async def export_scene(req: ExportRequest) -> Response:
    """Rasterize or serialize a scene graph to the requested format."""
    try:
        if req.format == "svg":
            result = _service.to_svg(req.scene)
        elif req.format == "pdf":
            result = _service.to_pdf(req.scene, scale=req.scan)
        else:
            result = _service.rasterize(req.scene, req.format, scale=req.scan)
    except ExportError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return Response(
        content=result.data,
        media_type=_CONTENT_TYPES[req.format],
        headers={
            "Content-Disposition": f'attachment; filename="design.{req.format}"'
        },
    )


@router.post("/p2l", response_class=Response)
async def save_p2l(req: P2lRequest) -> Response:
    """Serialize a scene graph to the .p2l project format."""
    metadata = dict(req.metadata or {})
    if req.name:
        metadata.setdefault("name", req.name)
    data = _service.serialize_p2l(req.scene, metadata=metadata)
    return Response(
        content=data,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="design.p2l"'
        },
    )


@router.post("/import", response_class=Response)
async def load_p2l(file: UploadFile) -> Response:
    """Deserialize an uploaded .p2l file back into a scene graph."""
    try:
        payload = await file.read()
        scene, metadata = _service.deserialize_p2l_payload(payload)
    except ExportError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return Response(
        content=scene.model_dump_json(by_alias=True),
        media_type="application/json",
        headers={"X-P2l-Metadata": str(metadata)},
    )