from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.schemas.scene_graph import SceneGraph, TextElement, Transform
from app.services.confidence import compute_overall
from app.services.fonts import FontMatcher, FontRegistry, default_font_registry
from app.services.image_utils import load_image
from app.services.text_detector import DetectedText

# Every test that renders reference text needs a concrete font. DejaVu Sans is
# near-universal on Linux (and bundled with Pillow's common installs).
_DEJAVU = "DejaVu Sans"
_DEJAVU_SERIF = "DejaVu Serif"
_DEJAVU_MONO = "DejaVu Sans Mono"


def _registry() -> FontRegistry:
    return default_font_registry()


def _have_system(family: str) -> bool:
    return _registry().resolve(family, 400) is not None


def _render(
    family: str = _DEJAVU,
    text: str = "The quick brown fox",
    *,
    size: int = 72,
    weight: int = 400,
    ink: tuple[int, int, int] = (20, 20, 20),
    bg: tuple[int, int, int] = (250, 250, 250),
) -> np.ndarray:
    img = Image.new("RGBA", (900, 160), bg + (255,))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(_registry().resolve(family, weight), size)
    draw.text((20, 14), text, font=font, fill=ink + (255,))
    return np.array(img.convert("RGBA"))


# -- registry ------------------------------------------------------------------
def test_registry_resolves_common_families() -> None:
    r = _registry()
    assert _have_system(_DEJAVU)
    family = r.get(_DEJAVU)
    assert family is not None
    assert family.category == "sans"
    assert family.generic == "sans-serif"
    assert r.truetype(_DEJAVU, 400, 40) is not None
    assert r.resolve("not-installed-font-xyz", 400) is None


def test_registry_generic_fallback_mapping() -> None:
    r = _registry()
    # every resolved family maps to the generic CSS family of its category
    for fam in r.available_families():
        assert fam.generic in ("sans-serif", "serif", "monospace")


def test_registry_empty_database_degrades_gracefully() -> None:
    r = FontRegistry(families=[])
    assert r.size == 0
    assert r.available_families() == []
    assert r.truetype("anything", 400, 12) is None


# -- matcher -------------------------------------------------------------------
def test_matcher_empty_content_yields_no_match() -> None:
    m = FontMatcher(_registry())
    assert m.match(_render(), "") == []


def test_matcher_blank_crop_yields_no_match() -> None:
    m = FontMatcher(_registry())
    blank = np.full((100, 300, 4), 250, dtype=np.uint8)
    assert m.match(blank, "SOMETHING") == []


@pytest.mark.skipif(
    not (_have_system(_DEJAVU) and _have_system(_DEJAVU_MONO) and _have_system(_DEJAVU_SERIF)),
    reason="reference fonts not installed",
)
def test_matcher_identifies_sans_serif_mono() -> None:
    m = FontMatcher(_registry())
    cases = [
        (_render(_DEJAVU, "The quick brown fox"), "The quick brown fox", _DEJAVU),
        (_render(_DEJAVU_SERIF, "The quick brown fox"), "The quick brown fox", _DEJAVU_SERIF),
        (_render(_DEJAVU_MONO, "MONO 1234"), "MONO 1234", _DEJAVU_MONO),
    ]
    for crop, content, expected in cases:
        top = m.best(crop, content)
        assert top is not None, f"no match for {expected}"
        assert top.family == expected
        assert top.score >= 0.8


@pytest.mark.skipif(not _have_system(_DEJAVU), reason="DejaVu Sans not installed")
def test_matcher_detects_bold_weight() -> None:
    m = FontMatcher(_registry())
    crop = _render(_DEJAVU, "SHOUT", size=84, weight=700)
    top = m.best(crop, "SHOUT")
    assert top is not None
    assert top.family == _DEJAVU
    assert top.weight == 700


@pytest.mark.skipif(not _have_system(_DEJAVU), reason="DejaVu Sans not installed")
def test_matcher_handles_light_text_on_dark_background() -> None:
    m = FontMatcher(_registry())
    crop = _render(_DEJAVU, "NEON", ink=(240, 240, 240), bg=(15, 15, 15))
    top = m.best(crop, "NEON")
    assert top is not None
    assert top.family == _DEJAVU


@pytest.mark.skipif(not _have_system(_DEJAVU), reason="DejaVu Sans not installed")
def test_matcher_is_scale_robust() -> None:
    m = FontMatcher(_registry())
    for size in (24, 48, 96):
        top = m.best(_render(_DEJAVU, "SCALE", size=size), "SCALE")
        assert top is not None and top.family == _DEJAVU, f"failed at {size}px"


