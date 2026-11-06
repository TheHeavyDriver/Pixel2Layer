from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.core.exceptions import ImageDecodeError


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
        raise ImageDecodeError("could not decode image data")
    if decoded.ndim == 2:
        bgra = cv2.cvtColor(decoded, cv2.COLOR_GRAY2BGRA)
    elif decoded.shape[2] == 3:
        bgra = cv2.cvtColor(decoded, cv2.COLOR_BGR2BGRA)
    elif decoded.shape[2] == 4:
        bgra = decoded
    else:
        raise ImageDecodeError("could not decode image data")
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


def estimate_background_color(bgr: np.ndarray, use_mean: bool = False) -> np.ndarray:
    """Estimate background color from the image border.
    
    Samples a 4-pixel border strip around the image edges and returns the
    aggregated BGR color. For very small images (< 8px either dimension), 
    samples the entire image instead.
    
    Args:
        bgr: BGR image array (H, W, 3)
        use_mean: If True, uses mean; if False (default), uses median
    
    Returns:
        BGR color triple as np.ndarray of shape (3,)
    """
    h, w = bgr.shape[:2]
    edge = 4
    if h < 8 or w < 8:
        samples = bgr.reshape(-1, 3)
    else:
        samples = np.concatenate(
            [
                bgr[:edge, :, :].reshape(-1, 3),
                bgr[-edge:, :, :].reshape(-1, 3),
                bgr[:, :edge, :].reshape(-1, 3),
                bgr[:, -edge:, :].reshape(-1, 3),
            ]
        )
    if use_mean:
        return samples.mean(axis=0)
    return np.median(samples, axis=0)