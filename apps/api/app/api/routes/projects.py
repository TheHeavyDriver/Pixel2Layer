from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserDep, StoreDep
from app.services.store import Project, ProjectVersion, User

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sceneGraph: dict[str, Any]
    sourceImage: str | None = None


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    sceneGraph: dict[str, Any] | None = None


class SaveVersionRequest(BaseModel):
    sceneGraph: dict[str, Any]
    label: str | None = Field(default=None, max_length=120)


class ProjectResponse(BaseModel):
    id: str
    name: str
    sceneGraph: dict[str, Any]
    sourceImage: str | None = None
    createdAt: str
    updatedAt: str


class ProjectSummary(BaseModel):
    id: str
    name: str
    sourceImage: str | None = None
    createdAt: str
    updatedAt: str


class VersionResponse(BaseModel):
    id: str
    projectId: str
    versionNo: int
    label: str | None = None
    sceneGraph: dict[str, Any]
    createdAt: str


def _iso(dt) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _project_response(p: Project) -> ProjectResponse:
    return ProjectResponse(
        id=p.id,
        name=p.name,
        sceneGraph=p.scene_graph,
        sourceImage=p.source_image,
        createdAt=_iso(p.created_at),
        updatedAt=_iso(p.updated_at),
    )


def _summary(p: Project) -> ProjectSummary:
    return ProjectSummary(
        id=p.id,
        name=p.name,
        sourceImage=p.source_image,
        createdAt=_iso(p.created_at),
        updatedAt=_iso(p.updated_at),
    )


def _version_response(v: ProjectVersion) -> VersionResponse:
    return VersionResponse(
        id=v.id,
        projectId=v.project_id,
        versionNo=v.version_no,
        label=v.label,
        sceneGraph=v.scene_graph,
        createdAt=_iso(v.created_at),
    )


def _owned_or_404(project: Project | None, user: User) -> Project:
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    if project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    return project


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    req: CreateProjectRequest,
    user: CurrentUserDep,
    store: StoreDep,
) -> ProjectResponse:
    project = await store.create_project(
        owner_id=user.id,
        name=req.name,
        scene_graph=req.sceneGraph,
        source_image=req.sourceImage,
    )
    return _project_response(project)


@router.get("", response_model=list[ProjectSummary])
async def list_projects(user: CurrentUserDep, store: StoreDep) -> list[ProjectSummary]:
    projects = await store.list_projects(user.id)
    return [_summary(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user: CurrentUserDep,
    store: StoreDep,
) -> ProjectResponse:
    project = await store.get_project(project_id)
    return _project_response(_owned_or_404(project, user))


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    req: UpdateProjectRequest,
    user: CurrentUserDep,
    store: StoreDep,
) -> ProjectResponse:
    project = _owned_or_404(await store.get_project(project_id), user)
    updated = await store.update_project(
        project.id, name=req.name, scene_graph=req.sceneGraph
    )
    return _project_response(updated)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    user: CurrentUserDep,
    store: StoreDep,
) -> None:
    project = _owned_or_404(await store.get_project(project_id), user)
    await store.delete_project(project.id)


@router.post(
    "/{project_id}/versions",
    response_model=VersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_version(
    project_id: str,
    req: SaveVersionRequest,
    user: CurrentUserDep,
    store: StoreDep,
) -> VersionResponse:
    project = _owned_or_404(await store.get_project(project_id), user)
    version = await store.create_version(
        project_id=project.id, scene_graph=req.sceneGraph, label=req.label
    )
    return _version_response(version)


@router.get("/{project_id}/versions", response_model=list[VersionResponse])
async def list_versions(
    project_id: str,
    user: CurrentUserDep,
    store: StoreDep,
) -> list[VersionResponse]:
    project = _owned_or_404(await store.get_project(project_id), user)
    versions = await store.list_versions(project.id)
    return [_version_response(v) for v in versions]


@router.post(
    "/{project_id}/versions/{version_no}/restore",
    response_model=ProjectResponse,
)
async def restore_version(
    project_id: str,
    version_no: int,
    user: CurrentUserDep,
    store: StoreDep,
) -> ProjectResponse:
    project = _owned_or_404(await store.get_project(project_id), user)
    restored = await store.restore_version(project.id, version_no)
    if restored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="version not found"
        )
    return _project_response(restored)