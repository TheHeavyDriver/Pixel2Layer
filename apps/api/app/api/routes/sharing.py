from __future__ import annotations

import secrets
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserDep, StoreDep
from app.services.store import Project, Share

router = APIRouter(prefix="/api", tags=["sharing"])


class CreateShareRequest(BaseModel):
    permission: Literal["view", "edit"] = "view"


class ShareResponse(BaseModel):
    token: str
    projectId: str
    permission: str
    url: str
    createdAt: str


class SharedProjectResponse(BaseModel):
    id: str
    name: str
    sceneGraph: dict[str, Any]
    sourceImage: str | None = None
    permission: str
    updatedAt: str


def _iso(dt) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _share_response(share: Share) -> ShareResponse:
    return ShareResponse(
        token=share.token,
        projectId=share.project_id,
        permission=share.permission,
        url=f"/share/{share.token}",
        createdAt=_iso(share.created_at),
    )


def _shared_project_response(project: Project, permission: str) -> SharedProjectResponse:
    return SharedProjectResponse(
        id=project.id,
        name=project.name,
        sceneGraph=project.scene_graph,
        sourceImage=project.source_image,
        permission=permission,
        updatedAt=_iso(project.updated_at),
    )


@router.post(
    "/projects/{project_id}/share",
    response_model=ShareResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_share(
    project_id: str,
    req: CreateShareRequest,
    user: CurrentUserDep,
    store: StoreDep,
) -> ShareResponse:
    project = await store.get_project(project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    share = await store.create_share(
        project_id=project.id,
        owner_id=user.id,
        token=secrets.token_urlsafe(16),
        permission=req.permission,
    )
    return _share_response(share)


@router.get("/projects/{project_id}/shares", response_model=list[ShareResponse])
async def list_shares(
    project_id: str,
    user: CurrentUserDep,
    store: StoreDep,
) -> list[ShareResponse]:
    project = await store.get_project(project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    shares = await store.list_shares(project.id)
    return [_share_response(s) for s in shares]


@router.delete(
    "/projects/{project_id}/shares/{token}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_share(
    project_id: str,
    token: str,
    user: CurrentUserDep,
    store: StoreDep,
) -> None:
    project = await store.get_project(project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    await store.delete_share(project.id, token)


class UpdateSharedRequest(BaseModel):
    sceneGraph: dict[str, Any] = Field(...)


@router.get("/share/{token}", response_model=SharedProjectResponse)
async def get_shared_project(token: str, store: StoreDep) -> SharedProjectResponse:
    share = await store.get_share_by_token(token)
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="share not found")
    project = await store.get_project(share.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    return _shared_project_response(project, share.permission)


@router.patch("/share/{token}", response_model=SharedProjectResponse)
async def update_shared_project(
    token: str,
    req: UpdateSharedRequest,
    store: StoreDep,
) -> SharedProjectResponse:
    share = await store.get_share_by_token(token)
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="share not found")
    if share.permission != "edit":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="this share link is view-only",
        )
    project = await store.get_project(share.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    updated = await store.update_project(project.id, scene_graph=req.sceneGraph)
    return _shared_project_response(updated, share.permission)