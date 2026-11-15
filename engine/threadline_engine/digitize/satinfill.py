"""Satin fill: fill a closed shape with one satin column that turns and changes width with the
shape, as Embrilliance does when a shape is set to Satin (petals, leaves, hearts, swooshes).

The shape's outline is split at its two tips into two sides (the satin's rails), and points on
the two sides are paired so each stitch goes straight across the shape: stitches follow the
shape's curve, wide where it's wide and narrow where it's narrow. The result is an ordinary
two-rail satin column, so its underlay, density, split long stitches and point editing all apply.

Choosing the tips: every pair of candidate points round the outline (evenly spaced, plus its sharp
corners) is tried, and the pair whose sides stay closest together all along (the shortest
stitches, the sides about the same length) wins. The next best, clearly different pairs are the
other "ways" (Embrilliance's satin direction), for when the first isn't the one wanted.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np
from shapely.geometry import Polygon

from .paths import flatten

# Candidate tips: this many evenly round the outline (plus its sharp corners).
CANDIDATES = 40
# Two tips must be at least this share of the outline apart, both ways round.
MIN_SIDE = 0.15
# How far apart rungs (the points on each side that line up) are along the satin (mm).
RUNG_MM = 2.5
# A corner sharper than this (degrees of turn) is kept as a corner, and is a candidate tip.
CORNER_DEG = 50
WAYS = 4
# The satin starts and ends where the shape is at least this wide (mm).
MIN_TIP_MM = 0.9


class SatinFillError(Exception):
    rpc_code = -32000


def _ring(outline: Sequence) -> np.ndarray:
    pts, _ = flatten(outline, True)
    poly = Polygon(pts).buffer(0)
    if poly.is_empty or poly.geom_type != "Polygon" or poly.area < 1.0:
        raise SatinFillError("This shape is too small, or crosses itself, to fill with satin")
    ring = np.asarray(poly.exterior.coords[:-1], dtype=float)
    return ring


def _resample(ring: np.ndarray, n: int) -> np.ndarray:
    """`n` points evenly spaced round a closed ring."""
    closed = np.vstack([ring, ring[:1]])
    seg = np.hypot(*np.diff(closed, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    at = np.linspace(0, cum[-1], n, endpoint=False)
    x = np.interp(at, cum, closed[:, 0])
    y = np.interp(at, cum, closed[:, 1])
    return np.stack([x, y], axis=1)


def _turns(pts: np.ndarray, k: int = 2) -> np.ndarray:
    """How sharply the ring turns at each point (degrees), looking `k` points either side."""
    a = np.roll(pts, k, axis=0)
    b = np.roll(pts, -k, axis=0)
    v1, v2 = pts - a, b - pts
    cross = v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0]
    dot = (v1 * v2).sum(axis=1)
    return np.degrees(np.abs(np.arctan2(cross, dot)))


def _sides(pts: np.ndarray, i: int, j: int) -> tuple[np.ndarray, np.ndarray]:
    """The ring split at points i and j: both sides, each running from i to j."""
    m = len(pts)
    fwd = [(i + t) % m for t in range(((j - i) % m) + 1)]
    back = [(i - t) % m for t in range(((i - j) % m) + 1)]
    return pts[fwd], pts[back]


def _at_fractions(side: np.ndarray, t: np.ndarray) -> np.ndarray:
    seg = np.hypot(*np.diff(side, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    at = t * cum[-1]
    return np.stack([np.interp(at, cum, side[:, 0]), np.interp(at, cum, side[:, 1])], axis=1)


def _cost(pts: np.ndarray, i: int, j: int, t: np.ndarray) -> float:
    a, b = _sides(pts, i, j)
    la = np.hypot(*np.diff(a, axis=0).T).sum()
    lb = np.hypot(*np.diff(b, axis=0).T).sum()
    widths = np.hypot(*(_at_fractions(a, t) - _at_fractions(b, t)).T)
    ratio = max(la, lb) / max(1e-6, min(la, lb))
    # Short stitches everywhere (the widest matters most), and two sides of about the same length.
    return float(widths.max() + 0.5 * widths.mean() + max(0.0, ratio - 1.6) * widths.mean())


def _pair_up(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """For each point on side a, the matching point on side b (an index), going along both sides
    together, never backwards, keeping the stitches as short as possible (dynamic time warping)."""
    na, nb = len(a), len(b)
    d = np.hypot(a[:, None, 0] - b[None, :, 0], a[:, None, 1] - b[None, :, 1])
    acc = np.full((na, nb), np.inf)
    acc[0, 0] = d[0, 0]
    for x in range(na):
        for y in range(nb):
            if x == 0 and y == 0:
                continue
            best = min(acc[x - 1, y] if x else np.inf, acc[x, y - 1] if y else np.inf, acc[x - 1, y - 1] if x and y else np.inf)
            acc[x, y] = d[x, y] + best
    # Walk back from the far end.
    # Walking back, the first time a point on side a is reached is its furthest match: keep that.
    match = np.full(na, -1, dtype=int)
    x, y = na - 1, nb - 1
    match[x] = y
    while x > 0 or y > 0:
        options = []
        if x and y:
            options.append((acc[x - 1, y - 1], x - 1, y - 1))
        if x:
            options.append((acc[x - 1, y], x - 1, y))
        if y:
            options.append((acc[x, y - 1], x, y - 1))
        _, x, y = min(options)
        if match[x] < 0:
            match[x] = y
    return match


def _thin(side: np.ndarray, step: float) -> np.ndarray:
    """Points about `step` apart along a side (its ends kept)."""
    seg = np.hypot(*np.diff(side, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    n = max(2, int(math.ceil(cum[-1] / step)) + 1)
    at = np.linspace(0, cum[-1], n)
    return np.stack([np.interp(at, cum, side[:, 0]), np.interp(at, cum, side[:, 1])], axis=1)


def _ways(pts: np.ndarray) -> list[tuple[int, int, float]]:
    m = len(pts)
    turn = _turns(pts)
    even = set(np.linspace(0, m, CANDIDATES, endpoint=False).astype(int).tolist())
    corners = {int(k) for k in np.nonzero(turn > CORNER_DEG)[0]}
    cand = sorted(even | corners)
    t = np.linspace(0.03, 0.97, 24)
    scored = []
    for x, i in enumerate(cand):
        for j in cand[x + 1 :]:
            frac = (j - i) / m
            if frac < MIN_SIDE or frac > 1 - MIN_SIDE:
                continue
            scored.append((_cost(pts, i, j, t), i, j))
    scored.sort()
    # Keep clearly different ways: tips not near an already chosen pair's tips.
    picked: list[tuple[int, int, float]] = []
    near = max(2, m // 12)

    def close(p: int, q: int) -> bool:
        return min((p - q) % m, (q - p) % m) <= near

    for c, i, j in scored:
        if any((close(i, a) and close(j, b)) or (close(i, b) and close(j, a)) for a, b, _ in picked):
            continue
        picked.append((i, j, c))
        if len(picked) >= WAYS:
            break
    return picked


def satin_fill(outline: Sequence, way: int = 0, tips: Sequence[Sequence[float]] | None = None) -> dict[str, Any]:
    """The two rails (sides) of a satin filling the shape `outline` (pen points, mm). `way` picks
    the tips: 0 is the best, then the others in order (it wraps round). `tips`: two points (mm) to
    use as the tips instead, the satin running from the first to the second (the direction dots
    dragged round the outline). Returns {"rail_a", "rail_b" (pen points, same count), "widest_mm", "ways"}."""
    ring = _ring(outline)
    length = float(np.hypot(*np.diff(np.vstack([ring, ring[:1]]), axis=0).T).sum())
    m = int(min(480, max(80, length / 0.6)))
    pts = _resample(ring, m)
    if tips is not None:
        if len(tips) != 2:
            raise SatinFillError("Give the satin's two tips")
        near = [int(np.argmin(np.hypot(pts[:, 0] - float(t[0]), pts[:, 1] - float(t[1])))) for t in tips]
        i, j = near
        if min((j - i) % m, (i - j) % m) < max(2, int(m * 0.05)):
            raise SatinFillError("Put the satin's two tips further apart round the shape")
        ways: list[tuple[int, int, float]] = [(i, j, 0.0)]
    else:
        ways = _ways(pts)
        if not ways:
            raise SatinFillError("This shape can't be filled with one satin")
        i, j, _ = ways[way % len(ways)]
    a, b = _sides(pts, i, j)
    # Pair the sides on points about 1 mm apart, then keep a rung every RUNG_MM along side a.
    step = max(0.8, length / 400)
    ta, tb = _thin(a, step), _thin(b, step)
    match = _pair_up(ta, tb)
    # Start and end where the shape is wide enough to sew: at the very tips the sides meet, and a
    # stitch there would be widened and pile up (the pull compensation covers the tip).
    wide = np.nonzero(np.hypot(*(ta - tb[match]).T) >= MIN_TIP_MM)[0]
    k0, k1 = (int(wide[0]), int(wide[-1])) if len(wide) >= 2 else (0, len(ta) - 1)
    seg = np.hypot(*np.diff(ta, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    turn_a = _turns(ta, 1) if len(ta) > 3 else np.zeros(len(ta))
    rungs = [k0]
    for k in range(k0 + 1, k1):
        if cum[k] - cum[rungs[-1]] >= RUNG_MM or turn_a[k] > CORNER_DEG:
            rungs.append(k)
    rungs.append(k1)
    rail_a: list[list[Any]] = []
    rail_b: list[list[Any]] = []
    last_b = -1
    for n, k in enumerate(rungs):
        kb = max(int(match[k]), last_b)
        # The first and last rungs: where the sides are first and last wide enough (the tips if not).
        if n == 0:
            kb = int(match[k0]) if k0 else 0
        elif n == len(rungs) - 1:
            kb = int(match[k1]) if k1 < len(ta) - 1 else len(tb) - 1
        last_b = kb
        end = n in (0, len(rungs) - 1)
        corner = "c" if end or turn_a[k] > CORNER_DEG else "s"
        pa, pb = ta[k], tb[kb]
        if rail_a and math.dist(rail_a[-1][:2], pa) < 0.15 and math.dist(rail_b[-1][:2], pb) < 0.15:
            continue
        rail_a.append([round(float(pa[0]), 2), round(float(pa[1]), 2), corner])
        rail_b.append([round(float(pb[0]), 2), round(float(pb[1]), 2), corner])
    widths = [math.dist(p[:2], q[:2]) for p, q in zip(rail_a, rail_b)]
    return {"rail_a": rail_a, "rail_b": rail_b, "widest_mm": round(max(widths), 2), "ways": len(ways)}


__all__ = ["SatinFillError", "satin_fill"]
