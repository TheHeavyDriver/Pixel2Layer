from __future__ import annotations

import numpy as np

from app.services.image_utils import load_image
from app.services.progressive import ProgressiveRouter
from tests.fixtures import make_poster, to_png_bytes


def test_flat_graphics_routes_to_vectorize_not_segment() -> None:
    img = make_poster(
        width=240, height=180, bg=(240, 240, 240),
        shapes=[
            ("circle", 60, 90, 30, (200, 40, 40)),
            ("rect", 120, 50, 80, 50, (40, 90, 200)),
        ],
    )
    image = load_image(to_png_bytes(img))
    complexity = ProgressiveRouter().classify(image)
    assert complexity.kind == "graphic"
    assert ProgressiveRouter().should_vectorize(complexity) is True
    assert ProgressiveRouter().should_segment(complexity) is False


def test_photograph_routes_to_segment() -> None:
    # noise everywhere → photographic-like texture, many colors
    rng = np.random.default_rng(7)
    img = rng.integers(0, 255, (160, 200, 3), dtype=np.uint8)
    image = load_image(to_png_bytes(img))
    complexity = ProgressiveRouter().classify(image)
    assert complexity.kind == "photographic"
    assert ProgressiveRouter().should_segment(complexity) is True
    assert ProgressiveRouter().should_vectorize(complexity) is False


def test_classify_returns_metrics() -> None:
    img = make_poster(width=100, height=80, bg=(250, 250, 250))
    image = load_image(to_png_bytes(img))
    c = ProgressiveRouter().classify(image)
    assert 0.0 <= c.edge_density <= 1.0
    assert c.unique_colors >= 1
    assert c.flat_ratio >= 0.0
    assert c.score >= 0.0