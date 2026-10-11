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

from .paths import Point, corner_indices, cumulative, dist, flatten, point_at, resample

STITCH, JUMP, TRIM = pe.STITCH, pe.JUMP, pe.TRIM
Rec = tuple[float, float, int]

TIE_MM = 0.7
MIN_STITCH_MM = 0.3
TRAVEL_STITCH_MM = 2.5
TRIM_TRAVEL_MM = 3.0  # travels longer than this are trimmed instead of left as a thread


class DigitizeError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


# ---------------------------------------------------------------- helpers


def _unit(dx: float, dy: float) -> Point:
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n > 1e-12 else (1.0, 0.0)


def stitch_run(points: Sequence[Point]) -> list[Rec]:
    """Points as stitches, dropping ones closer than MIN_STITCH_MM to the previous."""
    out: list[Rec] = []
    for p in points:
        if out and dist((out[-1][0], out[-1][1]), p) < MIN_STITCH_MM:
            continue
        out.append((p[0], p[1], STITCH))
    return out


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
    return recs + [(a[0] + u[0] * t, a[1] + u[1] * t, STITCH), (a[0], a[1], STITCH)]


def _edge_route(a: Point, b: Point, inside: Polygon) -> list[Point] | None:
    """A path from a to b that follows one edge of the shape (outside or a hole), staying inside,
    or None. Used to travel around holes instead of jumping over them."""
    zone = inside.buffer(-0.3)
    if zone.is_empty or zone.geom_type != "Polygon":
        return None
    pa, pb = ShapelyPoint(a), ShapelyPoint(b)
    best: list[Point] | None = None
    for ring in [zone.exterior, *zone.interiors]:
        line = LineString(ring.coords)
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
            if inside.buffer(1e-6).covers(ls) and (best is None or ls.length < LineString(best).length):
                best = route
    return best


def travel(a: Point, b: Point, inside: Polygon | None = None) -> list[Rec]:
    """Move from a to b inside `inside` with running stitches that later stitching covers:
    straight if possible, else around the edge of a hole. Otherwise jump (trimmed when long)."""
    d = dist(a, b)
    if d < MIN_STITCH_MM:
        return []
    if inside is not None:
        route = [a, b] if inside.buffer(1e-6).covers(LineString([a, b])) else _edge_route(a, b, inside)
        if route:
            return [(x, y, STITCH) for x, y in resample(route, TRAVEL_STITCH_MM)[1:]]
    out: list[Rec] = []
    if d > TRIM_TRAVEL_MM:
        out.append((a[0], a[1], TRIM))
    out.append((b[0], b[1], JUMP))
    return out


# ---------------------------------------------------------------- running stitch


@dataclass
class RunParams:
    style: str = "single"  # single | triple (whole line 3x) | bean (each stitch 3x)
    stitch_mm: float = 2.5

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "RunParams":
        d = d or {}
        p = cls(style=str(d.get("style", "single")), stitch_mm=float(d.get("stitch_mm", 2.5)))
        if p.style not in ("single", "triple", "bean"):
            raise DigitizeError(f"Unknown running stitch style: {p.style}")
        if not 0.5 <= p.stitch_mm <= 12:
            raise DigitizeError("Stitch length must be between 0.5 and 12 mm")
        return p


def run_points(nodes: Sequence, stitch_mm: float, closed: bool = False) -> list[Point]:
    poly, idx = flatten(nodes, closed)
    if closed and poly:
        poly = poly + [poly[0]]
        idx = idx + [len(poly) - 1]
    return resample(poly, stitch_mm, corner_indices(nodes, idx[: len(nodes)]))