# -- enhance -------------------------------------------------------------------
@pytest.mark.skipif(not _have_system(_DEJAVU), reason="DejaVu Sans not installed")
def test_enhance_fills_detected_text_fields() -> None:
    crop = _render(_DEJAVU, "BRAND")
    image = load_image(np_img_to_png(crop))
    box = _text_bounds(crop)
    text = DetectedText(
        content="BRAND",
        x=box[0],
        y=box[1],
        width=box[2],
        height=box[3],
        rotation=0.0,
        confidence=0.92,
        font_color="#141414",
        is_guess=False,
    )
    FontMatcher(_registry()).enhance(image, text)
    assert text.font_family == _DEJAVU
    assert text.font_match_score is not None and text.font_match_score >= 0.8
    assert "matched" in (text.font_note or "")


def test_enhance_leaves_guesses_untouched() -> None:
    image = load_image(np_img_to_png(_render(_DEJAVU)))
    text = DetectedText(
        content="",
        x=10,
        y=10,
        width=50,
        height=20,
        rotation=0.0,
        confidence=0.55,
        font_color="#000000",
        is_guess=True,
    )
    FontMatcher(_registry()).enhance(image, text)
    assert text.font_family == "sans-serif"
    assert text.font_match_score is None


# -- builder -------------------------------------------------------------------
def test_builder_emits_matched_font_for_ocr_text() -> None:
    from app.services.scene_graph_builder import DetectedElements, SceneGraphBuilder

    detected = DetectedElements(
        shapes=[],
        regions=[],
        texts=[
            DetectedText(
                content="HELLO",
                x=0,
                y=0,
                width=100,
                height=30,
                rotation=0.0,
                confidence=0.9,
                font_color="#000000",
                is_guess=False,
                font_family=_DEJAVU,
                font_weight=700,
                font_match_score=0.94,
                font_note=f"font '{_DEJAVU}' matched (score 0.94)",
            )
        ],
    )
    img = load_image(np_img_to_png(_render(_DEJAVU)))
    graph = SceneGraphBuilder().build(img, detected)
    text = graph.layers[0]
    assert text.font_family == _DEJAVU
    assert text.font_weight == 700
    assert "matched" in (text.confidence_note or "")
    assert text.confidence == 0.94  # font match quality raises the OCR confidence


def test_builder_emits_guess_note_when_font_unknown() -> None:
    from app.services.scene_graph_builder import DetectedElements, SceneGraphBuilder

    detected = DetectedElements(
        shapes=[],
        regions=[],
        texts=[
            DetectedText(
                content="WORD",
                x=0,
                y=0,
                width=60,
                height=20,
                rotation=0.0,
                confidence=0.85,
                font_color="#000000",
                is_guess=False,
            )
        ],
    )
    img = load_image(np_img_to_png(_render(_DEJAVU)))
    graph = SceneGraphBuilder().build(img, detected)
    text = graph.layers[0]
    assert text.font_family == "sans-serif"
    assert "font guessed" in (text.confidence_note or "")


# -- confidence ----------------------------------------------------------------
def _text_elem(conf: float, note: str, content: str = "X") -> TextElement:
    return TextElement(
        id="t1",
        type="text",
        name="Text",
        transform=Transform(x=0, y=0),
        content=content,
        fontFamily="sans-serif",
        fontSize=16,
        fontWeight=400,
        width=40,
        confidence=conf,
        confidenceNote=note,
    )


def test_confidence_scales_with_font_match_score() -> None:
    agg = compute_overall([_text_elem(0.9, "OCR text; font 'X' matched (score 0.95)")])
    matched_strong = agg["text"]
    agg = compute_overall([_text_elem(0.9, "OCR text; font guessed")])
    guessed = agg["text"]
    agg = compute_overall([_text_elem(0.9, "OCR text; font 'Y' matched (score 0.45)")])
    matched_weak = agg["text"]
    assert matched_strong > guessed
    assert matched_strong > matched_weak
    assert matched_weak > guessed  # any match beats an honest "font guessed"


def test_confidence_empty_content_always_penalized() -> None:
    agg = compute_overall([_text_elem(0.9, "OCR text; font 'X' matched (score 0.95)", content="")])
    assert agg["text"] < 0.6


# -- export --------------------------------------------------------------------
def test_svg_export_includes_font_weight() -> None:
    graph = SceneGraph(
        schemaVersion=1,
        canvas={"width": 100, "height": 100, "background": "#FFFFFF"},
        layers=[_text_elem(0.9, "x", content="Hi")],
        confidence={"text": 0.9},
        overallConfidence=0.9,
    )
    from app.services.export_service import ExportService

    svg = ExportService().to_svg(graph).data.decode("utf-8")
    assert 'font-weight="400"' in svg
    assert '<text ' in svg


