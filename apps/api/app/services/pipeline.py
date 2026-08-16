from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import numpy as np
from numpy import ndarray as NDArray

from app.services.color_extractor import ColorExtractor
from app.services.image_utils import LoadedImage, hexify, load_image
from app.services.scene_graph_builder import DetectedElements, SceneGraphBuilder
from app.services.shape_detector import ShapeDetector
from app.services.storage import StorageBackend
from app.services.text_detector import VisionTextDetector

ProgressFn = Callable[[str, float, float | None], Awaitable[None]]


@dataclass
class ReconstructionResult:
    scene_graph: dict
    original_url: str
    upload_id: str


class ReconstructionPipeline:
    """Runs the v0.2 pipeline: analyze → text → shapes → colors → scene graph.

    Progress callback (stage, stage_progress, overall) feeds the job queue so
    clients see a live checklist through SSE.
    """

    def __init__(
        self,
        storage: StorageBackend,
        shape_detector: ShapeDetector | None = None,
        color_extractor: ColorExtractor | None = None,
        text_detector: VisionTextDetector | None = None,
        builder: SceneGraphBuilder | None = None,
    ) -> None:
        self.storage = storage
        self.shape_detector = shape_detector or ShapeDetector()
        self.color_extractor = color_extractor or ColorExtractor()
        self.text_detector = text_detector or VisionTextDetector()
        self.builder = builder or SceneGraphBuilder()

    async def run(
        self, image_bytes: bytes, upload_id: str, progress: ProgressFn
    ) -> ReconstructionResult:
        await progress("analyzing", 0.2, None)
        image = load_image(image_bytes)

        await progress("text", 0.0, None)
        texts = await self.text_detector.detect(image)
        await progress("text", 1.0, None)

        await progress("shapes", 0.0, None)
        shapes = self.shape_detector.detect(image)
        await progress("shapes", 1.0, None)

        await progress("colors", 0.0, None)
        self._extract_colors(image, shapes)
        await progress("colors", 1.0, None)

        detected = DetectedElements(
            shapes=shapes, regions=[], texts=texts
        )
        background_fill = mean_border_hex(image.bgr)

        await progress("building", 0.2, None)
        graph = self.builder.build(image, detected, background_fill=background_fill)
        await progress("building", 1.0, None)

        return ReconstructionResult(
            scene_graph=graph.model_dump(by_alias=True),
            original_url=f"originals/{upload_id}",
            upload_id=upload_id,
        )

    def _extract_colors(self, image: LoadedImage, shapes) -> None:
        """Fill each shape's `fill` param from its dominant region color."""
        for shape in shapes:
            if shape.params.get("fill") is not None:
                continue
            mask = np.zeros((image.height, image.width), dtype=np.uint8)
            import cv2  # noqa: PLC0415

            cv2.drawContours(mask, [shape.contour], -1, 255, thickness=cv2.FILLED)
            region = self.color_extractor.extract(image, mask)
            if region.colors:
                shape.params["fill"] = region.colors[0].hex


def mean_border_hex(bgr: NDArray) -> str | None:
    """Dominant color of the image's border strip (proxy for background)."""
    h, w = bgr.shape[:2]
    if h < 8 or w < 8:
        return None
    edge = 4
    samples = np.concatenate(
        [
            bgr[:edge, :, :].reshape(-1, 3),
            bgr[-edge:, :, :].reshape(-1, 3),
            bgr[:, :edge, :].reshape(-1, 3),
            bgr[:, -edge:, :].reshape(-1, 3),
        ]
    )
    return hexify(tuple(samples.mean(axis=0)))