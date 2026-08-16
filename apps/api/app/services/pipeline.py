from __future__ import annotations

import io
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import cv2
import numpy as np
from numpy import ndarray as NDArray
from PIL import Image

from app.schemas.scene_graph import ImageElement, Transform
from app.services.color_extractor import ColorExtractor
from app.services.image_utils import LoadedImage, hexify, load_image
from app.services.progressive import ImageComplexity, ProgressiveRouter
from app.services.scene_graph_builder import DetectedElements, SceneGraphBuilder
from app.services.segmenter import build_segmenter
from app.services.shape_detector import ShapeDetector
from app.services.storage import StorageBackend
from app.services.text_detector import VisionTextDetector
from app.services.vectorizer import Vectorizer

ProgressFn = Callable[[str, float, float | None], Awaitable[None]]


@dataclass
class ReconstructionResult:
    scene_graph: dict
    original_url: str
    upload_id: str


class ReconstructionPipeline:
    """Runs the v0.4 pipeline: analyze → route → text/shapes/colors/vectorize.

    Progressive routing (v0.4) picks the right stages per image complexity:
    flat graphics → shapes + vector paths; photographic → approximate
    segmentation into masked image layers.
    """

    def __init__(
        self,
        storage: StorageBackend,
        shape_detector: ShapeDetector | None = None,
        color_extractor: ColorExtractor | None = None,
        text_detector: VisionTextDetector | None = None,
        builder: SceneGraphBuilder | None = None,
        vectorizer: Vectorizer | None = None,
        segmenter_backend=None,
        router: ProgressiveRouter | None = None,
    ) -> None:
        self.storage = storage
        self.shape_detector = shape_detector or ShapeDetector()
        self.color_extractor = color_extractor or ColorExtractor()
        self.text_detector = text_detector or VisionTextDetector()
        self.builder = builder or SceneGraphBuilder()
        self.vectorizer = vectorizer or Vectorizer()
        self.segmenter = build_segmenter(segmenter_backend)
        self.router = router or ProgressiveRouter()

    async def run(
        self, image_bytes: bytes, upload_id: str, progress: ProgressFn
    ) -> ReconstructionResult:
        await progress("analyzing", 0.2, None)
        image = load_image(image_bytes)

        # Progressive routing decides which stages help this image.
        complexity = self.router.classify(image)
        vectorize = self.router.should_vectorize(complexity)
        segment = self.router.should_segment(complexity)

        await progress("text", 0.0, None)
        texts = await self.text_detector.detect(image)
        await progress("text", 1.0, None)

        await progress("shapes", 0.0, None)
        shapes = self.shape_detector.detect(image)
        await progress("shapes", 1.0, None)

        await progress("colors", 0.0, None)
        self._extract_colors(image, shapes)
        await progress("colors", 1.0, None)

        vectors: list = []
        if vectorize:
            await progress("vectorizing", 0.0, None)
            vectors = self.vectorizer.detect(image)
            await progress("vectorizing", 1.0, None)

        images: list[ImageElement] = []
        if segment and self.segmenter.available():
            await progress("segmenting", 0.0, None)
            images = await self._segment(image, upload_id)
            await progress("segmenting", 1.0, None)

        detected = DetectedElements(
            shapes=shapes, regions=[], texts=texts, vectors=vectors, images=images
        )
        background_fill = mean_border_hex(image.bgr)

        await progress("building", 0.2, None)
        graph = self.builder.build(
            image,
            detected,
            background_fill=background_fill,
            options=self._build_options(complexity),
        )
        await progress("building", 1.0, None)

        return ReconstructionResult(
            scene_graph=graph.model_dump(by_alias=True),
            original_url=f"originals/{upload_id}",
            upload_id=upload_id,
        )

    def _build_options(self, complexity: ImageComplexity):
        from app.services.scene_graph_builder import BuildOptions

        return BuildOptions(
            complexity_kind=complexity.kind,
            complexity_score=complexity.score,
        )

    async def _segment(self, image: LoadedImage, upload_id: str) -> list[ImageElement]:
        """Segmented foregrounds → masked PNG cutouts stored for later use."""
        regions = self.segmenter.segment(image)
        elements: list[ImageElement] = []
        for index, region in enumerate(regions):
            cutout = _masked_cutout(image.rgba, region.mask, region)
            key = f"masked/{upload_id}/{index}.png"
            buf = io.BytesIO()
            cutout.save(buf, format="PNG")
            await self.storage.put(key, buf.getvalue(), "image/png")
            midpoint = (region.x + region.width / 2, region.y + region.height / 2)
            elements.append(
                ImageElement(
                    id=f"image_{upload_id[:8]}_{index}",
                    type="image",
                    name=f"Cutout {index + 1}",
                    transform=Transform(x=midpoint[0], y=midpoint[1]),
                    src=f"/api/storage/{key}",
                    width=float(region.width),
                    height=float(region.height),
                    confidence=region.confidence,
                    confidenceNote="approximate segmentation; masked from a flattened image",
                )
            )
        return elements

    def _extract_colors(self, image: LoadedImage, shapes) -> None:
        """Fill each shape's `fill` param from its dominant region color."""
        for shape in shapes:
            if shape.params.get("fill") is not None:
                continue
            mask = np.zeros((image.height, image.width), dtype=np.uint8)
            cv2.drawContours(mask, [shape.contour], -1, 255, thickness=cv2.FILLED)
            region = self.color_extractor.extract(image, mask)
            if region.colors:
                shape.params["fill"] = region.colors[0].hex


def _masked_cutout(rgba: NDArray, mask: NDArray, region) -> Image.Image:
    """Extract the region's pixels with alpha from the segmenter mask."""
    crop_mask = region.mask[region.y : region.y + region.height, region.x : region.x + region.width]
    crop = rgba[region.y : region.y + region.height, region.x : region.x + region.width]
    out = np.zeros((region.height, region.width, 4), dtype=np.uint8)
    out[:, :, :3] = crop[:, :, :3]
    out[:, :, 3] = crop_mask
    return Image.fromarray(out, "RGBA")


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