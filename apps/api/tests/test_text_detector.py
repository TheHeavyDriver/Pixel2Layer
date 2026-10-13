from __future__ import annotations

import asyncio

import cv2
import numpy as np

from app.services.image_utils import load_image
from app.services.text_detector import VisionTextDetector
from tests.fixtures import to_png_bytes

rng = np.random.default_rng(0)


def _detect(img: np.ndarray):
    detector = VisionTextDetector()
    return asyncio.run(detector.detect(load_image(to_png_bytes(img))))


# -- images that must NOT produce text layers ---------------------------


def test_flat_color_has_no_text() -> None:
    assert _detect(np.full((300, 400, 3), 240, np.uint8)) == []


def test_geometric_shapes_have_no_text() -> None:
    img = np.full((300, 400, 3), (250, 250, 250), np.uint8)
    cv2.circle(img, (120, 150), 70, (60, 90, 220), -1)
    cv2.rectangle(img, (250, 80), (370, 220), (220, 80, 60), -1)
    assert _detect(img) == []


def test_ring_has_no_text() -> None:
    img = np.full((300, 400, 3), (250, 250, 250), np.uint8)
    cv2.ellipse(img, (150, 150), (90, 55), 0, 0, 360, (60, 90, 220), -1)
    cv2.circle(img, (150, 150), 40, (250, 250, 250), -1)
    assert _detect(img) == []


def test_stripes_have_no_text() -> None:
    diag = np.full((300, 400, 3), (250, 250, 250), np.uint8)
    for i in range(-300, 400, 24):
        cv2.line(diag, (i, 0), (i + 300, 300), (60, 60, 60), 6)
    assert _detect(diag) == []

    vert = np.full((300, 400, 3), (250, 250, 250), np.uint8)
    for i in range(0, 400, 30):
        cv2.rectangle(vert, (i, 0), (i + 12, 300), (60, 60, 60), -1)
    assert _detect(vert) == []

    horiz = np.full((300, 400, 3), (250, 250, 250), np.uint8)
    for i in range(0, 300, 30):
        cv2.rectangle(horiz, (0, i), (400, i + 12), (60, 60, 60), -1)
    assert _detect(horiz) == []


def test_checkerboard_grid_has_no_text() -> None:
    img = np.full((300, 400, 3), (250, 250, 250), np.uint8)
    for y in range(0, 300, 40):
        for x in range(0, 400, 40):
            if (x // 40 + y // 40) % 2 == 0:
                cv2.rectangle(img, (x, y), (x + 40, y + 40), (60, 60, 60), -1)
    assert _detect(img) == []


def test_brick_texture_has_no_text() -> None:
    img = np.full((300, 400, 3), (250, 250, 250), np.uint8)
    for y in range(0, 300, 30):
        off = 0 if (y // 30) % 2 == 0 else 40
        for x in range(-40, 400, 80):
            cv2.rectangle(img, (x + off, y), (x + off + 76, y + 26), (180, 120, 110), -1)
    assert _detect(img) == []


def test_noise_has_no_text() -> None:
    noise = rng.integers(0, 255, (300, 400, 3), dtype=np.uint8)
    assert _detect(noise) == []
    blurred = cv2.GaussianBlur(noise, (0, 0), 2)
    assert _detect(blurred) == []


def test_smooth_gradient_has_no_text() -> None:
    ramp = np.linspace(180, 240, 400).astype(np.uint8)
    img = np.zeros((300, 400, 3), np.uint8)
    img[:, :, 0] = ramp
    img[:, :, 1] = ramp
    img[:, :, 2] = ramp
    assert _detect(img) == []


def test_photo_has_no_text() -> None:
    photo = rng.normal((90, 140, 180), 45, (300, 400, 3)).clip(0, 255).astype(np.uint8)
    assert _detect(photo) == []


# -- images that DO contain text ----------------------------------------


def test_big_text_detected_with_dark_color() -> None:
    img = np.full((300, 400, 3), (255, 255, 255), np.uint8)
    cv2.putText(img, "HELLO WORLD", (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (20, 20, 20), 3)
    texts = _detect(img)
    assert len(texts) == 1
    assert texts[0].is_guess
    assert texts[0].font_color == "#141414"
    assert texts[0].width > 100 and texts[0].height >= 20


def test_small_multiline_text_detected() -> None:
    img = np.full((300, 400, 3), (255, 255, 255), np.uint8)
    cv2.putText(
        img, "Small caption text here", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30, 30, 30), 1
    )
    cv2.putText(
        img, "Second line of copy", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30, 30, 30), 1
    )
    assert len(_detect(img)) >= 1


def test_light_on_dark_text_detected() -> None:
    img = np.full((300, 400, 3), (25, 25, 60), np.uint8)
    cv2.putText(img, "LIGHT ON DARK", (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (250, 250, 250), 3)
    texts = _detect(img)
    assert len(texts) == 1
    assert texts[0].font_color == "#FAFAFA"  # white, not gray


def test_colored_text_keeps_its_color() -> None:
    img = np.full((300, 400, 3), (255, 255, 255), np.uint8)
    # BGR (0, 0, 230) = pure red RGB(230, 0, 0)
    cv2.putText(img, "RED TEXT", (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 230), -1)
    texts = _detect(img)
    assert len(texts) == 1
    assert texts[0].font_color == "#E60000"


def test_huge_display_glyph_text_detected() -> None:
    img = np.full((400, 600, 3), (255, 255, 255), np.uint8)
    cv2.putText(img, "BIG", (60, 260), cv2.FONT_HERSHEY_SIMPLEX, 7.0, (10, 10, 10), 10)
    texts = _detect(img)
    assert len(texts) == 1
    assert texts[0].font_color == "#0A0A0A"


def test_text_on_textured_background_detected() -> None:
    img = rng.normal(150, 25, (300, 400, 3)).clip(0, 255).astype(np.uint8)
    cv2.putText(img, "CAPTION", (40, 160), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (15, 15, 15), 3)
    assert len(_detect(img)) == 1


def test_text_next_to_shapes_only_yields_the_text() -> None:
    img = np.full((300, 400, 3), (245, 245, 245), np.uint8)
    cv2.circle(img, (320, 60), 50, (60, 90, 220), -1)
    # BGR (200, 40, 40) = blue RGB(40, 40, 200)
    cv2.putText(img, "SALE TODAY", (40, 230), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (200, 40, 40), 3)
    texts = _detect(img)
    assert len(texts) == 1  # the circle must not become a text layer
    assert texts[0].font_color == "#2828C8"
    # the region hugs the text, not the circle
    assert texts[0].y > 150
