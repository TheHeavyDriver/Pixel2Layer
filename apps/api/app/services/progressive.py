from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.core.constants import (
    CANNY_THRESHOLD_HIGH,
    CANNY_THRESHOLD_LOW,
    COLOR_DIVERSITY_WEIGHT,
    COLOR_QUANTIZATION_BIN_SIZE,
    EDGE_DENSITY_WEIGHT,
    FLAT_BLOCK_SIZE,
    FLAT_BLOCK_VARIATION_THRESHOLD,
    GRAPHIC_VECTORIZATION_MIN_EDGE_DENSITY,
    MAX_EDGE_DENSITY_NORMALIZATION,
    MAX_UNIQUE_COLORS_NORMALIZATION,
)
from app.services.image_utils import LoadedImage


@dataclass
class ImageComplexity:
    edge_density: float  # 0..1 fraction of strong-gradient pixels
    unique_colors: int  # quantized color count
    flat_ratio: float  # fraction of pixels inside large uniform regions
    kind: str  # "graphic" | "photographic"
    score: float  # 0 (simple) .. 1 (complex)


class ProgressiveRouter:
    """Routes simple vs complex images through the appropriate pipeline stages.

    Flat graphics (few colors, sharp edges, large uniform areas) reconstruct
    well as geometric shapes + vector paths. Photographic content is better
    framed as approximate segmentation. Progressive routing lets the pipeline
    skip expensive, unhelpful stages based on the input.
    """

    def __init__(
        self,
        unique_color_threshold: int = 12,
        photo_edge_threshold: float = 0.06,
    ) -> None:
        self.unique_color_threshold = unique_color_threshold
        self.photo_edge_threshold = photo_edge_threshold

    def classify(self, image: LoadedImage) -> ImageComplexity:
        gray = cv2.cvtColor(image.bgr, cv2.COLOR_BGR2GRAY)

        # Edge density: photographic content has texture/gradients everywhere.
        edges = cv2.Canny(gray, CANNY_THRESHOLD_LOW, CANNY_THRESHOLD_HIGH)
        edge_density = float(edges.mean() / 255.0)

        # Quantized color count: flat graphics use few dominant colors.
        quantized = (
            image.bgr // COLOR_QUANTIZATION_BIN_SIZE * COLOR_QUANTIZATION_BIN_SIZE
        ).reshape(-1, 3)
        unique_colors = int(np.unique(quantized, axis=0).shape[0])

        # Flat Ratio: share of pixels belonging to a big uniform patch.
        flat_ratio = float(self._flat_ratio(gray))

        photographic = (
            edge_density > self.photo_edge_threshold
            and unique_colors > self.unique_color_threshold
        )
        kind = "photographic" if photographic else "graphic"
        score = float(
            max(
                0.0,
                min(
                    1.0,
                    EDGE_DENSITY_WEIGHT * min(1.0, edge_density / MAX_EDGE_DENSITY_NORMALIZATION)
                    + COLOR_DIVERSITY_WEIGHT
                    * min(1.0, unique_colors / MAX_UNIQUE_COLORS_NORMALIZATION),
                ),
            )
        )
        return ImageComplexity(
            edge_density=edge_density,
            unique_colors=unique_colors,
            flat_ratio=flat_ratio,
            kind=kind,
            score=score,
        )

    def should_vectorize(self, complexity: ImageComplexity) -> bool:
        """Vectorize when the image is a flat graphic with structured edges."""
        return complexity.kind == "graphic" and complexity.edge_density > GRAPHIC_VECTORIZATION_MIN_EDGE_DENSITY

    def should_segment(self, complexity: ImageComplexity) -> bool:
        """Segment every image (raster fallback for all kinds).

        Graphics used to skip segmentation, but vector paths and masked
        cutouts can cover the same element, so the pipeline now always
        segments and lets SceneGraphBuilder merge overlaps (option B).
        """
        return True

    def _flat_ratio(self, gray: np.ndarray) -> float:
        h, w = gray.shape
        if h < 8 or w < 8:
            return 0.0
        block = FLAT_BLOCK_SIZE
        num_h, num_w = h // block, w // block
        if num_h == 0 or num_w == 0:
            return 1.0
        cells = gray[: num_h * block, : num_w * block].reshape(num_h, block, num_w, block)
        spans = np.ptp(cells, axis=(1, 3))
        flat = (spans <= FLAT_BLOCK_VARIATION_THRESHOLD).astype(np.float32)
        if flat.sum() < 2:
            return float(flat.mean())
        return float(flat.mean())