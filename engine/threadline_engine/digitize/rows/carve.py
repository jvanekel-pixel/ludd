"""Carved lines: lines drawn over a fill that every row drops a needle on, so they show as
grooves. A fill's lines (geometry.carve) come flattened to polylines in mm, in the design's frame
(FillParams.carve).

Each line is turned into the rows' frame once; a row then finds where it crosses the lines' segments.
Crossings are worked out segment by segment with half-open ends, so a point where two segments of
one line meet counts once, then sorted and rid of duplicates: the same on every computer.
"""

from __future__ import annotations

import math
from typing import Callable, Sequence

import shapely
from shapely.geometry import LineString, Point as ShapelyPoint

from ..paths import Point

KEEP_FROM_END_MM = 0.4  # a crossing closer to a row's end than this is left to the end
ALONG_DEG = 15.0  # a carved segment this near the rows' direction can't be crossed cleanly
ALONG_SHARE = 1 / 3  # warn when more than this share of a line runs along the rows
ALONG_WARNING = "A carved line that runs along the stitch rows won't show. Turn the fill's angle or the line."
BEND_STEP_MM = 0.25  # how finely a segment is checked against a rippled row


def _turned(lines: Sequence[Sequence[Point]], angle_deg: float) -> list[list[tuple[Point, Point]]]:
    """Each line's segments in the rows' turned frame (the design turned by -angle about 0, 0)."""
    a = math.radians(-angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for line in lines:
        pts = [(x * ca - y * sa, x * sa + y * ca) for x, y in line]
        out.append([(p, q) for p, q in zip(pts, pts[1:]) if p != q])
    return out


def _steady(xs: list[float], x0: float, x1: float) -> list[float]:
    """Crossings inside the row (KEEP_FROM_END_MM from its ends), sorted, each once."""
    lo, hi = x0 + KEEP_FROM_END_MM, x1 - KEEP_FROM_END_MM
    out: list[float] = []
    for x in sorted(x for x in xs if lo <= x <= hi):
        if not out or round(x - out[-1], 6) > 0:
            out.append(x)
    return out


def _straight(segs, y: float) -> list[float]:
    xs = []
    for (px, py), (qx, qy) in segs:
        if (py <= y < qy) or (qy <= y < py):
            xs.append(px + (y - py) / (qy - py) * (qx - px))
    return xs


def _bent(segs, bend: Callable[[float], float], x0: float, x1: float) -> list[float]:
    """Where segments cross a rippled row, y = bend(x) between x0 and x1: each sign change of
    (segment's height - row's height), found to a millionth of a mm by halving."""
    xs = []
    for (px, py), (qx, qy) in segs:
        if max(px, qx) < x0 or min(px, qx) > x1:
            continue
        n = max(1, math.ceil(math.hypot(qx - px, qy - py) / BEND_STEP_MM))

        def at(t: float) -> tuple[float, float]:
            x = px + (qx - px) * t
            return x, py + (qy - py) * t - bend(min(max(x, x0), x1))

        prev_t, prev = 0.0, at(0.0)[1]
        for k in range(1, n + 1):
            t = k / n
            cur = at(t)[1]
            if prev == 0.0:
                xs.append(at(prev_t)[0])
            elif cur != 0.0 and (prev < 0) != (cur < 0):
                lo, hi, flo = prev_t, t, prev
                for _ in range(40):
                    mid = (lo + hi) / 2
                    fm = at(mid)[1]
                    if (fm < 0) == (flo < 0):
                        lo, flo = mid, fm
                    else:
                        hi = mid
                xs.append(at((lo + hi) / 2)[0])
            prev_t, prev = t, cur
    return xs


def forced_for_rows(lines: Sequence[Sequence[Point]], angle_deg: float) -> Callable[..., list[float]]:
    """tatami()'s "forced" hook for rows at `angle_deg`: (y, x0, x1, bend=None) -> where the row
    (turned frame) crosses a carved line, at least KEEP_FROM_END_MM inside its ends. `bend`:
    x -> the row's height there, for a rippled (wave) row."""
    segs = [s for line in _turned(lines, angle_deg) for s in line]

    def forced(y: float, x0: float, x1: float, bend: Callable[[float], float] | None = None) -> list[float]:
        xs = _straight(segs, y) if bend is None else _bent(segs, bend, x0, x1)
        return _steady(xs, x0, x1)

    return forced


def crossings_along(lines: Sequence[Sequence[Point]], path: Sequence[Point]) -> list[float]:
    """Where a curved row (a turning fill's, as points in mm) crosses a carved line: distances
    along it, at least KEEP_FROM_END_MM from its ends, in order."""
    if not lines or len(path) < 2:
        return []
    segs = [s for line in _turned(lines, 0.0) for s in line]
    found: list[float] = []
    start = 0.0
    for (ax, ay), (bx, by) in zip(path, path[1:]):
        rx, ry = bx - ax, by - ay
        length = math.hypot(rx, ry)
        if length <= 0:
            continue
        for (px, py), (qx, qy) in segs:
            sx, sy = qx - px, qy - py
            den = rx * sy - ry * sx
            if den == 0:
                continue  # parallel: never a clean crossing
            t = ((px - ax) * sy - (py - ay) * sx) / den
            u = ((px - ax) * ry - (py - ay) * rx) / den
            if 0 <= t < 1 and 0 <= u < 1:
                found.append(start + t * length)
        start += length
    return _steady(found, 0.0, start)


ALONG_STEP_MM = 1.0  # a carved line is compared with curved rows in stretches about this long


def along_curved_rows(lines: Sequence[Sequence[Point]], rows: Sequence[Sequence[Point]]) -> bool:
    """along_the_rows for curved rows (a turning fill's, as lists of points in mm): each stretch
    of a carved line is compared with the direction of the row nearest its middle."""
    segs = [LineString([p, q]) for row in rows for p, q in zip(row, row[1:]) if tuple(p) != tuple(q)]
    if not segs:
        return False
    tree = shapely.STRtree(segs)
    limit = math.tan(math.radians(ALONG_DEG))
    for line in lines:
        total = along = 0.0
        for (px, py), (qx, qy) in zip(line, line[1:]):
            dx, dy = qx - px, qy - py
            length = math.hypot(dx, dy)
            if length <= 0:
                continue
            n = max(1, math.ceil(length / ALONG_STEP_MM))
            for j in range(n):
                t = (j + 0.5) / n
                (ax, ay), (bx, by) = segs[int(tree.nearest(ShapelyPoint(px + dx * t, py + dy * t)))].coords
                rx, ry = bx - ax, by - ay
                total += length / n
                # Lines have no front or back: how far apart their directions are, 0 to 90.
                if abs(dx * ry - dy * rx) <= abs(dx * rx + dy * ry) * limit:
                    along += length / n
        if total > 0 and along > total * ALONG_SHARE:
            return True
    return False


def along_the_rows(lines: Sequence[Sequence[Point]], angle_deg: float) -> bool:
    """Whether any line runs within ALONG_DEG of the rows for more than ALONG_SHARE of its length."""
    limit = math.tan(math.radians(ALONG_DEG))
    for line in _turned(lines, angle_deg):
        total = along = 0.0
        for (px, py), (qx, qy) in line:
            dx, dy = abs(qx - px), abs(qy - py)
            d = math.hypot(dx, dy)
            total += d
            if dy <= dx * limit:
                along += d
        if total > 0 and along > total * ALONG_SHARE:
            return True
    return False
