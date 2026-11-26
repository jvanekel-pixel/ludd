"""Ripple fill: rings spreading from a point, like a drop in water.

Circles Ring spacing apart round the ripple's middle (params.ripple_center, else the middle of the
shape's widest spot, found as the Spiral fill finds it), cut to the shape and sewn from the middle
out. Whole rings come one after another, each reached by a short step out. The rings the shape's
edge cuts into arcs are joined along the edges (motif.sew_along_edges): each part of the shape the
rings reach into is sewn outward in turn, so joining thread doesn't pile up along an edge.

Written from first principles for LUDD. Coordinates are mm. Imports from `..stitches` stay inside
the function bodies: stitches imports this package.
"""

from __future__ import annotations

import math

import numpy as np
import shapely
from shapely.geometry import LineString, Point as ShapelyPoint

from ..paths import Point, dist
from . import FillPattern, Param, register, spiral
from .motif import edge_rings, edges, grown, onto_edges, own_frame, place, sew_along_edges

SAG_MM = 0.1  # no stitch cuts further than this inside its circle
SHORTEST_ARC_MM = 1.0  # shorter bits of a ring are left out
FARTHEST_MM = 2000.0  # a ripple's middle further than this from the shape is a slip
TOO_FAR = "The middle of this ripple is too far from the shape. Move it closer to the shape."
TURN = 2 * math.pi
WHOLE = [(0.0, TURN)]  # a ring the edge doesn't cut (see _arcs)


def _on_circle(center: Point, r: float, angle: float) -> Point:
    return center[0] + r * math.cos(angle), center[1] + r * math.sin(angle)


def _inside(area, points: list[Point]) -> np.ndarray:
    xy = np.asarray(points)
    return shapely.intersects_xy(area, xy[:, 0], xy[:, 1])


def _crossing_angles(center: Point, r: float, sides: tuple[np.ndarray, np.ndarray]) -> list[float]:
    """The angles at which the circle meets the sides, in order, each once."""
    a, b = sides
    d, f = b - a, a - np.asarray(center)
    qa = (d * d).sum(axis=1)
    qb = 2 * (f * d).sum(axis=1)
    disc = qb * qb - 4 * qa * ((f * f).sum(axis=1) - r * r)
    meets = (disc > 0) & (qa > 0)
    root = np.sqrt(disc[meets])
    angles: list[float] = []
    for t in ((-qb[meets] - root) / (2 * qa[meets]), (-qb[meets] + root) / (2 * qa[meets])):
        on = (t >= 0) & (t < 1)
        xy = f[meets][on] + d[meets][on] * t[on][:, None]
        angles += (np.arctan2(xy[:, 1], xy[:, 0]) % TURN).tolist()
    angles = sorted(0.0 if TURN - x < 1e-9 else x for x in angles)  # a hair under a turn is no turn
    return [x for i, x in enumerate(angles) if i == 0 or x - angles[i - 1] > 1e-9]


def _arcs(center: Point, r: float, sides, area) -> list[tuple[float, float]]:
    """The parts of the circle inside `area` as (start angle, how far round), by start angle; WHOLE
    when it's all inside. Arcs less than a stitch apart are one; very short ones are left out."""
    from ..stitches import MIN_STITCH_MM

    cuts = _crossing_angles(center, r, sides)
    if not cuts:
        return list(WHOLE) if _inside(area, [_on_circle(center, r, 0.0)])[0] else []
    spans = [(c, (cuts[(i + 1) % len(cuts)] - c) % TURN or TURN) for i, c in enumerate(cuts)]
    inside = _inside(area, [_on_circle(center, r, start + width / 2) for start, width in spans])
    if inside.all():
        return list(WHOLE)
    outside = int(np.argmin(inside))  # go round from just after a part that's outside
    arcs: list[tuple[float, float]] = []
    for j in range(1, len(spans) + 1):
        i = (outside + j) % len(spans)
        if not inside[i]:
            continue
        start, width = spans[i]
        if arcs:
            before, so_far = arcs[-1]
            gap = (start - before - so_far + math.pi) % TURN - math.pi
            if r * abs(gap) < MIN_STITCH_MM:  # carried on, or a gap too small to show
                arcs[-1] = (before, (start - before) % TURN + width)
                continue
        arcs.append((start, width))
    arcs = [(start % TURN, width) for start, width in arcs if r * width >= SHORTEST_ARC_MM]
    return sorted(arcs, key=lambda arc: round(arc[0], 6))


def _arc_points(center: Point, r: float, start: float, sweep: float, stitch: float) -> list[Point]:
    """Needle points from angle `start` round by `sweep`, close enough together that no stitch
    cuts more than SAG_MM inside the circle."""
    step = min(stitch / r, 2 * math.acos(max(-1.0, 1 - SAG_MM / r)))
    n = max(1, math.ceil(abs(sweep) / step - 1e-9))
    return [_on_circle(center, r, start + sweep * j / n) for j in range(n + 1)]


