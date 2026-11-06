"""In-memory store implementation for tests and local dev."""

from __future__ import annotations

from app.services.store import (
    Batch,
    Project,
    ProjectVersion,
    Share,
    Store,
    Template,
    User,
    _now,
    new_id,
)


class MemoryStore(Store):
    """In-process store for tests and local dev without Postgres."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._projects: dict[str, Project] = {}
        self._versions: dict[str, list[ProjectVersion]] = {}
        self._shares: dict[str, Share] = {}
        self._templates: dict[str, Template] = {}
        self._batches: dict[str, Batch] = {}

    async def init(self) -> None:
        self._users = {}
        self._projects = {}
        self._versions = {}
        self._shares = {}
        self._templates = {}
        self._batches = {}

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

    # -- shares ------------------------------------------------------------
    async def create_share(self, *, project_id, owner_id, token, permission) -> Share:
        share = Share(
            id=new_id(), token=token, project_id=project_id,
            owner_id=owner_id, permission=permission,
        )
        self._shares[token] = share
        return share

    async def get_share_by_token(self, token: str) -> Share | None:
        return self._shares.get(token)

    async def list_shares(self, project_id: str) -> list[Share]:
        return [s for s in self._shares.values() if s.project_id == project_id]

    async def delete_share(self, project_id: str, token: str) -> bool:
        share = self._shares.get(token)
        if share is None or share.project_id != project_id:
            return False
        self._shares.pop(token, None)
        return True

    # -- templates ---------------------------------------------------------
    async def create_template(self, *, owner_id, name, scene_graph, source_image=None) -> Template:
        template = Template(
            id=new_id(), owner_id=owner_id, name=name,
            scene_graph=scene_graph, source_image=source_image,
        )
        self._templates[template.id] = template
        return template

    async def list_templates(self) -> list[Template]:
        return sorted(
            self._templates.values(), key=lambda t: t.created_at, reverse=True
        )

    async def get_template(self, template_id: str) -> Template | None:
        return self._templates.get(template_id)

    async def delete_template(self, template_id: str) -> bool:
        return self._templates.pop(template_id, None) is not None

    # -- batches -----------------------------------------------------------
    async def create_batch(self, *, owner_id, job_ids) -> Batch:
        batch = Batch(id=new_id(), owner_id=owner_id, job_ids=list(job_ids))
        self._batches[batch.id] = batch
        return batch

    async def get_batch(self, batch_id: str) -> Batch | None:
        return self._batches.get(batch_id)
