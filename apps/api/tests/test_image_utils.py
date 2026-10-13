from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image

from app.services.image_utils import hexify, hexify_bgr, load_image
from app.services.shape_detector import ShapeDetector


def _png_bytes(arr_rgb: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr_rgb, "RGB").save(buf, "PNG")
    return buf.getvalue()


def _cv_png_bytes(arr_bgr: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", arr_bgr)
    assert ok
    return buf.tobytes()


def test_load_image_exposes_true_rgba() -> None:
    # True blue in RGB = (0, 0, 255); PNG stores it as BGR(255, 0, 0) on disk.
    blue = np.zeros((8, 8, 3), np.uint8)
    blue[:, :, 2] = 255
    img = load_image(_png_bytes(blue))
    assert tuple(img.rgba[0, 0]) == (0, 0, 255, 255)  # RGB order, not BGR
    assert tuple(img.bgr[0, 0]) == (255, 0, 0)
    assert tuple(img.rgb[0, 0]) == (0, 0, 255)


def test_load_image_rgb_property_derives_from_rgba() -> None:
    red = np.zeros((8, 8, 3), np.uint8)
    red[:, :, 0] = 255  # true red
    img = load_image(_png_bytes(red))
    _ = img.rgb  # derived view must not corrupt the cached planes
    _ = img.rgb
    assert tuple(img.rgba[0, 0]) == (255, 0, 0, 255)
    assert tuple(img.rgb[0, 0]) == (255, 0, 0)


def test_hexify_is_rgb_hexify_bgr_is_bgr() -> None:
    assert hexify((230, 0, 0)) == "#E60000"
    assert hexify_bgr((0, 0, 230)) == "#E60000"  # BGR red -> RGB hex
    assert hexify_bgr((255, 0, 0)) == "#0000FF"  # BGR blue -> RGB hex


def test_shape_fill_matches_original_color() -> None:
    # Regression: R/B channel swap made red shapes report blue fills.
    img = np.full((60, 60, 3), (250, 250, 250), np.uint8)
    cv2.rectangle(img, (10, 10), (50, 50), (0, 0, 230), -1)  # BGR = red 230
    shapes = ShapeDetector().detect(load_image(_cv_png_bytes(img)))
    assert shapes, "rectangle should be detected"
    assert shapes[0].params["fill"] == "#E60000"
