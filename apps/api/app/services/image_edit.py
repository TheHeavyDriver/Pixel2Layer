from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.services.segmenter import SegmentedRegion


@dataclass
class RegionInfo:
    """Public (serializable) view of a detected foreground region."""

    x: int
    y: int
    width: int
    height: int
    label: str
    confidence: float


def to_region_info(region: SegmentedRegion) -> RegionInfo:
    return RegionInfo(
        x=region.x,
        y=region.y,
        width=region.width,
        height=region.height,
        label=region.label,
        confidence=region.confidence,
    )


def keep_region(rgba: np.ndarray, region: SegmentedRegion) -> np.ndarray:
    """Clip an image's alpha to a single region's foreground pixels."""
    out = rgba.copy()
    out[:, :, 3] = region.mask
    return out


def remove_region(rgba: np.ndarray, region: SegmentedRegion) -> np.ndarray:
    """Transparent out a single region's foreground pixels (cut a hole)."""
    out = rgba.copy()
    out[:, :, 3] = np.where(region.mask > 0, 0, rgba[:, :, 3])
    return out


def crop_to_region(rgba: np.ndarray, region: SegmentedRegion) -> np.ndarray:
    """Crop an (RGBA) image to a region's bounding box, clamped to the image."""
    height, width = rgba.shape[:2]
    x1 = min(max(region.x, 0), width)
    y1 = min(max(region.y, 0), height)
    x2 = min(max(region.x + region.width, 0), width)
    y2 = min(max(region.y + region.height, 0), height)
    return rgba[y1:y2, x1:x2].copy()


def select_region(
    regions: list[SegmentedRegion], index: int
) -> SegmentedRegion:
    """Resolve a 0-based region index, raising a descriptive ValueError."""
    if not regions:
        raise ValueError("no foreground regions detected")
    if index < 0 or index >= len(regions):
        raise ValueError(f"unknown region index {index} (got {len(regions)} regions)")
    return regions[index]