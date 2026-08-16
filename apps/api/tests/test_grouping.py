from __future__ import annotations

from app.schemas.scene_graph import RectElement, SceneGraph, Transform
from app.services.grouping import LayerGrouper
from app.services.image_utils import load_image
from app.services.scene_graph_builder import DetectedElements, SceneGraphBuilder
from tests.fixtures import make_poster, to_png_bytes


def _graph(background: bool = True) -> SceneGraph:
    img = load_image(to_png_bytes(make_poster(width=400, height=300)))
    builder = SceneGraphBuilder()
    return builder.build(
        img, DetectedElements([], [], []), background_fill="#FFFFFF" if background else None
    )


DUMMY_LAYER = dict(
    type="rectangle",
    name="X",
    fill="#123456",
    opacity=1,
    visible=True,
    locked=False,
    confidence=0.9,
)


def _rect(id: str, x: float, y: float, w: float, h: float, name: str = "x") -> RectElement:
    return RectElement(
        id=id,
        type="rectangle",
        name=name,
        transform=Transform(x=x, y=y),
        fill="#123456",
        width=w,
        height=h,
        confidence=0.9,
    )


def test_empty_scene_has_no_groups() -> None:
    graph = _graph(background=False)
    assert LayerGrouper().suggest(graph) == []


def test_background_rect_flagged_as_background_group() -> None:
    graph = _graph()
    graph.layers = [_rect("bg", 200, 150, 400, 300, "Background")]
    groups = LayerGrouper().suggest(graph)
    assert [g.name for g in groups] == ["background"]
    assert groups[0].element_ids == ["bg"]


def test_header_footer_and_hero_bands_are_detected() -> None:
    graph = _graph()
    graph.layers = [
        _rect("header", 200, 40, 360, 60, "Header"),
        _rect("hero", 200, 150, 360, 140, "Hero"),
        _rect("footer", 200, 270, 360, 60, "Footer"),
    ]
    names = [g.name for g in LayerGrouper().suggest(graph)]
    assert "header" in names
    assert "footer" in names
    assert "hero" in names


def test_header_band_contains_all_top_elements() -> None:
    graph = _graph(background=False)
    graph.layers = [
        _rect("logo", 60, 40, 80, 60),
        _rect("title", 200, 45, 160, 50),
    ]
    groups = LayerGrouper().suggest(graph)
    by_name = {g.name: g for g in groups}
    assert "header" in by_name
    header_ids = set(by_name["header"].element_ids)
    assert header_ids == {"logo", "title"}


def test_tiny_elements_grouped_as_decorations() -> None:
    graph = _graph()
    graph.layers = [
        _rect("circle", 20, 20, 5, 5, "Dot"),
        _rect("rect", 200, 150, 200, 120, "Main"),
    ]
    groups = LayerGrouper().suggest(graph)
    by_name = {g.name: g for g in groups}
    assert "decorations" in by_name
    assert by_name["decorations"].element_ids == ["circle"]


def test_products_band_detected_for_similar_sized_columns() -> None:
    graph = _graph()
    graph.layers = [
        _rect("p1", 80, 150, 80, 120),
        _rect("p2", 200, 150, 80, 120),
        _rect("p3", 320, 150, 80, 120),
    ]
    groups = LayerGrouper().suggest(graph)
    by_name = {g.name: g for g in groups}
    assert "products" in by_name
    assert set(by_name["products"].element_ids) == {"p1", "p2", "p3"}


def test_layers_order_preserved_within_groups() -> None:
    graph = _graph(background=False)
    graph.layers = [
        _rect("top-a", 150, 40, 200, 60),
        _rect("top-b", 280, 50, 80, 50),
    ]
    groups = LayerGrouper().suggest(graph)
    header = next(g for g in groups if g.name == "header")
    assert header.element_ids == ["top-a", "top-b"]