def running(nodes: Sequence, params: RunParams, closed: bool = False) -> list[Rec]:
    pts = run_points(nodes, params.stitch_mm, closed)
    if len(pts) < 2:
        return stitch_run(pts)
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
        u = d.get("underlay", ["center"])
        p = cls(
            spacing_mm=float(d.get("spacing_mm", 0.4)),
            pull_comp_mm=float(d.get("pull_comp_mm") if d.get("pull_comp_mm") is not None else 0.2),
            underlay=None if u == "auto" else tuple(u),
            underlay_level=str(d.get("underlay_level", "normal")),
            comp_by_width=bool(d.get("comp_by_width", False)),
            auto_widen=bool(d.get("auto_widen", False)),
            split_mm=float(d.get("split_mm", 0) or 0),
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


SATIN_MAX_WIDTH_MM = 10.0  # wider satins snag and loosen; use a fill instead
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


def satin(rail_a: Sequence, rail_b: Sequence, params: SatinParams) -> tuple[list[Rec], list[str]]:
    pairs = satin_pairs(rail_a, rail_b, params.spacing_mm)
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
    if max(widths) > SATIN_MAX_WIDTH_MM:
        warnings.append(f"Parts of this satin are {max(widths):.1f} mm wide. Satins over {SATIN_MAX_WIDTH_MM:.0f} mm "
                        "snag and loosen; use a fill there.")
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

    out: list[Point] = []
    # Underlay: each kind returns to the start, so the top stitching starts where it should.
    if "center" in underlay:
        mids = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in pairs]
        line = resample(mids, TRAVEL_STITCH_MM)
        out += line + line[-2::-1]
    if "edge" in underlay:
        ins = [inset(a, b, 0.4) for a, b in pairs]
        out += resample([p[0] for p in ins], TRAVEL_STITCH_MM) + resample([p[1] for p in ins][::-1], TRAVEL_STITCH_MM)
    if "zigzag" in underlay:
        step = max(1, round(2.0 / params.spacing_mm))  # about 2 mm apart
        zz = [inset(a, b, 0.5) for a, b in pairs[::step]]
        fwd = [p for i, ab in enumerate(zz) for p in ([ab[0]] if i % 2 == 0 else [ab[1]])]
        back = [p for i, ab in enumerate(reversed(zz)) for p in ([ab[1]] if i % 2 == 0 else [ab[0]])]
        out += fwd + back
    # Top stitching, each side pushed out by half the pull compensation.
    for i, (a, b) in enumerate(pairs):
        comp = width_comp(params.pull_comp_mm, dist(a, b)) if params.comp_by_width else params.pull_comp_mm
        a2, b2 = inset(a, b, -comp / 2)
        p, q = (a2, b2) if i % 2 == 0 else (b2, a2)
        out.append(p)
        w = dist(p, q)
        if params.split_mm and w > params.split_mm:
            # Split a long stitch so it can't snag, staggering the splits so they don't line up.
            n = math.ceil(w / params.split_mm)
            shift = ((i % 3) - 1) / (3 * n)
            for k in range(1, n):
                f = k / n + shift
                out.append((p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f))
        out.append(q)
    return stitch_run(out), warnings


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

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "FillParams":
        d = d or {}
        u = d.get("underlay", ["edge", "tatami"])
        if u == "auto":
            # Automatic: light fabrics (denim, felt) need only an edge run; the rest a full base.
            u = ["edge"] if d.get("underlay_level") == "light" else ["edge", "tatami"]
        p = cls(
            angle_deg=float(d.get("angle_deg", 45.0)),
            spacing_mm=float(d.get("spacing_mm", 0.4)),
            stitch_mm=float(d.get("stitch_mm", 3.5)),
            pull_comp_mm=float(d.get("pull_comp_mm") if d.get("pull_comp_mm") is not None else 0.2),
            underlay=tuple(u),
            random_pct=float(d.get("random_pct", 0) or 0),
            reverse=bool(d.get("reverse", False)),
        )
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


def fill_polygon(outline: Sequence, holes: Sequence[Sequence] = ()) -> Polygon:
    shell, _ = flatten(outline, closed=True)
    if len(shell) < 3:
        raise DigitizeError("A fill needs at least three points")
    hole_polys = [flatten(h, closed=True)[0] for h in holes if len(h) >= 3]
    poly = Polygon(shell, hole_polys).buffer(0)  # buffer(0) repairs self-intersections
    if poly.is_empty or poly.area < 0.5:
        raise DigitizeError("This shape is too small to fill")
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    return poly


