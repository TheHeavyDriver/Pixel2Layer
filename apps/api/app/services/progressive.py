from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

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
        edges = cv2.Canny(gray, 80, 160)
        edge_density = float(edges.mean() / 255.0)

        # Quantized color count: flat graphics use few dominant colors.
        quantized = (image.bgr // 32 * 32).reshape(-1, 3)
        unique_colors = int(np.unique(quantized, axis=0).shape[0])

        # Flat Ratio: share of pixels belonging to a big uniform patch.
        flat_ratio = float(self._flat_ratio(gray))

        photographic = (
            edge_density > self.photo_edge_threshold
            and unique_colors > self.unique_color_threshold
        )
        kind = "photographic" if photographic else "graphic"
        score = float(
            max(0.0, min(1.0, 0.5 * min(1.0, edge_density / 0.12))
                + 0.5 * min(1.0, unique_colors / 64))
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
        return complexity.kind == "graphic" and complexity.edge_density > 0.008

    def should_segment(self, complexity: ImageComplexity) -> bool:
        """Segment when the image is photographic/complex (raster fallback)."""
        return complexity.kind == "photographic"

    def _flat_ratio(self, gray: np.ndarray) -> float:
        h, w = gray.shape
        if h < 8 or w < 8:
            return 0.0
        block = 8
        num_h, num_w = h // block, w // block
        if num_h == 0 or num_w == 0:
            return 1.0
        cells = gray[: num_h * block, : num_w * block].reshape(num_h, block, num_w, block)
        spans = np.ptp(cells, axis=(1, 3))
        flat = (spans <= 12).astype(np.float32)
        if flat.sum() < 2:
            return float(flat.mean())
        return float(flat.mean())