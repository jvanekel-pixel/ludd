"""Blend: the shape's color fades into a second (and a third or fourth) across the rows. Each
color is its own rows, sewn as its own part in its own thread.

The rows are exactly a one-color fill's rows (in each piece, half a row in from its lowest edge,
then one spacing apart), so together the colors cover like one fill. Each row is then given to a
color. Across the shape, in the fill's turned frame, t runs 0 to 1 over the height of all the
pieces together. With two colors the first has weight 1 - u and the second u, u = t ** gamma,
gamma = 2 ** -balance (so Balance moves where they meet); with three or more, triangular weights
in u peak at the start, evenly between and at the end. The weights add up to 1.

Rows are given out by error diffusion, lowest row first: each color adds its weight at the row's
height to its tally, the color with the highest tally gets the row (equal tallies: the lower
thread slot) and its tally drops by one row. A color whose last row is more than LONE_MM away (or
that has none yet) keeps its turn for the next row too, so no color is ever sewn as a lone row
across another. No color is left out while there is room: each color not yet sewn is due by its
last row with any weight, and a row goes only to a color that still lets every unsewn one start
a pair by its due row (soonest due first), so with two rows per color every color is sewn. A
color takes a row only where it has weight, unless nothing else fits. Weights are whole numbers
(millionths), so no last digit decides a row.

Written for LUDD from the Phase 6 spec (no code ported from other projects).
"""

from __future__ import annotations

import dataclasses

from shapely import affinity
from shapely.geometry import Point as ShapelyPoint

from . import FillPattern, Param, get, register

LONE_MM = 4.0  # a color whose last row is further than this keeps its turn for two rows
ONE_COLOR = ("This blend has only one color, so it sews as a plain fill. Add a second color under Pattern "
             "to make it fade.")
_ORDINALS = ("first", "second", "third", "fourth")
_UNIT = 1_000_000  # weights in millionths of a row


def too_few(missing: list[int]) -> str:
    """The warning when some colors get no rows at all (`missing`: their slots)."""
    names = [f"the {_ORDINALS[c]} color" for c in missing]
    which = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return (f"This shape has too few rows to blend all its colors, so {which} is not sewn. Make the "
            "shape bigger or lower the spacing (a smaller number) to fit more rows.")


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


def _whole_weights(t: float, gamma: float, colors: int) -> list[int]:
    """The weights at t as whole millionths that add up to exactly one row. Rounded before and
    after the power, so the last digit of a power never changes them."""
    t = min(1.0, max(0.0, round(t, 9)))
    u = round(t ** gamma, 9)
    w = [round(v * _UNIT) for v in _weights(u, colors)]
    big = max(range(colors), key=lambda c: (w[c], -c))  # the largest takes the rounding (ties: lower slot)
    w[big] += _UNIT - sum(w)
    return w


def plain_rows(miny: float, maxy: float, spacing: float) -> list[float]:
    """A one-color fill's rows between miny and maxy, as tatami() places them."""
    ys = []
    y = miny + spacing / 2
    while y < maxy:
        ys.append(y)
        y += spacing
    return ys


