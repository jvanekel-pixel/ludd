"""Paths from the pen tool: corner and curve nodes to polylines, and resampling by length.

Nodes are [x, y, kind] in mm, kind "c" (corner) or "s" (smooth/curve), the same convention
as Embrilliance and Hatch: left-click places a corner, right-click a curve point.
Curves are cubic Hermite segments with Catmull-Rom tangents at curve nodes and no tangent at
corners, so a corner stays sharp and the line leaves it straight.
"""

from __future__ import annotations

import math
from typing import Sequence

Point = tuple[float, float]
Node = Sequence  # [x, y, "c" | "s"]

FLATTEN_STEP_MM = 0.25  # curve samples about this far apart
MAX_SAMPLES_PER_SEGMENT = 96


def _pt(n: Node) -> Point:
    return float(n[0]), float(n[1])


def _smooth(n: Node) -> bool:
    return len(n) > 2 and n[2] == "s"


def dist(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def flatten(nodes: Sequence[Node], closed: bool = False) -> tuple[list[Point], list[int]]:
    """Polyline through the nodes. Also returns, for each node, its index in the polyline."""
    n = len(nodes)
    if n == 0:
        return [], []
    pts = [_pt(x) for x in nodes]
    if n == 1:
        return [pts[0]], [0]

    def tangent(i: int) -> Point:
        if not _smooth(nodes[i]):
            return (0.0, 0.0)
        if closed:
            prev, nxt = pts[(i - 1) % n], pts[(i + 1) % n]
        else:
            prev = pts[i - 1] if i > 0 else pts[i]
            nxt = pts[i + 1] if i < n - 1 else pts[i]
        return ((nxt[0] - prev[0]) * 0.5, (nxt[1] - prev[1]) * 0.5)

    out: list[Point] = [pts[0]]
    index = [0]
    segs = n if closed else n - 1
    for i in range(segs):
        j = (i + 1) % n
        p0, p1 = pts[i], pts[j]
        t0, t1 = tangent(i), tangent(j)
        if t0 == (0.0, 0.0) and t1 == (0.0, 0.0):
            out.append(p1)
        else:
            c1 = (p0[0] + t0[0] / 3, p0[1] + t0[1] / 3)
            c2 = (p1[0] - t1[0] / 3, p1[1] - t1[1] / 3)
            approx = dist(p0, c1) + dist(c1, c2) + dist(c2, p1)
            k = max(2, min(MAX_SAMPLES_PER_SEGMENT, math.ceil(approx / FLATTEN_STEP_MM)))
            for s in range(1, k + 1):
                t = s / k
                u = 1 - t
                out.append((
                    u**3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t**3 * p1[0],
                    u**3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t**3 * p1[1],
                ))
        if not (closed and j == 0):
            index.append(len(out) - 1)
    return out, index


def length(poly: Sequence[Point]) -> float:
    return sum(dist(a, b) for a, b in zip(poly, poly[1:]))


def point_at(poly: Sequence[Point], cum: Sequence[float], s: float) -> Point:
    """Point at arc length s along poly, given cumulative lengths `cum`."""
    if s <= 0:
        return poly[0]
    if s >= cum[-1]:
        return poly[-1]
    lo, hi = 0, len(cum) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if cum[mid] <= s:
            lo = mid
        else:
            hi = mid
    seg = cum[hi] - cum[lo]
    t = (s - cum[lo]) / seg if seg else 0.0
    a, b = poly[lo], poly[hi]
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def cumulative(poly: Sequence[Point]) -> list[float]:
    cum = [0.0]
    for a, b in zip(poly, poly[1:]):
        cum.append(cum[-1] + dist(a, b))
    return cum


def resample(poly: Sequence[Point], step: float, keep: Sequence[int] = ()) -> list[Point]:
    """Evenly spaced points at most `step` apart, always hitting the polyline indices in `keep`
    (corners), so stitches land exactly on sharp points."""
    if len(poly) < 2:
        return list(poly)
    stops = sorted({0, len(poly) - 1, *keep})
    out: list[Point] = [poly[0]]
    for a, b in zip(stops, stops[1:]):
        part = poly[a : b + 1]
        cum = cumulative(part)
        total = cum[-1]
        if total == 0:
            continue
        k = max(1, math.ceil(total / step - 1e-9))
        for i in range(1, k + 1):
            out.append(point_at(part, cum, total * i / k))
    return out


def corner_indices(nodes: Sequence[Node], node_index: Sequence[int]) -> list[int]:
    return [node_index[i] for i, nd in enumerate(nodes) if not _smooth(nd)]
