"""The craft line styles: backstitch, stem stitch, candlewicking, redwork and French knots.

`s` is the distance along the line, L the stitch length (stitch_mm) and n the unit normal
(-ty, tx) of its direction (tx, ty): on screen, the right hand side walking the way it was drawn.
Backstitch and stem stitch are laid from one sharp corner to the next, so a stitch never cuts
across one; candlewicking and redwork, which are single runs at heart, keep a needle point at
every point you clicked that isn't a curve point, as a single run does. Each refuses, before
laying anything out, a line that would take more stitches than any design.

Written from first principles for LUDD. Coordinates are mm. Imports from `..stitches` stay inside
the function bodies: stitches imports this package.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..paths import Point, corner_indices, cumulative, dist, flatten, point_at
from . import MAX_LINE_STITCHES, LineStyle, Param, register

CORNER_DEG = 35.0  # a turn sharper than this at a clicked point is a corner no stitch cuts across
CORNER_REACH_MM = 0.25  # how far either side of a point its turn is measured
SHORTEST_STEP_MM = 0.31  # half stitches are never laid closer than this: stitches under 0.3 mm are left out
KNOT_STITCHES = 12  # the stitches one knot takes, with the ones from and back to its middle
STAR = (0, 2, 4, 1, 3, 0, 2, 4, 1, 3, 0)  # a knot's five points drawn as a star, twice round


# ---------------------------------------------------------------- the line, measured


def _unit(a: Point, b: Point) -> Point:
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n > 1e-9 else (1.0, 0.0)


def _nearest_along(poly: Sequence[Point], cum: Sequence[float], p: Point) -> float:
    """How far along the line its point nearest `p` is; of equally near ones (to a millionth of a
    mm), the first, so that every computer begins a closed line at the same place."""
    best, along = math.inf, 0.0
    for i, (a, b) in enumerate(zip(poly, poly[1:])):
        dx, dy = b[0] - a[0], b[1] - a[1]
        square = dx * dx + dy * dy
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / square)) if square else 0.0
        off = math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1])
        if off < best - 1e-6:
            best, along = off, cum[i] + t * (cum[i + 1] - cum[i])
    return along


def _parts(length: float, longest: float, shortest: float = SHORTEST_STEP_MM) -> int:
    """How many equal parts to lay a stretch in: each at most `longest` long, and none under
    `shortest` (unless the whole stretch is). The ratios are rounded to a millionth first, so every
    computer counts the same."""
    return max(1, min(math.ceil(round(length / longest, 6)), math.floor(round(length / shortest, 6))))


class _Path:
    """A drawn line flattened, measured by the distance along it. A closed one begins where chosen
    (`start`). `kept` are the places of the points clicked that aren't curve points."""

    def __init__(self, nodes: Sequence, closed: bool, start: Point | None = None):
        poly, index = flatten(nodes, closed)
        if closed and poly:
            poly = [*poly, poly[0]]
        cum = cumulative(poly)
        total = cum[-1] if poly else 0.0
        marks = [cum[i] for i in corner_indices(nodes, index[: len(nodes)])]
        if closed and start is not None and total > 0:
            at = _nearest_along(poly, cum, start)
            if 1e-6 < at < total - 1e-6:
                first = point_at(poly, cum, at)
                poly = [first, *(p for p, s in zip(poly, cum) if s > at + 1e-9),
                        *(p for p, s in zip(poly[1:], cum[1:]) if s < at - 1e-9), first]
                marks = [(m - at) % total for m in marks]
                cum = cumulative(poly)
                total = cum[-1]
        self.closed, self.poly, self.cum, self.total = closed, poly, cum, total
        self.kept: list[float] = []
        for m in sorted(marks):
            if m > SHORTEST_STEP_MM and total - m > SHORTEST_STEP_MM and (
                    not self.kept or m - self.kept[-1] > SHORTEST_STEP_MM):
                self.kept.append(m)

    def at(self, s: float) -> Point:
        """The point `s` along the line (round and round a closed one)."""
        return point_at(self.poly, self.cum, s % self.total if self.closed else s)

    def turn(self, s: float) -> float:
        """How sharply the line turns at `s`, in degrees (to a thousandth)."""
        r = CORNER_REACH_MM
        before, after = (s - r, s + r) if self.closed else (max(0.0, s - r), min(self.total, s + r))
        a, b, c = self.at(before), self.at(s), self.at(after)
        u, v = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
        return round(math.degrees(abs(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]))), 3)

    def sharp(self) -> list[float]:
        """The kept points where the line turns sharply."""
        return [m for m in self.kept if self.turn(m) > CORNER_DEG]

    def stretches(self) -> list[tuple[float, float, bool]]:
        """The line from one sharp corner to the next, as (from, to, goes round): a closed line
        with no corner at all is one stretch that goes round."""
        corners = self.sharp()
        if self.closed and not corners and self.turn(0.0) <= CORNER_DEG:
            return [(0.0, self.total, True)]
        stops = [0.0, *corners, self.total]
        return [(a, b, False) for a, b in zip(stops, stops[1:])]

    def heading(self, s: float, lo: float, hi: float, loop: bool) -> Point:
        """The line's direction at `s`, seen within the stretch from `lo` to `hi` (so at a corner,
        the side being sewn)."""
        reach = 0.2
        if loop:
            return _unit(self.at(s - reach), self.at(s + reach))
        return _unit(self.at(max(lo, s - reach)), self.at(min(hi, s + reach)))

    def places(self, longest: float, extra: Sequence[float] = (), shortest: float = SHORTEST_STEP_MM) -> list[float]:
        """Where a single run along the line puts its needle, as distances along it: every kept
        point (and `extra` one), and the rest evenly, at most `longest` apart."""
        stops = [0.0, *sorted({*self.kept, *(e for e in extra if 0 < e < self.total)}), self.total]
        out = [0.0]
        for a, b in zip(stops, stops[1:]):
            n = _parts(b - a, longest, shortest)
            out += [a + (b - a) * k / n for k in range(1, n)] + [b]
        return out


