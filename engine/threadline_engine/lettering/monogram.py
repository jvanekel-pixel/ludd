"""Monograms: a small letter, a big one and a small one."""

from __future__ import annotations

from typing import Any, Callable

from .fonts import LetteringError
from .glyphs import Glyph
from .place import _centre, _move


def smallest_letter(size: float, style: str = "classic") -> float:
    """The height of the monogram's smallest letters (mm), for the small-letter warning."""
    return size * 0.7


def layout(letters: list[str], size: float, spacing: float, glyphs_for: Callable[[str, float], list[Glyph]],
           style: str = "classic") -> list[dict[str, Any]]:
    """The monogram of `letters` (the text without its spaces), centred side to side. `style`:
    "classic" (small, big, small) is the only one until P5-D2."""
    objects: list[dict[str, Any]] = []
    letters = letters[:3]
    if len(letters) != 3:
        raise LetteringError("A monogram needs three letters, e.g. first, last and middle initials")
    sizes = [size * 0.7, size, size * 0.7]
    parts = []
    for c, s in zip(letters, sizes):
        got = glyphs_for(c, s)
        parts.append(got[0] if got else Glyph([], 0.0))
    gap = size * 0.12
    widths = [p.advance - spacing for p in parts]
    total = sum(widths) + 2 * gap
    x = -total / 2
    for p, w, s in zip(parts, widths, sizes):
        # Vertically centre each letter on the big letter's middle.
        dy = s / 2 - size / 2
        objects += [_move(o, lambda a, b, x0=x, dy=dy: (a + x0, b + size / 2 + dy)) for o in p.objects]
        x += w + gap
    return _centre(objects, vertical=False)
