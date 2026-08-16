from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.schemas.scene_graph import (
    SCENE_GRAPH_SCHEMA_VERSION,
    CircleElement,
    EllipseElement,
    LineElement,
    PolygonElement,
    RectElement,
    SceneGraph,
    SceneGraphElement,
    TextElement,
    Transform,
)
from app.services.color_extractor import Region
from app.services.image_utils import LoadedImage
from app.services.shape_detector import DetectedShape
from app.services.text_detector import DetectedText


@dataclass
class DetectedElements:
    shapes: list[DetectedShape]
    regions: list[Region]
    texts: list[DetectedText]


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
    ) -> SceneGraph:
        elements: list[SceneGraphElement] = []

        if background_fill:
            elements.append(
                self._background_rect(image, background_fill)
            )

        for shape in detected.shapes:
            elem = self._shape_to_element(shape)
            if elem is not None:
                elements.append(elem)

        for text in detected.texts:
            elements.append(self._text_to_element(text))

        confidence, overall = self._score(elements)
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

    def _text_to_element(self, text: DetectedText) -> TextElement:
        note = (
            "text region detected; content will be recovered when OCR is enabled"
            if text.is_guess
            else "OCR text"
        )
        stroke = text.font_color
        return TextElement(
            id=self._uid("text"),
            type="text",
            name="Text",
            transform=Transform(
                x=text.x + text.width / 2, y=text.y + text.height / 2,
                rotation=text.rotation,
            ),
            content=text.content or "(text)",
            fontFamily="sans-serif",
            fontSize=text.font_size_estimate or max(12.0, text.height),
            fontWeight=400,
            fill=stroke,
            width=text.width,
            confidence=text.confidence,
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