def _sewable(points: list[Point]) -> list[Point]:
    """The points in order, leaving out any too near the one before to be a stitch, but always
    ending exactly on the last (so a closed line closes, and redwork ends where it began)."""
    from ..stitches import MIN_STITCH_MM

    kept: list[Point] = []
    for p in points:
        if not kept or dist(kept[-1], p) >= MIN_STITCH_MM:
            kept.append(p)
    if kept:
        while kept and dist(kept[-1], points[-1]) < MIN_STITCH_MM:
            kept.pop()
        kept.append(points[-1])
    return kept


def _refuse(estimate: float, how: str) -> None:
    """Refused before any of it is laid out: a long line (or many knots) could otherwise make
    millions of stitches and freeze LUDD."""
    from ..stitches import DigitizeError

    if estimate > MAX_LINE_STITCHES:
        raise DigitizeError(f"This line would need about {estimate:,.0f} stitches, far more than any design. {how}")


# ---------------------------------------------------------------- backstitch and stem stitch


def _half_steps(length: float, stitch: float, loop: bool) -> int:
    """How many half stitches a stretch takes (round a loop, at least four)."""
    return max(4 if loop else 2, _parts(length, stitch / 2))


def _back_order(n: int, loop: bool) -> list[int]:
    """Backstitch's holes in sewing order, counted in half stitches: forward two, back one. Round
    a loop it goes on until the first half stitch is covered three times too."""
    out = [0]
    for i in range(n if loop else n - 1):
        out.append(i + 2)
        if loop or i + 2 < n:
            out.append(i + 1)
    return out


