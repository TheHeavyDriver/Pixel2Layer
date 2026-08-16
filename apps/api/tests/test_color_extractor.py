from __future__ import annotations

import numpy as np

from app.services.color_extractor import ColorExtractor
from app.services.image_utils import load_image
from tests.fixtures import make_poster, to_png_bytes


def _full_mask(img: np.ndarray) -> np.ndarray:
    return np.full((img.shape[0], img.shape[1]), 255, dtype=np.uint8)


def test_dominant_color_solid_region() -> None:
    img = np.full((100, 100, 3), (250, 20, 20), dtype=np.uint8)  # BGR -> red-ish
    loaded = load_image(to_png_bytes(img))
    region = ColorExtractor().extract(loaded, _full_mask(img))
    assert region.colors
    assert region.colors[0].kind == "solid"
    assert region.colors[0].fraction > 0.9
    assert region.colors[0].hex == "#1414FA"  # BGR(250,20,20) -> RGB(20,20,250)


def test_detects_linear_gradient() -> None:
    img = make_poster(width=120, height=80, gradient=True)
    loaded = load_image(to_png_bytes(img))
    mask = _full_mask(img)
    region = ColorExtractor().extract(loaded, mask)
    assert region.gradient is not None
    assert region.gradient.kind == "linear"
    assert region.gradient.angle == 0.0  # left->right
    assert region.gradient.start != region.gradient.end


def test_solid_bg_no_gradient() -> None:
    img = np.full((80, 80, 3), (100, 100, 100), dtype=np.uint8)
    loaded = load_image(to_png_bytes(img))
    region = ColorExtractor().extract(loaded, _full_mask(img))
    assert region.gradient is None


def test_partial_mask_uses_bounds() -> None:
    img = np.full((120, 120, 3), (0, 0, 0), dtype=np.uint8)
    # draw a small white square region at top-left
    img[10:30, 10:30] = (255, 255, 255)
    loaded = load_image(to_png_bytes(img))
    mask = np.zeros((120, 120), dtype=np.uint8)
    mask[10:30, 10:30] = 255
    region = ColorExtractor().extract(loaded, mask)
    x, y, w, h = region.bounds
    assert (x, y) == (10, 10)
    assert (w, h) == (20, 20)
    assert region.colors[0].hex == "#FFFFFF"