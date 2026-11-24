"""Stitch generation for digitized objects: running stitch, satin column, tatami fill.

Written from first principles for LUDD (no code ported from other projects).
Coordinates are mm. Output is a list of (x, y, cmd) with cmd STITCH, JUMP or TRIM.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

import pyembroidery as pe
import shapely
from shapely import affinity
from shapely.geometry import LineString, Point as ShapelyPoint, Polygon
from shapely.ops import substring

from .paths import Point, corner_indices, cumulative, dist, flatten, point_at, resample, sharp_points
from .patterns import (FILL_PATTERNS, MOTIFS, contour_paths, cross_paths, gradient_ys, motif_points, nearest_rotation,
                       polygons, stipple_paths, wave_offset)

STITCH, JUMP, TRIM = pe.STITCH, pe.JUMP, pe.TRIM
Rec = tuple[float, float, int]

TIE_MM = 0.7
MIN_STITCH_MM = 0.3
TRAVEL_STITCH_MM = 2.5
TRIM_TRAVEL_MM = 3.0  # travels longer than this are trimmed instead of left as a thread
LONG_STITCH_MM = 7.0  # longer stitches lie loose and snag (quality.LONG_MM says the same)
MAX_SHAPE_MM = 1000.0  # far bigger than any hoop: a typing slip, which would take minutes to fill
MAX_STITCHES = 400_000  # per object; a whole 4x4 design is usually 5,000 to 30,000


class DigitizeError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


# ---------------------------------------------------------------- helpers


def _unit(dx: float, dy: float) -> Point:
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n > 1e-12 else (1.0, 0.0)


def stitch_run(points: Sequence[Point], min_mm: float = MIN_STITCH_MM, prev: Sequence | None = None) -> list[Rec]:
    """Points as stitches, dropping ones closer than `min_mm` to the previous (or to `prev`, the
    needle's position before these points)."""
    out: list[Rec] = []
    last = (prev[0], prev[1]) if prev is not None else None
    for p in points:
        if last is not None and dist(last, p) < min_mm:
            continue
        out.append((p[0], p[1], STITCH))
        last = (p[0], p[1])
    return out


def _min_step(spacing: float) -> float:
    """Shortest stitch kept in rows or satin columns `spacing` apart. Normally MIN_STITCH_MM; at a
    spacing under 0.4 mm it shrinks with it, so the step from one row or rung to the next isn't
    thrown away (that left fill rows short of the edge and made dense satins sparser)."""
    return min(MIN_STITCH_MM, 0.75 * spacing)


def _append(out: list[Rec], recs: Sequence[Rec]) -> None:
    """Add `recs` after `out`, without a second needle drop in the same hole where they meet."""
    if out and recs and out[-1][2] == STITCH and recs[0][2] == STITCH and dist(out[-1][:2], recs[0][:2]) < 1e-6:
        recs = recs[1:]
    out.extend(recs)


def _subdivide(points: Sequence[Point], max_mm: float) -> list[Point]:
    """Points with extra, evenly spaced ones on every step longer than `max_mm`."""
    out: list[Point] = list(points[:1])
    for a, b in zip(points, points[1:]):
        d = dist(a, b)
        n = math.ceil(d / max_mm - 1e-9) if d > max_mm else 1
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(1, n)]
        out.append(b)
    return out


def _finite(d: dict[str, Any], key: str, default: float) -> float:
    """A number setting: missing or null gives the default; anything not a finite number is refused."""
    v = d.get(key)
    if v is None:
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise DigitizeError(f"The setting {key} must be a number") from None
    if not math.isfinite(f):
        raise DigitizeError(f"The setting {key} must be a number")
    return f


def check_points(points: Sequence[Point], what: str = "shape") -> None:
    """Refuse points that aren't numbers, and shapes far bigger than any hoop."""
    if not all(math.isfinite(c) for p in points for c in p):
        raise DigitizeError(f"This {what} has a point that isn't a number")
    if points:
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        size = max(max(xs) - min(xs), max(ys) - min(ys))
        if size > MAX_SHAPE_MM:
            raise DigitizeError(f"This {what} is {size:.0f} mm across, far bigger than any hoop. Make it smaller.")


def tie_in(recs: list[Rec]) -> list[Rec]:
    """Lock the start: first stitch, a little way toward the second, and back."""
    s = [r for r in recs if r[2] == STITCH]
    if len(s) < 2:
        return recs
    i = recs.index(s[0])
    a, b = s[0], s[1]
    u = _unit(b[0] - a[0], b[1] - a[1])
    t = min(TIE_MM, dist((a[0], a[1]), (b[0], b[1])) * 0.8)
    lock = [(a[0] + u[0] * t, a[1] + u[1] * t, STITCH), (a[0], a[1], STITCH)]
    return recs[: i + 1] + lock + recs[i + 1 :]


def tie_off(recs: list[Rec]) -> list[Rec]:
    """Lock the end: last stitch, a little way back, and forward again."""
    s = [r for r in recs if r[2] == STITCH]
    if len(s) < 2:
        return recs
    a, b = s[-1], s[-2]
    u = _unit(b[0] - a[0], b[1] - a[1])
    t = min(TIE_MM, dist((a[0], a[1]), (b[0], b[1])) * 0.8)
    # The lock goes right after the last stitch, before any trailing trim or jump: after a jump
    # it would sew one long stitch back from where the needle jumped to (QA2 S1).
    i = len(recs) - 1
    while recs[i][2] != STITCH:
        i -= 1
    return recs[: i + 1] + [(a[0] + u[0] * t, a[1] + u[1] * t, STITCH), (a[0], a[1], STITCH)] + recs[i + 1 :]


class Zone:
    """The area travel stays inside, with the shapes travel() needs worked out once (a fill joins
    hundreds of regions; re-buffering the outline for each took seconds on wobbly shapes)."""

    def __init__(self, poly: Polygon):
        self.poly = poly
        self.cover = poly.buffer(1e-6)
        shapely.prepare(self.cover)
        self._rings: dict[float, list[LineString]] = {}

    def rings(self, inset: float = 0.3) -> list[LineString]:
        """The edges (outside and holes) of the shape shrunk by `inset` mm, which travel can follow.
        Every piece counts: a neck under twice the inset splits the shrunk shape, and giving up
        then turned all travel in the fill into trimmed jumps (QA2 S1)."""
        if inset not in self._rings:
            self._rings[inset] = [LineString(r.coords) for piece in polygons(self.poly.buffer(-inset))
                                  for r in [piece.exterior, *piece.interiors]]
        return self._rings[inset]


def _zone(inside: "Polygon | Zone") -> Zone:
    return inside if isinstance(inside, Zone) else Zone(inside)


def _edge_route(a: Point, b: Point, inside: "Polygon | Zone") -> list[Point] | None:
    """A path from a to b that follows one edge of the shape (outside or a hole), staying inside,
    or None. Used to travel around holes instead of jumping over them."""
    z = _zone(inside)
    # 0.3 mm in from the edge first; only when that can't connect a and b (they sit either side
    # of a neck narrower than 0.6 mm) hug the edge itself, which still crosses the neck.
    return _ring_route(a, b, z, 0.3) or _ring_route(a, b, z, 0.05)


def _ring_route(a: Point, b: Point, z: "Zone", inset: float) -> list[Point] | None:
    pa, pb = ShapelyPoint(a), ShapelyPoint(b)
    best: list[Point] | None = None
    for line in z.rings(inset):
        total = line.length
        # Step straight onto the ring, follow it, step straight off. The coverage check below
        # rejects routes whose straight legs would leave the shape.
        sa, sb = line.project(pa), line.project(pb)

        def arc(s0: float, s1: float) -> list[Point]:
            """Ring coordinates walking forward from s0 to s1, wrapping past the ring's start."""
            if s0 <= s1:
                return list(substring(line, s0, s1).coords)
            return list(substring(line, s0, total).coords) + list(substring(line, 0, s1).coords)[1:]

        for path in (arc(sa, sb), arc(sb, sa)[::-1]):
            route = [a, *path, b]
            ls = LineString(route)
            if z.cover.covers(ls) and (best is None or ls.length < LineString(best).length):
                best = route
    return best


