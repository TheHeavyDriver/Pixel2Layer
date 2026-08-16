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


async def test_create_template_requires_auth(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/templates", json={"name": "t", "sceneGraph": SCENE}
    )
    assert r.status_code == 401


async def test_template_save_gallery_get(client: httpx.AsyncClient) -> None:
    token = await _register(client, "owner@example.com")
    created = await client.post(
        "/api/templates",
        json={"name": "Poster layout", "sceneGraph": SCENE},
        headers=_auth(token),
    )
    assert created.status_code == 201
    template = created.json()
    assert template["name"] == "Poster layout"
    assert template["sceneGraph"]["canvas"]["width"] == 900

    gallery = await client.get("/api/templates")
    assert gallery.status_code == 200
    assert gallery.json()[0]["id"] == template["id"]
    assert "sceneGraph" not in gallery.json()[0]

    fetched = await client.get(f"/api/templates/{template['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["sceneGraph"] == SCENE


async def test_delete_template_only_owner(client: httpx.AsyncClient) -> None:
    token_a = await _register(client, "a@example.com")
    token_b = await _register(client, "b@example.com")
    created = await client.post(
        "/api/templates",
        json={"name": "Mine", "sceneGraph": SCENE},
        headers=_auth(token_a),
    )
    template_id = created.json()["id"]

    assert (
        await client.delete(f"/api/templates/{template_id}", headers=_auth(token_b))
    ).status_code == 404

    deleted = await client.delete(
        f"/api/templates/{template_id}", headers=_auth(token_a)
    )
    assert deleted.status_code == 204
    assert (await client.get(f"/api/templates/{template_id}")).status_code == 404


async def test_template_gallery_is_public_and_ordered(client: httpx.AsyncClient) -> None:
    token_a = await _register(client, "a@example.com")
    token_b = await _register(client, "b@example.com")
    for token, name in ((token_a, "first"), (token_b, "second")):
        await client.post(
            "/api/templates", json={"name": name, "sceneGraph": SCENE}, headers=_auth(token)
        )
    gallery = (await client.get("/api/templates")).json()
    assert [t["name"] for t in gallery] == ["second", "first"]