def _backstitch(nodes, params, closed=False, start=None) -> list[Point]:
    """Forward a stitch, back half of one: a hole every half stitch, three threads thick."""
    path = _Path(nodes, closed, start)
    if path.total <= 0:
        return path.poly[:1]
    _refuse(4 * path.total / params.stitch_mm + 2 * len(path.kept), "Make it shorter, or make its stitches longer.")
    out: list[Point] = []
    for a, b, loop in path.stretches():
        n = _half_steps(b - a, params.stitch_mm, loop)
        out += [path.at(a + (k % n if loop else k) * (b - a) / n) for k in _back_order(n, loop)]
    return _sewable(out)


def _stem(nodes, params, closed=False, start=None) -> list[Point]:
    """Stitches a stitch long slanting across the line, half the Width off it on either side, each
    starting half way along the one before: a rope."""
    path = _Path(nodes, closed, start)
    if path.total <= 0:
        return path.poly[:1]
    _refuse(4 * path.total / params.stitch_mm + 2 * len(path.kept), "Make it shorter, or make its stitches longer.")
    off = params.value("stem_width_mm") / 2
    out: list[Point] = []
    for a, b, loop in path.stretches():
        n = _half_steps(b - a, params.stitch_mm, loop)

        def hole(k: int, side: int) -> Point:
            """Half stitch k along the stretch, `off` to the side of the line: -1 or 1 along n."""
            s = a + (k % n if loop else k) * (b - a) / n
            x, y = path.at(s)
            tx, ty = path.heading(s, a, b, loop)
            return x - side * off * ty, y + side * off * tx

        for i in range(n if loop else n - 1):
            out += [hole(i, -1), hole(i + 2, 1)]  # then back to the next one's start
        if loop:
            out.append(hole(0, -1))
    if closed and len(out) > 1 and dist(out[0], out[-1]) > 1e-9:
        out.append(out[0])
    return _sewable(out)


# ---------------------------------------------------------------- knots


def _knot(middle: Point, along: Point, size: float) -> list[Point]:
    """One knot's needle points after its middle: five points round it, `size` across, drawn as a
    star twice round (ten stitches of about 0.95 x size), and back to the middle."""
    r = size / 2
    ux, uy = along
    ring = []
    for k in range(5):
        a = 2 * math.pi * k / 5
        co, si = math.cos(a), math.sin(a)
        ring.append((middle[0] + r * (ux * co - uy * si), middle[1] + r * (uy * co + ux * si)))
    return [*(ring[i] for i in STAR), middle]


def _knot_places(total: float, closed: bool, gap: float, size: float) -> list[float]:
    """Where candlewicking's knots go: evenly along the line, as near `gap` apart as whole gaps
    allow and never nearer than `size` + 1; an open line has one at each end, unless it's too
    short for two (then one in the middle)."""
    n = math.floor(round(total / gap, 6) + 0.5)
    n = min(n, math.floor(round(total / (size + 1), 6)))
    if closed:
        return [total * (k / max(n, 1)) for k in range(max(n, 1))]
    if n < 1:
        return [total / 2]
    return [total * (k / n) for k in range(n + 1)]


def _candlewick(nodes, params, closed=False, start=None) -> list[Point]:
    """A single run along the line that stops to sew a knot, centered on it, at each knot's place."""
    from ..stitches import DigitizeError

    size, gap = params.value("knot_mm"), params.value("knot_gap_mm")
    if gap < size + 1 - 1e-9:
        raise DigitizeError(f"Knots this close would touch: make the gap at least {size + 1:g} mm")
    path = _Path(nodes, closed, start)
    if path.total <= 0:
        return path.poly[:1]
    _refuse(path.total / params.stitch_mm + len(path.kept) + KNOT_STITCHES * (path.total / gap + 1),
            "Make it shorter, or put its knots further apart.")
    knots = _knot_places(path.total, closed, gap, size)
    at_knot = set(knots)
    out: list[Point] = []
    for s in path.places(params.stitch_mm, knots):
        out.append(path.at(s))
        if s in at_knot:
            out += _knot(path.at(s), path.heading(s, 0.0, path.total, closed), size)
    return out


