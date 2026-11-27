"""Lock stitches (ties) in three shapes, chosen per shape (params["tie_style"]), at its start and
end:

- standard: the ties LUDD has always sewn (stitches.tie_in and tie_off), a little way toward the
  next stitch and back;
- triangle: a small triangle, 0.6 mm a side, which holds better on knits and slippery thread;
- backtack: back and forth twice over up to 1 mm of the first stitch, the strongest.

At the start the lock is sewn toward the second stitch and at the end, mirrored, toward the one
before; at the end it still goes before a trailing trim or jump. No stitch of a lock is shorter
than a stitch. Appliques and lettering keep the standard ties, and so do the pieces joined inside
one fill.

Written from first principles for LUDD. Coordinates are mm. Imports from `.stitches` stay inside
the function bodies: stitches imports this module.
"""

from __future__ import annotations

import math
from typing import Any

TIE_STYLES = ("standard", "triangle", "backtack")
TRIANGLE_ALONG_MM = (0.6, 0.3)  # the triangle's corners: this far along toward the next stitch...
TRIANGLE_ACROSS_MM = 0.52  # ...and the second this far to the side
BACKTACK_MM = 1.0
BACKTACK_SHARE = 0.8  # a back-tack reaches no further than this share of the first stitch


def style_of(params: dict[str, Any]) -> str:
    """A shape's lock-stitch shape (missing or empty: standard); an unknown one is refused."""
    from .stitches import DigitizeError

    style = str(params.get("tie_style") or "standard")
    if style not in TIE_STYLES:
        raise DigitizeError(f"Unknown lock stitch style: {style}")
    return style


def _lock(a: tuple, b: tuple, style: str) -> list:
    """The lock's records after the needle point `a`, toward `b`, ending back at `a`."""
    from .stitches import MIN_STITCH_MM, STITCH

    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    ux, uy = (dx / length, dy / length) if length > 1e-12 else (1.0, 0.0)
    here = (a[0], a[1], STITCH)

    def at(along: float, across: float = 0.0):
        return a[0] + ux * along - uy * across, a[1] + uy * along + ux * across, STITCH

    if style == "triangle":
        far, near = TRIANGLE_ALONG_MM
        return [at(far), at(near, TRIANGLE_ACROSS_MM), here]
    reach = max(MIN_STITCH_MM, min(BACKTACK_MM, BACKTACK_SHARE * length))
    return [at(reach), here, at(reach), here]


def _locked(recs: list, i: int, others, style: str) -> list:
    """`recs` with a lock sewn after record i, toward the first of the records `others` (in order)
    that isn't in the same hole; unchanged if there's none."""
    a = recs[i]
    b = next((recs[k] for k in others if math.dist(a[:2], recs[k][:2]) > 1e-6), None)
    if b is None:
        return recs
    return recs[: i + 1] + _lock(a, b, style) + recs[i + 1 :]


def tie_in(recs: list, style: str = "standard") -> list:
    """Lock the start: the first stitch locked toward the next one."""
    from . import stitches

    if style == "standard":
        return stitches.tie_in(recs)
    sewn = [k for k, r in enumerate(recs) if r[2] == stitches.STITCH]
    return _locked(recs, sewn[0], sewn[1:], style) if len(sewn) > 1 else recs


def tie_off(recs: list, style: str = "standard") -> list:
    """Lock the end: the last stitch locked toward the one before, before any trailing trim or jump."""
    from . import stitches

    if style == "standard":
        return stitches.tie_off(recs)
    sewn = [k for k, r in enumerate(recs) if r[2] == stitches.STITCH]
    return _locked(recs, sewn[-1], sewn[-2::-1], style) if len(sewn) > 1 else recs
