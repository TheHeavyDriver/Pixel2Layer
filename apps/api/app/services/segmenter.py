from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import cv2
import numpy as np

from app.services.image_utils import LoadedImage


@dataclass
class SegmentedRegion:
    """A foreground region separated from the background.

    The mask selects the object's pixels; bounds give the crop rect in image
    space. Output is always *approximate* (segmentation of a flattened image
    can never be exact) — the pipeline labels it accordingly.
    """

    x: int
    y: int
    width: int
    height: int
    mask: np.ndarray  # uint8 (H, W) region of the full image, 255 = foreground
    label: str = "foreground"
    confidence: float = 0.5


class SegmenterBackend(ABC):
    """Interface for pluggable segmentation engines (SAM 2 / GrabCut, etc.)."""

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def segment(self, image: LoadedImage) -> list[SegmentedRegion]: ...


class VisionSegmenter(SegmenterBackend):
    """Lightweight OpenCV foreground/background separation.

    Default backend for v0.4: separates the border-colored background from the
    foreground, then splits disjoint foreground blobs into regions. Marks every
    result approximate, per the PRD's transparency requirement.
    """

    def __init__(
        self,
        min_region_area: float = 200.0,
        max_regions: int = 40,
        bg_tolerance: int = 28,
    ) -> None:
        self.min_region_area = min_region_area
        self.max_regions = max_regions
        self.bg_tolerance = bg_tolerance

    def available(self) -> bool:
        return True

    def segment(self, image: LoadedImage) -> list[SegmentedRegion]:
        background = self._background_color(image.bgr)
        diff = cv2.absdiff(image.bgr, background.astype(np.uint8))
        dist = diff.max(axis=2)
        fg = (dist > self.bg_tolerance).astype(np.uint8) * 255

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, kernel, iterations=1)
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel, iterations=2)

        num, labels, stats, _ = cv2.connectedComponentsWithStats(fg, connectivity=8)
        regions: list[SegmentedRegion] = []
        for label_idx in range(1, num):
            if len(regions) >= self.max_regions:
                break
            x, y, w, h, area = stats[label_idx]
            if area < self.min_region_area:
                continue
            if w < 10 or h < 10:
                continue
            mask = (labels == label_idx).astype(np.uint8) * 255
            regions.append(
                SegmentedRegion(
                    x=int(x),
                    y=int(y),
                    width=int(w),
                    height=int(h),
                    mask=mask,
                    label="foreground",
                    confidence=0.55,
                )
            )
        return regions

    @staticmethod
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
        med = np.median(samples, axis=0)
        return med


def build_segmenter(backend: SegmenterBackend | None = None) -> SegmenterBackend:
    """Factory that returns the configured backend (VisionSegmenter default)."""
    return backend or VisionSegmenter()