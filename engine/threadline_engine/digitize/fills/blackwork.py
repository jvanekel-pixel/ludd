"""Blackwork fill: a lattice of lines over the shape (fills/lattice.py: diamonds, a grid, honeycomb
or a grid with both diagonals), every stretch sewn twice, out and back, as in hand blackwork.

The lattice is laid from the middle of the shape, worked out in the shape's own frame
(motif.own_frame), so a moved or copied shape sews the same stitches. A simple shape's lattice
hangs together, so it sews as one path with no jump. Pieces apart are joined along the shape's
edge, where the thread reads as part of an outline; nothing covers it, so it never runs across an
open cell. Where the edge doesn't reach (one edge to another across the lattice), the fill jumps.

Written from first principles for LUDD. Coordinates are mm. Imports from `..stitches` stay inside
the function bodies: stitches imports this package.
"""

from __future__ import annotations

import math

import numpy as np
import shapely

from . import FillPattern, Param, register, spiral
from .lattice import clip_segments, double_run_paths, tile_segments
from .motif import own_frame, place

#: A fill taking more stitches than this says so (as Repeat does).
WARN_STITCHES = 60_000
#: A join may run this far in from the shape's edge, or within ON_LINE_MM of a lattice line.
EDGE_REACH_MM = 0.6
ON_LINE_MM = 0.05
_SAMPLE_MM = 0.2


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
    per_mm2 = sum(2 * line / length * max(1, math.ceil(round(length / stitch, 6)))
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
    joined = _joined(pieces, local)
    stitches = sum(len(p) for p in joined)
    warnings = [] if stitches <= WARN_STITCHES else [
        f"This fill takes about {round(stitches, -2):,} stitches: a very long sew-out on a home machine. "
        "Bigger cells or a smaller shape sew faster."]
    return [place(p, origin) for p in joined], warnings


def _joined(pieces: list, local) -> list:
    """Pieces apart (a thin tip's cell, say) joined along the shape's edge (_along_edge), in the
    shape's own frame, so that a moved shape travels the same way too. Where there's no such way
    they are left apart, and the fill jumps (_jump)."""
    from ..stitches import Zone

    if len(pieces) < 2:
        return pieces
    zone = Zone(local.buffer(0.3))  # as far outside the shape as the fill lets any travel go
    lines = shapely.STRtree([shapely.LineString(p[k:k + 2]) for p in pieces for k in range(len(p) - 1)])
    joined = [list(pieces[0])]
    for piece in pieces[1:]:
        way = _along_edge(joined[-1][-1], piece[0], zone, local.boundary, lines)
        if way is None:
            joined.append(list(piece))
        else:
            joined[-1] += way + piece
    return joined


def _along_edge(a, b, zone, edge, lines) -> list | None:
    """Running stitches from a to b along the shape's edge (or a lattice line), or None if no way
    keeps off the open cells: round the edge first, else straight."""
    from ..stitches import MIN_STITCH_MM, _edge_route, _route_stitches, dist

    if round(dist(a, b), 6) < MIN_STITCH_MM:
        return []
    straight = [a, b] if zone.cover.covers(shapely.LineString([a, b])) else None
    for route in (_edge_route(a, b, zone, steady=True), straight):
        if route is None:
            continue
        way = [(x, y) for x, y, _ in _route_stitches(a, route)]
        if _keeps_off_cells([a, *way], edge, lines):
            return way
    return None


def _keeps_off_cells(points: list, edge, lines: shapely.STRtree) -> bool:
    """Whether every part of this thread lies within EDGE_REACH_MM of the shape's edge or
    ON_LINE_MM of a lattice line, measured every _SAMPLE_MM. Distances are rounded to 0.001 mm
    and one exactly at its limit counts as within it, so a last digit can't choose between sewing
    a join and jumping."""
    samples = []
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        n = max(1, math.ceil(round(math.hypot(x1 - x0, y1 - y0) / _SAMPLE_MM, 6)))
        samples += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n + 1)]
    at = shapely.points(np.array(samples))
    far = at[np.round(shapely.distance(edge, at), 3) > EDGE_REACH_MM]
    if not len(far):
        return True
    _, off = lines.query_nearest(far, return_distance=True, all_matches=False)
    return bool(np.round(off.max(), 3) <= ON_LINE_MM)


def _jump(a, b, zone) -> list:
    """Between pieces no way along the edge reaches, the needle jumps (cutting the thread when long)."""
    from ..stitches import travel

    return travel(a, b)


def _jumps_note(recs) -> list:
    """How many times a fill had to jump, and what that means for the person sewing it."""
    from ..stitches import JUMP

    n = sum(1 for r in recs if r[2] == JUMP)
    if not n:
        return []
    times, threads = ("once", "a thread to snip") if n == 1 else (f"{n} times", f"{n} threads to snip")
    return [f"This Blackwork jumps {times}, where no edge leads from one part of its lattice to the next. "
            f"On a machine that cuts only at color changes, that's {threads}."]


register(FillPattern("blackwork", "open", params={"blackwork_mm": Param(5.0, 3.0, 12.0, "Cell size")}, paths=_paths,
                     step_mm2=lambda p: p.value("blackwork_mm") * p.stitch_mm / 4, auto_underlay=lambda level: [],
                     join=_jump, notes=_jumps_note))
