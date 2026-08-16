from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SCENE_GRAPH_SCHEMA_VERSION = 1

ElementType = Literal[
    "text",
    "rectangle",
    "circle",
    "ellipse",
    "line",
    "polygon",
    "vector",
    "image",
]


class Transform(BaseModel):
    x: float = 0.0
    y: float = 0.0
    scale_x: float = Field(1.0, alias="scaleX")
    scale_y: float = Field(1.0, alias="scaleY")
    rotation: float = 0.0  # degrees, clockwise

    model_config = {"populate_by_name": True}


class ElementBase(BaseModel):
    id: str
    type: ElementType
    name: str
    transform: Transform
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float | None = Field(None, alias="strokeWidth")
    stroke_dash_array: list[float] | None = Field(None, alias="strokeDashArray")
    opacity: float = 1.0
    visible: bool = True
    locked: bool = False
    confidence: float
    confidence_note: str | None = Field(None, alias="confidenceNote")

    model_config = {"populate_by_name": True}


class TextElement(ElementBase):
    type: Literal["text"]
    content: str
    font_family: str = Field(..., alias="fontFamily")
    font_size: float = Field(..., alias="fontSize")
    font_weight: int = Field(400, alias="fontWeight")
    font_style: Literal["normal", "italic"] | None = Field("normal", alias="fontStyle")
    text_align: Literal["left", "center", "right", "justify"] | None = Field(
        None, alias="textAlign"
    )
    letter_spacing: float | None = Field(None, alias="letterSpacing")
    line_height: float | None = Field(None, alias="lineHeight")
    width: float


class RectElement(ElementBase):
    type: Literal["rectangle"]
    width: float
    height: float
    rx: float | None = None
    ry: float | None = None


class CircleElement(ElementBase):
    type: Literal["circle"]
    radius: float


class EllipseElement(ElementBase):
    type: Literal["ellipse"]
    rx: float
    ry: float


class LineElement(ElementBase):
    type: Literal["line"]
    x1: float
    y1: float
    x2: float
    y2: float


class PolygonElement(ElementBase):
    type: Literal["polygon"]
    points: list[tuple[float, float]]


class VectorElement(ElementBase):
    type: Literal["vector"]
    path: str
    width: float
    height: float


class ImageElement(ElementBase):
    type: Literal["image"]
    src: str
    width: float
    height: float
    crop: dict | None = None


SceneGraphElement = (  # exported for type hints; pydantic discriminator below
    TextElement
    | RectElement
    | CircleElement
    | EllipseElement
    | LineElement
    | PolygonElement
    | VectorElement
    | ImageElement
)


class SceneGraph(BaseModel):
    schema_version: int = Field(SCENE_GRAPH_SCHEMA_VERSION, alias="schemaVersion")
    canvas: dict = Field(default_factory=lambda: {"width": 0, "height": 0, "background": None})
    layers: list[SceneGraphElement]
    confidence: dict[str, float]
    overall_confidence: float = Field(..., alias="overallConfidence")
    complexity: dict | None = Field(None, alias="complexity")

    model_config = {"populate_by_name": True}