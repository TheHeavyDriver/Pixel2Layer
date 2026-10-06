from __future__ import annotations

import functools
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from PIL import ImageFont

FontCategory = Literal["sans", "serif", "mono", "display"]

# Generic CSS families each category degrades to when a match is uncertain.
GENERIC_FALLBACK: dict[FontCategory, str] = {
    "sans": "sans-serif",
    "serif": "serif",
    "mono": "monospace",
    "display": "sans-serif",
}

# Preferred weights the matcher reasons about (regular vs bold).
WEIGHT_REGULAR = 400
WEIGHT_BOLD = 700


@dataclass(frozen=True)
class FontFamily:
    """A known font family with the font files it resolved to.

    `files` maps a CSS weight (400/700) to an absolute TTF/OTF path.
    """

    name: str
    category: FontCategory
    matches: tuple[str, ...]
    files: dict[int, str] = field(default_factory=dict)

    @property
    def generic(self) -> str:
        return GENERIC_FALLBACK[self.category]

    def has_weight(self, weight: int) -> bool:
        return weight in self.files or 400 in self.files


def _default_families() -> list[FontFamily]:
    """Curated open-license font database.

    Entry order is relevance order and is preserved when matching. `matches`
    names are looked up (case-insensitively) against fonts installed on the
    host; entries that resolve to nothing are simply skipped at runtime, so the
    database degrades gracefully on machines with fewer fonts.
    """
    raw = [
        # -- sans-serif ---------------------------------------------------------
        ("DejaVu Sans", "sans", ("DejaVu Sans",)),
        ("Liberation Sans", "sans", ("Liberation Sans",)),
        ("Open Sans", "sans", ("Open Sans",)),
        ("Fira Sans", "sans", ("Fira Sans",)),
        ("Ubuntu", "sans", ("Ubuntu",)),
        ("Noto Sans", "sans", ("Noto Sans",)),
        ("Roboto", "sans", ("Roboto",)),
        ("Lato", "sans", ("Lato",)),
        ("Montserrat", "sans", ("Montserrat",)),
        ("Source Sans 3", "sans", ("Source Sans", "Source Sans 3")),
        ("Inter", "sans", ("Inter",)),
        ("Nunito", "sans", ("Nunito",)),
        ("Work Sans", "sans", ("Work Sans",)),
        ("Carlito", "sans", ("Carlito",)),
        # -- serif ------------------------------------------------------------
        ("DejaVu Serif", "serif", ("DejaVu Serif",)),
        ("Liberation Serif", "serif", ("Liberation Serif",)),
        ("Noto Serif", "serif", ("Noto Serif",)),
        ("Roboto Slab", "serif", ("Roboto Slab",)),
        ("Merriweather", "serif", ("Merriweather",)),
        ("Lora", "serif", ("Lora",)),
        ("Playfair Display", "serif", ("Playfair Display",)),
        ("Gentium", "serif", ("Gentium", "Gentium Book")),
        # -- monospace --------------------------------------------------------
        ("DejaVu Sans Mono", "mono", ("DejaVu Sans Mono",)),
        ("Liberation Mono", "mono", ("Liberation Mono",)),
        ("Fira Mono", "mono", ("Fira Mono",)),
        ("Fira Code", "mono", ("Fira Code",)),
        ("Noto Sans Mono", "mono", ("Noto Sans Mono",)),
        ("Ubuntu Mono", "mono", ("Ubuntu Mono",)),
        ("Roboto Mono", "mono", ("Roboto Mono",)),
        ("JetBrains Mono", "mono", ("JetBrains Mono",)),
        ("Source Code Pro", "mono", ("Source Code Pro",)),
        # -- display ----------------------------------------------------------
        ("Oswald", "display", ("Oswald",)),
        ("Bebas Neue", "display", ("Bebas Neue",)),
        ("Anton", "display", ("Anton",)),
        ("Poppins", "display", ("Poppins",)),
        ("Bitter", "display", ("Bitter",)),
        ("Archivo Black", "display", ("Archivo Black",)),
    ]
    return [FontFamily(name, category, aliases) for name, category, aliases in raw]


