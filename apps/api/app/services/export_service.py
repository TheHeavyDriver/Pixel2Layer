from __future__ import annotations

import io
import json
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from app.schemas.scene_graph import SceneGraph, SceneGraphElement


class ExportError(ValueError):
    pass


@dataclass
class ExportResult:
    format: str
    data: bytes
    content_type: str


class ExportService:
    """Server-side rasterization of a scene graph to PNG/JPG/SVG, plus .p2l round-trip."""

    EXPORTABLE = ("png", "jpg", "svg")

    # -- PNG / JPG -------------------------------------------------------------
    def rasterize(self, graph: SceneGraph, fmt: str, *, scale: float = 1.0) -> ExportResult:
        fmt = fmt.lower()
        if fmt not in ("png", "jpg"):
            raise ExportError(f"unsupported raster format: {fmt}")
        width = int(graph.canvas["width"] * scale)
        height = int(graph.canvas["height"] * scale)
        if width <= 0 or height <= 0:
            raise ExportError("canvas has invalid dimensions")
        background = graph.canvas.get("background")
        img = Image.new(
            "RGBA",
            (width, height),
            _parse_hex(background) + (255,) if background else (0, 0, 0, 0),
        )
        self._draw_elements(img, graph.layers, scale)
        if fmt == "jpg":
            rgba = Image.new("RGB", img.size, (255, 255, 255))
            rgba.paste(img, mask=img.split()[3])
            buf = io.BytesIO()
            rgba.save(buf, format="JPEG", quality=85)
        else:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
        return ExportResult(format=fmt, data=buf.getvalue(), content_type=f"image/{fmt}")

    def _draw_elements(
        self, img: Image.Image, layers: list[SceneGraphElement], scale: float
    ) -> None:
        draw = ImageDraw.Draw(img)
        for elem in layers:
            if not elem.visible:
                continue
            if elem.type == "rectangle":
                w, h = elem.width * scale, elem.height * scale
                x, y = elem.transform.x * scale, elem.transform.y * scale
                x -= w / 2
                y -= h / 2
                fill = _parse_hex(elem.fill) if elem.fill else None
                draw.rectangle([x, y, x + w, y + h], fill=fill)
            elif elem.type == "circle":
                r = elem.radius * scale
                cx, cy = elem.transform.x * scale, elem.transform.y * scale
                fill = _parse_hex(elem.fill) if elem.fill else None
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
            elif elem.type == "ellipse":
                rx, ry = elem.rx * scale, elem.ry * scale
                cx, cy = elem.transform.x * scale, elem.transform.y * scale
                fill = _parse_hex(elem.fill) if elem.fill else None
                draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill)
            elif elem.type == "line":
                draw.line(
                    [
                        elem.x1 * scale,
                        elem.y1 * scale,
                        elem.x2 * scale,
                        elem.y2 * scale,
                    ],
                    fill=_parse_hex(elem.stroke) if elem.stroke else (0, 0, 0, 255),
                    width=max(1, int((elem.stroke_width or 1) * scale)),
                )
            elif elem.type == "polygon":
                pts = [(p[0] * scale, p[1] * scale) for p in elem.points]
                draw.polygon(pts, fill=_parse_hex(elem.fill) if elem.fill else None)
            elif elem.type == "text":
                self._draw_text(draw, elem)
            elif elem.type == "image":
                # v0.2 raster shells out to the cached original for images.
                pass

    def _draw_text(self, draw: ImageDraw.ImageDraw, elem) -> None:
        fill = _parse_hex(elem.fill) if elem.fill else (0, 0, 0, 255)
        try:
            size = int(elem.font_size * 0.62) or 12
            draw.text(
                (elem.transform.x, elem.transform.y - size / 2),
                elem.content,
                fill=fill,
                font=_load_default_font(size),
                anchor="lm",
            )
        except (ValueError, OSError):
            draw.text((elem.transform.x, elem.transform.y), elem.content, fill=fill)

    # -- SVG --------------------------------------------------------------------
    def to_svg(self, graph: SceneGraph) -> ExportResult:
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{graph.canvas["width"]}" '
            f'height="{graph.canvas["height"]}" viewBox="0 0 {graph.canvas["width"]} '
            f'{graph.canvas["height"]}">',
        ]
        if graph.canvas.get("background"):
            parts.append(
                f'<rect width="100%" height="100%" fill="{graph.canvas["background"]}"/>'
            )
        for elem in graph.layers:
            if not elem.visible:
                continue
            if elem.type == "rectangle":
                w, h = elem.width, elem.height
                x, y = elem.transform.x - w / 2, elem.transform.y - h / 2
                extra = f' rx="{elem.rx}"' if elem.rx else ""
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{w}" height="{h}"{extra} '
                    f'fill="{elem.fill}"/>'
                )
            elif elem.type == "circle":
                parts.append(
                    f'<circle cx="{elem.transform.x}" cy="{elem.transform.y}" '
                    f'r="{elem.radius}" fill="{elem.fill}"/>'
                )
            elif elem.type == "ellipse":
                parts.append(
                    f'<ellipse cx="{elem.transform.x}" cy="{elem.transform.y}" '
                    f'rx="{elem.rx}" ry="{elem.ry}" fill="{elem.fill}"/>'
                )
            elif elem.type == "line":
                parts.append(
                    f'<line x1="{elem.x1}" y1="{elem.y1}" x2="{elem.x2}" y2="{elem.y2}" '
                    f'stroke="{elem.stroke or "#000000"}" stroke-width="{elem.stroke_width or 1}"/>'
                )
            elif elem.type == "polygon":
                points = " ".join(f"{x},{y}" for x, y in elem.points)
                parts.append(f'<polygon points="{points}" fill="{elem.fill}"/>')
            elif elem.type == "text":
                parts.append(
                    f'<text x="{elem.transform.x}" y="{elem.transform.y}" '
                    f'font-family="{elem.font_family}" font-size="{elem.font_size}" '
                    f'text-anchor="middle" fill="{elem.fill or "#000"}">'
                    f"{_escape(elem.content)}</text>"
                )
        parts.append("</svg>")
        data = "\n".join(parts).encode("utf-8")
        return ExportResult(format="svg", data=data, content_type="image/svg+xml")

    # -- .p2l round-trip ------------------------------------------------------------
    def serialize_p2l(self, graph: SceneGraph, *, metadata: dict | None = None) -> bytes:
        payload = {
            "format": "pixel2layer-project",
            "version": graph.schema_version,
            "scene": graph.model_dump(by_alias=True),
            "metadata": metadata or {},
        }
        return json.dumps(payload, sort_keys=True).encode("utf-8")

    def deserialize_p2l(self, data: bytes) -> SceneGraph:
        scene, _ = self.deserialize_p2l_payload(data)
        return scene

    def deserialize_p2l_payload(self, data: bytes) -> tuple[SceneGraph, dict]:
        try:
            payload = json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ExportError("invalid .p2l payload") from exc
        if payload.get("format") != "pixel2layer-project":
            raise ExportError("not a pixel2layer project file")
        try:
            scene = SceneGraph.model_validate(payload["scene"])
        except Exception as exc:  # noqa: BLE001
            raise ExportError(f"invalid scene graph in .p2l: {exc}") from exc
        return scene, payload.get("metadata", {})


def _parse_hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _load_default_font(size: int):
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()