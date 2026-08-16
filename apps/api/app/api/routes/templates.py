from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserDep, StoreDep
from app.services.store import Template

router = APIRouter(prefix="/api/templates", tags=["templates"])


class CreateTemplateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sceneGraph: dict[str, Any]
    sourceImage: str | None = None


class TemplateResponse(BaseModel):
    id: str
    ownerId: str
    name: str
    sceneGraph: dict[str, Any]
    sourceImage: str | None = None
    createdAt: str


class TemplateSummary(BaseModel):
    id: str
    ownerId: str
    name: str
    sourceImage: str | None = None
    createdAt: str


def _iso(dt) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _template_response(
    t: Template, include_scene: bool = True
) -> TemplateResponse | TemplateSummary:
    if not include_scene:
        return TemplateSummary(
            id=t.id,
            ownerId=t.owner_id,
            name=t.name,
            sourceImage=t.source_image,
            createdAt=_iso(t.created_at),
        )
    return TemplateResponse(
        id=t.id,
        ownerId=t.owner_id,
        name=t.name,
        sceneGraph=t.scene_graph,
        sourceImage=t.source_image,
        createdAt=_iso(t.created_at),
    )


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    req: CreateTemplateRequest,
    user: CurrentUserDep,
    store: StoreDep,
) -> TemplateResponse:
    template = await store.create_template(
        owner_id=user.id,
        name=req.name,
        scene_graph=req.sceneGraph,
        source_image=req.sourceImage,
    )
    return _template_response(template)


@router.get("", response_model=list[TemplateSummary])
async def list_template_gallery(store: StoreDep) -> list[TemplateSummary]:
    templates = await store.list_templates()
    return [_template_response(t, include_scene=False) for t in templates]


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str, store: StoreDep) -> TemplateResponse:
    template = await store.get_template(template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")
    return _template_response(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    user: CurrentUserDep,
    store: StoreDep,
) -> None:
    template = await store.get_template(template_id)
    if template is None or template.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")
    await store.delete_template(template.id)