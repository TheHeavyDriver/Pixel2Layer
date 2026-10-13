from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import cv2
import numpy as np

from app.services.image_utils import LoadedImage, hexify


@dataclass
class DetectedText:
    content: str
    x: float
    y: float
    width: float
    height: float
    rotation: float
    confidence: float
    # Visual attributes inferred from the crop.
    font_color: str
    background_color: str | None = None
    font_size_estimate: float = 0.0
    is_guess: bool = False  # True when content couldn't be read (region only)
    # Font match results (filled by the FontMatcher, never by detection).
    font_family: str = "sans-serif"
    font_weight: int = 400
    font_style: str = "normal"
    font_match_score: float | None = None
    font_note: str | None = None


class OCRBackend(ABC):
    """Interface for pluggable OCR engines (PaddleOCR, Tesseract, EasyOCR)."""

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    async def recognize(self, image: LoadedImage) -> list[DetectedText]: ...


class VisionTextDetector:
    """Detects text *regions* via morphology without an OCR engine.

    Content stays unknown (is_guess=True) unless an OCRBackend is supplied;
    that is the safe v0.2 fallback that the PRD's vector-outline path uses.

    Every morphology hit is validated for glyph structure first — dense
    textures, stripes, noise, flat shapes and smooth gradients all fail the
    checks, so only text-like regions become layers.
    """

    def __init__(
        self,
        backend: OCRBackend | None = None,
        min_region_area: int = 80,
    ) -> None:
        self.backend = backend
        self.min_region_area = min_region_area

    async def detect(self, image: LoadedImage) -> list[DetectedText]:
        if self.backend is not None and self.backend.available():
            regions = await self.backend.recognize(image)
            return regions

        gray = cv2.cvtColor(image.bgr, cv2.COLOR_BGR2GRAY)
        # Morphological gradient highlights dense text blocks.
        grad = cv2.morphologyEx(
            gray, cv2.MORPH_GRADIENT,
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        )
        _, binary = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 5))
        closed = cv2.dilate(binary, kernel, iterations=2)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        results: list[DetectedText] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w * h < self.min_region_area:
                continue
            if w < 12 or h < 6:  # too thin to be text
                continue
            validated = self._text_like_bbox(gray, x, y, w, h)
            if validated is None:
                continue  # texture / shape / noise that merely looks dense
            x, y, w, h = validated
            crop = image.rgba[y : y + h, x : x + w]
            font_color = self._dominant_ink(crop)
            results.append(
                DetectedText(
                    content="",
                    x=float(x),
                    y=float(y),
                    width=float(w),
                    height=float(h),
                    rotation=0.0,
                    confidence=0.55,  # region geometry only
                    font_color=font_color,
                    font_size_estimate=float(h),
                    is_guess=True,
                )
            )
        return results

    def _text_like_bbox(
        self, gray: np.ndarray, x: int, y: int, w: int, h: int
    ) -> tuple[int, int, int, int] | None:
        """Validate glyph structure and return the tightened bbox (or None).

        Two ink maps are tried: strokes deviating from the *local* background
        (best for normal text over texture — noise never registers as ink) and
        strokes deviating from the region *border* color (best for thick
        display glyphs, whose interiors swallow a local median window). A
        region is accepted only when the glyph-structure checks pass on one of
        them: moderate ink coverage, substantially-filled ink columns, clean
        inter-character gaps, strokes spanning the line height, a varying row
        profile, and no long empty horizontal band. Solid shapes, stripes,
        grids, noise, textures and gradients fail both.
        """
        patch = gray[y : y + h, x : x + w]
        if patch.size == 0 or min(patch.shape[:2]) < 3:
            return None
        for ink_bool, min_row_var in (
            (self._local_stroke_mask(patch), 0.12),
            (self._border_stroke_mask(patch), 0.20),
        ):
            validated = self._validate_ink(ink_bool, x, y, w, h, min_row_var)
            if validated is not None:
                return validated
        return None

    def _local_stroke_mask(self, patch: np.ndarray) -> np.ndarray:
        """Strokes deviating from the local median background (Otsu)."""
        smooth = cv2.GaussianBlur(patch, (3, 3), 0)
        k = min(21, (min(patch.shape[:2]) // 2) * 2 - 1)
        if k < 3:
            return np.zeros(patch.shape, dtype=bool)
        local_bg = cv2.medianBlur(smooth, k)
        _, ink = cv2.threshold(
            cv2.absdiff(smooth, local_bg), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        return ink > 0

    def _border_stroke_mask(self, patch: np.ndarray) -> np.ndarray:
        """Strokes deviating from the region-border color (Otsu).

        The morphology box is dilated past the glyphs, so its border is
        background by construction. Unlike the local median, a single global
        reference never swallows thick display-glyph interiors.
        """
        b = max(2, min(patch.shape[:2]) // 25)
        border = np.concatenate(
            (
                patch[:b].ravel(),
                patch[-b:].ravel(),
                patch[:, :b].ravel(),
                patch[:, -b:].ravel(),
            )
        )
        bg = float(np.median(border))
        dev = np.abs(patch.astype(np.int16) - int(bg)).astype(np.uint8)
        _, ink = cv2.threshold(dev, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return ink > 0

    def _validate_ink(
        self, ink_bool: np.ndarray, x: int, y: int, w: int, h: int, min_row_var: float
    ) -> tuple[int, int, int, int] | None:
        """Run glyph-structure checks on an ink map; return the tightened bbox.

        The bbox is first trimmed to rows/cols that actually carry ink so
        regions inflated by background texture validate against the glyphs
        only.
        """
        # Trim to rows/cols carrying meaningful ink (>=2% of the busiest).
        row_ink = ink_bool.sum(axis=1)
        col_ink = ink_bool.sum(axis=0)
        if row_ink.max() == 0 or col_ink.max() == 0:
            return None
        rows = np.flatnonzero(row_ink >= max(1, 0.02 * int(row_ink.max())))
        cols = np.flatnonzero(col_ink >= max(1, 0.02 * int(col_ink.max())))
        tx, ty = x + int(cols[0]), y + int(rows[0])
        tw, th = int(cols[-1] - cols[0] + 1), int(rows[-1] - rows[0] + 1)
        if tw < 12 or th < 6:
            return None
        sub = ink_bool[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1]
        sub_h = sub.shape[0]

        density = float(sub.mean())
        if not 0.025 <= density <= 0.60:
            return None  # too sparse (edges of a solid) or too busy (noise)

        # Ink columns must be substantially filled: glyph stems span the line
        # height, while the mere outline of a circle/rectangle/texture does not.
        sub_col_ink = sub.sum(axis=0)
        ink_cols = sub_col_ink[sub_col_ink > 0]
        if ink_cols.size == 0 or float(ink_cols.mean() / sub_h) < 0.15:
            return None

        if int((sub_col_ink == 0).sum()) < 2:
            return None  # no clean gaps between characters

        if float((sub.sum(axis=1) > 0).mean()) < 0.4:
            return None  # strokes do not fill the line height

        # Glyph rows vary in ink load (crossbars, stems, letter gaps); the
        # near-constant-per-row profile of a ring/ellipse outline or uniform
        # bar field is structure-free. The border-referenced map needs the
        # stricter bar: grid/ring patterns profile at ~0.15-0.18 there while
        # real display text stays at 0.21+.
        sub_rows = sub.sum(axis=1).astype(np.float64)
        row_variation = float(np.std(sub_rows) / max(1.0, sub_rows.mean()))
        if row_variation < min_row_var:
            return None

        # Long horizontal voids mean stacked blocks (grid/brick textures),
        # not a text line; real line gaps stay under ~12px inside a region.
        zero_rows = (sub.sum(axis=1) == 0).astype(np.int8)
        longest = current = 0
        for flag_row in zero_rows:
            current = current + 1 if flag_row else 0
            longest = max(longest, current)
        if longest > 12:
            return None

        return tx, ty, tw, th

    def _dominant_ink(self, crop: np.ndarray) -> str:
        """Dominant *color* of the stroke pixels, honoring light-on-dark text.

        Strokes come from the validator's two ink maps: their consensus when
        it covers a real share of the crop, otherwise the border-referenced
        map (reliable on thick glyphs, where a local median window flips onto
        the strokes themselves). Correct even when glyphs fill most of the
        crop, where a global median would mistake ink for the background.
        """
        if crop.size == 0:
            return "#000000"
        gray = cv2.cvtColor(crop, cv2.COLOR_RGBA2GRAY)
        local_mask = (
            self._local_stroke_mask(gray) if min(gray.shape[:2]) >= 5 else None
        )
        border_mask = self._border_stroke_mask(gray) if gray.size >= 64 else None
        ink_mask = np.zeros(gray.shape, dtype=bool)
        if local_mask is not None and border_mask is not None:
            # Both maps contain the strokes (that is how the region was
            # validated), while their false positives — background patches a
            # flipped local window, border strips crossed by glyphs — rarely
            # overlap. The consensus isolates the actual strokes.
            consensus = local_mask & border_mask
            if int(consensus.sum()) >= max(8, int(0.02 * gray.size)):
                ink_mask = consensus
        if int(ink_mask.sum()) < 8:
            # Thin consensus: thick glyphs made the local window flip onto
            # the glyphs, where the border reference stays reliable.
            candidates = [border_mask, local_mask]
            ink_mask = next(
                (m for m in candidates if m is not None and int(m.sum()) >= 8),
                np.zeros(gray.shape, bool),
            )
        if int(ink_mask.sum()) < 8 and int((gray < 200).sum()) >= 8:
            ink_mask = gray < 200  # fall back to dark-on-light assumption
        if not ink_mask.any():
            color = np.median(crop[..., :3].reshape(-1, 3), axis=0)
        else:
            # Keep the strongest-deviation half of the strokes: antialias
            # pixels would otherwise drag the median toward the background.
            reference = float(np.median(gray))
            deviation = np.abs(gray.astype(np.int32) - int(reference))
            cutoff = float(np.median(deviation[ink_mask]))
            strong = ink_mask & (deviation >= cutoff)
            selection = strong if int(strong.sum()) >= 8 else ink_mask
            color = np.median(crop[..., :3][selection], axis=0)
        return hexify(tuple(int(v) for v in color))