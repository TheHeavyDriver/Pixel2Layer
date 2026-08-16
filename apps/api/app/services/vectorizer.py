from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from app.services.image_utils import LoadedImage, hexify


@dataclass
class DetectedVector:
    """A region reconstructed as an SVG path (vector) element."""

    path: str
    x: float  # bounds center x (canvas plane)
    y: float  # bounds center y
    width: float
    height: float
    fill: str | None
    confidence: float


class Vectorizer:
    """Converts regions of a flattened illustration into smooth SVG paths.

    Advanced reconstruction (v1.1): instead of a single Otsu silhouette, the
    image is decomposed into its dominant flat colors, and each colored region
    is traced independently:

    * **Per-color decomposition** — complex multi-color illustrations (logos,
      flat illustrations) become independent paths instead of one merged blob.
    * **Hole support** — interior contours (e.g. a ring, letter counters) are
      emitted as reversed-winding subpaths so the nonzero fill rule carves them
      out (renders correctly in Fabric, SVG, and raster exports alike).
    * **Corner-preserving bezier smoothing** — gently-curved contours become
      quadratic bezier (``Q``) curves instead of jagged polylines; real corners
      stay sharp.
    * **Background exclusion + light-on-dark** — the dominant border color is
      excluded, so both dark-on-light and light-on-dark flat graphics recover
      the same foreground regions.

    The output keeps the ``DetectedVector`` contract so the pipeline and
    SceneGraphBuilder are unchanged.
    """

    def __init__(
        self,
        min_area: float = 120.0,
        epsilon_factor: float = 0.015,
        max_candidates: int = 60,
        n_colors: int = 5,
        bg_tolerance: int = 28,
        corner_threshold_deg: float = 55.0,
    ) -> None:
        self.min_area = min_area
        self.epsilon_factor = epsilon_factor
        self.max_candidates = max_candidates
        self.n_colors = n_colors
        self.bg_tolerance = bg_tolerance
        self.corner_threshold_deg = corner_threshold_deg

    # -- region decomposition ---------------------------------------------------
    def detect(self, image: LoadedImage) -> list[DetectedVector]:
        """Vectorize each dominant flat-color region into a smooth path.

        Works on flat-color illustrations/logos, including multi-colored and
        light-on-dark ones (the v1.1 target). Photographic regions are left to
        the Segmenter.
        """
        background = _background_color(image.bgr)
        palette = self._pick_palette(image.bgr, background)

        # Nearest-centroid labels: every pixel belongs to exactly one palette
        # color or the background, so regions never overlap.
        labels = self._assign(image.bgr, palette, background)

        vectors: list[DetectedVector] = []
        for color_idx, color in enumerate(palette):
            mask = (labels == color_idx).astype(np.uint8) * 255
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

            num, components, stats, _ = cv2.connectedComponentsWithStats(
                mask, connectivity=8
            )
            for label in range(1, num):
                if len(vectors) >= self.max_candidates:
                    return vectors
                x, y, w, h, area = stats[label]
                if area < self.min_area:
                    continue
                if w < 8 or h < 8:
                    continue

                comp = (components[y : y + h, x : x + w] == label).astype(np.uint8) * 255
                vector = self._trace_component(comp, x, y, w, h, color, area)
                if vector is not None:
                    vectors.append(vector)
        return vectors

    def _pick_palette(
        self, bgr: np.ndarray, background: np.ndarray
    ) -> list[np.ndarray]:
        """Choose up to ``n_colors`` distinct flat colors, excluding background."""
        pixel = (bgr // 16 * 16).reshape(-1, 3)
        uniq, counts = np.unique(pixel, axis=0, return_counts=True)

        bg = background.astype(int)
        palette: list[np.ndarray] = []
        for u, _cnt in sorted(
            zip(uniq.tolist(), counts.tolist(), strict=False), key=lambda c: -c[1]
        ):
            if len(palette) >= self.n_colors:
                break
            if np.abs(np.asarray(u, dtype=int) - bg).max() <= self.bg_tolerance:
                continue  # background color
            if any(
                np.abs(np.asarray(u, dtype=int) - np.asarray(p, dtype=int)).max()
                <= self.bg_tolerance
                for p in palette
            ):
                continue  # already represented
            palette.append(np.asarray(u, dtype=np.uint8))
        return palette

    def _assign(
        self,
        bgr: np.ndarray,
        palette: list[np.ndarray],
        background: np.ndarray,
    ) -> np.ndarray:
        """Label each pixel with its nearest centroid (palette + background)."""
        h, w = bgr.shape[:2]
        labels = np.zeros((h, w), dtype=np.int16)
        best = np.full((h, w), np.iinfo(np.int32).max, dtype=np.int32)
        centroids = [*palette, background.astype(np.uint8)]
        for idx, centroid in enumerate(centroids):
            dist = cv2.absdiff(bgr, centroid).sum(axis=2).astype(np.int32)
            better = dist < best
            labels[better] = idx
            best[better] = dist[better]
        return labels

    # -- contour -> smooth SVG path --------------------------------------------
    def _trace_component(
        self,
        comp: np.ndarray,
        ox: int,
        oy: int,
        width: int,
        height: int,
        color: np.ndarray,
        area: float,
    ) -> DetectedVector | None:
        contours, hierarchy = cv2.findContours(
            comp, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_TC89_KCOS
        )
        if not contours or hierarchy is None:
            return None

        outer: np.ndarray | None = None
        outer_idx = -1
        for idx, contour in enumerate(contours):
            if hierarchy[0][idx][3] == -1:  # top-level contour
                outer = contour
                outer_idx = idx
                break
        if outer is None:
            return None

        # Skip near-rectangular blobs: geometric shapes already own those.
        rect = cv2.minAreaRect(outer)
        (_, _), (rw, rh), _ = rect
        bbox_area = max(1e-6, rw * rh)
        outer_area = cv2.contourArea(outer)
        if outer_area / bbox_area > 0.9:
            return None

        holes = [
            contours[idx]
            for idx, _ in enumerate(contours)
            if hierarchy[0][idx][3] == outer_idx
        ]

        # comp is already cropped to the component bbox, so its contours are in
        # local (0..width, 0..height) coordinates — normalize paths to that.
        path = self._closed_path_smooth(outer, 0, 0)
        if not path:
            return None
        for hole in holes:
            sub = self._closed_path_smooth(hole[::-1], 0, 0)
            if sub:
                path += " " + sub

        confidence = self._confidence(outer, area, bbox_area, len(holes))
        return DetectedVector(
            path=path,
            x=float(ox + width / 2),
            y=float(oy + height / 2),
            width=float(width),
            height=float(height),
            fill=hexify(tuple(color)),
            confidence=confidence,
        )

    def _closed_path_smooth(
        self, contour: np.ndarray, ox: int, oy: int
    ) -> str:
        """Return a closed SVG path string, origin-normalized to the bounds.

        Vertices with a sharp turn are kept as corner (``L``) points; gentle
        arcs become smooth quadratic bezier (``Q``) curves through midpoint
        anchors so the path is clean at any resolution.
        """
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(
            contour, self.epsilon_factor * perimeter, closed=True
        )
        pts = approx.reshape(-1, 2).astype(float)
        if len(pts) < 3:
            return ""
        if np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        n = len(pts)
        if n < 3:
            return ""

        def mid(a: int, b: int) -> tuple[float, float]:
            return ((pts[a][0] + pts[b][0]) / 2, (pts[a][1] + pts[b][1]) / 2)

        def is_corner(i: int) -> bool:
            a = pts[i] - pts[i - 1]
            b = pts[(i + 1) % n] - pts[i]
            la, lb = np.linalg.norm(a), np.linalg.norm(b)
            if la < 1e-6 or lb < 1e-6:
                return False
            cos_ang = float(np.clip(np.dot(a, b) / (la * lb), -1.0, 1.0))
            return math.degrees(math.acos(cos_ang)) > self.corner_threshold_deg

        parts = []
        start = mid(n - 1, 0)
        parts.append(f"M {start[0] - ox:.1f} {start[1] - oy:.1f}")
        for i in range(n):
            sx, sy = mid(i, (i + 1) % n)
            px, py = pts[i] - np.array([ox, oy])
            if is_corner(i):
                parts.append(f"L {px:.1f} {py:.1f}")
                parts.append(f"L {sx - ox:.1f} {sy - oy:.1f}")
            else:
                parts.append(f"Q {px:.1f} {py:.1f} {sx - ox:.1f} {sy - oy:.1f}")
        parts.append("Z")
        return " ".join(parts)

    # -- scoring -----------------------------------------------------------------
    def _confidence(
        self, contour: np.ndarray, area: float, bbox_area: float, holes: int
    ) -> float:
        # Smooth, well-filled blobs with few holes have crisp contours.
        perimeter = cv2.arcLength(contour, True)
        compactness = (4 * np.pi * area) / (perimeter * perimeter) if perimeter else 0
        fill_ratio = area / bbox_area if bbox_area else 0
        hole_penalty = min(0.15, 0.05 * holes)
        return float(
            max(
                0.0,
                min(
                    1.0,
                    0.6 * compactness + 0.3 * fill_ratio + 0.1 - hole_penalty,
                ),
            )
        )


def _background_color(bgr: np.ndarray) -> np.ndarray:
    """Robust estimate of the background via the image border."""
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
    return np.median(samples, axis=0)