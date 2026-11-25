"""The spiral fill: one line that winds from the middle of a shape out to its edge.

An Archimedean spiral, its rings `spiral_mm` apart, is drawn round the middle of the shape's
widest spot and cut to the shape. The first stretch of it inside the shape is sewn from the
middle out. Then each time comes the stretch with an end nearest along the edge the needle is on,
sewn from that end and joined along the edge: nothing covers an open fill, so a thread straight
across it would show, and taking the nearest keeps joining thread from piling up on the edge. On
the tight turns near the middle the needle goes down more often, so a stitch doesn't cut far
across the curve.

Written from first principles for LUDD. Coordinates are mm. Imports from `..stitches` stay inside
the function bodies: stitches imports this package.
"""

from __future__ import annotations

import bisect
import math
from collections import Counter, defaultdict

import numpy as np
import shapely
from shapely.geometry import LineString, Point as ShapelyPoint
from shapely.ops import substring

from ..paths import Point, dist, resample, sharp_points
from . import FillPattern, Param, register

SAMPLE_MM = 0.5  # how finely the spiral is drawn before it's cut to the shape
CLIP_SAMPLES = 500  # samples cut at a time: ordering the cuts of a whole big spiral at once is slow
SHORTEST_PIECE_MM = 1.0  # stretches inside the shape no longer than this are left out
SAME_WIDTH_MM = 0.1  # a spot that near the biggest circle's radius from the outline is as wide
SHORTEST_STITCH_MM = 0.8  # the stitch length aimed for on the tightest turns
SAG_MM = 0.15  # on a circle of radius r, a stitch 2 * sqrt(2 * SAG_MM * r) long cuts this far inside it
TIGHT_MM = 0.6  # rings closer than this get a warning
TIGHT_WARNING = "Rings this close sew like a solid fill and can pucker in the middle; 1 mm or more is safer."


def _middle(shape) -> Point:
    """The middle of the shape's widest spot: the center of the biggest circle that fits inside. When
    many spots are as wide (all along the middle of a rectangle), the search may pick one near an
    end, so the shape's centroid is used if it is one of them."""
    if hasattr(shapely, "maximum_inscribed_circle"):  # shapely 2.1 and later
        circle = shapely.maximum_inscribed_circle(shape)  # a line from its center to the outline
        centroid = shape.centroid
        if shape.contains(centroid) and shape.boundary.distance(centroid) >= circle.length - SAME_WIDTH_MM:
            return centroid.x, centroid.y
        x, y = circle.coords[0]
        return x, y
    p = shape.representative_point()
    return p.x, p.y


def _spiral(middle: Point, spacing: float, reach: float) -> list[Point]:
    """Points every SAMPLE_MM along a spiral round `middle` with rings `spacing` apart, from half a
    ring out until it's further than `reach` from the middle."""
    a = spacing / (2 * math.pi)  # the radius is a * theta
    r = spacing / 2
    theta = r / a
    points = [(middle[0] + r * math.cos(theta), middle[1] + r * math.sin(theta))]
    while r <= reach:
        theta += SAMPLE_MM / math.hypot(r, a)
        r = a * theta
        points.append((middle[0] + r * math.cos(theta), middle[1] + r * math.sin(theta)))
    return points


def _clip(spiral: list[Point], shape):
    """The parts of the spiral inside the shape as lists of points, in order from the middle out."""
    for first in range(0, len(spiral) - 1, CLIP_SAMPLES):
        line = LineString(spiral[first : first + CLIP_SAMPLES + 1])
        inside = [g for g in shapely.get_parts(line.intersection(shape)) if g.geom_type == "LineString" and g.length > 0]
        if not inside:
            continue
        # The overlay promises neither an order nor a direction: find where on the line each one lies.
        ends = shapely.line_locate_point(line, [shapely.get_point(g, i) for g in inside for i in (0, -1)])
        placed = sorted((min(s, e), list(g.coords)[:: 1 if s <= e else -1])
                        for g, s, e in zip(inside, ends[::2], ends[1::2]))
        yield from (points for _, points in placed)


def _pieces(spiral: list[Point], shape) -> list[list[Point]]:
    """The stretches of the spiral inside the shape, from the middle out."""
    from ..stitches import MIN_STITCH_MM

    joined: list[list[Point]] = []
    for points in _clip(spiral, shape):
        # Parts less than a stitch apart are one stretch: cut in two where one clip ends and the
        # next begins, or by the spiral grazing an edge. (Travelling across so small a gap would
        # make a stitch too short to keep.)
        if joined and dist(joined[-1][-1], points[0]) < MIN_STITCH_MM:
            joined[-1] += points
        else:
            joined.append(points)
    return joined


def _edge_ends(pieces: list[list[Point]], rings: list[LineString]) -> list[tuple]:
    """Each stretch's two ends as (edge, how far round it, where): the edge of the shape (in
    `rings`) that cut it there. (The very first starts in the middle; its start is never used.)"""
    where = [p for piece in pieces for p in (piece[0], piece[-1])]
    points = shapely.points(where)
    edges = np.array(rings, dtype=object)
    edge = shapely.distance(edges[:, None], points[None, :]).argmin(axis=0)
    along = shapely.line_locate_point(edges[edge], points)
    ends = [(int(e), float(s), p) for e, s, p in zip(edge, along, where)]
    return list(zip(ends[::2], ends[1::2]))


