from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import cv2
import httpx
import numpy as np
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


def _scene() -> dict:
    return {
        "schemaVersion": 1,
        "canvas": {"width": 200, "height": 150, "background": "#FFFFFF"},
        "layers": [
            {
                "id": "rect_1",
                "type": "rectangle",
                "name": "Rect",
                "transform": {"x": 100, "y": 75, "scaleX": 1, "scaleY": 1, "rotation": 0},
                "fill": "#FF0000",
                "stroke": None,
                "strokeWidth": None,
                "strokeDashArray": None,
                "opacity": 1,
                "visible": True,
                "locked": False,
                "confidence": 0.95,
                "confidenceNote": None,
                "width": 80,
                "height": 60,
                "rx": 0,
                "ry": 0,
            }
        ],
        "confidence": {"shapes": 0.95},
        "overallConfidence": 0.95,
    }


async def test_export_png(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/export", json={"format": "png", "scan": 1.0, "scene": _scene()})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert 'filename="design.png"' in r.headers["content-disposition"]


async def test_export_svg(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/export", json={"format": "svg", "scan": 1.0, "scene": _scene()})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"
    assert r.content.decode().startswith("<svg")


async def test_export_pdf(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/export", json={"format": "pdf", "scan": 1.0, "scene": _scene()})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    assert 'filename="design.pdf"' in r.headers["content-disposition"]


async def test_export_rejects_bad_format(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/export", json={"format": "gif", "scan": 1.0, "scene": _scene()})
    assert r.status_code == 422


async def test_p2l_save_and_import_roundtrip(client: httpx.AsyncClient) -> None:
    saved = await client.post(
        "/api/export/p2l",
        json={"scene": _scene(), "name": "poster"},
    )
    assert saved.status_code == 200
    assert saved.headers["content-type"] == "application/json"

    loaded = await client.post(
        "/api/export/import",
        files={"file": ("poster.p2l", saved.content, "application/json")},
    )
    assert loaded.status_code == 200
    scene = loaded.json()
    assert scene["canvas"]["width"] == 200
    assert scene["layers"][0]["type"] == "rectangle"
    assert 'name' in loaded.headers["x-p2l-metadata"]


async def test_import_rejects_garbage(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/export/import",
        files={"file": ("bad.p2l", b"not-json", "application/json")},
    )
    assert r.status_code == 400


async def test_export_png_can_reopen_in_pipeline(client: httpx.AsyncClient) -> None:
    """Export output is a valid PNG the pipeline would accept as input."""
    r = await client.post("/api/export", json={"format": "png", "scan": 1.0, "scene": _scene()})
    assert r.status_code == 200
    img = cv2.imdecode(np.frombuffer(r.content, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img is not None
    assert img.shape[:2] == (150, 200)