def _rows(poly: Polygon, angle: float, spacing: float, extend: float) -> list[list[tuple[float, float]]]:
    """Horizontal segments (in the rotated frame) for each row: [[(x0, x1), ...], ...] bottom to top."""
    minx, miny, maxx, maxy = poly.bounds
    shapely.prepare(poly)
    rows = []
    y = miny + spacing / 2
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
        y += spacing
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
           start_near: Point | None = None, travel_within: Polygon | None = None, random: float = 0.0) -> list[Rec]:
    """Tatami fill of `poly`: serpentine rows grouped into regions, regions joined by travel.
    Travel runs inside `travel_within` (default `poly`), where later stitching covers it."""
    rot = affinity.rotate(poly, -angle, origin=(0, 0))
    rows = _rows(rot, angle, spacing, extend)
    miny = rot.bounds[1]
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
            y = miny + spacing / 2 + r * spacing
            pts += _row_stitches(x0, x1, y, stitch, (r % 3) * stitch / 3, fwd, random, r)
            fwd = not fwd
        return [to_world(p) for p in pts]

    # Each region can be sewn four ways (first row left-to-right or not, bottom-up or top-down).
    options = []
    for reg in regions:
        f, b = region_points(reg, True), region_points(reg, False)
        options.append([f, f[::-1], b, b[::-1]])

    # Order regions greedily: next is whichever region has an end nearest the needle.
    # Rows can extend past the edge by `extend` (pull compensation); travel may go there too.
    inside = (travel_within or poly).buffer(extend + 0.05)
    out: list[Rec] = []
    pos = start_near
    remaining = list(range(len(options)))
    while remaining:
        k, seq = min(
            ((k, seq) for k in remaining for seq in options[k]),
            key=lambda ks: dist(pos, ks[1][0]) if pos else 0.0,
        )
        remaining.remove(k)
        if out:  # the first region starts where it starts; `start_near` only chose it
            out += travel(pos, seq[0], inside)
        out += stitch_run(seq)
        pos = seq[-1]
    return out


def fill(outline: Sequence, holes: Sequence[Sequence], params: FillParams) -> tuple[list[Rec], list[str]]:
    poly = fill_polygon(outline, holes)
    warnings = []
    if poly.area < 4:
        warnings.append("This fill is very small; a satin or running stitch may sew more cleanly.")
    start = tuple(poly.exterior.coords[0])
    out: list[Rec] = []
    if "edge" in params.underlay:
        edge = poly.buffer(-0.5)
        if not edge.is_empty and edge.geom_type == "Polygon":
            ring = list(edge.exterior.coords)
            out += stitch_run(resample(ring, TRAVEL_STITCH_MM))
    if "tatami" in params.underlay:
        under = poly.buffer(-0.6)
        if not under.is_empty:
            if under.geom_type == "MultiPolygon":
                under = max(under.geoms, key=lambda g: g.area)
            pos = (out[-1][0], out[-1][1]) if out else start
            cross = tatami(under, params.angle_deg + 90, 2.0, 3.0, 0.0, pos, travel_within=poly)
            if out and cross:
                # Walk from the edge run to where the cross-hatch starts (not one long stitch).
                out += travel(pos, (cross[0][0], cross[0][1]), poly)
            out += cross
    pos = (out[-1][0], out[-1][1]) if out else start
    top = tatami(poly, params.angle_deg, params.spacing_mm, params.stitch_mm, params.pull_comp_mm / 2, pos,
                 random=params.random_pct / 100)
    if params.reverse and top and all(r[2] == STITCH for r in top):
        top = top[::-1]  # same stitches, sewn from the other end
    if out and top:
        out += travel(pos, (top[0][0], top[0][1]), poly.buffer(params.pull_comp_mm / 2 + 0.05))
    out += top
    return out, warnings


# ---------------------------------------------------------------- objects


def generate(obj: dict[str, Any]) -> tuple[list[Rec], list[str]]:
    """Stitches for one digitized object (geometry already in final position), with ties."""
    kind = obj.get("kind")
    g = obj.get("geometry") or {}
    p = obj.get("params") or {}
    if kind == "run":
        nodes = g.get("nodes") or []
        if len(nodes) < 2:
            raise DigitizeError("A running stitch needs at least two points")
        recs, warnings = running(nodes, RunParams.from_dict(p), bool(g.get("closed"))), []
    elif kind == "satin":
        recs, warnings = satin(g.get("rail_a") or [], g.get("rail_b") or [], SatinParams.from_dict(p))
    elif kind == "fill":
        recs, warnings = fill(g.get("outline") or [], g.get("holes") or [], FillParams.from_dict(p))
    elif kind == "applique":
        from .applique import AppliqueParams, applique

        # Applique ties each of its three parts itself (the machine cuts at each stop).
        return applique(g.get("outline") or [], AppliqueParams.from_dict(p))
    else:
        raise DigitizeError(f"Unknown object type: {kind}")
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
    # A mirror flips the winding of satin rails; keep rails in their original order anyway.
    return {**obj, "geometry": g}


def bounds(points: Sequence[Point]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


__all__ = [
    "DigitizeError", "FillParams", "RunParams", "SatinParams", "fill", "fill_polygon", "generate",
    "geometry_points", "running", "satin", "satin_pairs", "tatami", "tie_in", "tie_off", "transform_geometry", "travel",
]
