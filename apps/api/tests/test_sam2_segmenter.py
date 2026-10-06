from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np

from app.services.finetune.sam2_segmenter import Sam2Segmenter
from app.services.image_utils import LoadedImage, load_image
from app.services.pipeline import ReconstructionPipeline
from app.services.progressive import ProgressiveRouter
from app.services.segmenter import (
    SegmentedRegion,
    SegmenterBackend,
    VisionSegmenter,
    build_segmenter,
)
from app.services.storage import LocalStorage
from tests.fixtures import make_poster, to_png_bytes

DEFAULT = "/nonexistent/sam2.pt"


def _sam2(weights: Path | str = DEFAULT) -> Sam2Segmenter:
    return Sam2Segmenter(
        checkpoint=Path("sam2.1_hiera_small.pt"),
        model_cfg="sam2.1_hiera_small",
        lora_weights=Path(weights),
    )


def test_factory_defaults_to_vision_segmenter() -> None:
    assert isinstance(build_segmenter(), VisionSegmenter)


def test_factory_respects_explicit_backend() -> None:
    class Fake(SegmenterBackend):
        def available(self) -> bool:
            return True

        def segment(self, image: LoadedImage):
            return [SegmentedRegion(x=0, y=0, width=10, height=10, mask=np.zeros((1, 1), np.uint8))]

    assert build_segmenter(Fake()) is not None


def test_factory_falls_back_when_no_lora_weights() -> None:
    from app.core.config import Settings

    s = Settings(sam2_lora_weights=Path(DEFAULT))
    assert isinstance(build_segmenter(settings=s), VisionSegmenter)


def test_sam2_available_false_without_weights_or_deps() -> None:
    seg = _sam2()
    assert seg.available() is False


def test_sam2_segment_raises_when_unavailable() -> None:
    seg = _sam2()
    image = load_image(to_png_bytes(make_poster(width=64, height=48, bg=(240, 240, 240))))
    try:
        seg.segment(image)
    except RuntimeError as exc:
        assert "not available" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")


def test_best_mask_and_conf_picks_highest_iou() -> None:
    H, W = 16, 16
    masks = np.zeros((3, 1, 1, H, W), dtype=np.float32)
    masks[0, 0, 0, 2:14, 4:12] = 0.4
    masks[1, 0, 0, 2:14, 4:12] = 0.9
    masks[2, 0, 0, 2:14, 4:12] = 0.2
    ious = np.array([[[0.3]], [[0.9]], [[0.1]]], dtype=np.float32)
    image = LoadedImage(
        bgr=np.zeros((H, W, 3), np.uint8),
        rgba=np.zeros((H, W, 4), np.uint8),
        width=W,
        height=H,
    )

    binary, conf = Sam2Segmenter._best_mask_and_conf(masks, ious, image)
    assert abs(conf - 0.9) < 1e-6
    binary = cv2.resize(binary, (W, H), interpolation=cv2.INTER_NEAREST)
    assert binary[5, 6] == 255 and binary[0, 0] == 0


class _DummySam2(SegmenterBackend):
    """Stand-in for Sam2Segmenter proving the pipeline integration contract."""

    def available(self) -> bool:
        return True

    def segment(self, image: LoadedImage) -> list[SegmentedRegion]:
        h, w = image.height, image.width
        mask = np.zeros((h, w), dtype=np.uint8)
        mask[10:40, 10:40] = 255
        return [
            SegmentedRegion(
                x=10, y=10, width=30, height=30, mask=mask, label="foreground", confidence=0.8
            )
        ]


def test_sam2_style_backend_runs_through_pipeline() -> None:
    storage = LocalStorage(Path(tempfile.mkdtemp()) / "storage")
    pipe = ReconstructionPipeline(
        storage, router=ProgressiveRouter(), segmenter_backend=_DummySam2()
    )
    rng = np.random.default_rng(7)
    noise = rng.integers(0, 255, (120, 160, 3), dtype=np.uint8)
    cv2.circle(noise, (60, 50), 25, (20, 200, 20), thickness=-1)

    import asyncio

    async def run():
        stages: list[str] = []

        async def progress(stage: str, sp: float, overall=None) -> None:
            stages.append(stage)

        result = await pipe.run(to_png_bytes(noise), "u-sam2", progress)
        return result, stages

    result, stages = asyncio.run(run())
    assert "segmenting" in stages
    assert any(e["type"] == "image" for e in result.scene_graph["layers"])