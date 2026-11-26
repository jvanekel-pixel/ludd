"""The hand-sewn look (P6-A5): small, repeatable irregularities, as a person sewing by hand makes.

At 100%:
- a line (single, triple, bean): each stitch's length varies by up to ±30% and each needle point
  moves up to 0.25 mm sideways;
- a satin: each rung's ends move up to 0.3 mm along the rung, and the spacing varies by ±20%;
- a rows fill: row ends move up to ±0.6 mm (rows/ends.py) and the needle points move as Random
  50% does (rows.hooks).

Every value comes from whole-number hashing of a point's or row's number, never from a sine, so
the same design gives the same stitches on every computer, and moving a shape moves its stitches.
"""

from __future__ import annotations

from typing import Sequence

from ..paths import Point, sharp_points

LINE_LENGTH = 0.15  # each needle point slides up to this share of the stitch beside it (±30% a stitch)
LINE_SIDE_MM = 0.25
SATIN_END_MM = 0.3
SATIN_SPACING = 0.1  # each rung slides up to this share of the gap beside it (±20% spacing)
FILL_END_MM = 0.6
FILL_RANDOM = 0.5  # as Random 50%


def unit(n: int, salt: int) -> float:
    """A repeatable pseudo-random number in [0, 1) for item `n` (a row, a needle point, a rung),
    one stream per `salt`: whole-number arithmetic only, the same on every computer."""
    v = (n * 0x9E3779B1 + salt * 0x85EBCA77 + 0x165667B1) & 0xFFFFFFFF
    v ^= v >> 15
    v = (v * 0x2C1B3C6D) & 0xFFFFFFFF
    v ^= v >> 12
    v = (v * 0x297A2D39) & 0xFFFFFFFF
    v ^= v >> 15
    return v / 2**32


def signed(n: int, salt: int) -> float:
    """unit() spread over [-1, 1)."""
    return unit(n, salt) * 2 - 1


def _toward(p: Point, q: Point, f: float) -> Point:
    return (p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f)


def line(points: Sequence[Point], pct: float) -> list[Point]:
    """A line's needle points with the hand-sewn look at `pct` (0 to 100). The first and last
    points, and sharp corners, stay where they are; the rest slide along the line toward the
    point before or after (so the stitch lengths vary) and move sideways."""
    pts = [(float(x), float(y)) for x, y in points]
    h = pct / 100
    if h <= 0 or len(pts) < 3:
        return pts
    pinned = set(sharp_points(pts))
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        p = pts[i]
        if i in pinned or p == pts[0] or p == pts[-1]:
            out.append(p)
            continue
        u = signed(i, 1)
        q = _toward(p, pts[i + 1] if u >= 0 else pts[i - 1], abs(u) * LINE_LENGTH * h)
        dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        d = (dx * dx + dy * dy) ** 0.5
        if d > 1e-9:
            side = signed(i, 2) * LINE_SIDE_MM * h
            q = (q[0] - dy / d * side, q[1] + dx / d * side)
        out.append(q)
    out.append(pts[-1])
    return out


def satin_pairs(pairs: Sequence[tuple[Point, Point]], pct: float) -> list[tuple[Point, Point]]:
    """A satin's rungs with the hand-sewn look at `pct` (0 to 100): each rung but the first and
    last slides toward a neighbor (the spacing varies), and each end moves along its rung (never
    so far that the two ends meet)."""
    h = pct / 100
    n = len(pairs)
    if h <= 0 or n == 0:
        return list(pairs)
    out = []
    for i, (a, b) in enumerate(pairs):
        if 0 < i < n - 1:
            v = signed(i, 5)
            j = i + 1 if v >= 0 else i - 1
            f = abs(v) * SATIN_SPACING * h
            a, b = _toward(a, pairs[j][0], f), _toward(b, pairs[j][1], f)
        dx, dy = b[0] - a[0], b[1] - a[1]
        w = (dx * dx + dy * dy) ** 0.5
        if w > 1e-9:
            reach = min(SATIN_END_MM * h, 0.25 * w)
            sa, sb = signed(i, 6) * reach, signed(i, 7) * reach
            a = (a[0] - dx / w * sa, a[1] - dy / w * sa)
            b = (b[0] + dx / w * sb, b[1] + dy / w * sb)
        out.append((a, b))
    return out
