"""Maze fill: one path that winds into the shape and back out between its own turns, never
crossing itself.

Rings follow the outline inward, Path spacing apart, the first half a spacing in (as the Contour
fill's do). The odd rings (1st, 3rd, ...) are linked into a spiral going in, and the even ones into
a spiral coming back out: each ring is left open next to where the ring before it was opened, and
joined to the ring two further in by a short diagonal through the opening of the one between. The
two spirals meet in the middle, so the path starts at the edge and ends beside where it began.

Where rings further in pinch the shape into pieces, each piece gets a maze of its own, put into
the path from the ring around them by two short steps side by side: still one path, and nothing
crosses. Pieces already apart at the first ring, and the halves of a shape with a hole (it's cut
open straight up and down through each hole), get separate mazes: each opens facing the one
before, and the travel between them goes round that one's outer ring. A shape in more than four
pieces, or with a hole, gets a warning that suggests Contour.

Every path is checked: it mustn't cross itself or leave the shape. Written from first principles
for LUDD. Coordinates are mm. Imports from `..stitches` stay inside the function bodies.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from typing import Iterator

import numpy as np
import shapely
from shapely.geometry import LineString, Point as ShapelyPoint, Polygon, box
from shapely.geometry.polygon import orient
from shapely.strtree import STRtree

from ..paths import Point, cumulative, dist, point_at
from ..patterns import polygons
from . import FillPattern, Param, register
from .motif import kept_points, own_frame, place

BRANCHED_WARNING = "This shape is too branched for one maze; Contour may suit it better."
MOST_PIECES = 4
SIMPLIFY_MM = 0.02  # a wobbly outline with thousands of points buffers very slowly
GAP_SHARES = (1.0, 1.5, 0.75, 2.0)  # how wide a ring is left open, in Path spacings (tried in turn)
SAG_MM = 0.08  # no stitch cuts further than this inside the curve it follows
SHORTEST_STEP_MM = 0.6  # stitches aren't made shorter than this to follow a tight curve
CORNER = 0.906307787  # the cosine of 25 degrees: turns sharper than that are corners, kept
CUT_MM = 0.002  # the slit that opens a shape at a hole
# How near two stitches that don't meet may come: this far apart if any layout allows it, else at
# least TOUCH_MM, so thread never lies on thread.
CLEAR_MM, TOUCH_MM = 0.2, 0.05
OPENINGS_TRIED = 6  # once some rings have to be left out, only the best places are tried
SMALL_MAZE_MM = 3000.0  # rings no longer than this in all are quick enough to try every place (see _spirals)
TRIES_PER_PIECE = 12  # ways of making a pinched-off piece's maze tried before it's sewn apart


def _about(v: float) -> float:
    """v to the nearest tenth, for choosing between near equals. The steps fall between the round
    numbers shapes are drawn at, so a last digit can't tip one either way."""
    return round(v + 0.0123, 1)


def _tidy(polygon: Polygon, tolerance: float) -> Polygon:
    """The polygon without the points its outline and holes can do without, each ring started at
    its top left (see motif.kept_points)."""

    def ring(r) -> list[Point]:
        points = [tuple(p) for p in np.round(np.asarray(r.coords, dtype=float)[:-1, :2], 6).tolist()]
        k = min(range(len(points)), key=lambda i: (round(points[i][1], 3), round(points[i][0], 3), i))
        closed = points[k:] + points[: k + 1]
        return [closed[i] for i in kept_points(closed, tolerance)]

    shell, holes = ring(polygon.exterior), [ring(r) for r in polygon.interiors]
    if len(shell) < 4 or any(len(h) < 4 for h in holes):
        return polygon
    tidied = Polygon(shell, holes)
    return tidied if tidied.is_valid else polygon


