from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import cv2
import numpy as np

from app.schemas.scene_graph import SceneGraph
from app.services.pipeline import ReconstructionPipeline
from app.services.progressive import ProgressiveRouter
from app.services.storage import LocalStorage
from tests.fixtures import make_poster, to_png_bytes


def _run(pipe, img_bytes: bytes, upload_id: str = "u1"):
    async def _r():
        stages: list[str] = []

        async def progress(stage: str, sp: float, overall=None) -> None:
            stages.append(stage)

        result = await pipe.run(img_bytes, upload_id, progress)
        return result, stages

    return asyncio.run(_r())


def test_graphic_pipeline_runs_vectorizing_stage() -> None:
    storage = LocalStorage(Path(tempfile.mkdtemp()) / "storage")
    pipe = ReconstructionPipeline(storage, router=ProgressiveRouter())
    img = make_poster(
        width=240,
        height=180,
        bg=(240, 240, 240),
        shapes=[
            ("circle", 60, 90, 30, (200, 40, 40)),
            ("rect", 120, 50, 80, 50, (40, 90, 200)),
        ],
    )
    result, stages = _run(pipe, to_png_bytes(img))
    assert "vectorizing" in stages
    graph = SceneGraph.model_validate(result.scene_graph)
    assert any(e.type == "rectangle" for e in graph.layers)
    assert graph.canvas["background"] is not None


def test_vectorizer_adds_vector_elements_for_irregular_blob() -> None:
    storage = LocalStorage(Path(tempfile.mkdtemp()) / "storage")
    pipe = ReconstructionPipeline(storage, router=ProgressiveRouter())
    img = make_poster(width=200, height=150, bg=(240, 240, 240))
    pts = np.array([[40, 40], [90, 30], [120, 70], [80, 110], [30, 90]], dtype=np.int32)
    cv2.fillPoly(img, [pts], (200, 60, 60))
    result, _ = _run(pipe, to_png_bytes(img))
    graph = SceneGraph.model_validate(result.scene_graph)
    vectors = [e for e in graph.layers if e.type == "vector"]
    assert vectors, "expected vector elements for the irregular blob"
    v = max(vectors, key=lambda e: e.width * e.height)
    assert v.path.startswith("M ")


def test_photo_pipeline_runs_segmenting_stage_and_stores_cutouts() -> None:
    root = Path(tempfile.mkdtemp()) / "storage"
    storage = LocalStorage(root)
    pipe = ReconstructionPipeline(storage, router=ProgressiveRouter())
    rng = np.random.default_rng(3)
    noise = rng.integers(0, 255, (140, 180, 3), dtype=np.uint8)
    # punch a solid-color blob so segmentation finds a foreground region
    cv2.circle(noise, (90, 70), 30, (20, 200, 20), thickness=-1)
    result, stages = _run(pipe, to_png_bytes(noise))
    assert "segmenting" in stages
    graph = SceneGraph.model_validate(result.scene_graph)
    images = [e for e in graph.layers if e.type == "image"]
    assert images, "expected segmented image layers"
    # cutout persisted for each image layer
    for img_elem in images:
        key = img_elem.src.removeprefix("/api/storage/")
        data = asyncio.run(storage.get(key))
        assert data is not None and data[:8] == b"\x89PNG\r\n\x1a\n"
        assert "approximate" in (img_elem.confidence_note or "")