from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import cv2
import numpy as np

from app.services.image_utils import LoadedImage


@dataclass
class DetectedText:
    content: str
    x: float
    y: float
    width: float
    height: float
    rotation: float
    confidence: float
    # Visual attributes inferred from the crop.
    font_color: str
    background_color: str | None = None
    font_size_estimate: float = 0.0
    is_guess: bool = False  # True when content couldn't be read (region only)


class OCRBackend(ABC):
    """Interface for pluggable OCR engines (PaddleOCR, Tesseract, EasyOCR)."""

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    async def recognize(self, image: LoadedImage) -> list[DetectedText]: ...


class VisionTextDetector:
    """Detects text *regions* via morphology without an OCR engine.

    Content stays unknown (is_guess=True) unless an OCRBackend is supplied;
    that is the safe v0.2 fallback that the PRD's vector-outline path uses.
    """

    def __init__(
        self,
        backend: OCRBackend | None = None,
        min_region_area: int = 80,
    ) -> None:
        self.backend = backend
        self.min_region_area = min_region_area

    async def detect(self, image: LoadedImage) -> list[DetectedText]:
        if self.backend is not None and self.backend.available():
            regions = await self.backend.recognize(image)
            return regions

        gray = cv2.cvtColor(image.bgr, cv2.COLOR_BGR2GRAY)
        # Morphological gradient highlights dense text blocks.
        grad = cv2.morphologyEx(
            gray, cv2.MORPH_GRADIENT,
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        )
        _, binary = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 5))
        closed = cv2.dilate(binary, kernel, iterations=2)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        results: list[DetectedText] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w * h < self.min_region_area:
                continue
            if w < 12 or h < 6:  # too thin to be text
                continue
            crop = image.rgba[y : y + h, x : x + w]
            font_color = self._dominant_ink(crop)
            results.append(
                DetectedText(
                    content="",
                    x=float(x),
                    y=float(y),
                    width=float(w),
                    height=float(h),
                    rotation=0.0,
                    confidence=0.55,  # region geometry only
                    font_color=font_color,
                    font_size_estimate=float(h),
                    is_guess=True,
                )
            )
        return results

    def _dominant_ink(self, crop: np.ndarray) -> str:
        gray = cv2.cvtColor(crop, cv2.COLOR_RGBA2GRAY)
        pixels = gray[gray < 200].astype(np.float32)  # darker = ink
        if len(pixels) == 0:
            return "#000000"
        ink = int(pixels.mean())
        return f"#{ink:02X}{ink:02X}{ink:02X}"