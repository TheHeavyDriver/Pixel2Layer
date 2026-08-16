from __future__ import annotations

from app.schemas.scene_graph import SceneGraphElement


class ScoringCategory:
    TEXT = "text"
    SHAPES = "shapes"
    COLORS = "colors"
    IMAGES = "images"
    VECTORS = "vector"


def _score_text(elem: SceneGraphElement) -> float:
    # Editable text reconstructed from OCR with a matched font scores well; low
    # confidence if it had to fall back to guessing the font.
    penalty = 0.0
    if elem.confidence_note and "font" in elem.confidence_note.lower():
        penalty = 0.15
    if not elem.content.strip():
        penalty = 0.4
    return max(0.0, min(1.0, elem.confidence - penalty))


def _score_shape(elem: SceneGraphElement) -> float:
    # Geometric shapes are exactly reconstructable when contours are clean.
    return max(0.0, min(1.0, elem.confidence))


def compute_overall(graph_layers: list[SceneGraphElement]) -> dict[str, float]:
    """Aggregate per-category confidence and an overall weighted score."""
    categories: dict[str, list[float]] = {}

    for elem in graph_layers:
        if elem.type == "text":
            cat = ScoringCategory.TEXT
            value = _score_text(elem)
        elif elem.type == "image":
            cat = ScoringCategory.IMAGES
            value = elem.confidence
        elif elem.type == "vector":
            cat = ScoringCategory.VECTORS
            value = elem.confidence
        else:
            cat = ScoringCategory.SHAPES
            value = _score_shape(elem)
        categories.setdefault(cat, []).append(value)

    per_category: dict[str, float] = {}
    values: list[float] = []
    for cat, scores in categories.items():
        mean = sum(scores) / len(scores)
        per_category[cat] = round(mean, 4)
        values.extend(scores)

    if not values:
        return {}

    overall = sum(values) / len(values)
    per_category["overall"] = round(overall, 4)
    return per_category