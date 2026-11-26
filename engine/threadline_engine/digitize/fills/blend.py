"""Blend: the shape's color fades into a second (and a third or fourth) across the rows. Each
color is its own rows, sewn as its own part in its own thread.

Across the shape, in the fill's turned frame, t runs 0 to 1 over its height. With two colors the
first has density rho * (1 - u) and the second rho * u, u = t ** gamma, gamma = 2 ** -balance
(so Balance moves where they meet); with three or more, triangular weights in u peak at the
start, evenly between and at the end. The weights always add up to 1, so together the colors
cover like one fill at the shape's density. A color's rows sit where its cumulative density
passes each half row (k - 1/2, as a one-color fill's first row lies half a row in from the edge).
Then rows of a color more than 4 mm from any other row of that color are dropped (a lone thread
across the other color would show), and a row within 0.15 mm of one of another color is moved
up to 0.15 mm away.

Written for LUDD from the Phase 6 spec (no code ported from other projects).
"""

from __future__ import annotations

import bisect
import dataclasses
from typing import Sequence

from shapely import affinity
from shapely.geometry import Point as ShapelyPoint

from . import FillPattern, Param, get, register

LONE_MM = 4.0  # a row further than this from every other row of its color is dropped
APART_MM = 0.15  # rows of different colors are at least this far apart
ONE_COLOR = ("This blend has only one color, so it sews as a plain fill. Add a second color under Pattern "
             "to make it fade.")
_STEPS = 4096  # the cumulative density is tabled at this many steps across the shape


def _r(v: float) -> float:
    """Rounded for a comparison, so the last digit of a sum never decides one (every computer
    keeps the same rows)."""
    return round(v, 6)


def _weights(u: float, colors: int) -> list[float]:
    """How much of the fill each color is at warped position u (0 to 1); they add up to 1."""
    if colors == 1:
        return [1.0]
    span = colors - 1
    return [max(0.0, 1.0 - abs(u * span - c)) for c in range(colors)]


def _cumulative(params, colors: int) -> list[list[float]]:
    """Per color, its share of the rows from t = 0 to t = i / _STEPS (trapezoids)."""
    gamma = 2.0 ** (-params.value("blend_balance"))
    table = [[0.0] * (_STEPS + 1) for _ in range(colors)]
    prev = _weights(0.0, colors)
    for i in range(1, _STEPS + 1):
        here = _weights((i / _STEPS) ** gamma, colors)
        for c in range(colors):
            table[c][i] = table[c][i - 1] + (prev[c] + here[c]) / (2 * _STEPS)
        prev = here
    return table


def _where(cum: Sequence[float], share: float) -> float:
    """The t (0 to 1) at which a color's cumulative share reaches `share`."""
    i = bisect.bisect_left(cum, share)
    if i <= 0:
        return 0.0
    if i > _STEPS:
        return 1.0
    a, b = cum[i - 1], cum[i]
    f = (share - a) / (b - a) if b > a else 0.0
    return (i - 1 + f) / _STEPS


def fade_heights(miny: float, maxy: float, params, colors: int) -> list[list[float]]:
    """Each color's rows where its density puts them, before lone rows are dropped and close ones
    moved apart: heights in the turned frame, lowest first, strictly inside miny..maxy."""
    height = maxy - miny
    rows_total = height / params.spacing_mm
    out: list[list[float]] = []
    for cum in _cumulative(params, colors):
        total = cum[-1] * rows_total
        ys = []
        k = 1
        while _r(k - 0.5) < _r(total):
            t = _where(cum, (k - 0.5) / rows_total)
            y = maxy - t * height if params.blend_flip else miny + t * height
            if _r(miny) < _r(y) < _r(maxy):
                ys.append(y)
            k += 1
        out.append(sorted(ys))
    return out


def _drop_lone(rows: list[list[float]]) -> list[list[float]]:
    out = []
    for ys in rows:
        out.append([y for i, y in enumerate(ys)
                    if any(_r(abs(y - ys[j])) <= LONE_MM for j in (i - 1, i + 1) if 0 <= j < len(ys))])
    return out


def _apart(rows: list[list[float]], maxy: float) -> list[list[float]]:
    """Each row at least APART_MM above every row of another color placed before it (lowest
    first, ties by color): a row too close is moved up."""
    tagged = sorted(((_r(y), c, y) for c, ys in enumerate(rows) for y in ys))
    top = [None] * len(rows)  # the highest row placed so far, per color
    out: list[list[float]] = [[] for _ in rows]
    for _, c, y in tagged:
        others = [t for d, t in enumerate(top) if d != c and t is not None]
        below = max(others) if others else None
        if below is not None and _r(y - below) < APART_MM:
            y = below + APART_MM
        if _r(y) >= _r(maxy):
            continue
        out[c].append(y)
        top[c] = y if top[c] is None else max(top[c], y)
    return [sorted(ys) for ys in out]


