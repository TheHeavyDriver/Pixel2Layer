from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.services.image_utils import LoadedImage, estimate_background_color

# Segmentation thresholds
# Minimum area (in pixels²) for a segmented region to be kept.
# Filters out tiny noise regions that aren't meaningful foreground objects.
# Set lower than shape detection threshold since segmentation captures more detail.
DEFAULT_MIN_REGION_AREA = 200

# Maximum number of foreground regions to extract from a single image.
# Prevents excessive processing time on highly fragmented images while capturing
# the most significant objects. Regions are processed largest-first.
DEFAULT_MAX_REGIONS = 40

# Color distance threshold (in BGR color space) for fixed-tolerance background separation.
# Pixels further than this distance from the estimated background color are considered
# foreground. Lower values = stricter separation, higher = more permissive.
DEFAULT_BG_TOLERANCE = 28


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
        min_region_area: float = DEFAULT_MIN_REGION_AREA,
        max_regions: int = DEFAULT_MAX_REGIONS,
        bg_tolerance: int = DEFAULT_BG_TOLERANCE,
        grabcut_iterations: int = 3,
    ) -> None:
        self.min_region_area = min_region_area
        self.max_regions = max_regions
        self.bg_tolerance = bg_tolerance
        self.grabcut_iterations = grabcut_iterations

    def available(self) -> bool:
        return True

    def segment(self, image: LoadedImage) -> list[SegmentedRegion]:
        background = estimate_background_color(image.bgr)
        dist = _color_distance(image.bgr, background)

        # Attempt 1: fixed-tolerance separation from the border color.
        regions = self._extract_regions(
            _fixed_mask(dist, self.bg_tolerance), confidence=0.55
        )
        if regions:
            return regions

        # Attempt 2: adaptive (Otsu) threshold on the same distance map.
        # Recovers images where the fixed tolerance is too tight/loose, e.g.
        # foreground touching the border so the border median is polluted.
        otsu = _otsu_mask(dist)
        if otsu is not None:
            regions = self._extract_regions(otsu, confidence=0.5)
            if regions:
                return regions

        # Attempt 3: GrabCut with the border as sure-background.
        # Handles full-bleed photos and textured backgrounds where no single
        # border color describes the background.
        grabcut = self._grabcut_mask(image)
        if grabcut is not None:
            regions = self._extract_regions(grabcut, confidence=0.45)
            if regions:
                return regions
        return []

    def _extract_regions(
        self, fg: np.ndarray, confidence: float
    ) -> list[SegmentedRegion]:
        """Split a binary foreground mask into disjoint regions."""
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
                    confidence=confidence,
                )
            )
        return regions

    def _grabcut_mask(self, image: LoadedImage) -> np.ndarray | None:
        """Foreground mask via GrabCut, border strip as sure-background."""
        h, w = image.bgr.shape[:2]
        edge = max(1, min(4, h // 2, w // 2))
        if h - 2 * edge <= 0 or w - 2 * edge <= 0:
            return None
        mask = np.full((h, w), cv2.GC_PR_FGD, dtype=np.uint8)
        mask[:edge, :] = cv2.GC_BGD
        mask[-edge:, :] = cv2.GC_BGD
        mask[:, :edge] = cv2.GC_BGD
        mask[:, -edge:] = cv2.GC_BGD
        bgd_model = np.zeros((1, 65), dtype=np.float64)
        fgd_model = np.zeros((1, 65), dtype=np.float64)
        try:
            cv2.grabCut(
                image.rgb,
                mask,
                None,
                bgd_model,
                fgd_model,
                self.grabcut_iterations,
                cv2.GC_INIT_WITH_MASK,
            )
        except cv2.error:
            return None
        fg = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8) * 255
        if not _sane_fraction(fg):
            return None
        return fg


def _color_distance(bgr: np.ndarray, background: np.ndarray) -> np.ndarray:
    """Per-pixel distance (0..255) from the estimated background color."""
    diff = cv2.absdiff(bgr, background.astype(np.uint8))
    return diff.max(axis=2)


def _fixed_mask(dist: np.ndarray, tolerance: int) -> np.ndarray:
    return (dist > tolerance).astype(np.uint8) * 255


def _otsu_mask(dist: np.ndarray) -> np.ndarray | None:
    """Adaptive threshold on the distance map; None when degenerate."""
    if dist.max() == 0:
        return None
    _, fg = cv2.threshold(dist, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if not _sane_fraction(fg):
        return None
    return fg


def _sane_fraction(fg: np.ndarray) -> bool:
    """Reject empty and full-bleed masks (nothing to split into regions)."""
    frac = float(fg.mean() / 255.0)
    return 0.01 < frac < 0.9


def build_segmenter(backend: SegmenterBackend | None = None, settings=None) -> SegmenterBackend:
    """Factory for the configured segmentation backend.

    Order of preference:
      1. An explicitly supplied ``backend``.
      2. The fine-tuned SAM 2 backend, when the app settings point at existing
         LoRA weights and torch + sam2 are installed.
      3. The lightweight ``VisionSegmenter`` (default, no heavy deps).
    """
    if backend is not None:
        return backend

    from app.services.finetune.sam2_segmenter import Sam2Segmenter

    cfg = settings if settings is not None else _default_settings()
    if cfg.sam2_lora_weights and Path(cfg.sam2_lora_weights).exists():
        candidate = Sam2Segmenter(
            checkpoint=cfg.sam2_checkpoint,
            model_cfg=cfg.sam2_model_cfg,
            lora_weights=cfg.sam2_lora_weights,
            device=cfg.sam2_device,
        )
        if candidate.available():
            return candidate
    return VisionSegmenter()


def _default_settings():
    from app.core.config import get_settings

    return get_settings()