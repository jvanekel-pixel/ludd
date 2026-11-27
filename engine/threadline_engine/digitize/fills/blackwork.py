"""Blackwork fill: a lattice of lines over the shape (fills/lattice.py: diamonds, a grid, honeycomb
or a grid with both diagonals), every stretch sewn twice, out and back, as in hand blackwork.

The lattice is laid from the middle of the shape, worked out in the shape's own frame
(motif.own_frame), so a moved or copied shape sews the same stitches. A simple shape's lattice
hangs together, so it sews as one path with no jump; pieces apart are joined inside the shape.

Written from first principles for LUDD. Coordinates are mm. Imports from `..stitches` stay inside
the function bodies: stitches imports this package.
"""

from __future__ import annotations

import math

from . import FillPattern, Param, register, spiral
from .lattice import clip_segments, double_run_paths, tile_segments
from .motif import own_frame, place


def _stitch(params) -> float:
    from ..stitches import LONG_STITCH_MM

    return min(max(params.stitch_mm, 1.0), LONG_STITCH_MM)


def _line_kinds(lattice: str, cell: float) -> list[tuple[float, float]]:
    """Each kind of line in a lattice, as (mm of line for each mm² of fabric, the length of a
    stretch from one crossing to the next)."""
    if lattice == "honeycomb":
        return [(2 / cell, cell / math.sqrt(3))]
    square = [(2 / cell, cell)]  # the grid, and the diamonds (the grid turned)
    if lattice == "crossed":
        return [*square, (2 * math.sqrt(2) / cell, cell / math.sqrt(2))]
    return square


def estimate(poly, params) -> float:
    """About how many stitches the fill takes: every stretch in whole stitches, sewn twice, and a
    little more where the lattice meets the edge."""
    cell, stitch = params.value("blackwork_mm"), _stitch(params)
    per_mm2 = sum(2 * line / length * max(1, math.ceil(length / stitch - 1e-9))
                  for line, length in _line_kinds(params.blackwork_lattice, cell))
    return poly.area * per_mm2 + 2 * poly.length / cell


def _paths(poly, params, pos):
    """The lattice over one piece of a fill: one path for each of its connected pieces."""
    from ..stitches import MAX_STITCHES, DigitizeError

    # Refused before the lattice is laid out: small cells over a big shape make far more stitches
    # than the area alone suggests (the diagonals of "crossed" most of all).
    about = estimate(poly, params)
    if about > MAX_STITCHES:
        raise DigitizeError(f"This fill would need about {about:,.0f} stitches, far more than any design. "
                            "Make it smaller, or use bigger cells.")
    local, origin = own_frame(poly)
    cell = params.value("blackwork_mm")
    segments = clip_segments(tile_segments(params.blackwork_lattice, cell, local.bounds), local)
    # With no start chosen, from the top left (not the outline's first point, which can come out of
    # the geometry library in another place on another computer).
    here = (pos[0] - origin[0], pos[1] - origin[1]) if params.start_mm is not None else spiral.FAR
    pieces = double_run_paths(segments, _stitch(params), here)
    return [place(p, origin) for p in _joined(pieces, local)], []


def _joined(pieces: list, local) -> list:
    """Pieces apart (a thin tip's cell, say) joined as the fill would join them (_sew_paths), but in
    the shape's own frame, so that a moved shape travels the same way too. Only where no way
    inside the shape is found are they left apart (the fill then jumps)."""
    from ..stitches import STITCH, Zone, travel

    if len(pieces) < 2:
        return pieces
    zone = Zone(local.buffer(0.3))  # as far outside the shape as the fill lets any travel go
    joined = [list(pieces[0])]
    for piece in pieces[1:]:
        way = travel(joined[-1][-1], piece[0], zone)
        if all(r[2] == STITCH for r in way):
            joined[-1] += [(x, y) for x, y, _ in way] + piece
        else:
            joined.append(list(piece))
    return joined


register(FillPattern("blackwork", "open", params={"blackwork_mm": Param(5.0, 3.0, 12.0, "Cell size")}, paths=_paths,
                     step_mm2=lambda p: p.value("blackwork_mm") * p.stitch_mm / 4, auto_underlay=lambda level: []))
