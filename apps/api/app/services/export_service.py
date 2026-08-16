from __future__ import annotations

import io
import json
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageDraw, ImageFont

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

    EXPORTABLE = ("png", "jpg", "svg", "pdf")

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

    # -- PDF --------------------------------------------------------------------
    def to_pdf(self, graph: SceneGraph, *, scale: float = 1.0) -> ExportResult:
        """Embed a rasterized scene as a single-page PDF (v0.5)."""
        width = int(graph.canvas["width"] * scale)
        height = int(graph.canvas["height"] * scale)
        if width <= 0 or height <= 0:
            raise ExportError("canvas has invalid dimensions")
        rgba = self.rasterize(graph, "png", scale=scale)
        img = Image.open(io.BytesIO(rgba.data)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PDF")
        return ExportResult(format="pdf", data=buf.getvalue(), content_type="application/pdf")

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
            elif elem.type == "vector":
                self._draw_vector_path(img, draw, elem, scale)
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

    def _draw_vector_path(
        self, img: Image.Image, draw: ImageDraw.ImageDraw, elem, scale: float
    ) -> None:
        """Render an SVG `d` path into the raster image.

        Multi-subpath paths (our vectorizer's holes: ring interiors, letter
        counters) are composited with an even-odd (XOR) rule so the interior is
        punched out instead of over-filled. Single-subpath paths keep the fast
        plain polygon fill.
        """
        subpaths = _flatten_subpaths(
            elem.path, samples_per_unit=128 if scale > 4 else 64
        )
        subpaths = [p for p in subpaths if len(p) >= 3]
        if not subpaths:
            return
        fill = _parse_hex(elem.fill) if elem.fill else None
        if fill is None:
            return
        cx, cy = elem.transform.x * scale, elem.transform.y * scale
        scaled = [
            [(cx + (px * scale), cy + (py * scale)) for px, py in sub] for sub in subpaths
        ]

        if len(scaled) == 1:
            draw.polygon(scaled[0], fill=fill)
            return

        # Multi-subpath: XOR each subpath's fill into a region mask.
        x0 = max(0, int(min(p[0] for sub in scaled for p in sub)))
        y0 = max(0, int(min(p[1] for sub in scaled for p in sub)))
        x1 = min(img.width, int(max(p[0] for sub in scaled for p in sub)) + 1)
        y1 = min(img.height, int(max(p[1] for sub in scaled for p in sub)) + 1)
        if x1 <= x0 or y1 <= y0:
            return
        mask = Image.new("L", (x1 - x0, y1 - y0), 0)
        for sub in scaled:
            layer = Image.new("L", (x1 - x0, y1 - y0), 0)
            ImageDraw.Draw(layer).polygon(
                [(p[0] - x0, p[1] - y0) for p in sub], fill=255
            )
            mask = ImageChops.logical_xor(mask.convert("1"), layer.convert("1"))
        fill_px = fill + (255,) if img.mode == "RGBA" else fill + (255,)
        img.paste(fill_px, (x0, y0), mask=mask.convert("L"))

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
            elif elem.type == "vector":
                cx, cy = elem.transform.x, elem.transform.y
                fill = elem.fill or "#000000"
                parts.append(
                    f'<path d="{elem.path}" fill-rule="evenodd" '
                    f'transform="translate({cx} {cy})" fill="{fill}"/>'
                )
            elif elem.type == "image":
                # Raster-to-raster: reference the source via a data-less group so
                # the SVG stays valid; actual cutouts are raster assets, not vector.
                parts.append(
                    f'<image x="{elem.transform.x - elem.width / 2}" '
                    f'y="{elem.transform.y - elem.height / 2}" width="{elem.width}" '
                    f'height="{elem.height}" href="{_escape(elem.src)}"/>'
                )
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


def _flatten_subpaths(
    d: str, samples_per_unit: int = 64
) -> list[list[tuple[float, float]]]:
    """Flatten an SVG path (M/L/C/Q/A/Z) into per-subpath point lists.

    Every top-level `M` starts a new subpath (our vectorizer emits hole
    interiors as extra `M…Z` segments), so consumers can apply even-odd fill.
    """
    import math

    tokens = d.replace(",", " ").split()
    if not tokens:
        return []
    subpaths: list[list[tuple[float, float]]] = []
    out: list[tuple[float, float]] = []
    cur = (0.0, 0.0)
    start: tuple[float, float] | None = None
    i = 0
    cmd = "M"

    def num(i: int) -> float:
        return float(tokens[i])

    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            cmd = token
            i += 1
            continue
        if cmd == "M":
            x, y = num(i), num(i + 1)
            i += 2
            if out:
                subpaths.append(out)
                out = []
            out.append((x, y))
            start = (x, y)
            cur = (x, y)
        elif cmd == "L":
            x, y = num(i), num(i + 1)
            i += 2
            out.append((x, y))
            cur = (x, y)
        elif cmd == "C":
            c1x, c1y, c2x, c2y = num(i), num(i + 1), num(i + 2), num(i + 3)
            x, y = num(i + 4), num(i + 5)
            i += 6
            n = max(4, int(samples_per_unit * math.hypot(x - cur[0], y - cur[1])))
            for t in range(1, n + 1):
                u = t / n
                mu = 1 - u
                px = (
                    mu**3 * cur[0]
                    + 3 * mu**2 * u * c1x
                    + 3 * mu * u**2 * c2x
                    + u**3 * x
                )
                py = (
                    mu**3 * cur[1]
                    + 3 * mu**2 * u * c1y
                    + 3 * mu * u**2 * c2y
                    + u**3 * y
                )
                out.append((px, py))
            cur = (x, y)
        elif cmd == "Q":
            qx, qy = num(i), num(i + 1)
            x, y = num(i + 2), num(i + 3)
            i += 4
            n = max(4, int(samples_per_unit * math.hypot(x - cur[0], y - cur[1])))
            for t in range(1, n + 1):
                u = t / n
                mu = 1 - u
                px = mu**2 * cur[0] + 2 * mu * u * qx + u**2 * x
                py = mu**2 * cur[1] + 2 * mu * u * qy + u**2 * y
                out.append((px, py))
            cur = (x, y)
        elif cmd == "A":
            rx, ry, rot = num(i), num(i + 1), num(i + 2)
            laf, sf = int(num(i + 3)), int(num(i + 4))
            x, y = num(i + 5), num(i + 6)
            i += 7
            pts = _arc_points(cur, (x, y), rx, ry, rot, laf, sf)
            out.extend(pts)
            cur = (x, y)
        elif cmd == "Z":
            if start and out and start != out[-1]:
                out.append(start)
                cur = start
            i += 1
        else:
            raise ValueError(f"unsupported SVG command: {cmd}")
    if out:
        subpaths.append(out)
    return subpaths


def _arc_points(
    start: tuple[float, float],
    end: tuple[float, float],
    rx: float,
    ry: float,
    rot: float,
    large: int,
    sweep: int,
) -> list[tuple[float, float]]:
    """Flatten an SVG elliptical arc to line segments (endpoint→center form)."""
    import math

    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0:
        return [end]
    phi = math.radians(rot % 360)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)
    x1, y1 = start
    x2, y2 = end
    dx = (x1 - x2) / 2
    dy = (y1 - y2) / 2
    x1p = cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    rx2, ry2 = rx * rx, ry * ry
    denom = rx2 * y1p * y1p + ry2 * x1p * x1p
    if abs(denom) < 1e-12:
        return [end]
    num = rx2 * ry2 - rx2 * y1p * y1p - ry2 * x1p * x1p
    coef = math.sqrt(max(0.0, num / denom))
    if large == sweep:
        coef = -coef
    cxp = coef * (rx * y1p / ry)
    cyp = coef * -(ry * x1p / rx)
    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2

    def angle(ux, uy, vx, vy):
        dot = ux * vx + uy * vy
        det = ux * vy - uy * vx
        return math.atan2(det, dot)

    theta1 = angle(1.0, 0.0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    delta = angle((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if sweep == 0 and delta > 0:
        delta -= 2 * math.pi
    if sweep == 1 and delta < 0:
        delta += 2 * math.pi
    steps = max(8, min(128, int(abs(delta) / (math.pi / 48))))
    pts: list[tuple[float, float]] = []
    for k in range(1, steps + 1):
        t = theta1 + delta * k / steps
        x = cx + rx * math.cos(t) * cos_phi - ry * math.sin(t) * sin_phi
        y = cy + rx * math.cos(t) * sin_phi + ry * math.sin(t) * cos_phi
        pts.append((x, y))
    return pts


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