def _spaced(points: list[Point], apart: float) -> list[Point]:
    """The points in order, leaving out any closer than `apart` to one already taken."""
    cells: dict[tuple[int, int], list[Point]] = {}
    taken = []
    for p in points:
        i, j = math.floor(p[0] / apart), math.floor(p[1] / apart)
        if any(dist(p, q) < apart - 1e-6 for di in (-1, 0, 1) for dj in (-1, 0, 1)
               for q in cells.get((i + di, j + dj), ())):
            continue
        cells.setdefault((i, j), []).append(p)
        taken.append(p)
    return taken


def _french_knots(nodes, params, closed=False, start=None) -> list:
    """A knot at every point clicked, with a jump from each to the next (trimmed when it's over
    3 mm). A closed line starts at the knot nearest `start`."""
    from ..stitches import stitch_run, travel

    size = params.value("knot_mm")
    points = [(float(n[0]), float(n[1])) for n in nodes]
    places = _spaced(points, size)
    _refuse(KNOT_STITCHES * len(places), "Make the line with fewer points.")
    left_out = len(points) - len(places)
    if left_out:
        params.notes.append(f"{left_out} French knot{' was' if left_out == 1 else 's were'} left out: points closer "
                            f"together than the knot size ({size:g} mm) would pile one knot on another. Move them "
                            "further apart to sew them all.")
    if closed and start is not None and places:
        k = min(range(len(places)), key=lambda i: (round(dist(places[i], start), 6), i))
        places = places[k:] + places[:k]
    out: list = []
    for i, middle in enumerate(places):
        if i + 1 < len(places):
            along = _unit(middle, places[i + 1])
        else:
            along = _unit(places[i - 1], middle) if i else (1.0, 0.0)
        if out:
            out += travel(out[-1][:2], middle)  # nothing between knots hides thread: a jump
        out += stitch_run([middle, *_knot(middle, along, size)])
    return out


# ---------------------------------------------------------------- run redwork


def _redwork(nodes, params, closed=False, start=None) -> list[Point]:
    """Out along the line and back, the way back's holes midway between the way out's (a closed
    line goes round twice), ending where it started. Where the way back passes a sharp corner it
    goes through it too."""
    path = _Path(nodes, closed, start)
    if path.total <= 0:
        return path.poly[:1]
    _refuse(2 * path.total / params.stitch_mm + 3 * len(path.kept), "Make it shorter, or make its stitches longer.")
    # Out in stitches of at least two half steps, so that the holes between them can be sewn.
    out = path.places(params.stitch_mm, shortest=2 * SHORTEST_STEP_MM)
    sharp = set(path.sharp())
    middles = [(a + b) / 2 for a, b in zip(out, out[1:])]
    back: list[float] = []
    if closed:
        for i, m in enumerate(middles):
            back.append(m)
            if out[i + 1] in sharp:
                back.append(out[i + 1])
        back.append(path.total)
    else:
        for i in range(len(middles) - 1, -1, -1):
            back.append(middles[i])
            if out[i] in sharp:
                back.append(out[i])
        back.append(0.0)
    return _sewable([path.at(s) for s in [*out, *back]])


KNOT_SIZE = Param(1.6, 1.0, 3.0, "Knot size")

register(LineStyle("backstitch", points=_backstitch))
register(LineStyle("stem", params={"stem_width_mm": Param(0.8, 0.3, 2.5, "Width")}, points=_stem))
register(LineStyle("candlewick", params={"knot_mm": KNOT_SIZE, "knot_gap_mm": Param(4.0, 2.0, 15.0, "Between knots")},
                   points=_candlewick))
register(LineStyle("redwork", points=_redwork))
register(LineStyle("knots", params={"knot_mm": KNOT_SIZE}, recs=_french_knots))