def _nearest_first(marks: list[tuple], along: float, length: float):
    """The marks on one edge `length` round, sorted by how far round it they are, from the nearest
    to `along` going either way."""
    ahead = bisect.bisect_left(marks, (along,))
    behind = ahead - 1
    for _ in range(len(marks)):
        a, b = marks[ahead % len(marks)], marks[behind % len(marks)]
        if (a[0] - along) % length <= (along - b[0]) % length:
            yield a
            ahead += 1
        else:
            yield b
            behind -= 1


def _strands(pair: tuple, k: int, marks: dict, links: dict) -> bool:
    """Whether sewing the stretch with ends `pair`, from end `k`, would leave unsewn stretches that
    can't be got to from where it finishes by going along edges and unsewn stretches. `marks` has
    the unsewn stretches' ends on each edge (this one's included), `links` how many of them run
    between each two edges."""
    here, there = pair[k][0], pair[1 - k][0]
    left = {edge: len(m) - (pair[0][0] == edge) - (pair[1][0] == edge) for edge, m in marks.items()}
    if not any(left.values()):
        return False  # it's the last
    if not left.get(there):
        return True
    if here == there or links[here][there] > 1:
        return False  # the same edges stay joined up
    reached, to_see = {there}, [there]
    while to_see:
        a = to_see.pop()
        for b, n in links[a].items():
            if n and b not in reached and {a, b} != {here, there}:
                reached.add(b)
                to_see.append(b)
    return any(n and edge not in reached for edge, n in left.items())


def _sewing_order(ends: list[tuple], lengths: list[float]) -> list[tuple[int, bool]]:
    """The order to sew the stretches in, as (stretch, from its far end?). `ends` has each stretch's
    two ends (see _edge_ends), in spiral order; `lengths` is how far it is round each edge.

    The first stretch, from the middle, goes first. Then each time comes the stretch with an end
    nearest along the edge the needle is on, sewn from that end, so each join is short. A choice
    that would leave stretches reachable only by cutting across the shape is passed over. That is
    Fleury's rule for walking every link of a network once, with the edges as its junctions and the
    stretches as its links. Spiral order is one such walk (what lies between two stretches is
    outside the shape or inside one hole, so one ends on the edge where the next begins), so there
    is always a choice that keeps to the edges."""
    marks: dict[int, list[tuple]] = defaultdict(list)  # per edge: (how far round, stretch, which end)
    links: dict[int, Counter] = defaultdict(Counter)  # links[a][b]: stretches between edges a and b
    for i, pair in enumerate(ends[1:], 1):
        for k, (edge, along, _) in enumerate(pair):
            bisect.insort(marks[edge], (along, i, k))
        a, b = pair[0][0], pair[1][0]
        if a != b:
            links[a][b] += 1
            links[b][a] += 1
    unsewn = set(range(1, len(ends)))
    order = [(0, False)]
    edge, along, point = ends[0][1]
    while unsewn:
        nearest = choice = None
        for _, i, k in _nearest_first(marks[edge], along, lengths[edge]):
            nearest = nearest or (i, k)
            if not _strands(ends[i], k, marks, links):
                choice = (i, k)
                break
        # Neither can happen when spiral order is a walk (see above); sew everything even so.
        if choice is None:
            choice = nearest or min(((i, k) for i in unsewn for k in (0, 1)),
                                    key=lambda c: (dist(point, ends[c[0]][c[1]][2]), c))
        i, k = choice
        for end, (e, s, _) in enumerate(ends[i]):
            del marks[e][bisect.bisect_left(marks[e], (s, i, end))]
        a, b = ends[i][0][0], ends[i][1][0]
        if a != b:
            links[a][b] -= 1
            links[b][a] -= 1
        unsewn.remove(i)
        order.append((i, k == 1))
        edge, along, point = ends[i][1 - k]
    return order


def _stitch_length(radius: float, stitch_mm: float) -> float:
    """The stitch to aim for where the spiral is `radius` from its middle: short on the tight turns,
    longer as they open out, never more than the fill's `stitch_mm`."""
    return min(max(2 * math.sqrt(2 * SAG_MM * radius), SHORTEST_STITCH_MM), stitch_mm)


def _needle_points(piece: list[Point], middle: Point, stitch_mm: float) -> list[Point]:
    """Needle drops along a piece of the spiral. Each goes exactly where the length since the one
    before reaches the stitch to aim for (not on the next sample, which could be 0.5 mm further).
    The last is the end of the piece, unless that's too close for a stitch."""
    from ..stitches import MIN_STITCH_MM

    out = [piece[0]]
    want = _stitch_length(dist(middle, piece[0]), stitch_mm)
    since = 0.0  # how far along the piece since the last needle drop
    for a, b in zip(piece, piece[1:]):
        step = dist(a, b)
        done = 0.0  # how much of this step has been walked
        while since + step - done >= want:
            done += want - since
            t = done / step
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            since = 0.0
            want = _stitch_length(dist(middle, out[-1]), stitch_mm)
        since += step - done
    if dist(out[-1], piece[-1]) >= MIN_STITCH_MM:
        out.append(piece[-1])
    return out