def _facing_edge(center: Point, r: float, spacing: float, rings: list) -> float | None:
    """The angle at which the ring of radius `r` comes nearest an edge it hasn't reached. The
    outline (rings[0]) is taken if it's within a ring spacing of that ring, even when a hole is a
    little nearer: nearly every later ring crosses the outline, so its joins can keep to it."""
    found: list[tuple[float, int, float]] = []  # (how far, which edge, the angle)
    for k, ring in enumerate(rings):
        xy = np.asarray(ring.coords)
        steps = xy[1:] - xy[:-1]
        squares = np.maximum((steps ** 2).sum(axis=1), 1e-18)
        t = np.clip(((np.asarray(center) - xy[:-1]) * steps).sum(axis=1) / squares, 0.0, 1.0)
        off = xy[:-1] + steps * t[:, None] - np.asarray(center)
        away = np.round(np.hypot(off[:, 0], off[:, 1]), 3)
        beyond = np.where(away >= r - 0.05, away, np.inf)
        i = int(np.argmin(beyond))
        if beyond[i] < np.inf:
            found.append((float(beyond[i]), k, math.atan2(off[i, 1], off[i, 0])))
    if not found:
        return None
    outline = [f for f in found if f[1] == 0 and f[0] <= r + spacing]
    return min(outline or found)[2]


def _step_out(paths: list, ring: list[Point], rings: list, cover, spacing: float, longest: float) -> None:
    """Carry the stitching on to a whole ring: straight if it's close by (the step out from the
    ring before), else along an edge of the shape; if neither stays inside, a new path begins."""
    from ..stitches import TRAVEL_STITCH_MM

    if not paths:
        paths.append(ring)
        return
    a, b = paths[-1][-1], ring[0]
    if dist(a, b) <= 1.5 * spacing and cover.covers(LineString([a, b])):
        spiral._join(paths[-1], ring, [a, b], longest)
        return
    way = spiral._way_round(a, b, rings, cover)
    if way:
        spiral._join(paths[-1], ring, way, min(TRAVEL_STITCH_MM, longest))
    else:
        paths.append(ring)


def _paths(poly, params, pos):
    """The ripple over one piece of a fill, sewn from the middle out. `pos`, the green dot's place
    on the edge when there is one, only matters with the middle outside the shape: the arcs nearest
    it come first."""
    from ..stitches import LONG_STITCH_MM, DigitizeError

    spacing = params.value("ripple_mm")
    longest = min(max(params.stitch_mm, 1.0), LONG_STITCH_MM)
    local, origin = own_frame(poly)
    if params.ripple_center is None:
        center = spiral._middle(local)
    else:
        center = (round(params.ripple_center[0] - origin[0], 6), round(params.ripple_center[1] - origin[1], 6))
    far = max(dist(center, p) for p in local.exterior.coords)
    if far > FARTHEST_MM:
        raise DigitizeError(TOO_FAR)
    area = grown(local)
    sides = edges(area)
    rings = edge_rings(local)
    cover = local.buffer(0.3)  # as far outside the shape as the fill lets any travel go
    shapely.prepare(cover)
    toward = (pos[0] - origin[0], pos[1] - origin[1]) if params.start_mm is not None else spiral.FAR
    first = max(1, math.floor(local.distance(ShapelyPoint(center)) / spacing))
    found = [(k * spacing, arcs) for k in range(first, math.floor(far / spacing) + 2)
             if (arcs := _arcs(center, k * spacing, sides, area))]
    paths: list[list[Point]] = []
    n = 0
    while n < len(found):
        whole = found[n][1] == WHOLE
        end = next((m for m in range(n, len(found)) if (found[m][1] == WHOLE) != whole), len(found))
        if whole:
            # Whole rings begin facing the edge the last of them comes nearest, so it ends right
            # by the edge, where the arcs of the next rings begin: no step cuts across them.
            facing = _facing_edge(center, found[end - 1][0], spacing, rings)
            where = paths[-1][-1] if paths else toward
            seam = math.atan2(where[1] - center[1], where[0] - center[0]) if facing is None else facing
            for r, _ in found[n:end]:
                _step_out(paths, _arc_points(center, r, seam, TURN, longest), rings, cover, spacing, longest)
        else:
            arcs = [_arc_points(center, r, start, width, longest) for r, spans in found[n:end] for start, width in spans]
            sew_along_edges(paths, onto_edges(arcs, rings), rings, cover, toward, longest)
        n = end
    return [place(p, origin) for p in paths], []


register(FillPattern("ripple", "open", params={"ripple_mm": Param(2.0, 0.6, 8.0, "Ring spacing")}, paths=_paths,
                     step_mm2=lambda p: p.value("ripple_mm") * min(p.stitch_mm, 3.0), auto_underlay=lambda level: []))
