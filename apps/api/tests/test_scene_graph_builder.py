from __future__ import annotations

from app.schemas.scene_graph import ImageElement, SceneGraph, Transform
from app.services.image_utils import load_image
from app.services.scene_graph_builder import DetectedElements, SceneGraphBuilder
from app.services.shape_detector import DetectedShape
from app.services.text_detector import DetectedText
from app.services.vectorizer import DetectedVector
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


def test_builds_line_element_without_fill_collision() -> None:
    # Regression: the line branch unpacked style (which carries fill) after an
    # explicit fill="none" -> TypeError on any detected line shape.
    img = load_image(to_png_bytes(make_poster(width=200, height=150)))
    detected = DetectedElements(
        shapes=[
            _dummy_shape(
                "line", x1=10.0, y1=20.0, x2=180.0, y2=130.0,
                stroke_width=4.0, stroke="#112233",
            )
        ],
        regions=[],
        texts=[],
    )
    graph = SceneGraphBuilder().build(img, detected, background_fill="#FFFFFF")
    lines = [layer for layer in graph.layers if layer.type == "line"]
    assert len(lines) == 1
    assert lines[0].fill == "none"
    assert lines[0].stroke == "#112233"


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


def _cutout(cx: float, cy: float, w: float, h: float, conf: float = 0.55) -> ImageElement:
    return ImageElement(
        id="img_1",
        type="image",
        name="Cutout 1",
        transform=Transform(x=cx, y=cy),
        src="/api/storage/masked/u/0.png",
        width=w,
        height=h,
        confidence=conf,
    )


def _detected_vector(cx: float, cy: float, w: float, h: float, conf: float) -> DetectedVector:
    return DetectedVector(
        path="M 0 0 Z", x=cx, y=cy, width=w, height=h,
        fill="#112233", confidence=conf,
    )


def _build_with(vectors, images):
    img = load_image(to_png_bytes(make_poster(width=200, height=150)))
    detected = DetectedElements(shapes=[], regions=[], texts=[], vectors=vectors, images=images)
    return SceneGraphBuilder().build(img, detected)


def test_merge_drops_cutout_covered_by_confident_vector() -> None:
    graph = _build_with(
        [_detected_vector(100, 75, 60, 60, 0.9)],
        [_cutout(100, 75, 60, 60, 0.55)],
    )
    kinds = [e.type for e in graph.layers]
    assert kinds == ["vector"]


def test_merge_drops_vector_covered_by_confident_cutout() -> None:
    graph = _build_with(
        [_detected_vector(100, 75, 60, 60, 0.4)],
        [_cutout(100, 75, 60, 60, 0.95)],
    )
    kinds = [e.type for e in graph.layers]
    assert kinds == ["image"]


def test_merge_prefers_vector_on_confidence_tie() -> None:
    graph = _build_with(
        [_detected_vector(100, 75, 60, 60, 0.55)],
        [_cutout(100, 75, 60, 60, 0.55)],
    )
    kinds = [e.type for e in graph.layers]
    assert kinds == ["vector"]


def test_merge_keeps_disjoint_vectors_and_cutouts() -> None:
    graph = _build_with(
        [_detected_vector(40, 40, 30, 30, 0.9)],
        [_cutout(160, 110, 30, 30, 0.55)],
    )
    kinds = sorted(e.type for e in graph.layers)
    assert kinds == ["image", "vector"]