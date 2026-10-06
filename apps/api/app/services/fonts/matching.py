from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.services.fonts.registry import (
    WEIGHT_BOLD,
    WEIGHT_REGULAR,
    FontRegistry,
    default_font_registry,
)
from app.services.image_utils import LoadedImage
from app.services.text_detector import DetectedText


@dataclass(frozen=True)
class FontMatch:
    """A ranked candidate font for a detected text crop."""

    family: str
    category: str
    weight: int
    style: str
    score: float
    note: str

    @property
    def note_short(self) -> str:
        return _font_note(self.family, self.weight, self.score)


def _font_note(family: str, weight: int, score: float) -> str:
    weight_label = " bold" if weight == WEIGHT_BOLD else ""
    return f"font '{family}'{weight_label} matched (score {score:.2f})"


class FontMatcher:
    """Matches a detected text crop against the font database by comparing
    rendered glyph silhouettes (template matching on ink masks).

    This is the OCR-fallback fidelity improvement: when OCR supplies text
    content, we render that content in each candidate family at the detected
    size and keep the family whose ink silhouette overlaps the crop best.
    Weight (regular vs bold) is refined for the winning family.
    """

    def __init__(
        self,
        registry: FontRegistry | None = None,
        *,
        canvas_height: int = 48,
        min_score: float = 0.62,
        max_results: int = 5,
        size_factors: tuple[float, ...] = (0.7, 0.85, 1.0, 1.2),
    ) -> None:
        self.registry = registry or default_font_registry()
        self.canvas_height = canvas_height
        self.min_score = min_score
        self.max_results = max_results
        self.size_factors = size_factors

    # -- public API ------------------------------------------------------------
    def match(self, crop: np.ndarray, content: str) -> list[FontMatch]:
        """Rank candidate fonts for `content` rendered against `crop` (RGBA).

        Each family is scored against both its regular and bold rendering (when
        a bold file exists); the best of the two becomes the family's score and
        also determines the inferred weight.
        """
        content = (content or "").strip()
        if not content:
            return []
        ink = self._ink_mask(crop)
        ink_tight = self._tight(ink)
        if ink_tight is None:
            return []
        target = self._canvas_dims(ink_tight, self.canvas_height)
        ink_small = _resize(ink_tight, target)

        results: list[FontMatch] = []
        for family in self.registry.available_families():
            score, weight = self._family_best(
                family, content, ink_small, ink_tight.shape[0], target
            )
            if score >= self.min_score:
                results.append(
                    FontMatch(
                        family=family.name,
                        category=family.category,
                        weight=weight,
                        style="normal",
                        score=score,
                        note=_font_note(family.name, weight, score),
                    )
                )
        results.sort(key=lambda m: m.score, reverse=True)
        return results[: self.max_results]

    def best(self, crop: np.ndarray, content: str) -> FontMatch | None:
        matches = self.match(crop, content)
        return matches[0] if matches else None

    def enhance(self, image: LoadedImage, text: DetectedText) -> DetectedText:
        """Fill font fields on `text` when a confident match is available."""
        if text.is_guess or not (text.content or "").strip():
            return text
        x0 = max(0, int(text.x))
        y0 = max(0, int(text.y))
        x1 = min(image.width, int(text.x + text.width))
        y1 = min(image.height, int(text.y + text.height))
        if x1 <= x0 or y1 <= y0:
            return text
        crop = image.rgba[y0:y1, x0:x1]
        match = self.best(crop, text.content)
        if match is None or match.score < self.min_score:
            return text
        text.font_family = match.family
        text.font_weight = match.weight
        text.font_style = match.style
        text.font_match_score = match.score
        text.font_note = match.note_short
        return text

    # -- scoring ---------------------------------------------------------------
    def _family_best(
        self,
        family,
        content: str,
        ink_small: np.ndarray,
        ink_height: int,
        target: tuple[int, int],
    ) -> tuple[float, int]:
        """Best silhouette IoU for `family`, choosing weight from regular/bold."""
        base_size = max(8, int(round(ink_height / 0.74)))
        best_score = 0.0
        best_weight = WEIGHT_REGULAR

        for weight, renderer in (
            (WEIGHT_REGULAR, self._render),
            (WEIGHT_BOLD, self._render_weight),
        ):
            if weight == WEIGHT_BOLD and WEIGHT_BOLD not in family.files:
                continue
            for factor in self.size_factors:
                rendered = renderer(family, content, int(base_size * factor))
                if rendered is None:
                    continue
                score = _iou(ink_small, _resize(rendered, target))
                if score > best_score:
                    best_score, best_weight = score, weight
        return best_score, best_weight

    # -- ink mask helpers ------------------------------------------------------
    def _ink_mask(self, crop: np.ndarray) -> np.ndarray:
        """Otsu binarization of a text crop into an ink=1 mask.

        The polarity is chosen so the *smaller* connected region is ink, which
        is correct for text on any background (light-on-dark included).
        """
        if crop.ndim == 3:
            gray = cv2.cvtColor(crop, cv2.COLOR_RGBA2GRAY)
        else:
            gray = crop
        if gray.size == 0:
            return np.zeros((0, 0), dtype=bool)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        mask = binary > 127
        if mask.sum() > (mask.size / 2):
            mask = ~mask
        return mask

    @staticmethod
    def _tight(mask: np.ndarray) -> np.ndarray | None:
        ys, xs = np.nonzero(mask)
        if len(ys) < 3:
            return None
        return mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]

    @staticmethod
    def _canvas_dims(tight: np.ndarray, height: int) -> tuple[int, int]:
        h, w = tight.shape
        width = min(224, max(8, int(round(w * height / max(1, h)))))
        return width, height

    def _render(
        self, family, content: str, size: int
    ) -> np.ndarray[bool, np.dtype] | None:
        """Render `content` in `family` at `size` and return its tight ink mask."""
        path = family.files.get(WEIGHT_REGULAR) or next(iter(family.files.values()))
        try:
            font = ImageFont.truetype(path, max(8, int(size)))
        except (OSError, ValueError):
            return None
        img = Image.new("L", (max(64, int(size * len(content) + size * 2)), size * 3), 0)
        draw = ImageDraw.Draw(img)
        draw.text((size, size), content, font=font, fill=255)
        bbox = img.getbbox()
        if not bbox:
            return None
        tight = np.array(img.crop(bbox), dtype=np.uint8) > 127
        return self._tight(tight)

    def _render_weight(self, family, content: str, size: int):
        try:
            font = ImageFont.truetype(family.files[WEIGHT_BOLD], max(8, int(size)))
        except (OSError, ValueError):
            return None
        img = Image.new("L", (max(64, int(size * len(content) + size * 2)), size * 3), 0)
        ImageDraw.Draw(img).text((size, size), content, font=font, fill=255)
        bbox = img.getbbox()
        if not bbox:
            return None
        return self._tight(np.array(img.crop(bbox), dtype=np.uint8) > 127)


def _resize(mask: np.ndarray, target: tuple[int, int]) -> np.ndarray:
    """Resize a boolean ink mask to `target` (width, height)."""
    width, height = target
    img = mask.astype(np.uint8) * 255
    resized = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)
    return resized > 127


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else 0.0