def row_heights(miny: float, maxy: float, params, colors: int) -> list[list[float]]:
    """Each color's rows: heights in the fill's turned frame, lowest first, strictly inside
    miny..maxy (the turned bounds of all the shape's pieces together). Never all empty: a shape too
    small to blend gets plain rows in the first color."""
    rows = fade_heights(miny, maxy, params, colors)
    if colors > 1:
        rows = _drop_lone(_apart(_drop_lone(rows), maxy))
    if not any(rows):
        s = params.spacing_mm
        plain = [miny + s * (k + 0.5) for k in range(int((maxy - miny) / s) + 1) if _r(miny + s * (k + 0.5)) < _r(maxy)]
        rows = [plain or [(miny + maxy) / 2]] + [[] for _ in range(colors - 1)]
    return rows


def _start(piece, params):
    """Where a piece begins: its outline's first point, or the edge nearest the chosen start."""
    if params.start_mm is None:
        return tuple(piece.exterior.coords[0])
    near = piece.exterior.interpolate(piece.exterior.project(ShapelyPoint(params.start_mm)))
    return (near.x, near.y)


def _parts(pieces, params):
    """Each color's rows as one part, in its thread slot, colors in order. Worked out with the
    shape moved to the origin and moved back after, so its needle points move with it."""
    ox = min(p.bounds[0] for p in pieces)
    oy = min(p.bounds[1] for p in pieces)

    def by(pt, sign):
        return None if pt is None else (pt[0] + sign * ox, pt[1] + sign * oy)

    moved = dataclasses.replace(params, start_mm=by(params.start_mm, -1), end_mm=by(params.end_mm, -1),
                                carve=tuple(tuple(by(q, -1) for q in line) for line in params.carve))
    parts = _sewn([affinity.translate(p, -ox, -oy) for p in pieces], moved)
    return [([(x + ox, y + oy, k) for x, y, k in recs], said, slot) for recs, said, slot in parts]


def _sewn(pieces, params):
    from .. import rows as row_hooks
    from ..stitches import STITCH, _append, fill_underlay, join_pieces, tatami, travel
    from ..paths import dist

    colors = 1 + len(params.blend)
    angle = params.angle_deg
    turned = [affinity.rotate(p, -angle, origin=(0, 0)).bounds for p in pieces]
    miny, maxy = min(b[1] for b in turned), max(b[3] for b in turned)
    rows = row_heights(miny, maxy, params, colors)
    spec = get(params.pattern)
    settings = {"random": params.random_pct / 100, **row_hooks.hooks(params, angle)}
    said = list(row_hooks.notes(params, angle))
    if colors == 1:
        said.append(ONE_COLOR)
    sewn = [c for c, ys in enumerate(rows) if ys]
    pad = params.pull_comp_mm / 2
    parts = []
    pos = None
    for c in sewn:
        out = []
        for k, piece in enumerate(pieces):
            last = c == sewn[-1] and k == len(pieces) - 1
            end_near = params.end_mm if last else None
            under = []
            if c == 0:
                start = _start(piece, params)
                under = fill_underlay(piece, params, spec, start)
                here = (under[-1][0], under[-1][1]) if under else start
            else:
                here = pos if pos is not None else _start(piece, params)
            top = tatami(piece, angle, params.spacing_mm, params.stitch_mm, pad, here, travel_within=piece,
                         row_ys=rows[c], end_near=end_near, **settings)
            if not top:
                continue
            plain_end = (top[-1][0], top[-1][1])
            if params.reverse and end_near is None and all(r[2] == STITCH for r in top):
                top = top[::-1]  # the same stitches, sewn from the other end
            recs = list(under)
            if recs:
                recs += travel(here, (top[0][0], top[0][1]), piece.buffer(pad + 0.05))
            _append(recs, top)
            if end_near is not None:
                # As a one-color fill does: a short run along the last row takes the needle exactly
                # to the end point when it is part way along an edge.
                edge = piece.boundary
                q = edge.interpolate(edge.project(ShapelyPoint(end_near)))
                if dist(recs[-1][:2], (q.x, q.y)) > 0.3:
                    tail = travel(recs[-1][:2], (q.x, q.y), piece.buffer(pad + 0.05))
                    if all(r[2] == STITCH for r in tail):
                        recs += tail
            out = join_pieces(out, recs)
            # The next color starts where this one ends when sewn forwards: sewn in reverse, each
            # color is then the forward one turned round, and still starts where the last ended.
            pos = plain_end
        if out:
            parts.append((out, said if not parts else [], c))
    return parts or [([], said, 0)]


register(FillPattern("blend", "rows", params={"blend_balance": Param(0.0, -1.0, 1.0, "Balance", unit="")},
                     parts=_parts, rows=lambda p: {}, step_mm2=lambda p: p.spacing_mm * p.stitch_mm,
                     tatami_underlay=False, auto_underlay=lambda level: []))
