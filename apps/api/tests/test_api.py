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
        environment="test",
        cors_origins="http://localhost:3000,http://localhost:3001",
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c


async def test_health(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["jobBackend"] == "memory"


async def test_upload_then_job_then_result(
    client: httpx.AsyncClient,
) -> None:
    # upload
    up = await client.post(
        "/api/upload",
        files={"file": ("poster.png", b"\x89PNG\r\n\x1a\nhello", "image/png")},
    )
    assert up.status_code == 201
    upload_json = up.json()
    assert upload_json["extension"] == "png"
    assert upload_json["uploadId"]

    # create job
    job = await client.post("/api/jobs", json={"upload_id": upload_json["uploadId"]})
    assert job.status_code == 202
    job_id = job.json()["id"]
    assert job.json()["status"] == "queued"

    # poll until done
    final = None
    for _ in range(200):
        get_r = await client.get(f"/api/jobs/{job_id}")
        assert get_r.status_code == 200
        state = get_r.json()
        if state["status"] in ("done", "failed"):
            final = state
            break
        await asyncio.sleep(0.01)
    assert final is not None
    assert final["status"] == "done"
    assert final["result"]["upload_id"] == upload_json["uploadId"]


async def test_upload_rejects_bad_type(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/upload",
        files={"file": ("x.gif", b"gif", "image/gif")},
    )
    assert r.status_code == 400


async def test_job_events_sse(client: httpx.AsyncClient) -> None:
    up = await client.post(
        "/api/upload",
        files={"file": ("poster.png", b"pngbytes", "image/png")},
    )
    upload_id = up.json()["uploadId"]

    job = await client.post("/api/jobs", json={"upload_id": upload_id})
    job_id = job.json()["id"]

    async with client.stream("GET", f"/api/jobs/{job_id}/events") as resp:
        assert resp.status_code == 200
        body = ""
        async for chunk in resp.aiter_text():
            body += chunk
            if "event:done" in body:
                break

    assert "event: done" in body
    assert "status" in body


async def test_job_404(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/jobs/nonexistent")
    assert r.status_code == 404