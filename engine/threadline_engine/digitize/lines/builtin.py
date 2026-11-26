"""The four running-stitch styles and four motifs LUDD 1.0 knew, with exactly the needle points
the old `stitches.running()` and `patterns._motif_unit()` made.

Imports from `..stitches` stay inside the function bodies: stitches imports this package.
"""

from __future__ import annotations

import math

from ..paths import cumulative, flatten, resample
from ..patterns import motif_points
from . import MAX_LINE_STITCHES, MOTIF_UNITS, LineStyle, motif_stitches, register, register_motif, sewn_unit


def _line(nodes, params, closed, start):
    """The line resampled to the stitch length, a closed one started where chosen. The flag says
    whether there are enough points for a style to work on (fewer than two are sewn as they are)."""
    from ..stitches import _ring_from, run_points

    pts = run_points(nodes, params.stitch_mm, closed)
    if len(pts) < 2:
        return pts, False
    if closed and start is not None:
        pts = _ring_from(pts, start)  # a border starts (and ends) exactly where chosen
    return pts, True


def _single(nodes, params, closed=False, start=None):
    return _line(nodes, params, closed, start)[0]


def _triple(nodes, params, closed=False, start=None):
    pts, ok = _line(nodes, params, closed, start)
    if not ok:
        return pts
    return pts + pts[-2::-1] + pts[1:]  # the whole line three times


def _bean(nodes, params, closed=False, start=None):
    pts, ok = _line(nodes, params, closed, start)
    if not ok:
        return pts
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        out += [b, a, b]  # each stitch three times
    return out


def _refuse_too_many(nodes, params, closed, unit, stitch: float) -> None:
    """Refused before any of it is worked out: a very busy motif of your own, or a hand-made motif
    file, could otherwise make millions of stitches and freeze LUDD."""
    from ..stitches import DigitizeError

    shape = unit if unit is not None else MOTIF_UNITS.get(params.motif)
    poly, _ = flatten(nodes, closed)
    if closed and poly:
        poly = poly + [poly[0]]
    if shape is None or len(poly) < 2:
        return  # (motif_points refuses an unknown motif itself)
    total = cumulative(poly)[-1]
    repeats = max(1, round(total / params.motif_mm))  # as motif_points lays them
    stitches = motif_stitches(shape, repeats, total / repeats, params.motif_width_mm, stitch)
    if stitches > MAX_LINE_STITCHES:
        raise DigitizeError(f"This line would need about {stitches:,.0f} stitches, far more than any design. "
                            "Make it smaller or less dense.")


def _motif(nodes, params, closed=False, start=None):
    # The motif's corners are the needle points; long sides are split to the stitch length. A motif
    # of your own that the line carries (params.motif_unit) is sewn instead of the named one.
    unit = sewn_unit(params.motif_unit, params.motif_mm, params.motif_width_mm)
    stitch = max(params.stitch_mm, 1.0)
    _refuse_too_many(nodes, params, closed, unit, stitch)
    pts = motif_points(nodes, params.motif, params.motif_mm, params.motif_width_mm, closed, unit=unit)
    return resample(pts, stitch, list(range(len(pts))))


register(LineStyle("single", points=_single))
register(LineStyle("triple", points=_triple))
register(LineStyle("bean", points=_bean))
register(LineStyle("motif", points=_motif))

register_motif("wave", [(i / 8, 0.5 * math.sin(2 * math.pi * i / 8)) for i in range(9)])
register_motif("zigzag", [(0.0, -0.5), (0.5, 0.5), (1.0, -0.5)])
register_motif("scallop", [(i / 8, 0.5 * math.sin(math.pi * i / 8) - 0.25) for i in range(9)])
register_motif("blanket", [(0.0, -0.5), (0.5, -0.5), (0.5, 0.5), (0.5, -0.5), (1.0, -0.5)])