def assign(ys: list[float], params, colors: int, lo: float, hi: float) -> list[int]:
    """Which color each row (heights `ys`, lowest first) goes to; the fade runs from lo to hi."""
    if colors == 1:
        return [0] * len(ys)
    gamma = 2.0 ** (-params.value("blend_balance"))
    height = hi - lo
    n = len(ys)
    weights = [_whole_weights(((hi - y) if params.blend_flip else (y - lo)) / height if height > 0 else 0.5,
                              gamma, colors) for y in ys]
    # The latest row each color can start its first pair on: its last row with any weight (the
    # pair's second row may lie just past it), and never the very last row.
    due = [min(n - 2, max((i for i in range(n) if weights[i][c] > 0), default=-1)) for c in range(colors)]
    tally = [0] * colors
    last: list[float | None] = [None] * colors
    held = None
    out = []
    for i, y in enumerate(ys):
        for c, w in enumerate(weights[i]):
            tally[c] += w

        def alone(c: int) -> bool:  # a row of c here would be lone unless it keeps the next row too
            return last[c] is None or _r(y - last[c]) > LONE_MM

        if held is not None:
            c, held = held, None
        else:
            more = i + 1 < n

            def fits(c: int) -> bool:
                """After c takes this row (and the next, if it must keep its turn), every color not
                yet sewn can still start a pair by its due row, soonest due first."""
                if alone(c) and not more:
                    return False
                at = i + (2 if alone(c) else 1)
                for d in sorted((d for d in range(colors) if last[d] is None and d != c), key=lambda d: (due[d], d)):
                    if at > due[d]:
                        return False
                    at += 2
                return True

            choices = ([c for c in range(colors) if fits(c)]
                       or [c for c in range(colors) if more or not alone(c)] or list(range(colors)))
            # A color is sewn where it has weight; one without any here only when nothing else fits.
            choices = [c for c in choices if weights[i][c] > 0] or choices
            c = max(choices, key=lambda c: (tally[c], -c))  # equal tallies: the lower thread slot
            if more and alone(c):
                held = c
        tally[c] -= _UNIT
        last[c] = y
        out.append(c)
    return out


def row_heights(miny: float, maxy: float, params, colors: int,
                span: tuple[float, float] | None = None) -> list[list[float]]:
    """Each color's rows in one piece whose turned bounds are miny..maxy: heights in the fill's
    turned frame, lowest first. Together they are a one-color fill's rows. `span`: where the fade
    runs (the turned bounds of all the shape's pieces together; default the piece's own). A piece
    too thin for a row gets one across its middle, in the color there."""
    ys, owners = _piece_rows(miny, maxy, params, colors, span)
    return [[y for y, o in zip(ys, owners) if o == c] for c in range(colors)]


def _piece_rows(miny, maxy, params, colors, span=None):
    """A piece's rows, lowest first, and the color each goes to."""
    lo, hi = span if span is not None else (miny, maxy)
    ys = plain_rows(miny, maxy, params.spacing_mm) or [(miny + maxy) / 2]
    return ys, assign(ys, params, colors, lo, hi)


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


def _numbered(hook, index):
    """A row hook (weave, feather) called with the row's number among all the colors' rows of its
    piece, as in a one-color fill, rather than its number among its own color's rows."""
    if hook is None:
        return None
    return lambda row, *rest: hook(index[row], *rest)


def _sewn(pieces, params):
    from .. import rows as row_hooks
    from ..stitches import STITCH, _append, fill_underlay, join_pieces, tatami, travel
    from ..paths import dist

    colors = 1 + len(params.blend)
    angle = params.angle_deg
    turned = [affinity.rotate(p, -angle, origin=(0, 0)).bounds for p in pieces]
    span = (min(b[1] for b in turned), max(b[3] for b in turned))
    rows = [_piece_rows(b[1], b[3], params, colors, span) for b in turned]  # per piece: heights, owners
    spec = get(params.pattern)
    hooks = row_hooks.hooks(params, angle)
    said = list(row_hooks.notes(params, angle))
    if colors == 1:
        said.append(ONE_COLOR)
    sewn = [c for c in range(colors) if any(c in owners for _, owners in rows)]
    if len(sewn) < colors:
        said.append(too_few([c for c in range(colors) if c not in sewn]))
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
            ys, owners = rows[k]
            index = [n for n, o in enumerate(owners) if o == c]  # these rows' numbers in the piece
            mine = [ys[n] for n in index]
            settings = {**hooks, "random": hooks.get("random", params.random_pct / 100),
                        "offsets": _numbered(hooks.get("offsets", row_hooks.weave.standard), index)}
            if "end_shift" in hooks:
                settings["end_shift"] = _numbered(hooks["end_shift"], index)
            top = tatami(piece, angle, params.spacing_mm, params.stitch_mm, pad, here, travel_within=piece,
                         row_ys=mine, end_near=end_near, **settings)
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