class _Ring:
    """A closed ring, walked by distance along it: the same way round every time, from its top left
    point."""

    def __init__(self, polygon):
        xy = np.round(np.asarray(orient(polygon, 1.0).exterior.coords, dtype=float)[:-1, :2], 6)
        points = [tuple(p) for p in xy.tolist()]
        points = [p for i, p in enumerate(points) if p != points[i - 1]]  # no point twice running
        k = min(range(len(points)), key=lambda i: (round(points[i][1], 3), round(points[i][0], 3), i))
        self.points = points[k:] + points[:k]
        self.closed = [*self.points, self.points[0]]
        self.cum = cumulative(self.closed)
        self.length = self.cum[-1]
        self._starts = np.asarray(self.closed[:-1])
        self._steps = np.asarray(self.closed[1:]) - self._starts
        self._squares = np.maximum((self._steps ** 2).sum(axis=1), 1e-18)

    def point(self, s: float) -> Point:
        return point_at(self.closed, self.cum, s % self.length)

    def project(self, where: Point) -> float:
        """How far round the ring its point nearest `where` is."""
        t = np.clip(((np.asarray(where) - self._starts) * self._steps).sum(axis=1) / self._squares, 0.0, 1.0)
        off = self._starts + self._steps * t[:, None] - np.asarray(where)
        i = int(np.argmin(np.round(np.hypot(off[:, 0], off[:, 1]), 6)))
        return self.cum[i] + float(t[i]) * (self.cum[i + 1] - self.cum[i])

    def walk(self, s: float, length: float) -> list[Point]:
        """The ring's points from `s` going forward `length`, both ends exactly there."""
        s %= self.length
        n = len(self.points)
        out = [self.point(s)]
        j = bisect.bisect_right(self.cum, s)
        while self.cum[j % n] + self.length * (j // n) < s + length - 1e-9:
            out.append(self.points[j % n])
            j += 1
        out.append(self.point(s + length))
        return [p for i, p in enumerate(out) if i == 0 or dist(p, out[i - 1]) > 1e-9]


@dataclass
class _Piece:
    rings: list  # _Ring, outermost first, each Path spacing inside the one before
    pieces: list  # the _Pieces its innermost ring pinches into
    outline: object  # the first ring's polygon


def _pieces(geom, spacing: float) -> list:
    """The pieces of an offset big enough for a ring, with necks and slivers too thin for two rows
    of thread opened out, in a fixed order."""
    thin = max(0.15, 0.2 * spacing)
    out = []
    for g in polygons(geom):
        opened = g.buffer(-thin, join_style="mitre").buffer(thin, join_style="mitre")
        # Nothing thin: keep the piece as it is (cutting an identical outline back to it would
        # leave extra points wherever the last digit happened to put them).
        parts = [g] if g.symmetric_difference(opened).area < 0.01 else polygons(opened.intersection(g))
        for part in parts:
            part = _tidy(part, 0.01)
            if not part.is_empty and part.exterior.length >= max(1.5 * spacing, 4.0) - 1e-3:
                out.append(part)
    return sorted(out, key=lambda p: (round(p.bounds[1], 2), round(p.bounds[0], 2), round(p.area, 2)))


def _tree(polygon, spacing: float) -> _Piece:
    """A piece's rings inward, until they run out or pinch it into more than one piece."""
    rings, shape = [_Ring(polygon)], polygon
    while True:
        inner = _pieces(shape.buffer(-spacing, join_style=1), spacing)
        if len(inner) != 1:
            return _Piece(rings, [_tree(p, spacing) for p in inner], polygon)
        shape = inner[0]
        rings.append(_Ring(shape))


def _count(piece: _Piece) -> int:
    """How many pieces a piece ends up as."""
    return sum(map(_count, piece.pieces)) if piece.pieces else 1


def _cut_open(shape) -> list:
    """The shape in pieces without holes: each hole is slit straight up and down through its
    middle."""
    from ..stitches import MIN_PART_MM2

    waiting, whole = [shape], []
    while waiting:
        piece = waiting.pop()
        if not piece.interiors:
            whole.append(piece)
            continue
        x0, _, x1, _ = min((r.bounds for r in piece.interiors), key=lambda b: (round(b[0], 3), round(b[1], 3)))
        middle = (x0 + x1) / 2
        slit = box(middle - CUT_MM / 2, piece.bounds[1] - 1, middle + CUT_MM / 2, piece.bounds[3] + 1)
        waiting += [shapely.transform(p, lambda xy: np.round(xy, 6)) for p in polygons(piece.difference(slit))
                    if p.area >= MIN_PART_MM2]
    return sorted(whole, key=lambda p: (round(p.bounds[1], 2), round(p.bounds[0], 2), round(p.area, 2)))


# ---------------------------------------------------------------- needle points


def _from_segment(p: Point, a: Point, b: Point) -> float:
    """How far p is from the straight line from a to b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    square = dx * dx + dy * dy
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / square)) if square else 0.0
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _strays(line: list[Point], cum: list[float], a: float, b: float) -> bool:
    """Whether the line between distances a and b along it strays more than SAG_MM from a
    straight stitch."""
    p, q = point_at(line, cum, a), point_at(line, cum, b)
    return any(_from_segment(line[k], p, q) > SAG_MM
               for k in range(bisect.bisect_right(cum, a), bisect.bisect_left(cum, b)))


def _along_curve(line: list[Point], longest: float) -> list[Point]:
    """Needle points along a stretch of a ring, from its start to its end: evenly spaced where
    that keeps every stitch within SAG_MM of it, else closer together where it curves."""
    cum = cumulative(line)
    total = round(cum[-1], 6)  # so a last digit can't add a stitch
    n = max(1, math.ceil(total / longest - 1e-9))
    stops = [total * i / n for i in range(n + 1)]
    if any(_strays(line, cum, a, b) for a, b in zip(stops, stops[1:])):
        stops = [0.0]
        while total - stops[-1] > 1e-6:
            s = stops[-1]
            step = min(longest, total - s)
            while step > SHORTEST_STEP_MM and _strays(line, cum, s, s + step):
                step = max(SHORTEST_STEP_MM, 0.8 * step)
            if 1e-6 < total - s - step < SHORTEST_STEP_MM:  # no stub left at the end
                step = (total - s) / 2
            stops.append(s + step)
    return [line[0], *(point_at(line, cum, s) for s in stops[1:-1]), line[-1]]


def _corners(walk: list[Point]) -> list[int]:
    """Where a walk round a ring turns sharply, wiggles under 0.1 mm smoothed over (as
    paths.sharp_points finds corners, but the same on every computer)."""
    keep = kept_points(walk, 0.1)
    found = []
    for a, i, c in zip(keep, keep[1:], keep[2:]):
        ux, uy = walk[i][0] - walk[a][0], walk[i][1] - walk[a][1]
        vx, vy = walk[c][0] - walk[i][0], walk[c][1] - walk[i][1]
        if ux * vx + uy * vy < CORNER * math.hypot(ux, uy) * math.hypot(vx, vy):
            found.append(i)
    return found


def _ring_needles(walk: list[Point], longest: float) -> list[Point]:
    """Needle points along part of a ring, its sharp corners kept."""
    stops = sorted({0, len(walk) - 1, *_corners(walk)})
    out = walk[:1]
    for a, b in zip(stops, stops[1:]):
        out += _along_curve(walk[a : b + 1], longest)[1:]
    return out


def _spaced(path: list[Point], on: list) -> tuple[list[Point], list]:
    """The path without points too close to the one before to be a stitch (as sewing drops them,
    so the check is on exactly what's sewn)."""
    from ..stitches import MIN_STITCH_MM

    kept, tags = [], []
    for p, tag in zip(path, on):
        if not kept or dist(kept[-1], p) >= MIN_STITCH_MM:
            kept.append(p)
            tags.append(tag)
    return kept, tags


# ---------------------------------------------------------------- one maze


def _build(rings: list, opening: float, gap: float, longest: float,
           most_step: float = math.inf) -> tuple[list[Point], list] | None:
    """The double spiral over `rings`, the first opened `opening` mm round it: its needle points
    and which ring each is on (None for the steps between rings). None if a step between rings
    would be longer than `most_step`."""
    from ..stitches import _subdivide

    at = [opening]
    for k in range(1, len(rings)):  # each ring opened next to where the one before it was
        at.append(rings[k].project(rings[k - 1].point(at[-1])))
    gaps = [min(gap, r.length / 3) for r in rings]
    walks = [r.walk(a, r.length - g) for r, a, g in zip(rings, at, gaps)]  # all but the opening
    legs: list[tuple[int | None, list[Point]]] = []

    def ring_leg(k: int, points: list[Point]) -> None:
        if legs:
            legs.append((None, [legs[-1][1][-1], points[0]]))
        legs.append((k, points))

    for k in range(0, len(rings), 2):  # in along the 1st, 3rd, 5th...
        ring_leg(k, walks[k])
    for k in reversed(range(1, len(rings), 2)):  # ...and back out along the others, the other way
        ring_leg(k, walks[k][::-1])
    if len(rings) > 1:  # out to the edge, into the first ring's opening, beside where it began
        legs.append((None, [legs[-1][1][-1], rings[0].point(at[0] - gaps[0] / 2)]))
    if any(dist(*points) > most_step for k, points in legs if k is None):
        return None
    path, on = [], []
    for k, points in legs:
        needles = _subdivide(points, longest) if k is None else _ring_needles(points, longest)
        path += needles
        on += [k] * len(needles)
    return _spaced(path, on)


def _room(path: list[Point], cover) -> float:
    """How near two stitches of the path that don't meet come to each other, in mm to a millionth,
    looking no further than CLEAR_MM; -1 if the path crosses itself or leaves the shape."""
    if len(path) < 2:
        return -1.0
    line = LineString(path)
    if not line.is_simple or not cover.covers(line):
        return -1.0
    xy = np.asarray(path)
    steps = shapely.linestrings(np.stack([xy[:-1], xy[1:]], axis=1))
    low, high = np.minimum(xy[:-1], xy[1:]) - CLEAR_MM, np.maximum(xy[:-1], xy[1:]) + CLEAR_MM
    i, j = STRtree(steps).query(shapely.box(low[:, 0], low[:, 1], high[:, 0], high[:, 1]))
    apart = j > i + 1
    near = shapely.distance(steps[i[apart]], steps[j[apart]])
    return round(min(CLEAR_MM, float(near.min())) if len(near) else CLEAR_MM, 6)


def _openings(ring: _Ring) -> list[float]:
    """Where a ring might be opened, best first: the middles of its longest straight sides (of
    equal ones, the top one first), then places evenly round it."""
    sides = []
    for i, (a, b) in enumerate(zip(ring.closed, ring.closed[1:])):
        length = dist(a, b)
        if round(length, 3) >= 2.0:
            sides.append((-_about(length), _about((a[1] + b[1]) / 2), _about((a[0] + b[0]) / 2),
                          ring.cum[i] + length / 2))
    return [s for *_, s in sorted(sides)[:8]] + [ring.length * i / 16 for i in range(16)]


def _openings_near(ring: _Ring, where: Point) -> list[float]:
    """Where a ring might be opened, the places nearest `where` first."""
    return [ring.project(where), *sorted(_openings(ring), key=lambda s: round(dist(ring.point(s), where), 3))]


def _openings_facing(ring: _Ring, line: LineString) -> list[float]:
    """Where a ring might be opened, the places facing `line` first (of equally near ones, the
    best sides first)."""
    return sorted(_openings(ring), key=lambda s: _about(line.distance(ShapelyPoint(ring.point(s)))))


def _spirals(rings: list, openings: list[float], spacing: float, longest: float, cover) -> Iterator[tuple]:
    """Mazes over a piece's rings that cross nowhere and stay in the shape, best first, as
    (needle points, the ring each is on, how many rings). All the rings if any way works, else
    fewer rings (the middle is left open); the first ring alone always works. With all the rings,
    a way keeping stitches CLEAR_MM apart is looked for first: from every place while there's
    little to sew (each try takes longer the more there is), else from the best OPENINGS_TRIED.
    A way keeping them only TOUCH_MM apart (so that thread never lies on thread) is next best."""
    n = len(rings)
    counts = sorted({c for c in [n, n - 1, n - 2, *(n - 2**i for i in range(2, 12))] if c > 1}, reverse=True)
    little = sum(r.length for r in rings) <= SMALL_MAZE_MM
    for count in counts:
        found = False
        close: list = []  # ways found while looking for a roomier one, that keep only TOUCH_MM apart
        places = openings if count == n else openings[:OPENINGS_TRIED]
        roomy = 0 if count < n else len(places) if little else OPENINGS_TRIED  # places searched for room
        for k, opening in enumerate(places):
            if k == roomy and close:
                found = True
                yield from close
                close = []
            wanted = CLEAR_MM if k < roomy else TOUCH_MM
            for share in GAP_SHARES:
                gap = share * spacing
                # Steps between rings stay short: a long one crosses to another part of a ring.
                built = _build(rings[:count], opening, gap, longest, 2 * math.hypot(2 * spacing, gap) + 0.5)
                if built is None:
                    continue
                path, on = built
                room = _room(path, cover)
                if room >= wanted:
                    found = True
                    yield path, on, count
                elif room >= TOUCH_MM:
                    close.append((path, on, count))
        if close:
            found = True
            yield from close
        if found:
            return
    path, on = _build(rings[:1], openings[0], spacing, longest)
    yield path, on, 1


def _grow(piece: _Piece, openings: list[float], spacing: float, longest: float, cover) -> Iterator[tuple]:
    """Mazes of a piece with the pieces pinched off inside it put in, best first: (needle points,
    the ring each is on, [(maze, its outer ring)] of pieces that couldn't be put in)."""
    for path, on, count in _spirals(piece.rings, openings, spacing, longest, cover):
        apart: list = []
        for inner in piece.pieces:
            joined = _put_in(path, on, count - 1, inner, spacing, longest, cover)
            if joined is None:
                alone, _, more = next(_grow(inner, _openings(inner.rings[0]), spacing, longest, cover))
                apart += [(alone, inner.rings[0]), *more]
            else:
                path, on, more = joined
                apart += more
        yield path, on, apart


def _away(p: Point, starts: np.ndarray, ends: np.ndarray) -> np.ndarray:
    """How far p is from each of the straight lines from starts to ends."""
    steps = ends - starts
    squares = np.maximum((steps ** 2).sum(axis=1), 1e-18)
    t = np.clip(((np.asarray(p) - starts) * steps).sum(axis=1) / squares, 0.0, 1.0)
    off = starts + steps * t[:, None] - np.asarray(p)
    return np.hypot(off[:, 0], off[:, 1])


def _put_in(path: list[Point], on: list, ring: int, inner: _Piece, spacing: float, longest: float, cover):
    """The maze of a piece pinched off inside ring `ring`, put into `path`: a short stretch of that
    ring beside it is cut out, and the piece is sewn from there and back again by two short steps
    side by side. (path, tags, mazes of pieces inside it left apart), or None if no way of doing it
    keeps the path from crossing itself."""
    host = [i for i in range(len(path) - 1) if on[i] == ring and on[i + 1] == ring]
    if not host:
        return None
    starts, ends = np.asarray([path[i] for i in host]), np.asarray([path[i + 1] for i in host])
    first = inner.rings[0]
    facing = sorted(_openings(first), key=lambda s: _about(float(_away(first.point(s), starts, ends).min())))
    for tries, (piece_path, _, apart) in enumerate(_grow(inner, facing, spacing, longest, cover)):
        if tries >= TRIES_PER_PIECE:
            break
        (ax, ay), (bx, by) = piece_path[0], piece_path[-1]
        nearest = np.argsort(np.round(_away(((ax + bx) / 2, (ay + by) / 2), starts, ends), 3), kind="stable")
        for k in nearest[:4]:
            for way in (piece_path, piece_path[::-1]):
                joined = _joined(path, on, host[int(k)], way, ring, spacing, longest)
                if joined is not None and _room(joined[0], cover) >= TOUCH_MM:
                    return joined[0], joined[1], apart
    return None


def _joined(path: list[Point], on: list, i: int, piece: list[Point], ring: int, spacing: float, longest: float):
    """`path` with `piece` sewn in the middle of its step i (on ring `ring`): across to the piece's
    start from one point of the step and back from its end to another a little further on. None if
    either way across is long."""
    from ..stitches import _subdivide

    p, q = path[i], path[i + 1]
    length = dist(p, q)
    width = min(max(dist(piece[0], piece[-1]), 0.5), length)
    middle = ((piece[0][0] + piece[-1][0]) / 2, (piece[0][1] + piece[-1][1]) / 2)
    along = ((middle[0] - p[0]) * (q[0] - p[0]) + (middle[1] - p[1]) * (q[1] - p[1])) / length
    t0 = min(max(0.0, along - width / 2), length - width)
    cuts = [(p[0] + (q[0] - p[0]) * t / length, p[1] + (q[1] - p[1]) * t / length) for t in (t0, t0 + width)]
    if max(dist(cuts[0], piece[0]), dist(piece[-1], cuts[1])) > 2 * spacing + width + 0.5:
        return None
    added = _subdivide([cuts[0], piece[0]], longest)[:-1] + piece + _subdivide([piece[-1], cuts[1]], longest)[1:]
    tags = [ring, *[None] * (len(added) - 2), ring]
    return _spaced(path[: i + 1] + added + path[i + 1 :], on[: i + 1] + tags + on[i + 1 :])


def _line_of(ring: _Ring) -> LineString:
    return LineString(ring.closed)


def _round_ring(ring: _Ring, a: Point, b: Point, longest: float) -> list[Point]:
    """The travel from a (on the ring) the shorter way round it to its point nearest b."""
    from ..stitches import TRAVEL_STITCH_MM

    s, t = ring.project(a), ring.project(b)
    ahead = (t - s) % ring.length
    walk = ring.walk(s, ahead) if ahead <= ring.length - ahead else ring.walk(t, ring.length - ahead)[::-1]
    return _ring_needles(walk, min(TRAVEL_STITCH_MM, longest))[1:]


def _mazes(roots: list, spacing: float, longest: float, cover, dot: Point | None) -> list[tuple]:
    """Each maze with its outer ring, in sewing order: the first by the green dot when there is
    one (else the top one, facing the next), then always the nearest, opening toward the one
    before."""
    waiting = list(roots)
    done: list[tuple] = []
    while waiting:
        if done:
            before = _line_of(done[-1][1])
            k = min(range(len(waiting)), key=lambda i: (round(before.distance(waiting[i].outline), 3), i))
        else:
            k = 0 if dot is None else min(range(len(waiting)), key=lambda i: (
                round(waiting[i].outline.exterior.distance(ShapelyPoint(dot)), 3), i))
        root = waiting.pop(k)
        ring = root.rings[0]
        if done:
            openings = _openings_facing(ring, _line_of(done[-1][1]))
        elif dot is not None:
            openings = _openings_near(ring, dot)
        elif waiting:
            mine = root.outline.exterior
            other = min(waiting, key=lambda r: (round(mine.distance(r.outline.exterior), 3),
                                                round(r.outline.bounds[1], 2), round(r.outline.bounds[0], 2)))
            openings = _openings_facing(ring, _line_of(other.rings[0]))
        else:
            openings = _openings(ring)
        path, _, apart = next(_grow(root, openings, spacing, longest, cover))
        done += [(path, ring), *apart]
    return done


def _paths(poly, params, pos):
    """The maze over one piece of a fill: one path, unless the shape has holes or pieces apart
    from the first ring; then each maze is a path, going on round its outer ring toward the next."""
    from ..stitches import LONG_STITCH_MM

    spacing = params.value("maze_mm")
    longest = min(max(params.stitch_mm, 1.0), LONG_STITCH_MM)
    local, origin = own_frame(poly)
    base = _tidy(local, SIMPLIFY_MM)
    roots = [_tree(p, spacing) for part in _cut_open(base)
             for p in _pieces(part.buffer(-spacing / 2, join_style=1), spacing)]
    if not roots:
        return [], []
    branched = bool(local.interiors) or sum(map(_count, roots)) > MOST_PIECES
    cover = local.buffer(0.05)
    shapely.prepare(cover)
    dot = (pos[0] - origin[0], pos[1] - origin[1]) if params.start_mm is not None else None
    mazes = _mazes(roots, spacing, longest, cover, dot)
    paths = []
    for (path, ring), after in zip(mazes, [*mazes[1:], None]):
        if after is not None:
            path = path + _round_ring(ring, path[-1], after[0][0], longest)
        paths.append(_spaced(path, [None] * len(path))[0])
    return [place(p, origin) for p in paths], [BRANCHED_WARNING] if branched else []


register(FillPattern("maze", "open", params={"maze_mm": Param(2.0, 0.8, 6.0, "Path spacing")}, paths=_paths,
                     step_mm2=lambda p: p.value("maze_mm") * min(p.stitch_mm, 3.0), auto_underlay=lambda level: []))
