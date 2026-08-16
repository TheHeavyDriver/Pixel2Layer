from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import asyncpg

from app.core.config import Settings

# ISO timestamp helper for the postgres backend (asyncpg returns aware datetimes).
_now = lambda: datetime.now(UTC)  # noqa: E731

DDL = """
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
    id           UUID PRIMARY KEY,
    owner_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    scene_graph  JSONB NOT NULL,
    source_image TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(owner_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS project_versions (
    id          UUID PRIMARY KEY,
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    version_no  INTEGER NOT NULL,
    label       TEXT,
    scene_graph JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, version_no)
);
"""


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


class MemoryStore(Store):
    """In-process store for tests and local dev without Postgres."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._projects: dict[str, Project] = {}
        self._versions: dict[str, list[ProjectVersion]] = {}

    async def init(self) -> None:
        self._users = {}
        self._projects = {}
        self._versions = {}

    async def close(self) -> None:
        pass

    # -- users ---------------------------------------------------------------
    async def create_user(self, *, email, password_hash, name) -> User:
        user = User(id=new_id(), email=email, password_hash=password_hash, name=name)
        self._users[user.id] = user
        return user

    async def get_user_by_email(self, email: str) -> User | None:
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    async def get_user_by_id(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    # -- projects ------------------------------------------------------------
    async def create_project(self, *, owner_id, name, scene_graph, source_image=None) -> Project:
        project = Project(
            id=new_id(), owner_id=owner_id, name=name,
            scene_graph=scene_graph, source_image=source_image,
        )
        self._projects[project.id] = project
        return project

    async def list_projects(self, owner_id: str) -> list[Project]:
        owned = [p for p in self._projects.values() if p.owner_id == owner_id]
        return sorted(owned, key=lambda p: p.updated_at, reverse=True)

    async def get_project(self, project_id: str) -> Project | None:
        return self._projects.get(project_id)

    async def update_project(self, project_id, *, name=None, scene_graph=None) -> Project | None:
        project = self._projects.get(project_id)
        if project is None:
            return None
        if name is not None:
            project.name = name
        if scene_graph is not None:
            project.scene_graph = scene_graph
        project.updated_at = _now()
        return project

    async def delete_project(self, project_id: str) -> bool:
        removed = self._projects.pop(project_id, None) is not None
        if removed:
            self._versions.pop(project_id, None)
        return removed

    # -- versions ------------------------------------------------------------
    async def create_version(self, *, project_id, scene_graph, label=None) -> ProjectVersion | None:
        if project_id not in self._projects:
            return None
        existing = self._versions.setdefault(project_id, [])
        version_no = (existing[-1].version_no + 1) if existing else 1
        version = ProjectVersion(
            id=new_id(), project_id=project_id, version_no=version_no,
            scene_graph=scene_graph, label=label,
        )
        existing.append(version)
        return version

    async def list_versions(self, project_id: str) -> list[ProjectVersion]:
        return list(self._versions.get(project_id, []))

    async def get_version(self, project_id: str, version_no: int) -> ProjectVersion | None:
        versions = self._versions.get(project_id, [])
        return next((v for v in versions if v.version_no == version_no), None)

    async def restore_version(self, project_id: str, version_no: int) -> Project | None:
        version = await self.get_version(project_id, version_no)
        if version is None:
            return None
        return await self.update_project(project_id, scene_graph=version.scene_graph)


class PostgresStore(Store):
    """asyncpg-backed store. Schema owned by this app (see DDL)."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("PostgresStore not initialised")
        return self._pool

    async def init(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=10)
        async with self.pool.acquire() as conn:
            await conn.execute(DDL)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    # -- rows → records ------------------------------------------------------
    @staticmethod
    def _user_from_row(row: asyncpg.Record) -> User:
        return User(
            id=str(row["id"]),
            email=row["email"],
            password_hash=row["password_hash"],
            name=row["name"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _project_from_row(row: asyncpg.Record) -> Project:
        scene = row["scene_graph"]
        if not isinstance(scene, dict):
            scene = json.loads(scene)
        return Project(
            id=str(row["id"]),
            owner_id=str(row["owner_id"]),
            name=row["name"],
            scene_graph=scene,
            source_image=row["source_image"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _version_from_row(row: asyncpg.Record) -> ProjectVersion:
        scene = row["scene_graph"]
        if not isinstance(scene, dict):
            scene = json.loads(scene)
        return ProjectVersion(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            version_no=row["version_no"],
            scene_graph=scene,
            label=row["label"],
            created_at=row["created_at"],
        )

    # -- users ---------------------------------------------------------------
    async def create_user(self, *, email, password_hash, name) -> User:
        row = await self.pool.fetchrow(
            """
            INSERT INTO users (id, email, password_hash, name)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (email) DO NOTHING
            RETURNING *
            """,
            uuid.UUID(new_id()), email, password_hash, name,
        )
        if row is None:
            raise ValueError("email already registered")
        return self._user_from_row(row)

    async def get_user_by_email(self, email: str) -> User | None:
        row = await self.pool.fetchrow(
            "SELECT * FROM users WHERE email = $1", email
        )
        return self._user_from_row(row) if row else None

    async def get_user_by_id(self, user_id: str) -> User | None:
        row = await self.pool.fetchrow("SELECT * FROM users WHERE id = $1", uuid.UUID(user_id))
        return self._user_from_row(row) if row else None

    # -- projects ------------------------------------------------------------
    async def create_project(self, *, owner_id, name, scene_graph, source_image=None) -> Project:
        row = await self.pool.fetchrow(
            """
            INSERT INTO projects (id, owner_id, name, scene_graph, source_image)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            RETURNING *
            """,
            uuid.UUID(new_id()), uuid.UUID(owner_id), name,
            json.dumps(scene_graph), source_image,
        )
        return self._project_from_row(row)

    async def list_projects(self, owner_id: str) -> list[Project]:
        rows = await self.pool.fetch(
            "SELECT * FROM projects WHERE owner_id = $1 ORDER BY updated_at DESC",
            uuid.UUID(owner_id),
        )
        return [self._project_from_row(r) for r in rows]

    async def get_project(self, project_id: str) -> Project | None:
        row = await self.pool.fetchrow(
            "SELECT * FROM projects WHERE id = $1", uuid.UUID(project_id)
        )
        return self._project_from_row(row) if row else None

    async def update_project(self, project_id, *, name=None, scene_graph=None) -> Project | None:
        row = await self.pool.fetchrow(
            """
            UPDATE projects
            SET name = COALESCE($2, name),
                scene_graph = COALESCE($3::jsonb, scene_graph),
                updated_at = now()
            WHERE id = $1
            RETURNING *
            """,
            uuid.UUID(project_id), name,
            json.dumps(scene_graph) if scene_graph is not None else None,
        )
        return self._project_from_row(row) if row else None

    async def delete_project(self, project_id: str) -> bool:
        res = await self.pool.execute(
            "DELETE FROM projects WHERE id = $1", uuid.UUID(project_id)
        )
        return res.endswith("1")

    # -- versions ------------------------------------------------------------
    async def create_version(self, *, project_id, scene_graph, label=None) -> ProjectVersion | None:
        row = await self.pool.fetchrow(
            """
            INSERT INTO project_versions (id, project_id, version_no, label, scene_graph)
            SELECT $1, p.id,
                   COALESCE(MAX(v.version_no), 0) + 1,
                   $3, $4::jsonb
            FROM projects p LEFT JOIN project_versions v ON v.project_id = p.id
            WHERE p.id = $2
            GROUP BY p.id
            RETURNING *
            """,
            uuid.UUID(new_id()), uuid.UUID(project_id), label, json.dumps(scene_graph),
        )
        return self._version_from_row(row) if row else None

    async def list_versions(self, project_id: str) -> list[ProjectVersion]:
        rows = await self.pool.fetch(
            "SELECT * FROM project_versions WHERE project_id = $1 ORDER BY version_no ASC",
            uuid.UUID(project_id),
        )
        return [self._version_from_row(r) for r in rows]

    async def get_version(self, project_id: str, version_no: int) -> ProjectVersion | None:
        row = await self.pool.fetchrow(
            "SELECT * FROM project_versions WHERE project_id = $1 AND version_no = $2",
            uuid.UUID(project_id), version_no,
        )
        return self._version_from_row(row) if row else None

    async def restore_version(self, project_id: str, version_no: int) -> Project | None:
        version = await self.get_version(project_id, version_no)
        if version is None:
            return None
        return await self.update_project(project_id, scene_graph=version.scene_graph)


def build_store(settings: Settings) -> Store:
    if settings.db_backend == "postgres":
        return PostgresStore(settings.postgres_url)
    return MemoryStore()