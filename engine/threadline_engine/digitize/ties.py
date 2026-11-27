"""Lock stitches (ties) in three shapes, chosen per shape (params["tie_style"]), at its start and
end:

- standard: the ties LUDD has always sewn (stitches.tie_in and tie_off), a little way toward the
  next stitch and back;
- triangle: a small triangle, 0.6 mm a side, which holds better on knits and slippery thread;
- backtack: back and forth twice over up to 1 mm of the first stitch, the strongest.

At the start the lock is sewn toward the second stitch and at the end, mirrored, toward the one
before; at the end it still goes before a trailing trim or jump. No stitch of a lock is shorter
than a stitch. On a fill, a triangle turns to the side that keeps it within TRIANGLE_OUT_MM of the
outline, and where neither side does, that end gets the standard tie. Appliques and lettering keep
the standard ties, and so do the pieces joined inside one fill.

Written from first principles for LUDD. Coordinates are mm. Imports from `.stitches` stay inside
the function bodies: stitches imports this module.
"""

from __future__ import annotations

import math
from typing import Any

from shapely.geometry import Point as ShapelyPoint

TIE_STYLES = ("standard", "triangle", "backtack")
TRIANGLE_ALONG_MM = (0.6, 0.3)  # the triangle's corners: this far along toward the next stitch...
TRIANGLE_ACROSS_MM = 0.52  # ...and the second this far to the side
TRIANGLE_OUT_MM = 0.1  # how far outside a fill's outline a triangle may reach
BACKTACK_MM = 1.0
BACKTACK_SHARE = 0.8  # a back-tack reaches no further than this share of the first stitch


def style_of(params: dict[str, Any]) -> str:
    """A shape's lock-stitch shape (missing or empty: standard); an unknown one is refused."""
    from .stitches import DigitizeError

    style = str(params.get("tie_style") or "standard")
    if style not in TIE_STYLES:
        raise DigitizeError(f"Unknown lock stitch style: {style}")
    return style


def _lock(a: tuple, b: tuple, style: str, inside: Any = None) -> list | None:
    """The lock's records after the needle point `a`, toward `b`, ending back at `a`; None for a
    triangle that can't stay by the shape `inside` on either side."""
    from .stitches import MIN_STITCH_MM, STITCH

    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    ux, uy = (dx / length, dy / length) if length > 1e-12 else (1.0, 0.0)
    here = (a[0], a[1], STITCH)

    def at(along: float, across: float = 0.0):
        return a[0] + ux * along - uy * across, a[1] + uy * along + ux * across, STITCH

    if style == "triangle":
        far, near = TRIANGLE_ALONG_MM
        for side in (1.0, -1.0):
            corners = [at(far), at(near, side * TRIANGLE_ACROSS_MM)]
            if inside is None or all(round(inside.distance(ShapelyPoint(c[:2])), 3) <= TRIANGLE_OUT_MM for c in corners):
                return [*corners, here]
        return None
    reach = max(MIN_STITCH_MM, min(BACKTACK_MM, BACKTACK_SHARE * length))
    return [at(reach), here, at(reach), here]


def _locked(recs: list, i: int, others, style: str, inside: Any) -> list | None:
    """`recs` with a lock sewn after record i, toward the first of the records `others` (in order)
    that isn't in the same hole; unchanged if there's none, None if the lock doesn't fit."""
    a = recs[i]
    b = next((recs[k] for k in others if math.dist(a[:2], recs[k][:2]) > 1e-6), None)
    if b is None:
        return recs
    lock = _lock(a, b, style, inside)
    return None if lock is None else recs[: i + 1] + lock + recs[i + 1 :]


def tie_in(recs: list, style: str = "standard", inside: Any = None) -> list:
    """Lock the start: the first stitch locked toward the next one. `inside`: a fill's shape, which
    a triangle stays by."""
    from . import stitches

    if style == "standard":
        return stitches.tie_in(recs)
    sewn = [k for k, r in enumerate(recs) if r[2] == stitches.STITCH]
    if len(sewn) < 2:
        return recs
    locked = _locked(recs, sewn[0], sewn[1:], style, inside)
    return stitches.tie_in(recs) if locked is None else locked


def tie_off(recs: list, style: str = "standard", inside: Any = None) -> list:
    """Lock the end: the last stitch locked toward the one before, before any trailing trim or jump.
    `inside` as for tie_in."""
    from . import stitches

    if style == "standard":
        return stitches.tie_off(recs)
    sewn = [k for k, r in enumerate(recs) if r[2] == stitches.STITCH]
    if len(sewn) < 2:
        return recs
    locked = _locked(recs, sewn[-1], sewn[-2::-1], style, inside)
    return stitches.tie_off(recs) if locked is None else locked