def _along(ring: LineString, s0: float, s1: float) -> list[Point]:
    """The ring's points walking forward from `s0` to `s1` along it, past where it starts if need be."""
    if s0 <= s1:
        return list(substring(ring, s0, s1).coords)
    return list(substring(ring, s0, ring.length).coords) + list(substring(ring, 0, s1).coords)[1:]


def _way_round(a: Point, b: Point, rings: list[LineString], cover) -> list[Point] | None:
    """The way from the end of one stretch of the spiral to the start of the next, along an edge of
    the shape. What lies between them is outside the shape or inside one hole, so they normally end on
    the same edge, and the way keeps to it even when cutting across to another would be shorter. If
    they don't (a stretch too short to sew lay between), it takes the edge that needs the least
    stepping across the shape. None if no way stays inside `cover`."""
    ends = ShapelyPoint(a), ShapelyPoint(b)
    for ring in sorted(rings, key=lambda r: r.distance(ends[0]) + r.distance(ends[1])):
        sa, sb = ring.project(ends[0]), ring.project(ends[1])
        ways = [[a, *_along(ring, sa, sb), b], [a, *_along(ring, sb, sa)[::-1], b]]
        ways = [w for w in ways if cover.covers(LineString(w))]
        if ways:
            return min(ways, key=lambda w: round(LineString(w).length, 3))
    return None


def _join(path: list[Point], stretch: list[Point], way: list[Point], longest: float) -> None:
    """Carry `path` on along `way` to the next `stretch` of the spiral, and then along that. The way's
    stitches are at most `longest`, and none anywhere is too short to keep."""
    from ..stitches import MIN_STITCH_MM, _subdivide

    walk = [path[-1]]
    for p in resample(way, longest, sharp_points(way))[1:-1]:
        if dist(walk[-1], p) >= MIN_STITCH_MM and dist(p, stretch[0]) >= MIN_STITCH_MM:
            walk.append(p)
    while stretch and dist(walk[-1], stretch[0]) < MIN_STITCH_MM:  # already there
        stretch = stretch[1:]
    path += _subdivide(walk + stretch[:1], longest)[1:] + stretch[1:]


def _spiral_paths(poly, params, pos):
    """The spiral over one piece of a fill, as one path starting in the middle. (Stretches that no
    way along an edge could join would be separate paths, which the fill joins as it does any
    others.) `pos`, where the fill was asked to start, isn't used: a spiral starts in the middle."""
    from ..stitches import MIN_STITCH_MM, TRAVEL_STITCH_MM

    spacing = params.value("spiral_mm")
    warnings = [TIGHT_WARNING] if spacing < TIGHT_MM else []
    # Worked out with the shape's bounds starting at (0, 0), rounded to a millionth of a mm, so a
    # moved or copied shape gets exactly the same spiral. Where several spots are equally wide, the
    # last-digit noise that moving leaves behind could otherwise pick another middle.
    x0, y0 = poly.bounds[:2]
    local = shapely.transform(poly, lambda xy: np.round(xy - (x0, y0), 6))
    middle = _middle(local)
    reach = max(dist(middle, p) for p in local.exterior.coords) + spacing
    rings = [LineString(r.coords) for r in [local.exterior, *local.interiors]]
    cover = local.buffer(0.3)  # as far outside the shape as the fill lets any travel go
    shapely.prepare(cover)
    longest = min(TRAVEL_STITCH_MM, params.stitch_mm)
    pieces = _pieces(_spiral(middle, spacing, reach), local)
    if not any(LineString(p).length > SHORTEST_PIECE_MM for p in pieces):
        return [], warnings
    ends = _edge_ends(pieces, rings)
    # A stretch too short to be worth sewing is left out, unless it's the way from one edge to
    # another: without it, a join would have to cut across the shape.
    keep = [i for i, p in enumerate(pieces) if LineString(p).length > SHORTEST_PIECE_MM or ends[i][0][0] != ends[i][1][0]]
    paths: list[list[Point]] = []
    for k, backwards in _sewing_order([ends[i] for i in keep], [r.length for r in rings]):
        points = _needle_points(pieces[keep[k]], middle, params.stitch_mm)
        if backwards:
            points = points[::-1]
        way = _way_round(paths[-1][-1], points[0], rings, cover) if paths else None
        if way:
            _join(paths[-1], points, way, longest)
            continue
        if paths and dist(paths[-1][-1], points[0]) < MIN_STITCH_MM:
            points = points[1:]  # already there
        if points:
            paths.append(points)
    return [[(x + x0, y + y0) for x, y in path] for path in paths], warnings


register(FillPattern("spiral", "open", params={"spiral_mm": Param(1.5, 0.4, 6.0, "Ring spacing")}, paths=_spiral_paths,
                     step_mm2=lambda p: p.value("spiral_mm") * min(p.stitch_mm, 3.0), auto_underlay=lambda level: []))
