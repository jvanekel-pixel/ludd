"""Mesh fill: a net of two sets of lines.

Lines at the fill's angle, Cell size apart and centered on the shape, then lines at that angle
plus Crossing angle. Each set is sewn back and forth, with every move from one line to the next
along an edge of the shape (motif.sew_along_edges), so a move never has to cross the net.

Written from first principles for LUDD (freestanding lace will build on it). Coordinates are mm.
Imports from `..stitches` stay inside the function bodies: stitches imports this package.
"""

from __future__ import annotations

import math

import shapely

from ..paths import Point, dist, resample
from . import FillPattern, Param, register, spiral
from .motif import clip, edge_rings, edges, grown, own_frame, place, sew_along_edges, turn, turned

SHORTEST_LINE_MM = 0.8  # shorter bits of line are left out, unless they're the way between two edges


def _lines(shape, degrees: float, cell: float, rings: list) -> list[list[Point]]:
    """The set of lines at `degrees`, each as its two ends in the shape's frame, line by line."""
    frame = turned(shape, degrees)
    area = grown(frame)
    sides = edges(area)
    minx, miny, maxx, maxy = frame.bounds
    count = max(1, round(round(maxy - miny, 3) / cell))
    found = []
    for k in range(count):
        y = (miny + maxy) / 2 + (k - (count - 1) / 2) * cell
        pieces = sorted(clip([(minx - 1, y), (maxx + 1, y)], area, sides), key=lambda p: round(p[0][0], 6))
        found += [turn([p[0], p[-1]], degrees) for p in pieces]
    if not found:
        return []
    ends = spiral._edge_ends(found, rings)
    return [line for line, (a, b) in zip(found, ends) if dist(*line) >= SHORTEST_LINE_MM or a[0] != b[0]]


def _paths(poly, params, pos):
    """The net over one piece of a fill."""
    from ..stitches import LONG_STITCH_MM

    cell, cross = params.value("mesh_mm"), params.value("mesh_cross_deg")
    longest = min(max(params.stitch_mm, 1.0), LONG_STITCH_MM)
    local, origin = own_frame(poly)
    rings = edge_rings(local)
    cover = local.buffer(0.3)  # as far outside the shape as the fill lets any travel go
    shapely.prepare(cover)
    here = (pos[0] - origin[0], pos[1] - origin[1]) if params.start_mm is not None else spiral.FAR
    paths: list[list[Point]] = []
    for degrees in (params.angle_deg, params.angle_deg + cross):
        lines = _lines(local, math.remainder(degrees, 360), cell, rings)
        sew_along_edges(paths, [resample(line, longest) for line in lines], rings, cover, here, longest)
    return [place(p, origin) for p in paths], []


register(FillPattern("mesh", "open",
                     params={"mesh_mm": Param(3.0, 1.0, 10.0, "Cell size"),
                             "mesh_cross_deg": Param(90.0, 45.0, 90.0, "Crossing angle", unit="°")},
                     paths=_paths, step_mm2=lambda p: p.value("mesh_mm") * min(p.stitch_mm, 3.0) / 2,
                     auto_underlay=lambda level: []))
