from __future__ import annotations

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
    """Converts non-geometric contours into SVG `d` paths.

    A lightweight, dependency-free alternative to Potrace: connected components
    of region colors are traced with OpenCV contours and simplified into a
    closed SVG path (M…L…Z) that survives resolution-independent scaling in the
    Fabric editor and export layers.
    """

    def __init__(
        self,
        min_area: float = 120.0,
        epsilon_factor: float = 0.015,
        max_candidates: int = 60,
    ) -> None:
        self.min_area = min_area
        self.epsilon_factor = epsilon_factor
        self.max_candidates = max_candidates

    def detect(self, image: LoadedImage) -> list[DetectedVector]:
        """Vectorize the image's solid-color regions into path elements.

        Works best on flat-color illustrations/logos (the v0.4 target).
        Photographic regions are left to the Segmenter.
        """
        gray = cv2.cvtColor(image.bgr, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        # Morph-open to drop specks/text antialias halos before contouring.
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_KCOS)

        vectors: list[DetectedVector] = []
        for contour in contours:
            if len(vectors) >= self.max_candidates:
                break
            area = cv2.contourArea(contour)
            if area < self.min_area:
                continue
            # Skip near-rectangular blobs: shapes/text-handling already own those.
            rect = cv2.minAreaRect(contour)
            (_, _), (rw, rh), _ = rect
            bbox_area = max(1e-6, rw * rh)
            if area / bbox_area > 0.9:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            if w < 8 or h < 8:
                continue

            path = self._contour_to_path(contour, x, y)
            fill = self._dominant_color(image, contour)
            confidence = self._confidence(contour, area, bbox_area)
            vectors.append(
                DetectedVector(
                    path=path,
                    x=float(x + w / 2),
                    y=float(y + h / 2),
                    width=float(w),
                    height=float(h),
                    fill=fill,
                    confidence=confidence,
                )
            )
        return vectors

    # -- path generation ------------------------------------------------------
    def _contour_to_path(self, contour: np.ndarray, ox: int, oy: int) -> str:
        """Return a closed SVG path string, origin-normalized to the bounds."""
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(
            contour, self.epsilon_factor * perimeter, closed=True
        )
        pts = approx.reshape(-1, 2).astype(float)
        if len(pts) < 3:
            return ""
        first = pts[0]
        parts = [f"M {first[0] - ox:.1f} {first[1] - oy:.1f}"]
        parts.extend(f"L {p[0] - ox:.1f} {p[1] - oy:.1f}" for p in pts[1:])
        parts.append("Z")
        return " ".join(parts)

    # -- pixel sampling ----------------------------------------------------------------
    def _confidence(self, contour: np.ndarray, area: float, bbox_area: float) -> float:
        # Smooth, well-filled blobs have crisp contours -> high confidence.
        perimeter = cv2.arcLength(contour, True)
        compactness = (4 * np.pi * area) / (perimeter * perimeter) if perimeter else 0
        fill_ratio = area / bbox_area if bbox_area else 0
        return float(
            max(0.0, min(1.0, 0.6 * compactness + 0.3 * fill_ratio + 0.1))
        )

    def _dominant_color(self, image: LoadedImage, contour: np.ndarray) -> str:
        mask = np.zeros((image.height, image.width), dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, thickness=cv2.FILLED)
        erosion = cv2.erode(mask, np.ones((3, 3), np.uint8), iterations=1)
        if not np.any(erosion):
            erosion = mask
        mean = cv2.mean(image.bgr, mask=erosion)[:3]
        return hexify(mean)