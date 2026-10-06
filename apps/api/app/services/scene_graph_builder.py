from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.schemas.scene_graph import (
    SCENE_GRAPH_SCHEMA_VERSION,
    CircleElement,
    EllipseElement,
    ImageElement,
    LineElement,
    PolygonElement,
    RectElement,
    SceneGraph,
    SceneGraphElement,
    TextElement,
    Transform,
    VectorElement,
)
from app.services.color_extractor import Region
from app.services.image_utils import LoadedImage
from app.services.shape_detector import DetectedShape
from app.services.text_detector import DetectedText
from app.services.vectorizer import DetectedVector


@dataclass
class DetectedElements:
    shapes: list[DetectedShape]
    regions: list[Region]
    texts: list[DetectedText]
    vectors: list[DetectedVector] | None = None
    images: list[ImageElement] | None = None


@dataclass
class BuildOptions:
    """Pipeline-injected hints (progressive routing v0.4)."""

    complexity_kind: str | None = None  # "graphic" | "photographic"
    complexity_score: float | None = None  # 0 (simple) .. 1 (complex)


class SceneGraphBuilder:
    """Composes detected elements into an ordered, schema-compliant scene graph.

    Layering: background-sized shapes first, then shapes, then text on top.
    """

    def __init__(self, element_origin: str = "reconstruction") -> None:
        self.element_origin = element_origin

    def build(
        self,
        image: LoadedImage,
        detected: DetectedElements,
        background_fill: str | None = None,
        options: BuildOptions | None = None,
    ) -> SceneGraph:
        elements: list[SceneGraphElement] = []
        _ = options  # used by the pipeline for routing decisions; reserved here

        if background_fill:
            elements.append(
                self._background_rect(image, background_fill)
            )

        for shape in detected.shapes:
            elem = self._shape_to_element(shape)
            if elem is not None:
                elements.append(elem)

        for vector in detected.vectors or []:
            elements.append(self._vector_to_element(vector))

        for image_elem in detected.images or []:
            elements.append(image_elem)

        for text in detected.texts:
            elements.append(self._text_to_element(text))

        confidence, overall = self._score(elements)
        complexity = None
        if options is not None and options.complexity_kind:
            complexity = {"kind": options.complexity_kind}
            if options.complexity_score is not None:
                complexity["score"] = round(options.complexity_score, 4)
        graph = SceneGraph(
            schemaVersion=SCENE_GRAPH_SCHEMA_VERSION,
            canvas={
                "width": image.width,
                "height": image.height,
                "background": background_fill,
            },
            layers=elements,
            confidence=confidence,
            overallConfidence=overall,
            complexity=complexity,
        )
        return graph

    # -- element factories -------------------------------------------------------
    def _background_rect(self, image: LoadedImage, fill: str) -> RectElement:
        return RectElement(
            id=self._uid("bg"),
            type="rectangle",
            name="Background",
            transform=Transform(x=0, y=0),
            fill=fill,
            width=float(image.width),
            height=float(image.height),
            confidence=1.0,
            confidenceNote="dominant background color",
        )

    def _shape_to_element(self, shape: DetectedShape) -> SceneGraphElement | None:
        p = shape.params
        style = {"fill": p.get("fill"), "confidence": shape.confidence}
        if shape.kind == "rectangle":
            return RectElement(
                id=self._uid("rect"), type="rectangle", name="Rectangle",
                transform=Transform(x=p["x"], y=p["y"], rotation=p.get("rotation", 0.0)),
                width=p["width"], height=p["height"], **style,
            )
        if shape.kind == "rounded-rectangle":
            return RectElement(
                id=self._uid("rect"), type="rectangle", name="Rounded Rectangle",
                transform=Transform(x=p["x"], y=p["y"], rotation=p.get("rotation", 0.0)),
                width=p["width"], height=p["height"], rx=p.get("rx"), ry=p.get("ry"),
                **style,
            )
        if shape.kind == "circle":
            return CircleElement(
                id=self._uid("circle"), type="circle", name="Circle",
                transform=Transform(x=p["x"], y=p["y"]),
                radius=p["radius"], **style,
            )
        if shape.kind == "ellipse":
            return EllipseElement(
                id=self._uid("ellipse"), type="ellipse", name="Ellipse",
                transform=Transform(x=p["x"], y=p["y"], rotation=p.get("rotation", 0.0)),
                rx=p["rx"], ry=p["ry"], **style,
            )
        if shape.kind == "line":
            return LineElement(
                id=self._uid("line"), type="line", name="Line",
                transform=Transform(x=0, y=0),
                x1=p["x1"], y1=p["y1"], x2=p["x2"], y2=p["y2"],
                stroke=p.get("stroke"), strokeWidth=p.get("stroke_width"),
                fill="none", **style,
            )
        if shape.kind == "polygon":
            return PolygonElement(
                id=self._uid("polygon"), type="polygon", name="Polygon",
                transform=Transform(x=0, y=0),
                points=[tuple(pt) for pt in p["points"]], **style,
            )
        return None

    def _vector_to_element(self, vector: DetectedVector) -> VectorElement:
        return VectorElement(
            id=self._uid("vector"),
            type="vector",
            name="Vector",
            transform=Transform(x=vector.x, y=vector.y),
            path=vector.path,
            width=vector.width,
            height=vector.height,
            fill=vector.fill,
            confidence=vector.confidence,
            confidenceNote="vector outline from contour tracing",
        )

    def _text_to_element(self, text: DetectedText) -> TextElement:
        if text.is_guess:
            note = (
                "text region detected; content will be recovered when OCR is enabled"
            )
            font_family = "sans-serif"
            font_weight = 400
            font_style = "normal"
        else:
            note = f"OCR text; {text.font_note or 'font guessed'}"
            font_family = text.font_family or "sans-serif"
            font_weight = text.font_weight or 400
            font_style = text.font_style or "normal"
        stroke = text.font_color
        confidence = text.confidence
        if text.font_match_score is not None:
            confidence = min(1.0, max(text.confidence, text.font_match_score))
        return TextElement(
            id=self._uid("text"),
            type="text",
            name="Text",
            transform=Transform(
                x=text.x + text.width / 2, y=text.y + text.height / 2,
                rotation=text.rotation,
            ),
            content=text.content or "(text)",
            fontFamily=font_family,
            fontSize=text.font_size_estimate or max(12.0, text.height),
            fontWeight=font_weight,
            fontStyle=font_style,
            fill=stroke,
            width=text.width,
            confidence=confidence,
            confidenceNote=note,
        )

    # -- confidence ----------------------------------------------------------------
    def _score(self, layers: list[SceneGraphElement]):
        from app.services.confidence import compute_overall

        per = compute_overall(layers)
        return per, per.get("overall", 1.0)

    @staticmethod
    def _uid(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:8]}"