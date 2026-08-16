from __future__ import annotations

import cv2
import numpy as np


def make_poster(
    *,
    width: int = 320,
    height: int = 240,
    bg: tuple[int, int, int] = (240, 240, 240),
    shapes: list[tuple] | None = None,
    gradient: bool = False,
) -> np.ndarray:
    """Build a flat-color graphic-design fixture in BGR (OpenCV layout)."""
    if gradient:
        # left->right gradient between two colors
        x = np.linspace(0, 1, width, dtype=np.float32)
        ramp = np.zeros((height, width, 3), dtype=np.float32)
        for _c in range(3):
            ramp[:, :, _c] = bg[_c] * (1 - x) + 50 * x
        img = ramp.astype(np.uint8)
    else:
        img = np.full((height, width, 3), bg, dtype=np.uint8)

    for spec in shapes or []:
        kind = spec[0]
        if kind == "circle":
            _, cx, cy, r, color = spec
            cv2.circle(img, (cx, cy), r, color, thickness=-1)
        elif kind == "rect":
            _, x, y, w, h, color = spec
            cv2.rectangle(img, (x, y), (x + w, y + h), color, thickness=-1)
        elif kind == "line":
            _, x1, y1, x2, y2, color = spec
            cv2.line(img, (x1, y1), (x2, y2), color, thickness=4)
        elif kind == "polygon":
            _, pts, color = spec
            cv2.fillPoly(img, [np.array(pts, dtype=np.int32)], color)
        elif kind == "ellipse":
            _, cx, cy, rx, ry, color = spec
            cv2.ellipse(img, (cx, cy), (rx, ry), 0, 0, 360, color, thickness=-1)
    return img


def to_png_bytes(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("imencode failed")
    return buf.tobytes()