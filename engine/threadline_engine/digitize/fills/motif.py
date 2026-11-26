"""Motif fill: rows of a little pattern across the shape.

Rows run at the fill's angle, Height + Row gap apart and centered on the shape. Each is a line of
whole repeats (patterns.motif_points) laid so that they are centered across the shape, every other
row moved along by Shift alternate rows x Repeat. What falls outside the shape is cut off, and bits
that reach along less than half a repeat are left out. Rows are sewn back and forth, each joined to
the next along the edge of the shape: nothing covers an open fill, so a thread straight across it
would show.

Also here: what the maze, ripple and mesh fills share with this one. All four work in the shape's
own frame (own_frame: its bounds start at (0, 0), rounded, as the spiral's do), and cut their
lines to the shape with their own arithmetic, so a moved or copied shape, and another computer's
maths library, give the same stitches. The motif, ripple and mesh fills join their lines along the
edges with sew_along_edges(), which orders them as the Spiral fill orders its own.

Written from first principles for LUDD. Coordinates are mm. Imports from `..stitches` stay inside
the function bodies: stitches imports this package.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, Point as ShapelyPoint, box
from shapely.geometry.polygon import orient

from ..paths import Point, dist, resample
from ..patterns import motif_points, polygons
from . import FillPattern, Param, register, spiral

GRAZE_MM = 0.01  # lines are cut to the shape grown this much, so one that only touches its edge stays whole
DECIMALS = 6  # the shape's own frame is rounded to a millionth of a mm
OTHER_EDGE_MM = 10_000.0  # added to how far it is to a point by another edge (see reach)


# ---------------------------------------------------------------- shared with maze, ripple and mesh


def _rounded(shape):
    return shapely.transform(shape, lambda xy: np.round(xy, DECIMALS))


def own_frame(poly) -> tuple[shapely.Polygon, Point]:
    """The shape moved so its bounds start at (0, 0), rounded, and how far it was moved. A moved or
    copied shape then gets exactly the same stitches (see spiral._spiral_paths)."""
    x0, y0 = poly.bounds[:2]
    return shapely.transform(poly, lambda xy: np.round(xy - (x0, y0), DECIMALS)), (x0, y0)


def place(points: Sequence[Point], origin: Point) -> list[Point]:
    """Points from a shape's own frame back where the shape is (with no -0.0 left over)."""
    x0, y0 = origin
    return [(round(x + x0, 9) + 0.0, round(y + y0, 9) + 0.0) for x, y in points]


def turn(points: Sequence[Point], degrees: float) -> list[Point]:
    """Points turned by `degrees` about (0, 0)."""
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    return [(x * c - y * s, x * s + y * c) for x, y in points]


def turned(shape, degrees: float):
    """The shape turned so that lines at `degrees` lie level, rounded as its own frame is."""
    flat = _rounded(affinity.rotate(shape, -degrees, origin=(0, 0)))
    if not flat.is_valid:  # a zero-width spike can turn invalid when rotated
        flat = max(polygons(flat.buffer(0)) or [flat], key=lambda g: g.area)
    return flat


def grown(shape):
    """The shape grown by GRAZE_MM, ready to cut lines to."""
    area = _rounded(shape.buffer(GRAZE_MM))
    shapely.prepare(area)
    return area


def edges(area) -> tuple[np.ndarray, np.ndarray]:
    """Every side of the area's outline and holes, as (where each starts, where each ends)."""
    rings = [np.asarray(r.coords, dtype=float)[:, :2] for p in polygons(area) for r in [p.exterior, *p.interiors]]
    return np.concatenate([r[:-1] for r in rings]), np.concatenate([r[1:] for r in rings])


