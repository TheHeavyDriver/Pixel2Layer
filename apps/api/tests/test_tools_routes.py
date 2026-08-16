from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest

from app.core.config import Settings
from app.main import create_app
from tests.fixtures import make_poster, to_png_bytes


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


def _scene() -> dict:
    return {
        "schemaVersion": 1,
        "canvas": {"width": 400, "height": 300, "background": "#FFFFFF"},
        "layers": [
            {
                "id": "bg",
                "type": "rectangle",
                "name": "Background",
                "transform": {"x": 200, "y": 150, "scaleX": 1, "scaleY": 1, "rotation": 0},
                "fill": "#F0F0F0",
                "width": 400,
                "height": 300,
                "opacity": 1,
                "visible": True,
                "locked": False,
                "confidence": 1.0,
            },
            {
                "id": "h",
                "type": "rectangle",
                "name": "Header",
                "transform": {"x": 200, "y": 50, "scaleX": 1, "scaleY": 1, "rotation": 0},
                "fill": "#112233",
                "width": 360,
                "height": 70,
                "opacity": 1,
                "visible": True,
                "locked": False,
                "confidence": 0.9,
            },
            {
                "id": "f",
                "type": "rectangle",
                "name": "Footer",
                "transform": {"x": 200, "y": 270, "scaleX": 1, "scaleY": 1, "rotation": 0},
                "fill": "#445566",
                "width": 360,
                "height": 60,
                "opacity": 1,
                "visible": True,
                "locked": False,
                "confidence": 0.9,
            },
        ],
        "confidence": {"shapes": 0.9},
        "overallConfidence": 0.9,
    }


async def test_background_removal_returns_masked_cutout(client: httpx.AsyncClient) -> None:
    img = make_poster(
        width=120,
        height=90,
        bg=(230, 230, 230),
        shapes=[("circle", 60, 45, 20, (20, 200, 20))],
    )
    r = await client.post(
        "/api/tools/background-removal",
        files={"file": ("photo.png", to_png_bytes(img), "image/png")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["width"] == 120
    assert body["height"] == 90
    assert body["url"].startswith("/api/storage/assets/bg-removal-")
    stored = await client.get(body["url"])
    assert stored.status_code == 200
    assert stored.content[:8] == b"\x89PNG\r\n\x1a\n"
    out = cv2.imdecode(
        np.frombuffer(stored.content, dtype=np.uint8), cv2.IMREAD_UNCHANGED
    )
    assert out is not None and out.shape[2] == 4
    assert out[:, :, 3].max() > 0  # some foreground alpha preserved


async def test_background_removal_requires_foreground(client: httpx.AsyncClient) -> None:
    img = make_poster(width=60, height=40, bg=(10, 10, 10))
    r = await client.post(
        "/api/tools/background-removal",
        files={"file": ("flat.png", to_png_bytes(img), "image/png")},
    )
    assert r.status_code == 422


async def test_background_removal_rejects_bad_bytes(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/tools/background-removal",
        files={"file": ("bad.png", b"not-an-image", "image/png")},
    )
    assert r.status_code == 400


async def test_grouping_endpoint_returns_suggestions(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/tools/grouping", json={"scene": _scene()})
    assert r.status_code == 200
    groups = r.json()["groups"]
    assert isinstance(groups, list)
    names = {g["name"] for g in groups}
    assert "background" in names
    assert {"header", "footer"} <= names
    header = next(g for g in groups if g["name"] == "header")
    assert "h" in header["elementIds"]