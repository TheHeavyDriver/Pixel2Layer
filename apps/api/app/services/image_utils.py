from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class LoadedImage:
    """Normalized image for downstream pipeline modules."""

    bgr: np.ndarray  # uint8 BGR, (H, W, 3)
    rgba: np.ndarray  # uint8 RGBA, (H, W, 4)
    width: int
    height: int

    @property
    def rgb(self) -> np.ndarray:
        return cv2.cvtColor(self.bgr, cv2.COLOR_BGR2RGB)


def load_image(data: bytes) -> LoadedImage:
    """Decode raw image bytes into RGBA + BGR arrays with correct channel order.

    OpenCV decodes to BGR/BGRA, so we normalize to BGRA first and then derive
    a true RGBA and a true BGR view — getting this wrong silently swaps red
    and blue everywhere downstream (fills, cutouts, exports).
    """
    raw = np.frombuffer(data, dtype=np.uint8)
    decoded = cv2.imdecode(raw, cv2.IMREAD_UNCHANGED)
    if decoded is None:
        raise ValueError("could not decode image data")
    if decoded.ndim == 2:
        bgra = cv2.cvtColor(decoded, cv2.COLOR_GRAY2BGRA)
    elif decoded.shape[2] == 3:
        bgra = cv2.cvtColor(decoded, cv2.COLOR_BGR2BGRA)
    elif decoded.shape[2] == 4:
        bgra = decoded
    else:
        raise ValueError("could not decode image data")
    rgba = cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGBA)
    bgr = cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)
    height, width = rgba.shape[:2]
    return LoadedImage(bgr=bgr, rgba=rgba, width=width, height=height)


def hexify(rgb: tuple[int, int, int]) -> str:
    r, g, b = (int(v) for v in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def hexify_bgr(bgr) -> str:
    """Format a BGR channel triple (OpenCV pixel/mean/centroid) as a hex color."""
    b, g, r = (float(v) for v in bgr)
    return hexify((int(round(r)), int(round(g)), int(round(b))))