def edge_rings(shape) -> list[LineString]:
    """The shape's edges (its outline, then its holes) as closed lines, each going the same way
    round from its top left point, so that every computer walks them alike."""
    shape = orient(shape, 1.0)
    rings = []
    for ring in [shape.exterior, *shape.interiors]:
        points = list(ring.coords)[:-1]
        k = min(range(len(points)), key=lambda i: (round(points[i][1], 3), round(points[i][0], 3), i))
        rings.append(LineString(points[k:] + points[:k] + [points[k]]))
    return [rings[0], *sorted(rings[1:], key=lambda r: (round(r.bounds[1], 3), round(r.bounds[0], 3)))]


def clip(points: Sequence[Point], area, sides: tuple[np.ndarray, np.ndarray] | None = None) -> list[list[Point]]:
    """The parts of the line through `points` inside `area`, in order along it. Parts less than a
    stitch apart (where the line only grazes out of the shape) are one.

    Worked out here rather than with the geometry library's overlay, which gives pieces in no
    fixed order, and merges a line that runs back over itself (the blanket stitch does)."""
    from ..stitches import MIN_STITCH_MM

    line = np.asarray(points, dtype=float)
    if len(line) < 2:
        return []
    a, b = edges(area) if sides is None else sides
    low, high = np.minimum(a, b), np.maximum(a, b)
    cuts: list[list[float]] = []  # for each step of the line, where along it (0 to 1) it meets a side
    middles = []
    for p, q in zip(line[:-1], line[1:]):
        r = q - p
        square = float(r @ r)
        ts = [0.0, 1.0]
        near = np.all((high >= np.minimum(p, q) - 1e-6) & (low <= np.maximum(p, q) + 1e-6), axis=1)
        if square > 0 and near.any():
            s, ap = b[near] - a[near], a[near] - p
            denom = r[0] * s[:, 1] - r[1] * s[:, 0]
            across = np.abs(denom) > 1e-12
            t = (ap[:, 0] * s[:, 1] - ap[:, 1] * s[:, 0])[across] / denom[across]
            u = (ap[:, 0] * r[1] - ap[:, 1] * r[0])[across] / denom[across]
            ts += t[(u >= -1e-9) & (u <= 1 + 1e-9) & (t > 0) & (t < 1)].tolist()
            along = ~across & (np.abs(ap[:, 0] * r[1] - ap[:, 1] * r[0]) <= 1e-9 * math.sqrt(square))
            for end in (a[near][along], b[near][along]):  # a side lying along the line
                te = ((end - p) @ r) / square
                ts += te[(te > 0) & (te < 1)].tolist()
        ts = sorted(set(ts))
        cuts.append(ts)
        middles += [p + r * ((t0 + t1) / 2) for t0, t1 in zip(ts, ts[1:])]
    mids = np.asarray(middles)
    inside = shapely.intersects_xy(area, mids[:, 0], mids[:, 1])
    pieces: list[list[Point]] = []
    carrying = False
    k = 0
    for (p, q), ts in zip(zip(line[:-1], line[1:]), cuts):
        for t0, t1 in zip(ts, ts[1:]):
            if t1 - t0 > 1e-9:
                if inside[k]:
                    start, end = (p if t0 == 0 else p + (q - p) * t0), (q if t1 == 1 else p + (q - p) * t1)
                    if not carrying:
                        pieces.append([(float(start[0]), float(start[1]))])
                    pieces[-1].append((float(end[0]), float(end[1])))
                carrying = bool(inside[k])
            k += 1
    joined: list[list[Point]] = []
    for piece in pieces:
        if joined and dist(joined[-1][-1], piece[0]) < MIN_STITCH_MM:
            joined[-1] += piece
        else:
            joined.append(piece)
    return joined


def by_edge(p: Point, rings: list) -> tuple[int, float, Point]:
    """The edge nearest p, how far round it that is, and p (as spiral._edge_ends describes a
    stretch's end)."""
    spot = ShapelyPoint(p)
    k = min(range(len(rings)), key=lambda j: (round(rings[j].distance(spot), 3), j))
    return k, rings[k].project(spot), p