def travel(a: Point, b: Point, inside: "Polygon | Zone | None" = None) -> list[Rec]:
    """Move from a to b inside `inside` with running stitches that later stitching covers:
    straight if possible, else around the edge of a hole. Otherwise jump (trimmed when long)."""
    d = dist(a, b)
    if d < MIN_STITCH_MM:
        return []
    if inside is not None:
        route = _route(a, b, _zone(inside))
        if route:
            return _route_stitches(a, route)
    out: list[Rec] = []
    if d > TRIM_TRAVEL_MM:
        out.append((a[0], a[1], TRIM))
    out.append((b[0], b[1], JUMP))
    return out


def _route(a: Point, b: Point, z: "Zone") -> list[Point] | None:
    """A way from a to b inside the zone: straight if it can, else along one of its edges."""
    return [a, b] if z.cover.covers(LineString([a, b])) else _edge_route(a, b, z)


def _route_stitches(a: Point, route: list[Point]) -> list[Rec]:
    """Running stitches along a route from a (not included), ending exactly on its last point."""
    # Keep the route's corners, so stitches don't cut across a notch outside the shape.
    pts = resample(route, TRAVEL_STITCH_MM, sharp_points(route))
    out_pts: list[Point] = []
    for p in pts[1:]:
        if dist(out_pts[-1] if out_pts else a, p) >= MIN_STITCH_MM:
            out_pts.append(p)
        elif p == pts[-1] and out_pts:
            out_pts[-1] = p  # always end exactly on b
    return [(x, y, STITCH) for x, y in out_pts]


# ---------------------------------------------------------------- running stitch


@dataclass
class RunParams:
    style: str = "single"  # single | triple (whole line 3x) | bean (each stitch 3x) | motif
    stitch_mm: float = 2.5
    motif: str = "wave"  # for style "motif": wave | zigzag | scallop | blanket
    motif_mm: float = 4.0  # length of one repeat
    motif_width_mm: float = 2.5

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "RunParams":
        d = d or {}
        p = cls(style=str(d.get("style", "single")), stitch_mm=_finite(d, "stitch_mm", 2.5),
                motif=str(d.get("motif", "wave")), motif_mm=_finite(d, "motif_mm", 4.0),
                motif_width_mm=_finite(d, "motif_width_mm", 2.5))
        if p.style not in ("single", "triple", "bean", "motif"):
            raise DigitizeError(f"Unknown running stitch style: {p.style}")
        if p.style == "motif":
            if p.motif not in MOTIFS:
                raise DigitizeError(f"Unknown motif: {p.motif}")
            if not 1.5 <= p.motif_mm <= 20 or not 0.5 <= p.motif_width_mm <= 10:
                raise DigitizeError("A motif repeats every 1.5 to 20 mm and is 0.5 to 10 mm wide")
        if not 0.5 <= p.stitch_mm <= 12:
            raise DigitizeError("Stitch length must be between 0.5 and 12 mm")
        return p


def run_points(nodes: Sequence, stitch_mm: float, closed: bool = False) -> list[Point]:
    poly, idx = flatten(nodes, closed)
    if closed and poly:
        poly = poly + [poly[0]]
        idx = idx + [len(poly) - 1]
    return resample(poly, stitch_mm, corner_indices(nodes, idx[: len(nodes)]))


def running(nodes: Sequence, params: RunParams, closed: bool = False, start: Point | None = None) -> list[Rec]:
    if params.style == "motif":
        # The motif's corners are the needle points; long sides are split to the stitch length.
        pts = motif_points(nodes, params.motif, params.motif_mm, params.motif_width_mm, closed)
        return stitch_run(resample(pts, max(params.stitch_mm, 1.0), list(range(len(pts)))))
    pts = run_points(nodes, params.stitch_mm, closed)
    if len(pts) < 2:
        return stitch_run(pts)
    if closed and start is not None:
        pts = _ring_from(pts, start)  # a border starts (and ends) exactly where chosen
    if params.style == "triple":
        pts = pts + pts[-2::-1] + pts[1:]
    elif params.style == "bean":
        out = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            out += [b, a, b]
        pts = out
    return stitch_run(pts)


# ---------------------------------------------------------------- satin column


UNDERLAY_LEVELS = ("light", "normal", "heavy")


@dataclass
class SatinParams:
    spacing_mm: float = 0.4  # distance between stitches along the column
    pull_comp_mm: float = 0.2  # total widening (split between the two sides)
    underlay: tuple[str, ...] | None = ("center",)  # any of: center, edge, zigzag; None: chosen by width
    underlay_level: str = "normal"  # for automatic underlay: light | normal | heavy (from the fabric)
    comp_by_width: bool = False  # scale pull compensation with the column's width at each stitch
    auto_widen: bool = False  # widen spots too thin to stitch
    split_mm: float = 0.0  # split stitches longer than this into shorter, staggered ones (0: off)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "SatinParams":
        d = d or {}
        u = d.get("underlay")
        if u is None:
            u = ["center"]  # missing or null: the default (QA2 S6)
        if u != "auto" and (not isinstance(u, (list, tuple)) or not all(isinstance(x, str) for x in u)):
            raise DigitizeError("The setting underlay must be a list of underlay names")
        p = cls(
            spacing_mm=_finite(d, "spacing_mm", 0.4),
            pull_comp_mm=_finite(d, "pull_comp_mm", 0.2),
            underlay=None if u == "auto" else tuple(u),
            underlay_level=str(d.get("underlay_level", "normal")),
            comp_by_width=bool(d.get("comp_by_width", False)),
            auto_widen=bool(d.get("auto_widen", False)),
            split_mm=_finite(d, "split_mm", 0.0),
        )
        if p.split_mm and not 2 <= p.split_mm <= 12:
            raise DigitizeError("Split satin stitches longer than 2 to 12 mm")
        if p.underlay_level not in UNDERLAY_LEVELS:
            raise DigitizeError(f"Unknown underlay amount: {p.underlay_level}")
        if not 0.15 <= p.spacing_mm <= 3:
            raise DigitizeError("Satin spacing must be between 0.15 and 3 mm")
        if not 0 <= p.pull_comp_mm <= 2:
            raise DigitizeError("Pull compensation must be between 0 and 2 mm")
        bad = set(p.underlay or ()) - {"center", "edge", "zigzag"}
        if bad:
            raise DigitizeError(f"Unknown satin underlay: {', '.join(sorted(bad))}")
        return p


SATIN_MAX_WIDTH_MM = LONG_STITCH_MM  # wider satins (unsplit) snag and loosen; split them or use a fill
SATIN_MIN_WIDTH_MM = 0.8
SATIN_WIDEN_TO_MM = 1.0  # auto-widen: thinner spots are widened to this


def auto_satin_underlay(width_mm: float, level: str) -> tuple[str, ...]:
    """Underlay for a column of this (typical) width: narrow columns need little, wide ones a
    firm base; stretchy and lofty fabrics (heavy) need more."""
    if level == "light":
        return () if width_mm < 2 else ("center",) if width_mm < 5 else ("edge",)
    if level == "heavy":
        return ("center",) if width_mm < 2 else ("edge", "zigzag") if width_mm < 5 else ("center", "edge", "zigzag")
    return ("center",) if width_mm < 2 else ("edge",) if width_mm < 5 else ("edge", "zigzag")


def width_comp(base_mm: float, width_mm: float) -> float:
    """Pull compensation for a column this wide: a 4 mm column gets the base amount, wider
    columns more (they pull in more), narrow ones less."""
    return base_mm * min(max(0.6 + 0.1 * width_mm, 0.6), 2.0)


