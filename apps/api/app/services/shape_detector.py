from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from app.services.image_utils import LoadedImage, hexify


@dataclass
class DetectedShape:
    kind: str  # rectangle | rounded-rectangle | circle | ellipse | line | polygon
    params: dict
    confidence: float
    contour: np.ndarray = field(repr=False)


class ShapeDetector:
    """Reconstructs geometric primitives from contours in a flattened image.

    Works best on flat-color graphic designs (the v0.2 target). Photographic
    regions are left for the Segmenter (v0.4).
    """

    def __init__(
        self,
        min_area: float = 60.0,
        max_candidates: int = 500,
    ) -> None:
        self.min_area = min_area
        self.max_candidates = max_candidates

    def detect(self, image: LoadedImage) -> list[DetectedShape]:
        gray = cv2.cvtColor(image.bgr, cv2.COLOR_BGR2GRAY)
        # Invert so colored regions on light backgrounds become filled objects.
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        shapes: list[DetectedShape] = []
        for contour in contours:
            if len(shapes) >= self.max_candidates:
                break
            shape = self._classify(contour)
            if shape is None:
                continue
            if self._region_area(shape) < self.min_area:
                continue
            shape.params["fill"] = self._dominant_color(image, shape.contour)
            shapes.append(shape)
        return shapes

    # -- classification ------------------------------------------------------
    def _classify(self, contour: np.ndarray) -> DetectedShape | None:
        perimeter = cv2.arcLength(contour, True)
        if perimeter < 5:
            return None
        area = cv2.contourArea(contour)
        if area < self.min_area:
            return None

        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        n = len(approx)

        # Lines: thin, elongated contours with near-zero enclosed area ratio.
        if self._is_line_like(approx, area, perimeter):
            return self._line_params(contour)

        # Circles / ellipses via fit.
        if n >= 8:
            circle, confidence = self._fit_circle_like(contour, area)
            if circle is not None:
                return circle
            ellipse, conf = self._fit_ellipse(contour, area)
            if ellipse is not None:
                return DetectedShape(
                    kind="ellipse",
                    params=ellipse,
                    confidence=conf,
                    contour=contour,
                )

        # Polygons (4-gons -> rectangle / rounded rect; more -> generic polygon).
        if n == 4:
            return self._rectangle_params(contour, approx)
        if 3 <= n <= 12:
            points = [(float(p[0][0]), float(p[0][1])) for p in approx]
            return DetectedShape(
                kind="polygon",
                params={"points": points},
                confidence=0.7 if n == 3 else 0.8,
                contour=contour,
            )
        return None

    def _is_line_like(self, approx: np.ndarray, area: float, perimeter: float) -> bool:
        if len(approx) < 2:
            return False
        (x, y), (w, h), angle = cv2.minAreaRect(approx)
        min_side, max_side = sorted((w, h))
        if max_side <= 0:
            return False
        # enclosed area is tiny relative to the bounding box area
        bbox = w * h
        ratio = area / bbox if bbox else 0
        return min_side <= 6.0 and ratio < 0.2

    def _line_params(self, contour: np.ndarray) -> DetectedShape | None:
        (cx, cy), (w, h), angle = cv2.minAreaRect(contour)
        (x1, y1), (x2, y2) = self._rect_endpoints(cx, cy, w, h, angle)
        return DetectedShape(
            kind="line",
            params={
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "stroke_width": float(sorted((w, h))[0]),
            },
            confidence=0.7,
            contour=contour,
        )

    def _rect_endpoints(
        self, cx: float, cy: float, w: float, h: float, angle: float
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        if w < h:
            w, h = h, w
            angle += 90
        rad = math.radians(angle)
        half = w / 2
        dx = half * math.cos(rad)
        dy = half * math.sin(rad)
        return (cx - dx, cy - dy), (cx + dx, cy + dy)

    def _fit_circle_like(
        self, contour: np.ndarray, area: float
    ) -> tuple[DetectedShape | None, float]:
        (cx, cy), radius = cv2.minEnclosingCircle(contour)
        if radius <= 1:
            return None, 0.0
        circle_area = math.pi * radius * radius
        ratio = area / circle_area
        perimeter = cv2.arcLength(contour, True)
        perimeter_ratio = perimeter / (2 * math.pi * radius) if radius else 0
        if 0.8 <= ratio <= 1.2 and 0.9 <= perimeter_ratio <= 1.15:
            conf = self._clamp(1.0 - abs(1 - ratio))
            shape = DetectedShape(
                kind="circle",
                params={
                    "x": float(cx),
                    "y": float(cy),
                    "radius": float(radius),
                },
                confidence=conf,
                contour=contour,
            )
            return shape, conf
        return None, 0.0

    def _fit_ellipse(
        self, contour: np.ndarray, area: float
    ) -> tuple[dict | None, float]:
        if len(contour) < 5:
            return None, 0.0
        try:
            box = cv2.fitEllipse(contour)
        except cv2.error:
            return None, 0.0
        (cx, cy), (mah, mia), angle = box
        if mia <= 1:
            return None, 0.0
        rx, ry = mah / 2, mia / 2
        ellipse_area = math.pi * rx * ry
        ratio = area / ellipse_area if ellipse_area else 0
        if not (0.75 <= ratio <= 1.3):
            return None, 0.0
        conf = self._clamp(1.0 - abs(1 - ratio) * 2)
        return (
            {
                "x": float(cx),
                "y": float(cy),
                "rx": float(rx),
                "ry": float(ry),
                "rotation": float(angle),
            },
            conf,
        )

    def _rectangle_params(
        self, contour: np.ndarray, approx: np.ndarray
    ) -> DetectedShape:
        rect = cv2.minAreaRect(contour)
        (cx, cy), (w, h), angle = rect
        w, h = abs(w), abs(h)
        # Normalize so width is the long axis; adjust rotation to stay meaningful.
        if w < h:
            w, h = h, w
            angle += 90
        bbox_area = w * h
        contour_area = cv2.contourArea(contour)
        ratio = contour_area / bbox_area if bbox_area else 0
        conf = self._clamp(ratio)

        # rounded rectangle: area ratio of a true corner-less quad is high; we
        # estimate corner rounding from contour/bbox perimeter difference.
        perimeter = cv2.arcLength(contour, True)
        ideal_perimeter = 2 * (w + h)
        rounding = self._clamp(1 - (perimeter / ideal_perimeter))
        if rounding > 0.06:
            return DetectedShape(
                kind="rounded-rectangle",
                params={
                    "x": float(cx),
                    "y": float(cy),
                    "width": float(w),
                    "height": float(h),
                    "rotation": float(angle),
                    "rx": round(min(w, h) * rounding * 0.5, 2),
                    "ry": round(min(w, h) * rounding * 0.5, 2),
                },
                confidence=conf,
                contour=contour,
            )

        return DetectedShape(
            kind="rectangle",
            params={
                "x": float(cx),
                "y": float(cy),
                "width": float(w),
                "height": float(h),
                "rotation": float(angle),
            },
            confidence=conf,
            contour=contour,
        )

    # -- pixel sampling ----------------------------------------------------------------
    def _region_area(self, shape: DetectedShape) -> float:
        return float(cv2.contourArea(shape.contour))

    def _dominant_color(self, image: LoadedImage, contour: np.ndarray) -> str:
        mask = np.zeros((image.height, image.width), dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, thickness=cv2.FILLED)
        erosion = cv2.erode(mask, np.ones((3, 3), np.uint8), iterations=1)
        if not np.any(erosion):
            erosion = mask
        mean = cv2.mean(image.bgr, mask=erosion)[:3]
        return hexify(mean)

    @staticmethod
    def _clamp(v: float) -> float:
        return float(max(0.0, min(1.0, v)))