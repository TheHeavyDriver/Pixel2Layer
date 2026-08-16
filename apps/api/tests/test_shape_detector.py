from __future__ import annotations

from app.services.image_utils import load_image
from app.services.shape_detector import ShapeDetector
from tests.fixtures import make_poster, to_png_bytes


def test_detects_circle() -> None:
    img = make_poster(width=200, height=150, shapes=[("circle", 90, 70, 40, (40, 40, 200))])
    shapes = ShapeDetector().detect(load_image(to_png_bytes(img)))
    circles = [s for s in shapes if s.kind == "circle"]
    assert len(circles) == 1
    c = circles[0]
    # radius ~40 within tolerance
    assert 30 <= c.params["radius"] <= 50
    assert c.params["fill"] == "#C82828"
    assert c.confidence > 0.8


def test_detects_rectangle() -> None:
    img = make_poster(
        width=220, height=160,
        shapes=[("rect", 30, 20, 100, 60, (60, 180, 60))],
    )
    shapes = ShapeDetector().detect(load_image(to_png_bytes(img)))
    rects = [s for s in shapes if s.kind == "rectangle"]
    assert len(rects) == 1
    r = rects[0]
    assert 90 <= r.params["width"] <= 110
    assert 50 <= r.params["height"] <= 70
    # fill should be near #3CB43C (BGR 60,180,60)
    assert r.params["fill"].startswith("#3")


def test_detects_ellipse() -> None:
    img = make_poster(
        width=220, height=160,
        shapes=[("ellipse", 110, 70, 60, 30, (200, 60, 60))],
    )
    shapes = ShapeDetector().detect(load_image(to_png_bytes(img)))
    ellipses = [s for s in shapes if s.kind == "ellipse"]
    assert len(ellipses) == 1
    e = ellipses[0]
    long, short = max(e.params["rx"], e.params["ry"]), min(e.params["rx"], e.params["ry"])
    assert 45 <= long <= 65
    assert 20 <= short <= 35


def test_detects_line() -> None:
    img = make_poster(
        width=200, height=150,
        shapes=[("line", 20, 75, 180, 75, (30, 30, 30))],
    )
    shapes = ShapeDetector().detect(load_image(to_png_bytes(img)))
    lines = [s for s in shapes if s.kind == "line"]
    assert len(lines) >= 1
    line = lines[0]
    assert abs((line.params["x2"] - line.params["x1"]) - 160) < 8  # horizontal-ish span


def test_detects_polygon() -> None:
    pts = [(50, 30), (110, 30), (80, 90)]
    img = make_poster(width=160, height=120, shapes=[("polygon", pts, (240, 180, 40))])
    shapes = ShapeDetector().detect(load_image(to_png_bytes(img)))
    polygons = [s for s in shapes if s.kind == "polygon"]
    assert len(polygons) == 1
    assert len(polygons[0].params["points"]) == 3


def test_empty_image_produces_no_shapes() -> None:
    img = make_poster(width=80, height=60)  # solid bg only
    shapes = ShapeDetector().detect(load_image(to_png_bytes(img)))
    assert len(shapes) == 0