def reach(a: tuple, b: tuple, rings: list) -> float:
    """How far it is from one point by an edge (see by_edge) to another along that edge; far more
    than that when they're by different edges, as joining them cuts across the shape."""
    if a[0] != b[0]:
        return OTHER_EDGE_MM + dist(a[2], b[2])
    length = rings[a[0]].length
    along = abs(a[1] - b[1]) % length
    return min(along, length - along)


def in_edge_order(stretches: list[list[Point]], rings: list, here: Point) -> list[list[Point]]:
    """Stretches that end on the shape's edges, in sewing order, each turned the way it's sewn:
    first the one with an end nearest `here` along an edge, then always the nearest along the edge
    the needle is on, passing over a choice that would leave others to be reached only by cutting
    across the shape (the Spiral fill's rule, spiral._sewing_order)."""
    # How far round, to a millionth of a mm, so that equally near ends are the same on every computer.
    ends = [tuple((edge, round(along, 6), p) for edge, along, p in pair)
            for pair in spiral._edge_ends(stretches, rings)]
    start = by_edge(here, rings)
    first, backwards = min(((i, e) for i in range(len(stretches)) for e in (0, 1)),
                           key=lambda c: (round(reach(start, ends[c[0]][c[1]], rings), 6), c))
    order = [first, *[i for i in range(len(stretches)) if i != first]]
    pairs = [ends[i] for i in order]
    if backwards:
        pairs[0] = pairs[0][::-1]
    sewn = spiral._sewing_order(pairs, [round(r.length, 6) for r in rings])
    return [stretches[order[i]][::-1] if (backwards if i == 0 else back) else stretches[order[i]]
            for i, back in sewn]


def sew_along_edges(paths: list[list[Point]], stretches: list[list[Point]], rings: list, cover, here: Point,
                    longest: float) -> None:
    """Sew stretches that end on the shape's edges (see in_edge_order), each joined to the one
    before along an edge, onto the end of `paths`; only if no way along an edge stays inside
    `cover` does a new path begin (the fill then travels to it). `here`: where to begin, when
    nothing is sewn yet."""
    from ..stitches import TRAVEL_STITCH_MM

    if not stretches:
        return
    for stretch in in_edge_order(stretches, rings, paths[-1][-1] if paths else here):
        way = spiral._way_round(paths[-1][-1], stretch[0], rings, cover) if paths else None
        if way:
            spiral._join(paths[-1], stretch, way, min(TRAVEL_STITCH_MM, longest))
        else:
            paths.append(list(stretch))


# ---------------------------------------------------------------- the motif fill


def _check_size(unit: Sequence[Point], repeats: float, repeat: float, height: float, stitch: float) -> None:
    """Refuse a motif so busy that the fill would be far more stitches than any design, laying
    `repeats` of it. (The fill's area guard can't know how long a motif of your own is.)"""
    from ..stitches import MAX_STITCHES, MIN_STITCH_MM, DigitizeError

    length = sum(math.hypot((u1 - u0) * repeat, (v1 - v0) * height) for (u0, v0), (u1, v1) in zip(unit, unit[1:]))
    stitches = repeats * min(max(len(unit) - 1, length / stitch), length / MIN_STITCH_MM + 1)
    if stitches > MAX_STITCHES:
        raise DigitizeError(f"This fill would need about {stitches:,.0f} stitches, far more than any design. "
                            "Make it smaller or less dense.")


