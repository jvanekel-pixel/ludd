"""Monograms of one, two or three letters (P5-D2). Styles: classic (small, big, small), block
(all the same size) and stacked (two small letters one above the other, then a big one)."""

from __future__ import annotations

from typing import Any, Callable

from ..digitize import stitches as dz
from .fonts import LetteringError
from .glyphs import Glyph
from .place import _centre, _move

STYLES = ("classic", "block", "stacked")
SIDE_LETTER = 0.7  # classic: the small letters, times the letter height
LETTER_GAP = 0.12  # between letters side by side, times the letter height
STACK_GAP = 0.06  # between two stacked letters: with it they're as tall as the big one
STACKED_LETTER = (1 - STACK_GAP) / 2


def _sizes(count: int, size: float, style: str) -> list[float]:
    """Each letter's height (mm)."""
    if style == "block":
        return [size] * count
    if style == "stacked":
        return [size * STACKED_LETTER] * (count - 1) + [size]
    # Classic: small, big, small. Two letters are the small one, then the big one; one is big.
    return [size] if count == 1 else [size * SIDE_LETTER, size, size * SIDE_LETTER][:count]


def smallest_letter(size: float, style: str = "classic", count: int = 3) -> float:
    """The height of the smallest letter (mm) in a monogram of `count` letters, for the
    small-letter warning (one letter alone is full size)."""
    return min(_sizes(min(max(count, 1), 3), size, style))


def layout(letters: list[str], size: float, spacing: float, glyphs_for: Callable[[str, float], list[Glyph]],
           style: str = "classic") -> list[dict[str, Any]]:
    """The monogram of `letters` (the text without its spaces), centred side to side, each
    letter's middle on the big letter's middle."""
    if style not in STYLES:
        raise LetteringError(f"This LUDD doesn't have the monogram style “{style}”")
    if not 1 <= len(letters) <= 3:
        raise LetteringError("A monogram takes one, two or three letters, like A, AB or ABC. Delete the extra "
                             "letters, or untick Monogram.")
    sizes = _sizes(len(letters), size, style)
    parts = []
    for c, s in zip(letters, sizes):
        got = glyphs_for(c, s)
        parts.append(got[0] if got else Glyph([], 0.0))
    if style == "stacked" and len(parts) > 1:
        return _centre(_stacked(parts, sizes, size), vertical=False)
    objects: list[dict[str, Any]] = []
    gap = size * LETTER_GAP
    widths = [p.advance - spacing for p in parts]
    total = sum(widths) + (len(parts) - 1) * gap
    x = -total / 2
    for p, w, s in zip(parts, widths, sizes):
        # Vertically centre each letter on the big letter's middle.
        dy = s / 2 - size / 2
        objects += [_move(o, lambda a, b, x0=x, dy=dy: (a + x0, b + size / 2 + dy)) for o in p.objects]
        x += w + gap
    return _centre(objects, vertical=False)


def _box(part: Glyph) -> tuple[float, float, float, float] | None:
    pts = [p for o in part.objects for p in dz.geometry_points(o)]
    return dz.bounds(pts) if pts else None


def _stacked(parts: list[Glyph], sizes: list[float], size: float) -> list[dict[str, Any]]:
    """The small letters in a column, one above the other (one alone sits in the middle), then
    the big letter beside them. They're lined up by their shapes, not their advance widths."""
    small, big = parts[:-1], parts[-1]
    height = sizes[0]
    # Each small letter's baseline: the top one's cap at the big letter's top, the bottom one on
    # its baseline.
    baselines = [height / 2] if len(small) == 1 else [-size / 2 + height, size / 2]
    boxes = [_box(p) for p in small]
    column = max((x1 - x0 for x0, _, x1, _ in filter(None, boxes)), default=0.0)
    objects: list[dict[str, Any]] = []
    for part, box, base in zip(small, boxes, baselines):
        if box:
            dx = column / 2 - (box[0] + box[2]) / 2
            objects += [_move(o, lambda a, b, dx=dx, base=base: (a + dx, b + base)) for o in part.objects]
    box = _box(big)
    if box:
        dx = column + size * LETTER_GAP - box[0]
        objects += [_move(o, lambda a, b, dx=dx: (a + dx, b + size / 2)) for o in big.objects]
    return objects
