from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.main import create_app
from app.services.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


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


# -- unit: password + token helpers ------------------------------------------

def test_password_hash_roundtrip() -> None:
    stored = hash_password("correct horse battery staple")
    assert stored.startswith("pbkdf2_sha256$")
    assert verify_password("correct horse battery staple", stored)
    assert not verify_password("wrong password", stored)


def test_password_hashes_are_salted() -> None:
    assert hash_password("same") != hash_password("same")


def test_access_token_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    token = create_access_token("user-123", secret="sekrit", expires_minutes=60)
    assert decode_access_token(token, secret="sekrit") == "user-123"
    assert decode_access_token(token, secret="wrong") is None
    assert decode_access_token("garbage", secret="sekrit") is None


def test_access_token_expires() -> None:
    token = create_access_token("u1", secret="s", expires_minutes=-1)
    assert decode_access_token(token, secret="s") is None


# -- API: register / login / me ----------------------------------------------

async def test_register_returns_token_and_user(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/auth/register",
        json={"email": "ada@example.com", "password": "password123", "name": "Ada"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["token"]
    assert body["user"]["email"] == "ada@example.com"
    assert body["user"]["name"] == "Ada"


async def test_register_normalizes_email(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/auth/register",
        json={"email": "  Ada@Example.COM ", "password": "password123"},
    )
    assert r.status_code == 201
    assert r.json()["user"]["email"] == "ada@example.com"


async def test_duplicate_email_conflicts(client: httpx.AsyncClient) -> None:
    payload = {"email": "dupe@example.com", "password": "password123"}
    assert (await client.post("/api/auth/register", json=payload)).status_code == 201
    r = await client.post("/api/auth/register", json=payload)
    assert r.status_code == 409


async def test_register_rejects_short_password(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/auth/register",
        json={"email": "x@example.com", "password": "short"},
    )
    assert r.status_code == 422


async def test_login_success_and_failure(client: httpx.AsyncClient) -> None:
    await client.post(
        "/api/auth/register", json={"email": "bob@example.com", "password": "password123"}
    )
    ok = await client.post(
        "/api/auth/login", json={"email": "bob@example.com", "password": "password123"}
    )
    assert ok.status_code == 200
    assert ok.json()["token"]

    bad = await client.post(
        "/api/auth/login", json={"email": "bob@example.com", "password": "nope"}
    )
    assert bad.status_code == 401


async def test_me_requires_token(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (
        await client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"})
    ).status_code == 401


async def test_me_returns_current_user(client: httpx.AsyncClient) -> None:
    reg = await client.post(
        "/api/auth/register",
        json={
            "email": "me@example.com",
            "password": "password123",
            "name": "Me",
        },
    )
    token = reg.json()["token"]
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "me@example.com"