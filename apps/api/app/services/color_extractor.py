from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from sklearn.cluster import KMeans

from app.services.image_utils import LoadedImage, hexify


@dataclass
class DetectedColor:
    hex: str
    fraction: float  # share of pixels (0..1)
    kind: str  # "solid" | "gradient-start" | "gradient-end"


@dataclass
class Gradient:
    start: str
    end: str
    angle: float  # degrees, 0 = left->right, 90 = top->bottom
    kind: str = "linear"


@dataclass
class Region:
    mask: np.ndarray
    bounds: tuple[int, int, int, int]  # x, y, w, h
    colors: list[DetectedColor] = field(default_factory=list)
    gradient: Gradient | None = None


class ColorExtractor:
    """Extracts dominant colors and simple two-stop linear gradients per region.

    K-means clustering (k<=3) over region pixels gives the dominant color; a
    mean-intensity scan across rows/columns detects linear gradients.
    """

    def __init__(self, max_colors: int = 3) -> None:
        self.max_colors = max_colors

    def extract(self, image: LoadedImage, mask: np.ndarray) -> Region:
        ys, xs = np.nonzero(mask)
        if len(ys) == 0:
            return Region(mask=mask, bounds=(0, 0, 0, 0))
        x, y = int(xs.min()), int(ys.min())
        w, h = int(xs.max() - x + 1), int(ys.max() - y + 1)
        region_mask = mask[y : y + h, x : x + w]
        patch = image.bgr[y : y + h, x : x + w]
        colors = self._dominant_colors(patch, region_mask)
        gradient = self._detect_gradient(patch, region_mask)
        return Region(mask=mask, bounds=(x, y, w, h), colors=colors, gradient=gradient)

    # -- dominant colors ----------------------------------------------------------
    def _dominant_colors(self, patch: np.ndarray, mask: np.ndarray) -> list[DetectedColor]:
        pixels = patch.reshape(-1, 3)[mask.reshape(-1) > 0]
        if len(pixels) == 0:
            return [DetectedColor(hex="#000000", fraction=1.0, kind="solid")]

        k = min(self.max_colors, len(pixels))
        # Degenerate single-color regions: k-means would warn — return early.
        span = pixels.max(axis=0) - pixels.min(axis=0)
        if int(span.sum()) <= 2:
            mean = pixels.mean(axis=0)
            return [DetectedColor(hex=hexify(tuple(mean)), fraction=1.0, kind="solid")]

        kmeans = KMeans(n_clusters=k, n_init=5, random_state=0)
        labels = kmeans.fit_predict(pixels.astype(np.float32))
        counts = np.bincount(labels, minlength=k)
        order = np.argsort(-counts)
        return [
            DetectedColor(
                hex=hexify(tuple(kmeans.cluster_centers_[i])),
                fraction=float(counts[i] / labels.size),
                kind="solid",
            )
            for i in order
        ]

    # -- gradient detection -------------------------------------------------------
    def _detect_gradient(self, patch: np.ndarray, mask: np.ndarray) -> Gradient | None:
        h, w = patch.shape[:2]
        if h < 3 or w < 3:
            return None

        # Grab the endpoints from real masked pixels.
        ys, xs = np.nonzero(mask)
        start = hexify(tuple(patch[ys[0], xs[0], :3]))
        end = hexify(tuple(patch[ys[-1], xs[-1], :3]))
        if start == end:
            return None

        col_means = self._masked_means(patch, mask, axis="x")  # per column -> varies along x
        row_means = self._masked_means(patch, mask, axis="y")  # per row -> varies along y
        x_ok, x_slope = self._linear_coherence(col_means)
        y_ok, y_slope = self._linear_coherence(row_means)

        if not (x_ok or y_ok):
            return None
        if not (x_ok or y_ok):
            return None
        if x_ok and (not y_ok or abs(x_slope) >= abs(y_slope)):
            angle = 0.0
        else:
            angle = 90.0
        return Gradient(start=start, end=end, angle=angle)

    def _masked_means(self, patch: np.ndarray, mask: np.ndarray, axis: str) -> np.ndarray:
        h, w = patch.shape[:2]
        gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gray[gray == 0] = np.nan  # treat as background
        if axis == "x":  # per column
            return np.nanmean(np.where(mask > 0, gray, np.nan), axis=0)
        return np.nanmean(np.where(mask > 0, gray, np.nan), axis=1)

    @staticmethod
    def _linear_coherence(vals: np.ndarray) -> tuple[bool, float]:
        valid = vals[~np.isnan(vals)]
        if len(valid) < 3:
            return False, 0.0
        idx = np.arange(len(vals))
        # interpolate nan for a smooth fit
        filled = np.array(vals)
        filled[np.isnan(filled)] = np.interp(
            np.flatnonzero(np.isnan(filled)), np.flatnonzero(~np.isnan(filled)), valid
        )
        res = np.polyfit(idx, filled, 1)
        fit = np.polyval(res, idx)
        resid = np.mean(np.abs(filled - fit))
        span = filled.max() - filled.min()
        return bool(span > 18 and resid < span * 0.35), float(res[0])