def _rail_sections(rail: Sequence, rungs: int) -> list[tuple[list[Point], list[float]]]:
    """Split a rail into sections between consecutive nodes (one rung per node)."""
    poly, idx = flatten(rail)
    out = []
    for k in range(rungs - 1):
        part = poly[idx[k] : idx[k + 1] + 1]
        out.append((part, cumulative(part)))
    return out


def satin_pairs(rail_a: Sequence, rail_b: Sequence, spacing: float) -> list[tuple[Point, Point]]:
    """Matching points on both rails. Each pair of nodes (a[k], b[k]) is a rung; between rungs
    both rails are walked at the same fraction of their length, so stitches never cross."""
    if len(rail_a) != len(rail_b) or len(rail_a) < 2:
        raise DigitizeError("A satin column needs the same number of points on each side, at least two")
    pairs: list[tuple[Point, Point]] = []
    for (pa, ca), (pb, cb) in zip(_rail_sections(rail_a, len(rail_a)), _rail_sections(rail_b, len(rail_b))):
        la, lb = ca[-1], cb[-1]
        mid_len = (la + lb) / 2
        n = max(1, math.ceil(mid_len / spacing))
        start = 1 if pairs else 0
        for i in range(start, n + 1):
            t = i / n
            pairs.append((point_at(pa, ca, la * t), point_at(pb, cb, lb * t)))
    return pairs


def _widen(a: Point, b: Point, to: float) -> tuple[Point, Point]:
    """Push both ends apart (about the middle) so the stitch is `to` long."""
    w = dist(a, b)
    if w >= to:
        return a, b
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    ux, uy = _unit(b[0] - a[0], b[1] - a[1]) if w > 1e-9 else (1.0, 0.0)
    return (mx - ux * to / 2, my - uy * to / 2), (mx + ux * to / 2, my + uy * to / 2)


RIBBON_MIN_WIDTH_MM = 0.5
RIBBON_MAX_WIDTH_MM = 12.0
MITER_LIMIT = 2.0  # at a sharp corner the edges reach at most this many half-widths out


def ribbon_pairs(nodes: Sequence, width_mm: float, spacing: float, closed: bool = False) -> list[tuple[Point, Point]]:
    """A satin ribbon: stitches straight across a centre line, `width_mm` wide, `spacing` apart
    along it. Each stitch is square to the line; at corners it follows the bisector, so the
    edges stay `width_mm` apart (up to a miter limit)."""
    return _ribbon(nodes, width_mm, spacing, closed)[0]


def _crossings(a0: Point, b0: Point, a1: Point, b1: Point) -> bool:
    """Do the stitches a0-b0 and a1-b1 cross each other?"""
    def side(p: Point, q: Point, r: Point) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    return side(a1, b1, a0) * side(a1, b1, b0) < 0 and side(a0, b0, a1) * side(a0, b0, b1) < 0


def _crossing_rungs(pairs: Sequence[tuple[Point, Point]], skip: set[int] = frozenset()) -> int:
    """How many neighbouring stitches cross each other (a column folding over itself), not
    counting those next to a sharp corner in `skip`, where a mitred corner fans them on purpose."""
    return sum(1 for i, (p, q) in enumerate(zip(pairs, pairs[1:]))
               if not ({i - 1, i, i + 1, i + 2} & skip) and _crossings(*p, *q))


FOLD_WARNING = ("This satin curves more tightly than it is wide, so the stitches bunch up on the inside of the "
                "curve. Make it narrower or the curve wider.")


def _ribbon(nodes: Sequence, width_mm: float, spacing: float, closed: bool = False) -> tuple[list[tuple[Point, Point]], set[int]]:
    """ribbon_pairs, plus the indices of the stitches at sharp corners."""
    if len(nodes) < 2:
        raise DigitizeError("A satin ribbon needs at least two points")
    if not RIBBON_MIN_WIDTH_MM <= width_mm <= RIBBON_MAX_WIDTH_MM:
        raise DigitizeError(f"Satin width must be between {RIBBON_MIN_WIDTH_MM} and {RIBBON_MAX_WIDTH_MM:.0f} mm")
    poly, idx = flatten(nodes, closed)
    keep = corner_indices(nodes, idx)
    if closed:
        poly = [*poly, poly[0]]
        keep = [k for k in keep if k != 0] + [0, len(poly) - 1]
    pts = resample(poly, spacing, keep)
    # Drop points that landed on top of each other (a corner hit exactly by the resampling).
    pts = [q for i, q in enumerate(pts) if i == 0 or dist(q, pts[i - 1]) > 1e-6]
    if len(pts) < 2:
        raise DigitizeError("This satin ribbon is too short")
    n = len(pts)
    half = width_mm / 2

    def direction(a: Point, b: Point) -> Point:
        return _unit(b[0] - a[0], b[1] - a[1])

    pairs: list[tuple[Point, Point]] = []
    for i, q in enumerate(pts):
        if closed and (i == 0 or i == n - 1):
            d_in, d_out = direction(pts[-2], pts[-1]), direction(pts[0], pts[1])
        else:
            d_in = direction(pts[i - 1], q) if i > 0 else direction(q, pts[i + 1])
            d_out = direction(q, pts[i + 1]) if i < n - 1 else d_in
        tx, ty = d_in[0] + d_out[0], d_in[1] + d_out[1]
        tl = math.hypot(tx, ty)
        tx, ty = (tx / tl, ty / tl) if tl > 1e-9 else d_out
        nx, ny = -ty, tx
        # Miter: the cosine of half the turn between the incoming and outgoing directions.
        c = max(nx * -d_out[1] + ny * d_out[0], 1 / MITER_LIMIT)
        r = half / c
        pairs.append(((q[0] + nx * r, q[1] + ny * r), (q[0] - nx * r, q[1] - ny * r)))
    corner_pts = {poly[k] for k in keep}
    corners = {i for i, q in enumerate(pts) if q in corner_pts and 0 < i < n - 1}
    if closed:
        corners |= {0, n - 1} if poly[0] in corner_pts else set()
    return pairs, corners


def satin_with_ends(pairs: list[tuple[Point, Point]], params: SatinParams, start: Point | None = None,
                    end: Point | None = None) -> tuple[list[Rec], list[str]]:
    """A satin that starts and stops where chosen (the green and red dots), anywhere along it.

    It's sewn from one end to the other, as always, when that's enough. To stop part way along it's
    sewn in two parts that meet at the stop: from one end up to it, then (after a move along the
    middle of the part still to be sewn, which covers it) from the other end back to it. To start
    part way along, the needle first runs along the middle to the end it sews from, under the
    satin that then covers it."""
    n = len(pairs)
    if (start is None and end is None) or n < 4:
        return satin_from_pairs(pairs, params)
    mids = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in pairs]
    near = lambda p: min(range(n), key=lambda i: dist(mids[i], p))  # noqa: E731
    s = near(start) if start is not None else None
    if end is not None:
        k = near(end)
        if k <= 1:
            parts = [list(range(n - 1, -1, -1))]  # from the far end to the stop's end
        elif k >= n - 2:
            parts = [list(range(n))]
        else:
            # Two ways to meet at the stop: choose the one that starts at the end nearer the start.
            forward = [list(range(0, k + 1)), list(range(n - 1, k, -1))]
            backward = [list(range(n - 1, k - 1, -1)), list(range(0, k))]
            if s is None:
                parts = forward
            else:
                parts = forward if abs(s - 0) <= abs(s - (n - 1)) else backward
    else:
        parts = [list(range(n))] if s is None or s <= n - 1 - s else [list(range(n - 1, -1, -1))]

    out: list[Rec] = []
    warnings: list[str] = []

    def run_along(frm: Point, i: int, j: int, to: Point) -> list[Rec]:
        """Running stitches from `frm` along the middle of the satin, rung i to rung j, to `to`."""
        step = 1 if j >= i else -1
        path = [frm, *[mids[x] for x in range(i, j + step, step)], to]
        pts = resample(path, TRAVEL_STITCH_MM)
        return [(x, y, STITCH) for x, y in pts[1:] if dist((x, y), frm) > 1e-6]

    for idx in parts:
        recs, w = satin_from_pairs([pairs[i] for i in idx], params)
        warnings += [x for x in w if x not in warnings]
        if not recs:
            continue
        first = (recs[0][0], recs[0][1])
        if out:
            here = (out[-1][0], out[-1][1])
            out += run_along(here, near(here), idx[0], first)
        elif start is not None and s is not None:
            # Start on the satin itself: the point of its stitch nearest the chosen one (exactly the
            # dot's place when it's on the satin; a point off it, e.g. a dot left behind when its
            # points were moved, never makes a line across bare fabric), then run along the
            # middle, under the satin, to where it sews from.
            a, b = pairs[s]
            ab = (b[0] - a[0], b[1] - a[1])
            ll = ab[0] ** 2 + ab[1] ** 2
            t = max(0.0, min(1.0, ((start[0] - a[0]) * ab[0] + (start[1] - a[1]) * ab[1]) / ll)) if ll else 0.5
            on = (a[0] + ab[0] * t, a[1] + ab[1] * t)
            out += [(on[0], on[1], STITCH)]
            out += run_along(on, s, idx[0], first)
        _append(out, recs)
    if end is not None and out and parts:
        # The last stitch crosses the satin at the stop; if it finished on the other side, one more
        # pass back along it (with the satin stitches, so it doesn't show) ends on the chosen side.
        a, b = pairs[parts[-1][-1]]
        side = a if dist(a, end) <= dist(b, end) else b
        here = (out[-1][0], out[-1][1])
        if dist(here, side) > 0.5:
            pts = resample([here, side], min(params.split_mm or SATIN_MAX_WIDTH_MM, SATIN_MAX_WIDTH_MM))
            out += [(x, y, STITCH) for x, y in pts[1:]]
    return out, warnings


