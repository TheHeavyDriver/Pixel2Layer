from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.scene_graph import SceneGraph, SceneGraphElement


@dataclass
class GroupSuggestion:
    """A detected semantic grouping of layers (v0.5+ backlog: smart layer grouping).

    `name` is a human-friendly label (header / hero / footer / decoration /
    product / content). `element_ids` preserve layer order within the group.
    """

    name: str
    element_ids: list[str] = field(default_factory=list)


class LayerGrouper:
    """Suggests smart layer groups from spatial layout of a scene graph.

    Heuristics (meant to be useful, not perfect):
    - a full-canvas rectangle is labelled *background*;
    - small peripheral elements are *decorations*;
    - remaining elements are clustered into horizontal bands by their vertical
      center, then labelled *header* (top band), *footer* (bottom band),
      *hero* (tallest band), *products* (band of similar-sized columns), or
      *content* (everything else).
    """

    def __init__(
        self,
        band_gap_ratio: float = 0.10,
        band_overlap: float = 0.20,
        bg_cover_ratio: float = 0.90,
        decoration_ratio: float = 0.02,
    ) -> None:
        self.band_gap_ratio = band_gap_ratio
        self.band_overlap = band_overlap
        self.bg_cover_ratio = bg_cover_ratio
        self.decoration_ratio = decoration_ratio

    def suggest(self, scene: SceneGraph) -> list[GroupSuggestion]:
        if not scene.layers:
            return []
        width = scene.canvas["width"]
        height = scene.canvas["height"]
        if not width or not height:
            width = max(
                (b["x"] + b["width"] for b in self._bounds_of_all(scene.layers)),
                default=1,
            )
            height = max(
                (b["y"] + b["height"] for b in self._bounds_of_all(scene.layers)),
                default=1,
            )

        background = GroupSuggestion("background")
        decorations = GroupSuggestion("decorations")
        rest: list[tuple[SceneGraphElement, dict]] = []
        for layer in scene.layers:
            b = self._bounds(layer)
            if b is None:
                continue
            area = b["width"] * b["height"]
            covers_canvas = (
                b["width"] >= width * self.bg_cover_ratio
                and b["height"] >= height * self.bg_cover_ratio
            )
            tiny = area <= width * height * self.decoration_ratio
            if covers_canvas:
                background.element_ids.append(layer.id)
            elif tiny:
                decorations.element_ids.append(layer.id)
            else:
                rest.append((layer, b))

        bands = self._cluster_bands(rest, height)
        suggestions: list[GroupSuggestion] = []
        if background.element_ids:
            suggestions.append(background)
        suggestions.extend(self._label_bands(bands, width, height))
        if decorations.element_ids:
            suggestions.append(decorations)
        return suggestions

    # -- helpers ----------------------------------------------------------------
    def _cluster_bands(
        self, items: list[tuple[SceneGraphElement, dict]], height: float
    ) -> list[list[tuple[SceneGraphElement, dict]]]:
        """Cluster elements into horizontal bands by vertical-center proximity."""
        gap = max(1.0, height * self.band_gap_ratio)
        bands: list[list[tuple[SceneGraphElement, dict]]] = []
        for item in sorted(items, key=lambda it: it[1]["cy"]):
            placed = False
            for band in bands:
                band_cy = sum(b["cy"] for _, b in band) / len(band)
                v_overlap = self._vertical_overlap(item[1], band)
                if v_overlap >= self.band_overlap:
                    band.append(item)
                    placed = True
                    break
                if abs(item[1]["cy"] - band_cy) <= gap:
                    band.append(item)
                    placed = True
                    break
            if not placed:
                bands.append([item])
        return bands

    @staticmethod
    def _vertical_overlap(b: dict, band: list[tuple[SceneGraphElement, dict]]) -> float:
        """Fraction of the new box's height overlapping the band's boxes."""
        band_top = min(x[1]["y"] for x in band)
        band_bottom = max(x[1]["y"] + x[1]["height"] for x in band)
        top = max(b["y"], band_top)
        bottom = min(b["y"] + b["height"], band_bottom)
        overlap = max(0.0, bottom - top)
        return overlap / max(1e-6, b["height"])

    def _label_bands(
        self, bands: list[list[tuple[SceneGraphElement, dict]]], width: float, height: float
    ) -> list[GroupSuggestion]:
        if not bands:
            return []
        suggestions: list[GroupSuggestion] = []
        # tallest band = hero; everything else labelled by position.
        def _band_height(i: int) -> float:
            return self._band_bottom(bands[i]) - self._band_top(bands[i])

        tallest_idx = max(range(len(bands)), key=_band_height)
        for i, band in enumerate(bands):
            top = self._band_top(band)
            bottom = self._band_bottom(band)
            label: str
            if top <= height * 0.25:
                label = "header"
            elif bottom >= height * 0.75:
                label = "footer"
            elif self._looks_like_products(band, width):
                label = "products"
            elif i == tallest_idx and (bottom - top) >= height * 0.25:
                label = "hero"
            else:
                label = "content"
            suggestion = GroupSuggestion(label)
            for item in sorted(band, key=lambda it: it[1]["x"]):
                suggestion.element_ids.append(item[0].id)
            suggestions.append(suggestion)
        return suggestions

    def _looks_like_products(
        self, band: list[tuple[SceneGraphElement, dict]], width: float
    ) -> bool:
        if len(band) < 2:
            return False
        widths = [b["width"] for _, b in band]
        avg = sum(widths) / len(widths)
        similar = sum(1 for w in widths if abs(w - avg) <= avg * 0.4)
        span = max(b["x"] + b["width"] for _, b in band) - min(b["x"] for _, b in band)
        return similar / len(widths) >= 0.75 and span >= width * 0.5

    @staticmethod
    def _band_top(band: list[tuple[SceneGraphElement, dict]]) -> float:
        return min(b["y"] for _, b in band)

    @staticmethod
    def _band_bottom(band: list[tuple[SceneGraphElement, dict]]) -> float:
        return max(b["y"] + b["height"] for _, b in band)

    # -- element geometry ---------------------------------------------------------
    def _bounds_of_all(self, layers: list[SceneGraphElement]) -> list[dict]:
        return [b for b in (self._bounds(el) for el in layers) if b is not None]

    def _bounds(self, el: SceneGraphElement) -> dict | None:
        t = el.transform
        cx, cy = t.x, t.y
        if el.type == "rectangle":
            w, h = el.width, el.height
        elif el.type == "circle":
            w = h = el.radius * 2
        elif el.type == "ellipse":
            w, h = el.rx * 2, el.ry * 2
        elif el.type == "image" or el.type == "vector":
            w, h = el.width, el.height
        elif el.type == "text":
            w, h = el.width, el.font_size or 24
        elif el.type == "line":
            xs = [el.x1, el.x2]
            ys = [el.y1, el.y2]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            if w == 0 and h == 0:
                return None
            return {
                "x": min(xs),
                "y": min(ys),
                "width": max(1.0, w),
                "height": max(1.0, h),
                "cx": min(xs) + w / 2,
                "cy": min(ys) + h / 2,
            }
        elif el.type == "polygon":
            xs = [p[0] for p in el.points]
            ys = [p[1] for p in el.points]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            if w == 0 and h == 0:
                return None
            return {
                "x": min(xs),
                "y": min(ys),
                "width": max(1.0, w),
                "height": max(1.0, h),
                "cx": min(xs) + w / 2,
                "cy": min(ys) + h / 2,
            }
        else:  # pragma: no cover - defensive
            return None

        return {
            "x": cx - w / 2,
            "y": cy - h / 2,
            "width": max(1.0, w),
            "height": max(1.0, h),
            "cx": cx,
            "cy": cy,
        }