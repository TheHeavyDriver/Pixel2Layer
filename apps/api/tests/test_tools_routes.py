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


def _two_region_image() -> np.ndarray:
    """Image with two well-separated foreground blobs on a flat background."""
    return make_poster(
        width=160,
        height=120,
        bg=(200, 200, 200),
        shapes=[
            ("circle", 40, 30, 15, (10, 10, 240)),
            ("circle", 120, 90, 15, (10, 220, 10)),
        ],
    )


async def test_detect_regions_returns_region_boxes(client: httpx.AsyncClient) -> None:
    img = _two_region_image()
    r = await client.post(
        "/api/tools/regions",
        files={"file": ("photo.png", to_png_bytes(img), "image/png")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["width"] == 160
    assert body["height"] == 120
    assert len(body["regions"]) == 2
    for region in body["regions"]:
        assert region["label"] == "foreground"
        assert 0 <= region["confidence"] <= 1
        assert region["width"] > 0 and region["height"] > 0
    xs = sorted(region["x"] for region in body["regions"])
    assert xs[0] < 80 < xs[1]


async def test_region_crop_crops_to_region(client: httpx.AsyncClient) -> None:
    img = _two_region_image()
    r = await client.post(
        "/api/tools/region-crop",
        params={"index": 0},
        files={"file": ("photo.png", to_png_bytes(img), "image/png")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["url"].startswith("/api/storage/assets/region-crop-")
    assert body["width"] < 160
    assert body["height"] < 120
    stored = await client.get(body["url"])
    assert stored.status_code == 200
    out = cv2.imdecode(
        np.frombuffer(stored.content, dtype=np.uint8), cv2.IMREAD_UNCHANGED
    )
    assert out is not None
    assert out.shape[1] == body["width"]
    assert out.shape[0] == body["height"]


async def test_region_crop_rejects_unknown_index(client: httpx.AsyncClient) -> None:
    img = _two_region_image()
    r = await client.post(
        "/api/tools/region-crop",
        params={"index": 5},
        files={"file": ("photo.png", to_png_bytes(img), "image/png")},
    )
    assert r.status_code == 422
    assert "region index" in r.json()["detail"]


async def test_region_mask_keep_isolates_region(client: httpx.AsyncClient) -> None:
    img = _two_region_image()
    r = await client.post(
        "/api/tools/region-mask",
        params={"index": 0, "mode": "keep"},
        files={"file": ("photo.png", to_png_bytes(img), "image/png")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["width"] == 160
    assert body["height"] == 120
    stored = await client.get(body["url"])
    assert stored.status_code == 200
    out = cv2.imdecode(
        np.frombuffer(stored.content, dtype=np.uint8), cv2.IMREAD_UNCHANGED
    )
    assert out is not None and out.shape[2] == 4
    alpha = out[:, :, 3]
    # Only one blob survives: pixels near the kept circle are opaque, the
    # other circle is transparent.
    assert alpha[30, 40] == 255
    assert alpha[90, 120] == 0


async def test_region_mask_remove_cuts_region(client: httpx.AsyncClient) -> None:
    img = _two_region_image()
    r = await client.post(
        "/api/tools/region-mask",
        params={"index": 0, "mode": "remove"},
        files={"file": ("photo.png", to_png_bytes(img), "image/png")},
    )
    assert r.status_code == 200
    body = r.json()
    stored = await client.get(body["url"])
    out = cv2.imdecode(
        np.frombuffer(stored.content, dtype=np.uint8), cv2.IMREAD_UNCHANGED
    )
    assert out is not None
    alpha = out[:, :, 3]
    assert alpha[30, 40] == 0
    assert alpha[90, 120] == 255


async def test_region_mask_rejects_invalid_mode(client: httpx.AsyncClient) -> None:
    img = _two_region_image()
    r = await client.post(
        "/api/tools/region-mask",
        params={"index": 0, "mode": "banana"},
        files={"file": ("photo.png", to_png_bytes(img), "image/png")},
    )
    assert r.status_code == 422


async def test_region_ops_require_foreground(client: httpx.AsyncClient) -> None:
    img = make_poster(width=60, height=40, bg=(10, 10, 10))
    for path, params in (
        ("/api/tools/region-crop", {"index": 0}),
        ("/api/tools/region-mask", {"index": 0, "mode": "keep"}),
    ):
        r = await client.post(
            path,
            params=params,
            files={"file": ("flat.png", to_png_bytes(img), "image/png")},
        )
        assert r.status_code == 422