def _rows(local, params, stitch: float) -> list[list[list[Point]]]:
    """The motif's rows over the shape (in its own frame), top to bottom as they lie at angle 0:
    in each row, the pieces inside the shape, each the needle points along it."""
    from ..lines import MOTIF_UNITS, sewn_unit  # here, not at the top: lines imports this package
    from ..stitches import DigitizeError

    unit = sewn_unit(params.motif_unit)  # a motif of your own; None: the built-in one named
    if unit is None and params.motif not in MOTIF_UNITS:
        raise DigitizeError(f"Unknown motif: {params.motif}")
    shape_unit = MOTIF_UNITS[params.motif] if unit is None else unit
    repeat, height = params.value("motif_mm"), params.value("motif_width_mm")
    gap, shift = params.value("motif_gap_mm"), params.value("motif_stagger") * repeat
    frame = turned(local, params.angle_deg)
    area = grown(frame)
    sides = edges(area)
    minx, miny, maxx, maxy = frame.bounds
    pitch = height + gap
    rows = max(1, round((round(maxy - miny, 3) + gap) / pitch))
    across = max(1, math.ceil(round(maxx - minx, 3) / repeat - 1e-9))  # whole repeats to cover the width
    us, vs = [u for u, _ in shape_unit], [v for _, v in shape_unit]
    off = (min(vs) + max(vs)) / 2 * height  # a motif drawn to one side of its line still sits in its row
    spare = 1 + math.ceil(max(0.0, -min(us), max(us) - 1))  # repeats laid past each end
    # About the repeats the shape holds, and those laid past the ends of each row (many more for a
    # motif of your own that loops far past its ends).
    _check_size(shape_unit, frame.area / (repeat * pitch) + rows * (2 * spare - 1), repeat, height, stitch)
    first = (minx + maxx) / 2 - across / 2 * repeat
    found: list[list[list[Point]]] = []
    for k in range(rows):
        y = (miny + maxy) / 2 + (k - (rows - 1) / 2) * pitch - off
        x = first + (shift if k % 2 else 0.0)
        band = frame.intersection(box(minx - 1, y + min(vs) * height - 0.1, maxx + 1, y + max(vs) * height + 0.1))
        row = []
        if not band.is_empty:
            # Repeats only where the shape is on this row, on the same grid for every row.
            start = x + (math.floor((band.bounds[0] - x) / repeat) - spare) * repeat
            count = math.ceil((band.bounds[2] - start) / repeat) + spare
            laid = motif_points([[start, y, "c"], [start + count * repeat, y, "c"]], params.motif, repeat, height,
                                unit=unit)
            for piece in clip(laid, area, sides):
                lo, hi = min(px for px, _ in piece), max(px for px, _ in piece)
                if round(hi - lo, 6) >= round(repeat / 2, 6):
                    needles = resample(piece, stitch, range(len(piece)))  # the motif's corners are needle points
                    row.append(turn(needles, params.angle_deg))
        found.append(row)
    return found


def _paths(poly, params, pos):
    """The motif over one piece of a fill, its rows' pieces joined along the edges."""
    from ..stitches import LONG_STITCH_MM

    stitch = min(max(params.stitch_mm, 1.0), LONG_STITCH_MM)
    local, origin = own_frame(poly)
    pieces = [piece for row in _rows(local, params, stitch) for piece in row]
    cover = local.buffer(0.3)  # as far outside the shape as the fill lets any travel go
    shapely.prepare(cover)
    here = (pos[0] - origin[0], pos[1] - origin[1]) if params.start_mm is not None else spiral.FAR
    paths: list[list[Point]] = []
    sew_along_edges(paths, pieces, edge_rings(local), cover, here, stitch)
    return [place(p, origin) for p in paths], []


register(FillPattern("motif", "open",
                     params={"motif_mm": Param(5.0, 1.5, 20.0, "Repeat"),
                             "motif_width_mm": Param(4.0, 0.5, 10.0, "Height"),
                             "motif_gap_mm": Param(0.5, 0.0, 10.0, "Row gap"),
                             "motif_stagger": Param(0.5, 0.0, 1.0, "Shift alternate rows", unit="")},
                     paths=_paths, step_mm2=lambda p: (p.value("motif_width_mm") + p.value("motif_gap_mm")) * 2,
                     auto_underlay=lambda level: []))