def satin(rail_a: Sequence, rail_b: Sequence, params: SatinParams, start: Point | None = None,
          end: Point | None = None) -> tuple[list[Rec], list[str]]:
    pairs = satin_pairs(rail_a, rail_b, params.spacing_mm)
    recs, warnings = satin_with_ends(pairs, params, start, end)
    crossed = _crossing_rungs(pairs)
    if crossed >= 3 and crossed > 0.1 * len(pairs):
        warnings.append("The two sides of this satin cross each other (or were drawn in opposite directions), so "
                        "its stitches are long and bunched. Redraw one side.")
    return recs, warnings


def satin_ribbon(nodes: Sequence, width_mm: float, params: SatinParams, closed: bool = False,
                 start: Point | None = None, end: Point | None = None) -> tuple[list[Rec], list[str]]:
    pairs, corners = _ribbon(nodes, width_mm, params.spacing_mm, closed)
    if closed and start is not None and len(pairs) > 2:
        # A satin border starts (and ends) at the stitch nearest the chosen point.
        n = len(pairs) - 1  # the last pair closes the loop on the first
        k = min(range(n), key=lambda i: dist(((pairs[i][0][0] + pairs[i][1][0]) / 2, (pairs[i][0][1] + pairs[i][1][1]) / 2), start))
        body = pairs[:n]
        pairs = body[k:] + body[:k] + [body[k]]
        corners = {(c - k) % n for c in corners}
    elif not closed and (start is not None or end is not None):
        recs, warnings = satin_with_ends(pairs, params, start, end)
        if _crossing_rungs(pairs, corners) >= 3:
            warnings.append(FOLD_WARNING)
        return recs, warnings
    recs, warnings = satin_from_pairs(pairs, params)
    if _crossing_rungs(pairs, corners) >= 3:
        warnings.append(FOLD_WARNING)
    return recs, warnings


def _split_across(p: Point, q: Point, max_mm: float, i: int) -> list[Point]:
    """The needle points inside one long satin stitch p-q, so no piece is longer than `max_mm`.
    The splits move a little from stitch to stitch (by `i`) so they don't line up in a ridge;
    there are enough pieces that even the moved ones stay within `max_mm`."""
    w = dist(p, q)
    if not max_mm or w <= max_mm:
        return []
    n = math.ceil(w / (0.75 * max_mm) - 1e-9)  # the longest piece is 4/3 of w / n
    shift = ((i % 3) - 1) / (3 * n)
    return [(p[0] + (q[0] - p[0]) * (k / n + shift), p[1] + (q[1] - p[1]) * (k / n + shift)) for k in range(1, n)]


