from __future__ import annotations

from app.schemas.scene_graph import SceneGraph
from app.services.image_utils import load_image
from app.services.scene_graph_builder import DetectedElements, SceneGraphBuilder
from app.services.shape_detector import DetectedShape
from app.services.text_detector import DetectedText
from tests.fixtures import make_poster, to_png_bytes


def _dummy_shape(kind: str, **params) -> DetectedShape:
    import numpy as np

    return DetectedShape(
        kind=kind, params=params, confidence=0.95, contour=np.empty((1, 1, 2), dtype=np.int32)
    )


def test_builds_ordered_scene_graph() -> None:
    img = load_image(to_png_bytes(make_poster(width=200, height=150)))
    detected = DetectedElements(
        shapes=[
            _dummy_shape("rectangle", x=50, y=40, width=100, height=50, fill="#112233"),
            _dummy_shape("circle", x=120, y=100, radius=25, fill="#334455"),
        ],
        regions=[],
        texts=[],
    )
    graph = SceneGraphBuilder().build(img, detected, background_fill="#FFFFFF")
    assert isinstance(graph, SceneGraph)
    assert len(graph.layers) == 3
    # background is first (back-most)
    assert graph.layers[0].type == "rectangle"
    assert graph.layers[0].name == "Background"
    assert graph.layers[1].type == "rectangle"
    assert graph.layers[2].type == "circle"
    assert graph.canvas["width"] == 200
    assert graph.canvas["height"] == 150
    assert graph.schema_version == 1
    # confidence output present
    assert "overall" in graph.confidence
    assert graph.overall_confidence > 0


def test_builds_text_element() -> None:
    img = load_image(to_png_bytes(make_poster(width=100, height=80)))
    detected = DetectedElements(
        shapes=[],
        regions=[],
        texts=[
            DetectedText(
                content="HELLO",
                x=10,
                y=10,
                width=60,
                height=20,
                rotation=0,
                confidence=0.9,
                font_color="#000000",
                is_guess=False,
            )
        ],
    )
    graph = SceneGraphBuilder().build(img, detected)
    text = graph.layers[0]
    assert text.type == "text"
    assert text.content == "HELLO"
    assert text.confidence == 0.9
    assert text.width == 60


def test_empty_detection_is_valid() -> None:
    img = load_image(to_png_bytes(make_poster(width=50, height=50)))
    graph = SceneGraphBuilder().build(img, DetectedElements([], [], []))
    assert graph.layers == []
    assert graph.overall_confidence == 1.0


def test_guess_text_gets_note() -> None:
    img = load_image(to_png_bytes(make_poster(width=100, height=80)))
    detected = DetectedElements(
        shapes=[],
        regions=[],
        texts=[
            DetectedText(
                content="",
                x=0,
                y=0,
                width=30,
                height=14,
                rotation=0,
                confidence=0.55,
                font_color="#010101",
                is_guess=True,
            )
        ],
    )
    graph = SceneGraphBuilder().build(img, detected)
    text = graph.layers[0]
    assert "region" in (text.confidence_note or "")
    assert text.confidence < 0.6