from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.main import create_app

SCENE = {
    "schemaVersion": 1,
    "canvas": {"width": 900, "height": 600, "background": "#FFFFFF"},
    "layers": [],
    "confidence": {},
    "overallConfidence": 1,
}


@pytest.fixture()
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(
        storage_dir=tmp_path / "storage",
        job_backend="memory",
        db_backend="memory",
        environment="test",
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c


async def _register(client: httpx.AsyncClient, email: str) -> str:
    r = await client.post(
        "/api/auth/register", json={"email": email, "password": "password123"}
    )
    assert r.status_code == 201
    return r.json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_projects_require_auth(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/projects")).status_code == 401
    create = await client.post(
        "/api/projects", json={"name": "p", "sceneGraph": SCENE}
    )
    assert create.status_code == 401


async def test_project_crud_flow(client: httpx.AsyncClient) -> None:
    token = await _register(client, "owner@example.com")

    create = await client.post(
        "/api/projects",
        json={"name": "Poster", "sceneGraph": SCENE},
        headers=_auth(token),
    )
    assert create.status_code == 201
    project = create.json()
    assert project["name"] == "Poster"
    assert project["sceneGraph"]["canvas"]["width"] == 900

    listing = await client.get("/api/projects", headers=_auth(token))
    assert listing.status_code == 200
    assert [p["id"] for p in listing.json()] == [project["id"]]

    fetched = await client.get(f"/api/projects/{project['id']}", headers=_auth(token))
    assert fetched.status_code == 200
    assert fetched.json()["sceneGraph"] == SCENE

    updated = await client.patch(
        f"/api/projects/{project['id']}",
        json={"name": "Renamed", "sceneGraph": {**SCENE, "overallConfidence": 0.5}},
        headers=_auth(token),
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"
    assert updated.json()["sceneGraph"]["overallConfidence"] == 0.5

    deleted = await client.delete(f"/api/projects/{project['id']}", headers=_auth(token))
    assert deleted.status_code == 204
    gone = await client.get(f"/api/projects/{project['id']}", headers=_auth(token))
    assert gone.status_code == 404


async def test_projects_are_user_scoped(client: httpx.AsyncClient) -> None:
    token_a = await _register(client, "a@example.com")
    token_b = await _register(client, "b@example.com")

    create = await client.post(
        "/api/projects",
        json={"name": "Private", "sceneGraph": SCENE},
        headers=_auth(token_a),
    )
    project_id = create.json()["id"]

    # B cannot read, mutate, or delete A's project
    get_r = await client.get(f"/api/projects/{project_id}", headers=_auth(token_b))
    assert get_r.status_code == 404

    assert (
        await client.patch(
            f"/api/projects/{project_id}", json={"name": "hacked"}, headers=_auth(token_b)
        )
    ).status_code == 404
    assert (
        await client.delete(f"/api/projects/{project_id}", headers=_auth(token_b))
    ).status_code == 404

    # B's own list is empty
    listing = await client.get("/api/projects", headers=_auth(token_b))
    assert listing.json() == []


async def test_version_history_save_list_restore(client: httpx.AsyncClient) -> None:
    token = await _register(client, "ver@example.com")
    create = await client.post(
        "/api/projects", json={"name": "V", "sceneGraph": SCENE}, headers=_auth(token)
    )
    project_id = create.json()["id"]

    await client.post(
        f"/api/projects/{project_id}/versions",
        json={"sceneGraph": {**SCENE, "overallConfidence": 0.9}, "label": "v1"},
        headers=_auth(token),
    )
    await client.post(
        f"/api/projects/{project_id}/versions",
        json={"sceneGraph": {**SCENE, "overallConfidence": 0.4}, "label": "v2"},
        headers=_auth(token),
    )

    versions = await client.get(
        f"/api/projects/{project_id}/versions", headers=_auth(token)
    )
    assert versions.status_code == 200
    rows = versions.json()
    assert [v["versionNo"] for v in rows] == [1, 2]
    assert rows[0]["sceneGraph"]["overallConfidence"] == 0.9

    # mutate the project body, then roll back to v1
    await client.patch(
        f"/api/projects/{project_id}",
        json={"sceneGraph": {**SCENE, "overallConfidence": 0.1}},
        headers=_auth(token),
    )
    restored = await client.post(
        f"/api/projects/{project_id}/versions/1/restore", headers=_auth(token)
    )
    assert restored.status_code == 200
    assert restored.json()["sceneGraph"]["overallConfidence"] == 0.9


async def test_versions_respect_ownership(client: httpx.AsyncClient) -> None:
    token_a = await _register(client, "va@example.com")
    token_b = await _register(client, "vb@example.com")
    create = await client.post(
        "/api/projects", json={"name": "V", "sceneGraph": SCENE}, headers=_auth(token_a)
    )
    project_id = create.json()["id"]

    assert (
        await client.get(f"/api/projects/{project_id}/versions", headers=_auth(token_b))
    ).status_code == 404
    save = await client.post(
        f"/api/projects/{project_id}/versions",
        json={"sceneGraph": SCENE},
        headers=_auth(token_b),
    )
    assert save.status_code == 404
    restore = await client.post(
        f"/api/projects/{project_id}/versions/1/restore", headers=_auth(token_b)
    )
    assert restore.status_code == 404