@pytest.mark.skipif(not _have_system(_DEJAVU), reason="DejaVu Sans not installed")
def test_png_export_renders_text_with_matched_font() -> None:
    from io import BytesIO

    from app.services.export_service import ExportService

    graph = SceneGraph(
        schemaVersion=1,
        canvas={"width": 200, "height": 100, "background": "#FFFFFF"},
        layers=[
            TextElement(
                id="t1",
                type="text",
                name="Text",
                transform=Transform(x=100, y=50),
                content="Typo",
                fontFamily=_DEJAVU,
                fontSize=40,
                fontWeight=700,
                width=120,
                fill="#101010",
                confidence=0.9,
            )
        ],
        confidence={"text": 0.9},
        overallConfidence=0.9,
    )
    data = ExportService().rasterize(graph, "png").data
    img = Image.open(BytesIO(data)).convert("L")
    arr = np.array(img)
    dark = int((arr < 100).sum())
    assert dark > 20  # glyphs actually painted using the resolved font


def test_text_detector_defaults_still_valid() -> None:
    # DetectedText default font fields must match the previous hard-coded values.
    t = DetectedText(
        content="", x=0, y=0, width=10, height=10, rotation=0.0,
        confidence=0.5, font_color="#000", is_guess=True,
    )
    assert t.font_family == "sans-serif"
    assert t.font_weight == 400
    assert t.font_style == "normal"


def np_img_to_png(img: np.ndarray) -> bytes:
    from tests.fixtures import to_png_bytes

    return to_png_bytes(img)


# -- pipeline end-to-end --------------------------------------------------------
class _StubTextDetector:
    def __init__(self, texts: list[DetectedText]) -> None:
        self.texts = texts

    async def detect(self, image):
        return list(self.texts)


def _run_pipeline(storage, img_bytes: bytes, texts: list[DetectedText]):
    from app.services.pipeline import ReconstructionPipeline
    from app.services.progressive import ProgressiveRouter

    pipe = ReconstructionPipeline(
        storage,
        text_detector=_StubTextDetector(texts),
        router=ProgressiveRouter(),
    )
    import asyncio

    async def _r():
        async def progress(stage: str, sp: float, overall=None) -> None:
            pass

        return await pipe.run(img_bytes, "u1", progress)

    return asyncio.run(_r())


@pytest.mark.skipif(not _have_system(_DEJAVU), reason="DejaVu Sans not installed")
def test_pipeline_surfaces_matched_font_in_scene_graph() -> None:
    from app.schemas.scene_graph import SceneGraph
    from app.services.storage import LocalStorage

    crop = _render(_DEJAVU, "HEADLINE")
    box = _text_bounds(crop)
    text = DetectedText(
        content="HEADLINE",
        x=box[0],
        y=box[1],
        width=box[2],
        height=box[3],
        rotation=0.0,
        confidence=0.9,
        font_color="#141414",
        is_guess=False,
        font_size_estimate=box[3],
    )
    storage = LocalStorage(Path(tempfile.mkdtemp()) / "storage")
    result = _run_pipeline(storage, np_img_to_png(crop), [text])
    graph = SceneGraph.model_validate(result.scene_graph)
    text_elems = [e for e in graph.layers if e.type == "text"]
    assert text_elems
    elem = text_elems[0]
    assert elem.font_family == _DEJAVU
    assert "matched" in (elem.confidence_note or "")


def test_pipeline_skips_matching_when_font_matcher_disabled() -> None:
    from app.schemas.scene_graph import SceneGraph
    from app.services.pipeline import ReconstructionPipeline
    from app.services.progressive import ProgressiveRouter
    from app.services.storage import LocalStorage

    crop = _render(_DEJAVU, "HEADLINE")
    box = _text_bounds(crop)
    text = DetectedText(
        content="HEADLINE",
        x=box[0],
        y=box[1],
        width=box[2],
        height=box[3],
        rotation=0.0,
        confidence=0.9,
        font_color="#141414",
        is_guess=False,
        font_size_estimate=box[3],
    )
    pipe = ReconstructionPipeline(
        LocalStorage(Path(tempfile.mkdtemp()) / "storage"),
        text_detector=_StubTextDetector([text]),
        router=ProgressiveRouter(),
        font_matcher=None,
    )
    import asyncio

    async def _r():
        async def progress(stage, sp, overall=None):
            pass

        return await pipe.run(np_img_to_png(crop), "u1", progress)

    graph = SceneGraph.model_validate(asyncio.run(_r()).scene_graph)
    elem = next(e for e in graph.layers if e.type == "text")
    assert elem.font_family == "sans-serif"
    assert "font guessed" in (elem.confidence_note or "")


def _text_bounds(img: np.ndarray) -> tuple[float, float, float, float]:
    gray = img[..., :3].mean(axis=2)
    ink = gray < 128
    ys, xs = np.where(ink)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max(), ys.max()
    return float(x0), float(y0), float(x1 - x0 + 1), float(y1 - y0 + 1)