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


async def _project(client: httpx.AsyncClient, token: str, name: str = "Poster") -> dict:
    r = await client.post(
        "/api/projects", json={"name": name, "sceneGraph": SCENE}, headers=_auth(token)
    )
    assert r.status_code == 201
    return r.json()


async def test_create_list_and_get_share(client: httpx.AsyncClient) -> None:
    token = await _register(client, "owner@example.com")
    project = await _project(client, token)

    created = await client.post(
        f"/api/projects/{project['id']}/share",
        json={"permission": "edit"},
        headers=_auth(token),
    )
    assert created.status_code == 201
    share = created.json()
    assert share["projectId"] == project["id"]
    assert share["permission"] == "edit"
    assert share["url"] == f"/share/{share['token']}"

    listing = await client.get(
        f"/api/projects/{project['id']}/shares", headers=_auth(token)
    )
    assert listing.status_code == 200
    assert [s["token"] for s in listing.json()] == [share["token"]]

    fetched = await client.get(f"/api/share/{share['token']}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["name"] == "Poster"
    assert body["sceneGraph"] == SCENE
    assert body["permission"] == "edit"


async def test_share_requires_ownership(client: httpx.AsyncClient) -> None:
    token_a = await _register(client, "a@example.com")
    token_b = await _register(client, "b@example.com")
    project = await _project(client, token_a)

    create = await client.post(
        f"/api/projects/{project['id']}/share",
        json={"permission": "view"},
        headers=_auth(token_b),
    )
    assert create.status_code == 404
    assert (
        await client.get(
            f"/api/projects/{project['id']}/shares", headers=_auth(token_b)
        )
    ).status_code == 404


async def test_revoke_share_blocks_access(client: httpx.AsyncClient) -> None:
    token = await _register(client, "owner@example.com")
    project = await _project(client, token)

    created = (await client.post(
        f"/api/projects/{project['id']}/share",
        json={"permission": "view"},
        headers=_auth(token),
    )).json()["token"]

    revoked = await client.delete(
        f"/api/projects/{project['id']}/shares/{created}", headers=_auth(token)
    )
    assert revoked.status_code == 204
    assert (await client.get(f"/api/share/{created}")).status_code == 404


async def test_view_only_share_rejects_edit(client: httpx.AsyncClient) -> None:
    token = await _register(client, "owner@example.com")
    project = await _project(client, token)
    created = await client.post(
        f"/api/projects/{project['id']}/share",
        json={"permission": "view"},
        headers=_auth(token),
    )
    token_value = created.json()["token"]

    assert (
        await client.patch(
            f"/api/share/{token_value}",
            json={"sceneGraph": {**SCENE, "overallConfidence": 0.1}},
        )
    ).status_code == 403


async def test_edit_share_saves_to_project(client: httpx.AsyncClient) -> None:
    token = await _register(client, "owner@example.com")
    project = await _project(client, token)
    created = await client.post(
        f"/api/projects/{project['id']}/share",
        json={"permission": "edit"},
        headers=_auth(token),
    )
    token_value = created.json()["token"]

    updated = await client.patch(
        f"/api/share/{token_value}",
        json={"sceneGraph": {**SCENE, "overallConfidence": 0.42}},
    )
    assert updated.status_code == 200
    assert updated.json()["sceneGraph"]["overallConfidence"] == 0.42

    # the owner's project reflects the shared edit
    fetched = await client.get(
        f"/api/projects/{project['id']}", headers=_auth(token)
    )
    assert fetched.json()["sceneGraph"]["overallConfidence"] == 0.42