def _discover_system_fonts() -> dict[str, list[tuple[str, str]]]:
    """Index installed fonts via fontconfig: family(casefold) -> [(path, style)].

    Parses `fc-list` lines of the form `path: Family,Fallback:style=Regular,Book`
    where family/fallback names and their styles are 1:1 comma-paired records.
    """
    index: dict[str, list[tuple[str, str]]] = {}
    try:
        raw = subprocess.run(
            ["fc-list"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return index
    for line in raw.splitlines():
        parts = line.split(":")
        if len(parts) < 3:
            continue
        names = [n.strip() for n in parts[1].split(",") if n.strip()]
        style_part = parts[2].split("=", 1)[1] if "=" in parts[2] else parts[2]
        styles = [s.strip() for s in style_part.split(",")]
        for name, style in zip(names, styles, strict=False):
            if name:
                index.setdefault(name.casefold(), []).append((parts[0].strip(), style))
    return index


class FontRegistry:
    """Expanded, curated font database resolvable to actual font files.

    Resolution order: system fonts discovered through fontconfig, then a
    bundled-font directory (optional, for reproducible deployments). Only
    families that actually resolve are retained in the active database.
    """

    def __init__(
        self,
        families: list[FontFamily] | None = None,
        bundled_dir: str | Path | None = None,
    ) -> None:
        self.bundled_dir = Path(bundled_dir) if bundled_dir else None
        self._system = _discover_system_fonts()
        self._by_name: dict[str, FontFamily] = {}
        for family in families if families is not None else _default_families():
            resolved = self._resolve(family)
            if resolved.files:
                self._by_name[resolved.name] = resolved

    # -- database API -----------------------------------------------------------
    @property
    def size(self) -> int:
        return len(self._by_name)

    def available_families(self) -> list[FontFamily]:
        """Families usable for matching, in database (relevance) order."""
        return list(self._by_name.values())

    def categories(self) -> list[FontCategory]:
        return sorted({f.category for f in self._by_name.values()})

    def get(self, name: str, *, case_insensitive: bool = True) -> FontFamily | None:
        if name in self._by_name:
            return self._by_name[name]
        if case_insensitive:
            target = name.casefold()
            for key, family in self._by_name.items():
                if key.casefold() == target:
                    return family
        return None

    def resolve(self, name: str, weight: int = WEIGHT_REGULAR) -> str | None:
        family = self.get(name)
        if family is None:
            return None
        return (
            family.files.get(weight)
            or family.files.get(WEIGHT_REGULAR)
            or next(iter(family.files.values()))
        )

    def truetype(self, name: str, weight: int, size: int):
        """Load a font at `size` for PIL; None when unresolvable or unloadable."""
        path = self.resolve(name, weight)
        if path is None:
            return None
        try:
            return ImageFont.truetype(path, int(size))
        except (OSError, ValueError):
            return None

    # -- resolution -------------------------------------------------------------
    def _resolve(self, family: FontFamily) -> FontFamily:
        files: dict[int, str] = {}
        regular = self._pick_file(family.matches, prefer_bold=False)
        bold = self._pick_file(family.matches, prefer_bold=True)
        if regular:
            files[WEIGHT_REGULAR] = regular
        if bold:
            files[WEIGHT_BOLD] = bold
        if not files and self.bundled_dir is not None:
            files = _resolve_bundled(self.bundled_dir, family.name, family.matches)
        return FontFamily(
            name=family.name,
            category=family.category,
            matches=family.matches,
            files=files,
        )

    def _pick_file(self, aliases: tuple[str, ...], *, prefer_bold: bool) -> str | None:
        candidates: list[tuple[str, str, str]] = []
        for alias in aliases:
            key = alias.casefold()
            for name, entries in self._system.items():
                if key == name or key in name.split():
                    candidates.extend((name, path, style) for path, style in entries)
        if not candidates:
            return None
        best = max(candidates, key=lambda c: self._pick_score(c, aliases, prefer_bold))
        return best[1]

    @staticmethod
    def _pick_score(
        candidate: tuple[str, str, str], aliases: tuple[str, ...], prefer_bold: bool
    ) -> int:
        name, _path, style = candidate
        style_l = style.casefold()
        score = 8 if any(name.casefold() == alias.casefold() for alias in aliases) else 0
        if prefer_bold:
            if "bold" in style_l:
                score += 6
            elif any(t in style_l for t in ("black", "heavy", "extra", "demi", "semi")):
                score += 5
            else:
                score -= 3
        else:
            if any(t in style_l for t in ("regular", "book", "normal", "roman")):
                score += 6
            elif "medium" in style_l:
                score += 4
            elif "light" in style_l:
                score += 2
            elif any(t in style_l for t in ("bold", "black", "heavy", "demi", "semi")):
                score -= 4
        for weaken in ("condensed", "oblique", "italic", "narrow", "expanded"):
            if weaken in style_l:
                score -= 2
        return score


def _resolve_bundled(dir: Path, name: str, matches: tuple[str, ...]) -> dict[int, str]:
    files: dict[int, str] = {}
    stem = name.replace(" ", "")
    for weight, token in ((WEIGHT_REGULAR, "Regular"), (WEIGHT_BOLD, "Bold")):
        for ext in ("ttf", "otf"):
            path = dir / f"{stem}-{token}.{ext}"
            if path.is_file():
                files[weight] = str(path)
                break
    _ = matches
    return files


@functools.lru_cache(maxsize=1)
def default_font_registry() -> FontRegistry:
    """Process-wide shared registry (fc-list discovery is cached)."""
    return FontRegistry()