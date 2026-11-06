"""Persistence layer for users, projects, versions, shares, templates, and batches.

Public API:
    - Data classes: User, Project, ProjectVersion, Share, Template, Batch
    - Store protocol (ABC)
    - get_store() factory function
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings

# ISO timestamp helper
_now = lambda: datetime.now(UTC)  # noqa: E731


@dataclass
class User:
    id: str
    email: str
    name: str | None
    password_hash: str
    created_at: datetime = field(default_factory=_now)


@dataclass
class Project:
    id: str
    owner_id: str
    name: str
    scene_graph: dict[str, Any]
    source_image: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)


@dataclass
class ProjectVersion:
    id: str
    project_id: str
    version_no: int
    scene_graph: dict[str, Any]
    label: str | None = None
    created_at: datetime = field(default_factory=_now)


@dataclass
class Share:
    id: str
    token: str
    project_id: str
    owner_id: str
    permission: str  # "view" | "edit"
    created_at: datetime = field(default_factory=_now)


@dataclass
class Template:
    id: str
    owner_id: str
    name: str
    scene_graph: dict[str, Any]
    source_image: str | None = None
    created_at: datetime = field(default_factory=_now)


@dataclass
class Batch:
    id: str
    owner_id: str | None
    job_ids: list[str]
    created_at: datetime = field(default_factory=_now)


def new_id() -> str:
    return uuid.uuid4().hex


class Store(ABC):
    """Persistence for users, projects, and snapshot versions."""

    @abstractmethod
    async def init(self) -> None:
        """Create connections / schema. Called once at app startup."""

    @abstractmethod
    async def close(self) -> None:
        """Release connections. Called once at app shutdown."""

    @abstractmethod
    async def create_user(self, *, email: str, password_hash: str, name: str | None) -> User: ...

    @abstractmethod
    async def get_user_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> User | None: ...

    @abstractmethod
    async def create_project(
        self,
        *,
        owner_id: str,
        name: str,
        scene_graph: dict[str, Any],
        source_image: str | None = None,
    ) -> Project: ...

    @abstractmethod
    async def list_projects(self, owner_id: str) -> list[Project]: ...

    @abstractmethod
    async def get_project(self, project_id: str) -> Project | None: ...

    @abstractmethod
    async def update_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        scene_graph: dict[str, Any] | None = None,
    ) -> Project | None: ...

    @abstractmethod
    async def delete_project(self, project_id: str) -> bool: ...

    @abstractmethod
    async def create_version(
        self,
        *,
        project_id: str,
        scene_graph: dict[str, Any],
        label: str | None = None,
    ) -> ProjectVersion | None: ...

    @abstractmethod
    async def list_versions(self, project_id: str) -> list[ProjectVersion]: ...

    @abstractmethod
    async def get_version(self, project_id: str, version_no: int) -> ProjectVersion | None: ...

    @abstractmethod
    async def restore_version(self, project_id: str, version_no: int) -> Project | None: ...

    # -- shares -------------------------------------------------------------
    @abstractmethod
    async def create_share(
        self, *, project_id: str, owner_id: str, token: str, permission: str
    ) -> Share: ...

    @abstractmethod
    async def get_share_by_token(self, token: str) -> Share | None: ...

    @abstractmethod
    async def list_shares(self, project_id: str) -> list[Share]: ...

    @abstractmethod
    async def delete_share(self, project_id: str, token: str) -> bool: ...

    # -- templates ----------------------------------------------------------
    @abstractmethod
    async def create_template(
        self,
        *,
        owner_id: str,
        name: str,
        scene_graph: dict[str, Any],
        source_image: str | None = None,
    ) -> Template: ...

    @abstractmethod
    async def list_templates(self) -> list[Template]: ...

    @abstractmethod
    async def get_template(self, template_id: str) -> Template | None: ...

    @abstractmethod
    async def delete_template(self, template_id: str) -> bool: ...

    # -- batches ------------------------------------------------------------
    @abstractmethod
    async def create_batch(self, *, owner_id: str | None, job_ids: list[str]) -> Batch: ...

    @abstractmethod
    async def get_batch(self, batch_id: str) -> Batch | None: ...


# Import implementations and expose factory
from app.services.store.memory import MemoryStore  # noqa: E402
from app.services.store.postgres import PostgresStore  # noqa: E402

__all__ = [
    "User",
    "Project",
    "ProjectVersion",
    "Share",
    "Template",
    "Batch",
    "Store",
    "MemoryStore",
    "PostgresStore",
    "new_id",
    "get_store",
    "build_store",  # Keep backward compatibility alias
]


def get_store(settings: Settings) -> Store:
    """Factory function to create the appropriate store implementation."""
    if settings.db_backend == "postgres":
        return PostgresStore(settings.postgres_url)
    return MemoryStore()


# Backward compatibility alias
build_store = get_store
