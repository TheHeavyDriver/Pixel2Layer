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
    """Decode raw image bytes into an RGBA-normalized array (preserving alpha)."""
    raw = np.frombuffer(data, dtype=np.uint8)
    rgba = cv2.imdecode(raw, cv2.IMREAD_UNCHANGED)
    if rgba is None:
        raise ValueError("could not decode image data")
    if rgba.ndim == 2:
        rgba = cv2.cvtColor(rgba, cv2.COLOR_GRAY2RGBA)
    elif rgba.shape[2] == 3:
        rgba = cv2.cvtColor(rgba, cv2.COLOR_RGB2RGBA)
    bgr = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
    height, width = rgba.shape[:2]
    return LoadedImage(bgr=bgr, rgba=rgba, width=width, height=height)


def hexify(rgb: tuple[int, int, int]) -> str:
    r, g, b = (int(v) for v in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"