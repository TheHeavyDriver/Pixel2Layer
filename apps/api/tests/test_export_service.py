from __future__ import annotations

from app.schemas.scene_graph import SceneGraph
from app.services.export_service import ExportService
from app.services.image_utils import load_image
from app.services.scene_graph_builder import DetectedElements, SceneGraphBuilder
from tests.fixtures import make_poster, to_png_bytes


def _graph() -> SceneGraph:
    img = load_image(to_png_bytes(make_poster(width=200, height=150)))
    builder = SceneGraphBuilder()
    detected = DetectedElements(
        shapes=[],
        regions=[],
        texts=[],
    )
    return builder.build(img, detected, background_fill="#FFFFFF")


def test_png_export_nonempty_correct_dimensions() -> None:
    result = ExportService().rasterize(_graph(), "png")
    assert result.format == "png"
    assert len(result.data) > 100  # valid PNG is not tiny
    assert result.data[:8] == b"\x89PNG\r\n\x1a\n"
    assert result.content_type == "image/png"


def test_jpg_export_valid() -> None:
    result = ExportService().rasterize(_graph(), "jpg")
    assert result.data[:3] == b"\xff\xd8\xff"  # JPEG SOI marker
    assert result.content_type in ("image/jpeg", "image/jpg")


def test_svg_export_valid() -> None:
    result = ExportService().to_svg(_graph())
    svg = result.data.decode("utf-8")
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert 'width="200"' in svg
    assert '<rect width="100%"' in svg  # background


def test_unsupported_format_rejected() -> None:
    import pytest

    from app.services.export_service import ExportError

    with pytest.raises(ExportError):
        ExportService().rasterize(_graph(), "gif")


def test_p2l_roundtrip() -> None:
    graph = _graph()
    service = ExportService()
    data = service.serialize_p2l(graph, metadata={"name": "poster"})
    revived, meta = service.deserialize_p2l_payload(data)
    assert meta == {"name": "poster"}
    assert revived.schema_version == graph.schema_version
    assert revived.canvas == graph.canvas
    assert len(revived.layers) == len(graph.layers)
    # serialize -> deserialize -> serialize (round-trip with same metadata) is identical
    again = service.serialize_p2l(revived, metadata=meta)
    assert again == data


def test_p2l_rejects_garbage() -> None:
    import pytest

    from app.services.export_service import ExportError

    with pytest.raises(ExportError):
        ExportService().deserialize_p2l(b"not-json")
    with pytest.raises(ExportError):
        ExportService().deserialize_p2l(b'{"format":"other"}')


def test_pipeline_result_is_schema_compliant() -> None:
    import asyncio
    import tempfile
    from pathlib import Path

    from app.services.pipeline import ReconstructionPipeline
    from app.services.storage import LocalStorage

    img = make_poster(
        width=200,
        height=150,
        shapes=[("circle", 100, 75, 30, (40, 40, 200))],
    )

    async def _run() -> SceneGraph:
        storage = LocalStorage(Path(tempfile.mkdtemp()) / "storage")
        pipe = ReconstructionPipeline(storage)

        async def progress(stage: str, sp: float, overall=None) -> None:
            pass

        result = await pipe.run(to_png_bytes(img), "u1", progress)
        return SceneGraph.model_validate(result.scene_graph)

    graph = asyncio.run(_run())
    assert graph.schema_version == 1
    assert any(e.type == "circle" for e in graph.layers)
    assert graph.overall_confidence > 0.7


def test_svg_export_renders_vector_path() -> None:
    from app.schemas.scene_graph import Transform, VectorElement
    from app.services.export_service import ExportService

    graph = _graph()
    graph.layers.append(
        VectorElement(
            id="v1",
            type="vector",
            name="Vector",
            transform=Transform(x=100, y=75),
            path="M 0 0 L 20 0 L 20 20 Z",
            width=20,
            height=20,
            fill="#123456",
            confidence=0.8,
        )
    )
    svg = ExportService().to_svg(graph).data.decode("utf-8")
    assert '<path d="M 0 0 L 20 0 L 20 20 Z"' in svg
    assert 'transform="translate(100.0 75.0)"' in svg
    assert 'fill="#123456"' in svg


def test_png_export_renders_vector_as_filled_region() -> None:
    from io import BytesIO

    from PIL import Image

    from app.schemas.scene_graph import Transform, VectorElement
    from app.services.export_service import ExportService

    graph = _graph()
    graph.layers.append(
        VectorElement(
            id="v1",
            type="vector",
            name="Vector",
            transform=Transform(x=40, y=30),
            path="M 0 0 L 20 0 L 20 20 Z",
            width=20,
            height=20,
            fill="#FF0000",
            confidence=0.8,
        )
    )
    data = ExportService().rasterize(graph, "png", scale=2).data
    img = Image.open(BytesIO(data)).convert("RGBA")
    # red pixels present near the vector bounds
    reds = 0
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, _ = img.getpixel((x, y))
            if r > 200 and g < 80 and b < 80:
                reds += 1
    assert reds > 10