def satin_from_pairs(pairs: list[tuple[Point, Point]], params: SatinParams) -> tuple[list[Rec], list[str]]:
    """Underlay and top stitching for a satin, given matching points on its two edges."""
    widths = [dist(a, b) for a, b in pairs]
    warnings = []
    if params.auto_widen and min(widths) < SATIN_WIDEN_TO_MM:
        thin = sum(1 for w in widths if w < SATIN_WIDEN_TO_MM)
        pairs = [_widen(a, b, SATIN_WIDEN_TO_MM) for a, b in pairs]
        warnings.append(f"Widened {thin} stitch{'es' if thin != 1 else ''} to {SATIN_WIDEN_TO_MM:.0f} mm: thinner satin "
                        "piles up in one spot and can break the thread.")
        widths = [dist(a, b) for a, b in pairs]
    underlay = params.underlay
    if underlay is None:
        underlay = auto_satin_underlay(sorted(widths)[len(widths) // 2], params.underlay_level)
    if max(widths) > SATIN_MAX_WIDTH_MM and not params.split_mm:
        warnings.append(f"Parts of this satin are {max(widths):.1f} mm wide. Stitches over {SATIN_MAX_WIDTH_MM:.0f} mm "
                        "lie loose and can snag: tick Split long stitches, or use a fill there.")
    if not params.auto_widen and min(widths) < SATIN_MIN_WIDTH_MM:
        warnings.append(f"Parts of this satin are only {min(widths):.1f} mm wide; under {SATIN_MIN_WIDTH_MM} mm "
                        "the stitches pile up. Widen it or use a triple run.")

    def inset(a: Point, b: Point, amount: float) -> tuple[Point, Point]:
        """Move both ends toward each other by `amount` (negative widens)."""
        w = dist(a, b)
        if w < 1e-9:
            return a, b
        f = min(amount, w * 0.45) / w
        return ((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f), (b[0] + (a[0] - b[0]) * f, b[1] + (a[1] - b[1]) * f))

    under: list[Point] = []
    # Underlay: each kind returns to the start, so the top stitching starts where it should.
    if "center" in underlay:
        mids = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in pairs]
        line = resample(mids, TRAVEL_STITCH_MM)
        under += line + line[-2::-1]
    if "edge" in underlay:
        ins = [inset(a, b, 0.4) for a, b in pairs]
        under += resample([p[0] for p in ins], TRAVEL_STITCH_MM) + resample([p[1] for p in ins][::-1], TRAVEL_STITCH_MM)
    if "zigzag" in underlay:
        step = max(1, round(2.0 / params.spacing_mm))  # about 2 mm apart
        zz = [inset(a, b, 0.5) for a, b in pairs[::step]]
        fwd = [p for i, ab in enumerate(zz) for p in ([ab[0]] if i % 2 == 0 else [ab[1]])]
        # The way back takes, at each rung, the side the way out didn't, so the two passes cross
        # (an X). Counting from the far end retraced the same legs when the count was even (QA2 S2).
        back = [ab[1] if i % 2 == 0 else ab[0] for i, ab in reversed(list(enumerate(zz)))]
        under += fwd + back
    # Top stitching, each side pushed out by half the pull compensation.
    top: list[Point] = []
    longest_piece = 0.0
    for i, (a, b) in enumerate(pairs):
        comp = width_comp(params.pull_comp_mm, dist(a, b)) if params.comp_by_width else params.pull_comp_mm
        a2, b2 = inset(a, b, -comp / 2)
        p, q = (a2, b2) if i % 2 == 0 else (b2, a2)
        # Split a long stitch so it can't snag, staggering the splits so they don't line up.
        across = [p, *_split_across(p, q, params.split_mm, i), q]
        longest_piece = max(longest_piece, *(dist(u, v) for u, v in zip(across, across[1:])))
        top += across
    if params.split_mm:
        # At a sharp corner of a wide ribbon or border the step along the outer edge, from one
        # stitch to the next, can be longer than Longest too: add needle points along it (QA2 S4).
        top = _subdivide(top, params.split_mm)
    if params.split_mm and longest_piece > SATIN_MAX_WIDTH_MM:
        # Split is on but Longest is set over 7 mm, so some pieces are still long (QA2 S5: this
        # used to say "tick Split long stitches", which was already ticked).
        warnings.append(f"Split long stitches is set to {params.split_mm:g} mm, so some stitches are {longest_piece:.1f} mm "
                        f"and can snag: set Longest to {SATIN_MAX_WIDTH_MM:.0f} mm or less.")
    if params.split_mm and under:
        # The underlay's stitches across the column (and the step up to the top stitching) are
        # split too, or "Split long stitches" couldn't clear the long-stitch check on wide satins.
        under = _subdivide([*under, top[0]], params.split_mm)[:-1]
    first = stitch_run(under)
    return first + stitch_run(top, _min_step(params.spacing_mm), first[-1] if first else None), warnings


# ---------------------------------------------------------------- tatami fill


@dataclass
class FillParams:
    angle_deg: float = 45.0
    spacing_mm: float = 0.4  # row spacing (density)
    stitch_mm: float = 3.5
    pull_comp_mm: float = 0.2
    underlay: tuple[str, ...] = ("edge", "tatami")  # any of: edge, tatami
    random_pct: float = 0.0  # move penetrations by up to this % of a stitch (0-50)
    reverse: bool = False  # sew the top stitching from the other end
    start_mm: tuple[float, float] | None = None  # begin at the edge nearest this point (Optimize jumps, the green dot)
    end_mm: tuple[float, float] | None = None  # end as near this point as the rows allow (the red dot)
    pattern: str = "tatami"  # tatami | gradient | wave | contour | stipple | cross
    gradient_to_mm: float = 1.6  # gradient: row spacing at the sparse end
    wave_mm: float = 1.5  # wave: height of the ripple
    wave_length_mm: float = 8.0  # wave: length of one ripple
    stipple_mm: float = 3.0  # stipple: how far apart the meandering line's turns are
    cross_mm: float = 2.5  # cross-stitch: size of one square
    underlay_spacing_mm: float = 2.0  # cross-hatch underlay rows (closer on stretchy and lofty fabrics)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "FillParams":
        d = d or {}
        u = d.get("underlay", ["edge", "tatami"])
        under_spacing = 2.0
        if u == "auto":
            # Automatic: light fabrics (denim, felt) need only an edge run; the rest a full base,
            # closer on stretchy and lofty fabrics (knit, fleece, towel), which need a firmer one.
            u = ["edge"] if d.get("underlay_level") == "light" else ["edge", "tatami"]
            if d.get("underlay_level") == "heavy":
                under_spacing = 1.5
        if not isinstance(u, (list, tuple)):
            raise DigitizeError("Unknown fill underlay")
        p = cls(
            angle_deg=_finite(d, "angle_deg", 45.0),
            spacing_mm=_finite(d, "spacing_mm", 0.4),
            stitch_mm=_finite(d, "stitch_mm", 3.5),
            pull_comp_mm=_finite(d, "pull_comp_mm", 0.2),
            underlay=tuple(u),
            random_pct=_finite(d, "random_pct", 0.0),
            reverse=bool(d.get("reverse", False)),
            start_mm=_start_point(d.get("start_mm")),
            end_mm=_start_point(d.get("end_mm")),
            pattern=str(d.get("pattern", "tatami")),
            gradient_to_mm=_finite(d, "gradient_to_mm", 1.6),
            wave_mm=_finite(d, "wave_mm", 1.5),
            wave_length_mm=_finite(d, "wave_length_mm", 8.0),
            stipple_mm=_finite(d, "stipple_mm", 3.0),
            cross_mm=_finite(d, "cross_mm", 2.5),
            underlay_spacing_mm=under_spacing,
        )
        if not 0 <= p.pull_comp_mm <= 2:
            raise DigitizeError("Pull compensation must be between 0 and 2 mm")
        if p.pattern not in FILL_PATTERNS:
            raise DigitizeError(f"Unknown fill pattern: {p.pattern}")
        if not 0.3 <= p.gradient_to_mm <= 5 or not 0.3 <= p.wave_mm <= 6 or not 2 <= p.wave_length_mm <= 40:
            raise DigitizeError("Gradient spacing 0.3-5 mm, wave height 0.3-6 mm and length 2-40 mm")
        if not 1 <= p.stipple_mm <= 10 or not 1 <= p.cross_mm <= 8:
            raise DigitizeError("Stipple size 1-10 mm and cross-stitch size 1-8 mm")
        if not 0 <= p.random_pct <= 50:
            raise DigitizeError("Random must be between 0 and 50%")
        if not 0.2 <= p.spacing_mm <= 5:
            raise DigitizeError("Fill spacing must be between 0.2 and 5 mm")
        if not 1 <= p.stitch_mm <= 8:
            raise DigitizeError("Fill stitch length must be between 1 and 8 mm")
        bad = set(p.underlay) - {"edge", "tatami"}
        if bad:
            raise DigitizeError(f"Unknown fill underlay: {', '.join(sorted(bad))}")
        return p


MIN_PART_MM2 = 0.5  # pieces of a shape smaller than this are too small to sew


def valid_parts(shell: Sequence[Point], holes: Sequence[Sequence[Point]] = ()) -> list[Polygon]:
    """The areas inside `shell` and outside `holes`, biggest first. An outline that crosses itself
    (a figure 8, a bow-tie) or a hole that cuts the shape in two gives several pieces, and every
    piece is kept: repairing it by keeping one piece left half the shape bare without a word."""
    raw = Polygon(shell, [h for h in holes if len(h) >= 3])
    if raw.is_valid:
        geom = raw.buffer(0)
    else:
        whole = shapely.make_valid(Polygon(shell), method="structure", keep_collapsed=False)
        cut = [shapely.make_valid(Polygon(h), method="structure", keep_collapsed=False) for h in holes if len(h) >= 3]
        geom = whole.difference(shapely.union_all(cut)) if cut else whole
    return sorted((p.buffer(0) for p in polygons(geom) if p.area >= MIN_PART_MM2), key=lambda g: -g.area)


def fill_parts(outline: Sequence, holes: Sequence[Sequence] = ()) -> list[Polygon]:
    """The pieces of a fill (or applique) outline with its holes, biggest first."""
    try:
        shell, _ = flatten(outline, closed=True)
        hole_rings = [flatten(h, closed=True)[0] for h in holes if len(h) >= 3]
    except (TypeError, ValueError, IndexError):
        raise DigitizeError("This shape has a point that isn't a number") from None
    if len(shell) < 3:
        raise DigitizeError("A fill needs at least three points")
    check_points(shell)
    for h in hole_rings:
        check_points(h, "hole")  # a bad hole used to vanish silently and be sewn over (QA2 S7)
    parts = valid_parts(shell, hole_rings)
    if not parts or sum(p.area for p in parts) < MIN_PART_MM2:
        raise DigitizeError("This shape is too small to fill")
    return parts


def fill_polygon(outline: Sequence, holes: Sequence[Sequence] = ()) -> Polygon:
    """The biggest piece of a fill (see fill_parts for all of them)."""
    return fill_parts(outline, holes)[0]


def _rows(poly: Polygon, angle: float, spacing: float, extend: float, ys: Sequence[float] | None = None) -> list[list[tuple[float, float]]]:
    """Horizontal segments (in the rotated frame) for each row: [[(x0, x1), ...], ...] bottom to top.
    Rows are `spacing` apart, or at the heights `ys` (a gradient fill)."""
    minx, miny, maxx, maxy = poly.bounds
    shapely.prepare(poly)
    rows = []
    heights = iter(ys) if ys is not None else None
    y = next(heights, maxy) if heights is not None else miny + spacing / 2
    while y < maxy:
        hit = poly.intersection(LineString([(minx - 1, y), (maxx + 1, y)]))
        segs = []
        for ln in hit.geoms if hasattr(hit, "geoms") else [hit]:
            if ln.is_empty or ln.geom_type != "LineString":
                continue
            xs = [c[0] for c in ln.coords]
            x0, x1 = min(xs) - extend, max(xs) + extend
            if x1 - x0 > MIN_STITCH_MM:
                segs.append((x0, x1))
        rows.append(sorted(segs))
        y = next(heights, maxy) if heights is not None else y + spacing
    return rows


def _jitter(row: int, k: int) -> float:
    """A repeatable pseudo-random number in [-1, 1] for penetration k of a row (same design, same stitches)."""
    v = math.sin(row * 12.9898 + k * 78.233) * 43758.5453
    return (v - math.floor(v)) * 2 - 1


def _row_stitches(x0: float, x1: float, y: float, step: float, offset: float, forward: bool,
                  random: float = 0.0, row: int = 0) -> list[Point]:
    """Stitches along a row; inner penetrations sit on a grid shifted by `offset` (brick pattern).
    `random` (0..0.5) moves each penetration by up to that fraction of a stitch, which breaks up
    the lines a regular pattern makes across a fill (Embrilliance's "Rnd")."""
    k0 = math.floor((x0 - offset) / step) + 1
    k1 = math.ceil((x1 - offset) / step)
    grid = ((offset + k * step + (random * step / 2) * _jitter(row, k)) for k in range(k0, k1))
    inner = [x for x in grid if x0 + MIN_STITCH_MM < x < x1 - MIN_STITCH_MM]
    xs = [x0, *inner, x1]
    # Dropping a penetration too close to an end can leave one gap longer than `step`: split it.
    even: list[float] = [xs[0]]
    for x in xs[1:]:
        gap = x - even[-1]
        if gap > step + 1e-9:
            n = math.ceil(gap / step)
            even += [even[-1] + gap * i / n for i in range(1, n)]
        even.append(x)
    xs = even
    if not forward:
        xs.reverse()
    return [(x, y) for x in xs]


def tatami(poly: Polygon, angle: float, spacing: float, stitch: float, extend: float,
           start_near: Point | None = None, travel_within: Polygon | None = None, random: float = 0.0,
           sparse_to: float | None = None, wave: tuple[float, float] | None = None,
           end_near: Point | None = None) -> list[Rec]:
    """Tatami fill of `poly`: serpentine rows grouped into regions, regions joined by travel.
    Travel runs inside `travel_within` (default `poly`), where later stitching covers it.
    `end_near`: finish as near this point as the rows allow (the region that can end nearest it
    is sewn last, the way round that ends nearest it).
    `sparse_to`: rows open out to this spacing across the shape (a gradient). `wave`: (height,
    length) of a ripple given to every row."""
    rot = affinity.rotate(poly, -angle, origin=(0, 0))
    if not rot.is_valid:
        # A shape with a zero-width spike (an arm exactly twice the underlay inset) can turn
        # invalid when rotated; its rows would then run straight across, outside the shape.
        rot = max(polygons(rot.buffer(0)) or [Polygon()], key=lambda g: g.area)
        if rot.is_empty:
            return []
    ys = gradient_ys(rot.bounds[1], rot.bounds[3], spacing, sparse_to) if sparse_to else None
    rows = _rows(rot, angle, spacing, extend, ys)
    miny = rot.bounds[1]
    shapely.prepare(rot)
    unvisited = {(r, i) for r, segs in enumerate(rows) for i in range(len(segs))}
    regions: list[list[tuple[int, int]]] = []
    while unvisited:
        r, i = min(unvisited)
        region = [(r, i)]
        unvisited.discard((r, i))
        while True:
            x0, x1 = rows[r][i]
            nxt = [(r + 1, j) for j, (a, b) in enumerate(rows[r + 1])] if r + 1 < len(rows) else []
            nxt = [c for c in nxt if c in unvisited and rows[c[0]][c[1]][0] < x1 and rows[c[0]][c[1]][1] > x0]
            # The step to the next row runs along one end or the other. Where the edge lies almost
            # along the rows (a star's arm, the rim of a hole) that step would be a long loose
            # stitch: start a new region there instead, and let travel() make the move inside the shape.
            nxt = [c for c in nxt if abs(rows[c[0]][c[1]][0] - x0) <= stitch and abs(rows[c[0]][c[1]][1] - x1) <= stitch]
            if not nxt:
                break
            r, i = nxt[0]
            region.append((r, i))
            unvisited.discard((r, i))
        regions.append(region)

    def to_world(p: Point) -> Point:
        a = math.radians(angle)
        return (p[0] * math.cos(a) - p[1] * math.sin(a), p[0] * math.sin(a) + p[1] * math.cos(a))

    def region_points(region, forward_first: bool) -> list[Point]:
        pts: list[Point] = []
        fwd = forward_first
        for r, i in region:
            x0, x1 = rows[r][i]
            y = ys[r] if ys is not None else miny + spacing / 2 + r * spacing
            if wave:
                # Every row gets the same needle positions (no brick stagger) and a stitch at least
                # every quarter wave, so neighbouring rows are copies of each other moved across:
                # they ripple together and never cross. Points that would leave the shape stay put.
                step = min(stitch, wave[1] / 4)
                row = _row_stitches(x0, x1, y, step, 0.0, fwd, random, r)
                fade = wave[1] / 2  # the ripple eases out over the last half wave, so row ends meet the edge cleanly

                def rippled(x: float, yy: float) -> Point:
                    k = min(1.0, (x - x0) / fade, (x1 - x) / fade) if fade > 0 else 1.0
                    q = (x, yy + wave_offset(x, *wave) * max(0.0, k))
                    return q if rot.contains(ShapelyPoint(q)) else (x, yy)

                row = [rippled(x, yy) for x, yy in row]
            else:
                row = _row_stitches(x0, x1, y, stitch, (r % 3) * stitch / 3, fwd, random, r)
            pts += row
            fwd = not fwd
        return [to_world(p) for p in pts]

    # Each region can be sewn four ways (first row left-to-right or not, bottom-up or top-down).
    options = []
    for reg in regions:
        f, b = region_points(reg, True), region_points(reg, False)
        options.append([f, f[::-1], b, b[::-1]])

    # Order regions greedily: next is whichever region has an end nearest the needle.
    # Rows can extend past the edge by `extend` (pull compensation); travel may go there too.
    inside = Zone((travel_within or poly).buffer(extend + 0.05))
    min_step = _min_step(min(spacing, sparse_to) if sparse_to else spacing)
    out: list[Rec] = []
    pos = start_near
    remaining = list(range(len(options)))
    last = None
    if end_near and regions:
        k, j, ends_at = _end_row(regions, rows, ys, miny, spacing, angle, end_near)
        reg = regions[k]
        low, high = reg[:j], reg[j:][::-1]  # `high` is sewn from its far row back to the end row
        regions[k] = high
        hf, hb = region_points(high, True), region_points(high, False)
        options[k] = [s for s in (hf, hb) if s]
        if low:
            # Sewn towards the end row (never away from it), so the move on to the far side of
            # `high` crosses only rows still to be sewn, which cover it.
            regions.append(low)
            options.append([region_points(low, True), region_points(low, False)])
            remaining.append(len(options) - 1)
        last = k
        end_near = ends_at
    while remaining:
        if last is not None and remaining == [last]:
            # The last region: whichever way ends at the end point.
            k, seq = last, min(options[last], key=lambda s: dist(s[-1], end_near))
        else:
            k, seq = min(
                ((k, seq) for k in remaining if k != last for seq in options[k]),
                key=lambda ks: dist(pos, ks[1][0]) if pos else 0.0,
            )
        remaining.remove(k)
        if out:  # the first region starts where it starts; `start_near` only chose it
            out += travel(pos, seq[0], inside)
        _append(out, stitch_run(seq, min_step))
        pos = seq[-1]
    return out


def _end_row(regions, rows, ys, miny: float, spacing: float, angle: float, end: Point) -> tuple[int, int, Point]:
    """Which region and row (its place in the region) has a row end nearest `end`, and that row end
    (mm). Rows are in the fill's turned frame; `end` is in the design's."""
    a = math.radians(-angle)
    ex, ey = end[0] * math.cos(a) - end[1] * math.sin(a), end[0] * math.sin(a) + end[1] * math.cos(a)
    best = (math.inf, 0, 0, (ex, ey))
    for k, reg in enumerate(regions):
        for j, (r, i) in enumerate(reg):
            y = ys[r] if ys is not None else miny + spacing / 2 + r * spacing
            for x in rows[r][i]:
                d = math.hypot(x - ex, y - ey)
                if d < best[0]:
                    best = (d, k, j, (x, y))
    _, k, j, (x, y) = best
    b = math.radians(angle)
    return k, j, (x * math.cos(b) - y * math.sin(b), x * math.sin(b) + y * math.cos(b))


OPEN_PATTERNS = ("contour", "stipple", "cross")


def _stipple_seed(poly: Polygon) -> int:
    """The stipple's random seed, from the shape's size and area only, so moving the shape (or
    copying it) keeps the same stipple instead of shuffling it."""
    x0, y0, x1, y1 = poly.bounds
    return int(round(poly.area * 10) * 31 + round((x1 - x0) * 100) * 7 + round((y1 - y0) * 100)) % 100000


def _open_paths(poly: Polygon, params: FillParams, pos: Point) -> tuple[list[list[Point]], list[str]]:
    """The paths of a contour, stipple or cross-stitch fill (sewn in this order), with warnings."""
    warnings: list[str] = []
    if params.pattern == "contour":
        paths = contour_paths(poly, params.spacing_mm, params.stitch_mm, pos)
    elif params.pattern == "stipple":
        paths = stipple_paths(poly, params.stipple_mm, min(params.stitch_mm, 2.5), _stipple_seed(poly), pos)
        if paths:
            reach = shapely.union_all([LineString(p) for p in paths if len(p) > 1]).buffer(params.stipple_mm)
            bare = poly.difference(reach).area
            if bare > 4 and bare > 0.1 * poly.area:
                warnings.append(f"Parts of this shape are too narrow for {params.stipple_mm:g} mm stipple loops, so they "
                                "are left empty. Make the loops smaller.")
    else:
        paths = cross_paths(poly, params.cross_mm)
        if params.cross_mm * math.sqrt(2) > LONG_STITCH_MM:
            # Diagonals of big squares would be loose stitches: give each a needle point midway.
            paths = [_subdivide(p, LONG_STITCH_MM) for p in paths]
    return paths, warnings


def _sew_paths(paths: Sequence[Sequence[Point]], inside: "Polygon | Zone", pos: Point | None) -> list[Rec]:
    """Paths sewn one after another, joined by travel inside the shape."""
    out: list[Rec] = []
    here = pos
    zone = _zone(inside)
    for path in paths:
        if out:
            out += travel(here, path[0], zone)
        _append(out, stitch_run(path))
        here = path[-1]
    return out


def _edge_rings(poly: Polygon) -> list[list[Point]]:
    """The edge-run underlay: every edge (outside and holes) of every piece of the shape shrunk by
    0.5 mm, biggest piece first, its outside before its holes."""
    rings: list[list[Point]] = []
    for part in polygons(poly.buffer(-0.5)):
        if part.area < MIN_PART_MM2:
            continue
        rings.append(list(part.exterior.coords))
        rings += [list(r.coords) for r in part.interiors if Polygon(r).area >= MIN_PART_MM2]
    return rings


def _ring_from(ring: Sequence[Point], p: Point) -> list[Point]:
    """A closed ring re-started exactly where it passes nearest `p` (not just at its nearest corner)."""
    line = LineString(ring)
    if line.length <= 0:
        return list(ring)
    d = line.project(ShapelyPoint(p))
    if d <= 1e-6 or d >= line.length - 1e-6:
        return list(ring)
    head = list(substring(line, d, line.length).coords)
    tail = list(substring(line, 0, d).coords)
    return head + tail[1:]


def _ring_run(ring: Sequence[Point]) -> list[Point]:
    """A closed ring as running-stitch points, keeping its sharp corners."""
    return resample(ring, TRAVEL_STITCH_MM, sharp_points(ring))


def _fill_part(poly: Polygon, params: FillParams, end_here: bool = True) -> tuple[list[Rec], list[str]]:
    """Underlay and top stitching for one piece of a fill. `end_here`: this piece is sewn last, so
    it ends near the fill's end point (if one is set)."""
    end_near = params.end_mm if end_here else None
    warnings: list[str] = []
    start = tuple(poly.exterior.coords[0])
    if params.start_mm is not None:
        # Begin at the edge nearest the chosen start (so the jump from the last piece is short).
        near = poly.exterior.interpolate(poly.exterior.project(ShapelyPoint(params.start_mm)))
        start = (near.x, near.y)
    open_pattern = params.pattern in OPEN_PATTERNS
    top: list[Rec] = []
    target = None
    if open_pattern:
        # Worked out first, so the edge run can end next to where the pattern starts: nothing
        # covers an open pattern, so a long move to its start would show on top.
        paths, warnings = _open_paths(poly, params, start)
        if not paths:
            raise DigitizeError(f"This shape is too small for a {params.pattern} fill; try a smaller size")
        top = _sew_paths(paths, poly.buffer(0.3), start)
        target = (top[0][0], top[0][1])
    out: list[Rec] = []
    if "edge" in params.underlay:
        rings = _edge_rings(poly)
        if target is not None and rings:
            # Sew the edge nearest the pattern's start last, starting (and so ending) right by it,
            # and start each edge before it next to where the following one starts: nothing covers
            # an open pattern's underlay, so long moves between edges would show through.
            last = min(range(len(rings)), key=lambda k: min(dist(p, target) for p in rings[k]))
            rings = [r for k, r in enumerate(rings) if k != last] + [nearest_rotation(rings[last], target)]
            for k in range(len(rings) - 2, -1, -1):
                rings[k] = nearest_rotation(rings[k], rings[k + 1][0])
        for ring in rings:
            if out:
                if target is None:
                    ring = nearest_rotation(ring, out[-1][:2])
                out += travel(out[-1][:2], ring[0], poly)
            elif target is None and params.start_mm is not None:
                ring = _ring_from(ring, start)  # begin at the chosen start
            _append(out, stitch_run(_ring_run(ring)))
    # Open patterns would show a cross-hatch underlay through them, and so would the sparse end of
    # a gradient (which should fade out to bare fabric).
    if "tatami" in params.underlay and not open_pattern and params.pattern != "gradient":
        for under in polygons(poly.buffer(-0.6)):
            if under.area < MIN_PART_MM2:
                continue
            pos = (out[-1][0], out[-1][1]) if out else start
            cross = tatami(under, params.angle_deg + 90, params.underlay_spacing_mm, 3.0, 0.0, pos, travel_within=poly)
            if out and cross:
                # Walk from the edge run to where the cross-hatch starts (not one long stitch).
                out += travel(pos, (cross[0][0], cross[0][1]), poly)
            _append(out, cross)
    pos = (out[-1][0], out[-1][1]) if out else start
    if not open_pattern:
        top = tatami(poly, params.angle_deg, params.spacing_mm, params.stitch_mm, params.pull_comp_mm / 2, pos,
                     random=params.random_pct / 100,
                     sparse_to=params.gradient_to_mm if params.pattern == "gradient" else None,
                     wave=(params.wave_mm, params.wave_length_mm) if params.pattern == "wave" else None,
                     end_near=end_near)
    if params.reverse and end_near is None and top and all(r[2] == STITCH for r in top):
        top = top[::-1]  # same stitches, sewn from the other end
    if out and top:
        out += travel(pos, (top[0][0], top[0][1]), poly.buffer(params.pull_comp_mm / 2 + 0.05))
    _append(out, top)
    if end_near is not None and out and not open_pattern:
        # The rows finish at the row end nearest the end point; when that point is part way along
        # an edge the rows run beside, a short run along the last row (on top of it, so it doesn't
        # show) takes the needle exactly there.
        edge = poly.boundary
        q = edge.interpolate(edge.project(ShapelyPoint(end_near)))
        if dist(out[-1][:2], (q.x, q.y)) > 0.3:
            last = travel(out[-1][:2], (q.x, q.y), poly.buffer(params.pull_comp_mm / 2 + 0.05))
            if all(r[2] == STITCH for r in last):  # never end a fill on a jump (QA2 S1)
                out += last
    return out, warnings


def _start_point(v: Any) -> tuple[float, float] | None:
    """A start point from settings: [x, y] in mm, or nothing."""
    try:
        x, y = float(v[0]), float(v[1])
    except (TypeError, ValueError, IndexError):
        return None
    return (x, y) if math.isfinite(x) and math.isfinite(y) else None


def fill(outline: Sequence, holes: Sequence[Sequence], params: FillParams) -> tuple[list[Rec], list[str]]:
    parts = fill_parts(outline, holes)
    warnings: list[str] = []
    area = sum(p.area for p in parts)
    step = params.cross_mm ** 2 / 4 if params.pattern == "cross" else params.spacing_mm * min(params.stitch_mm, 2.5 if params.pattern == "stipple" else params.stitch_mm)
    if area / step > MAX_STITCHES:
        raise DigitizeError(f"This fill would need about {area / step:,.0f} stitches, far more than any design. "
                            "Make it smaller or less dense.")
    if area < 4:
        warnings.append("This fill is very small; a satin or running stitch may sew more cleanly.")
    out: list[Rec] = []
    if params.end_mm is not None and len(parts) > 1:
        # Several pieces (a hole cutting the shape in two): the one the end point is on goes last.
        end_pt = ShapelyPoint(params.end_mm)
        last = min(range(len(parts)), key=lambda k: parts[k].boundary.distance(end_pt))
        parts = [p for k, p in enumerate(parts) if k != last] + [parts[last]]
    for k, poly in enumerate(parts):
        recs, part_warnings = _fill_part(poly, params, end_here=k == len(parts) - 1)
        warnings += [w for w in part_warnings if w not in warnings]
        if out and recs:
            # Separate pieces (an outline that crosses itself, a hole cutting the shape in two):
            # lock off, move to the next piece, lock in.
            out = tie_off(out) + travel(out[-1][:2], recs[0][:2]) + tie_in(recs)
        else:
            out += recs
    return out, warnings


# ---------------------------------------------------------------- objects


def generate(obj: dict[str, Any]) -> tuple[list[Rec], list[str]]:
    """Stitches for one digitized object (geometry already in final position), with ties."""
    kind = obj.get("kind")
    g = obj.get("geometry") or {}
    p = obj.get("params") or {}
    for key in ("nodes", "rail_a", "rail_b"):
        if g.get(key):
            try:
                check_points([(float(n[0]), float(n[1])) for n in g[key]])
            except (TypeError, ValueError, IndexError):
                raise DigitizeError("This shape has a point that isn't a number") from None
    if kind == "run":
        nodes = g.get("nodes") or []
        if len(nodes) < 2:
            raise DigitizeError("A running stitch needs at least two points")
        recs, warnings = running(nodes, RunParams.from_dict(p), bool(g.get("closed")), _start_point(p.get("start_mm"))), []
    elif kind == "satin" and g.get("nodes") is not None:
        # A ribbon: a centre line and a width (what the Satin tool draws).
        recs, warnings = satin_ribbon(g["nodes"], _finite(g, "width_mm", 3.0), SatinParams.from_dict(p), bool(g.get("closed")),
                                      _start_point(p.get("start_mm")), _start_point(p.get("end_mm")))
    elif kind == "satin":
        # A column: two edges clicked rung by rung (older projects).
        recs, warnings = satin(g.get("rail_a") or [], g.get("rail_b") or [], SatinParams.from_dict(p),
                               _start_point(p.get("start_mm")), _start_point(p.get("end_mm")))
    elif kind == "fill":
        recs, warnings = fill(g.get("outline") or [], g.get("holes") or [], FillParams.from_dict(p))
    elif kind == "applique":
        from .applique import AppliqueParams, applique

        # Applique ties each of its three parts itself (the machine cuts at each stop).
        return applique(g.get("outline") or [], AppliqueParams.from_dict(p), g.get("holes") or [])
    else:
        raise DigitizeError(f"Unknown object type: {kind}")
    if sum(1 for r in recs if r[2] == STITCH) < 2:
        warnings = [*warnings, "This is shorter than one stitch, so it sews as a single needle drop. "
                               "Make it bigger or delete it."]
    if p.get("tie_in", True):
        recs = tie_in(recs)
    if p.get("tie_off", True):
        recs = tie_off(recs)
    return recs, warnings


def geometry_points(obj: dict[str, Any]) -> list[Point]:
    g = obj.get("geometry") or {}
    nodes = [*(g.get("nodes") or []), *(g.get("rail_a") or []), *(g.get("rail_b") or []), *(g.get("outline") or [])]
    for h in g.get("holes") or []:
        nodes += h
    return [(float(n[0]), float(n[1])) for n in nodes]


def transform_geometry(obj: dict[str, Any], t: Any, center: Point) -> dict[str, Any]:
    """Apply a layout transform to an object's nodes, so stitches regenerate at the new size."""
    a = math.radians(t.rotate)
    ca, sa = math.cos(a), math.sin(a)
    fx = -1.0 if t.flip_x else 1.0
    fy = -1.0 if t.flip_y else 1.0
    cx, cy = center

    def tf(n):
        px = (float(n[0]) - cx) * fx * t.scale_x
        py = (float(n[1]) - cy) * fy * t.scale_y
        return [px * ca - py * sa + cx + t.x, px * sa + py * ca + cy + t.y, *n[2:]]

    g = dict(obj.get("geometry") or {})
    for key in ("nodes", "rail_a", "rail_b", "outline"):
        if g.get(key):
            g[key] = [tf(n) for n in g[key]]
    if g.get("holes"):
        g["holes"] = [[tf(n) for n in h] for h in g["holes"]]
    if g.get("width_mm") is not None and (t.scale_x != 1 or t.scale_y != 1):
        # A ribbon gets wider and narrower with the shape (by the average of the two scales).
        g["width_mm"] = float(g["width_mm"]) * math.sqrt(abs(t.scale_x * t.scale_y))
    out = {**obj, "geometry": g}
    # A fill's chosen start and end move, turn and resize with it.
    p = obj.get("params") or {}
    moved = {k: tf(p[k])[:2] for k in ("start_mm", "end_mm") if _start_point(p.get(k)) is not None}
    if moved:
        out["params"] = {**p, **moved}
    # A mirror flips the winding of satin rails; keep rails in their original order anyway.
    return out


def bounds(points: Sequence[Point]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


__all__ = [
    "DigitizeError", "FillParams", "RunParams", "SatinParams", "fill", "fill_polygon", "generate",
    "geometry_points", "ribbon_pairs", "running", "satin", "satin_from_pairs", "satin_pairs", "satin_ribbon", "tatami", "tie_in", "tie_off", "transform_geometry", "travel",
]
