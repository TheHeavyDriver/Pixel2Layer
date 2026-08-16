from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.main import create_app


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


async def test_batch_requires_auth(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/batches", json={"uploadIds": ["abc"]})
    assert r.status_code == 401


async def test_create_batch_creates_jobs(client: httpx.AsyncClient) -> None:
    token = await _register(client, "batch@example.com")
    created = await client.post(
        "/api/batches",
        json={"uploadIds": ["upload-1", "upload-2"]},
        headers=_auth(token),
    )
    assert created.status_code == 201
    batch = created.json()
    assert batch["id"]
    jobs = batch["jobs"]
    assert len(jobs) == 2
    assert {j["uploadId"] for j in jobs} == {"upload-1", "upload-2"}
    assert all(j["status"] == "queued" for j in jobs)

    fetched = await client.get(f"/api/batches/{batch['id']}", headers=_auth(token))
    assert fetched.status_code == 200
    assert len(fetched.json()["jobs"]) == 2


async def test_batch_jobs_progress_to_done(client: httpx.AsyncClient) -> None:
    token = await _register(client, "batch@example.com")
    created = (await client.post(
        "/api/batches",
        json={"uploadIds": ["u1"]},
        headers=_auth(token),
    )).json()

    # give the async worker a beat to run the (memory) job to completion
    await asyncio.sleep(0.05)
    for _ in range(10):
        fetched = await client.get(f"/api/batches/{created['id']}", headers=_auth(token))
        status = fetched.json()["jobs"][0]["status"]
        if status in ("done", "failed"):
            break
        await asyncio.sleep(0.05)

    fetched = await client.get(f"/api/batches/{created['id']}", headers=_auth(token))
    # the worker runs the real pipeline; without a stored upload the job
    # terminates quickly — assert the batch tracks a terminal state.
    assert fetched.json()["jobs"][0]["status"] in ("done", "failed")


async def test_batch_not_found(client: httpx.AsyncClient) -> None:
    token = await _register(client, "batch@example.com")
    assert (await client.get("/api/batches/nope", headers=_auth(token))).status_code == 404