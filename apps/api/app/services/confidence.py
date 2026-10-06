from __future__ import annotations

import re

from app.schemas.scene_graph import SceneGraphElement

_FONT_MATCH = re.compile(r"matched \(score ([0-9.]+)\)")


class ScoringCategory:
    TEXT = "text"
    SHAPES = "shapes"
    COLORS = "colors"
    IMAGES = "images"
    VECTORS = "vector"


def _score_text(elem: SceneGraphElement) -> float:
    # Editable text reconstructed from OCR with a confident font match scores
    # best; a guessed/unmatched font or missing content lowers confidence.
    penalty = 0.0
    note = elem.confidence_note or ""
    if not elem.content.strip():
        penalty = 0.4
    else:
        score_match = _FONT_MATCH.search(note)
        if score_match:
            # Confidence in the font grows linearly with the silhouette IoU.
            font_score = float(score_match.group(1))
            penalty = max(0.0, round(0.18 - 0.18 * font_score, 3))
        elif "font" in note.lower():
            penalty = 0.15
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