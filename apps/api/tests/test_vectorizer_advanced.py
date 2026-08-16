from __future__ import annotations

from io import BytesIO

import cv2
import numpy as np
from PIL import Image

from app.services.export_service import ExportService
from app.services.image_utils import load_image
from app.services.vectorizer import Vectorizer
from tests.fixtures import make_poster, to_png_bytes


def _detect(img: np.ndarray, **kwargs) -> list:
    return Vectorizer(**kwargs).detect(load_image(to_png_bytes(img)))


def test_multicolor_regions_become_separate_vectors() -> None:
    # A complex illustration: three disjoint flat-colored irregular blobs.
    img = make_poster(width=240, height=180, bg=(245, 245, 245))
    cv2.fillPoly(
        img,
        [np.array([[30, 40], [70, 25], [90, 60], [60, 90], [30, 75]], np.int32)],
        (200, 60, 60),
    )
    cv2.fillPoly(
        img,
        [np.array([[120, 30], [165, 28], [185, 55], [150, 95], [118, 80]], np.int32)],
        (50, 150, 60),
    )
    cv2.fillPoly(
        img,
        [np.array([[130, 120], [190, 110], [200, 150], [170, 175], [120, 160]], np.int32)],
        (60, 90, 210),
    )

    vectors = _detect(img, min_area=60)
    # three regions (plus no background / no duplicate), each its own path+fill
    assert len(vectors) >= 3
    fills = {v.fill for v in vectors if v.fill}
    assert len(fills) >= 3
    # regions carry separate bounds instead of being merged into one blob
    assert len({round(v.x) for v in vectors}) >= 3


def test_ring_emits_hole_as_reversed_subpath() -> None:
    # Donut: filled disc with a background-colored hole burned into it.
    img = make_poster(width=180, height=150, bg=(250, 250, 250))
    cv2.circle(img, (90, 75), 42, (220, 70, 40), thickness=-1)
    cv2.circle(img, (90, 75), 16, (250, 250, 250), thickness=-1)  # the hole

    vectors = _detect(img, min_area=60)
    assert vectors, "expected the ring to be detected"
    ring = max(vectors, key=lambda v: v.width * v.height)
    # two subpaths: outer + inner hole (path contains a second M)
    assert ring.path.count("M") >= 2
    assert ring.path.rstrip().endswith("Z")
    assert ring.fill and ring.fill.startswith("#")


def test_curved_region_emits_bezier_commands() -> None:
    img = make_poster(width=200, height=160, bg=(245, 245, 245))
    cv2.circle(img, (100, 80), 50, (40, 120, 220), thickness=-1)
    vectors = _detect(img, min_area=60)
    assert vectors
    blob = max(vectors, key=lambda v: v.width * v.height)
    # smooth contour → quadratic bezier segments, not just line segments
    assert "Q " in blob.path


def test_light_blob_on_dark_background_is_recovered() -> None:
    img = make_poster(width=200, height=150, bg=(30, 30, 30))
    cv2.fillPoly(
        img,
        [np.array([[40, 40], [90, 25], [130, 60], [80, 110], [35, 90]], np.int32)],
        (240, 240, 240),
    )
    vectors = _detect(img, min_area=60)
    assert vectors, "expected light blob on dark bg to be vectorized"
    blob = max(vectors, key=lambda v: v.width * v.height)
    # the foreground (light) region, not the dark background
    assert blob.fill and blob.fill.startswith("#F")
    assert blob.path.startswith("M ")


def test_solid_background_produces_no_vectors() -> None:
    img = make_poster(width=100, height=80, bg=(240, 240, 240))
    assert _detect(img, min_area=50) == []


def test_png_export_renders_ring_with_unfilled_center() -> None:
    """The even-odd (XOR) raster fill punches the hole out of the disc."""
    from app.schemas.scene_graph import SceneGraph, Transform, VectorElement

    ring_path = _detect(
        (lambda img: img)(
            _ring_image()
        ),
        min_area=60,
    )[0].path
    graph = SceneGraph(
        schemaVersion=1,
        canvas={"width": 180, "height": 150, "background": "#FFFFFF"},
        layers=[
            VectorElement(
                id="v1",
                type="vector",
                name="Ring",
                transform=Transform(x=90, y=75),
                path=ring_path,
                width=84,
                height=84,
                fill="#FF0000",
                confidence=0.8,
            )
        ],
        confidence={"vector": 0.8},
        overallConfidence=0.8,
    )
    data = ExportService().rasterize(graph, "png").data
    img = Image.open(BytesIO(data)).convert("RGBA")

    def is_red(x: int, y: int) -> bool:
        r, g, b, _ = img.getpixel((x, y))
        return r > 180 and g < 90 and b < 90

    # annulus band is red
    assert any(is_red(x, y) for x in range(60, 120) for y in range(60, 90))
    # the center hole is not red (punched out)
    center = [is_red(x, y) for x in range(85, 95) for y in range(70, 80)]
    assert not any(center)


def test_svg_export_marks_multisubpath_path_evenodd() -> None:
    from app.schemas.scene_graph import SceneGraph, Transform, VectorElement

    graph = SceneGraph(
        schemaVersion=1,
        canvas={"width": 100, "height": 100, "background": "#FFFFFF"},
        layers=[
            VectorElement(
                id="v1",
                type="vector",
                name="Ring",
                transform=Transform(x=50, y=50),
                path="M 0 0 L 40 0 L 40 40 Z M 10 10 L 10 30 L 30 30 Z",
                width=40,
                height=40,
                fill="#123456",
                confidence=0.8,
            )
        ],
        confidence={"vector": 0.8},
        overallConfidence=0.8,
    )
    svg = ExportService().to_svg(graph).data.decode("utf-8")
    assert 'fill-rule="evenodd"' in svg
    assert 'd="M 0 0 L 40 0 L 40 40 Z M 10 10 L 10 30 L 30 30 Z"' in svg


def _ring_image() -> np.ndarray:
    img = make_poster(width=180, height=150, bg=(250, 250, 250))
    cv2.circle(img, (90, 75), 42, (220, 70, 40), thickness=-1)
    cv2.circle(img, (90, 75), 16, (250, 250, 250), thickness=-1)
    return img


def test_vectorizer_names_remain_closed_paths() -> None:
    """Regression: simple blobs still produce single closed paths starting M/Z."""
    img = make_poster(width=200, height=150, bg=(240, 240, 240))
    pts = np.array([[40, 40], [90, 30], [120, 70], [80, 110], [30, 90]], dtype=np.int32)
    cv2.fillPoly(img, [pts], (200, 60, 60))
    vectors = _detect(img, min_area=60)
    assert vectors
    vec = max(vectors, key=lambda v: v.width * v.height)
    assert vec.path.startswith("M ")
    assert vec.path.rstrip().endswith("Z")
    assert vec.width > 0 and vec.height > 0