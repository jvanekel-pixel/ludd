"""Geometry for artwork import: the exact size of drawn paths (stroke widths included), curves
flattened to points, which areas a fill covers (its fill rule), and pen points fitted to them.

The same shapes on every computer: areas that need GEOS (paths that cross themselves or each
other, stroke outlines) come back in a fixed order with each ring starting at its smallest point,
and points are rounded to 0.0001 mm before anything is fitted to them.
"""

from __future__ import annotations

import math
from typing import Callable, Iterable, Sequence

import numpy as np
import shapely
from shapely.geometry import LinearRing, LineString, Polygon
from shapely.ops import polygonize, unary_union

from ..digitize.paths import resample
from ..shapeops import to_nodes
from . import ArtError, widestroke
from .model import Point, Subpath
from .widestroke import ring_of

FLATTEN_TOL_MM = 0.05  # a flattened curve stays this close to the curve (artwork is flattened to 0.1 mm)
FLATTEN_STEP_MM = 0.25  # ... in steps about this long
MAX_CURVE_STEPS = 4096
CORNER_DEG = 40.0  # a joint turning more than this is a sharp corner
CORNER_MIN_EDGE_MM = 0.3  # ... when both sides of it are at least this long (not just jitter)
JOIN_MM = 0.1  # a line whose ends are this close is closed
STRAIGHT_MM = 0.03  # a piece that stays this close to its chord is drawn as one straight line
TURN_PER_POINT_DEG = 30.0  # fitted points come close enough that a curve turns about this much per step
ROUND = 4  # decimals kept before fitting (0.0001 mm)

# Checked before GEOS is asked to cut up or outline shapes whose lines cross, or to compare crowded
# outlines pair by pair: single calls that can't be stopped, which a small file can make take minutes
# and gigabytes.
MAX_CROSSINGS = 20_000  # places where a shape's lines cross or touch (neighbors along a line aside)
MAX_NEAR_PAIRS = 20_000_000  # pairs of line pieces with overlapping boxes, looked at while counting
MAX_BOX_PAIRS = 2_000_000  # pairs of outlines with overlapping boxes (as one inside another has)
# A wide stroke with more points than this is outlined in a child process that can be stopped:
# GEOS can take minutes and gigabytes over a line that doubles back on itself, even one that never
# crosses itself.
OUTLINE_IN_CHILD = 400
TANGLED = ("This drawing has a shape whose outline crosses or touches itself more than 20,000 times, too tangled to "
           "import. Simplify it in your drawing program, save it again and import that.")
CROWDED = ("This drawing has thousands of outlines inside or on top of one another, too many for LUDD to work out. "
           "Simplify it in your drawing program (fewer overlapping shapes), save it again and import that.")

_AXES = ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0))


class Box:
    def __init__(self) -> None:
        self.x0 = self.y0 = math.inf
        self.x1 = self.y1 = -math.inf

    def add(self, x: float, y: float) -> None:
        self.x0, self.y0 = min(self.x0, x), min(self.y0, y)
        self.x1, self.y1 = max(self.x1, x), max(self.y1, y)

    def join(self, other: "Box") -> None:
        if not other.empty:
            self.add(other.x0, other.y0)
            self.add(other.x1, other.y1)

    @property
    def empty(self) -> bool:
        return self.x0 > self.x1

    @property
    def width(self) -> float:
        return 0.0 if self.empty else self.x1 - self.x0

    @property
    def height(self) -> float:
        return 0.0 if self.empty else self.y1 - self.y0


# ---------------------------------------------------------------- paths


def scaled(sub: Subpath, scale: float, cx: float, cy: float) -> Subpath:
    """`sub` moved so (cx, cy) is at (0, 0) and made `scale` times its size."""

    def f(p: Point) -> Point:
        return (p[0] - cx) * scale, (p[1] - cy) * scale

    return Subpath(f(sub.start), [(seg[0], *(f(p) for p in seg[1:])) for seg in sub.segments], sub.closed)


def _controls(sub: Subpath) -> Iterable[list[Point]]:
    """Each segment as its control points: [start, end] or [start, c1, c2, end]."""
    at = sub.start
    for seg in sub.segments:
        yield [at, *seg[1:]]
        at = seg[-1]


def _span(pts: Sequence[Point]) -> float:
    """The length of a segment's control polygon (at least its own length)."""
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def control_length(sub: Subpath) -> float:
    return sum(_span(c) for c in _controls(sub))


def _bezier(c: Sequence[Point], t: float) -> Point:
    u = 1 - t
    a, b, cc, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
    return (a * c[0][0] + b * c[1][0] + cc * c[2][0] + d * c[3][0],
            a * c[0][1] + b * c[1][1] + cc * c[2][1] + d * c[3][1])


def _turning_points(p0: float, p1: float, p2: float, p3: float) -> list[float]:
    """The t in (0, 1) where one coordinate of a cubic turns back."""
    d0, d1, d2 = p1 - p0, p2 - p1, p3 - p2
    a, b, c = d0 - 2 * d1 + d2, 2 * (d1 - d0), d0
    if abs(a) < 1e-12:
        roots = [-c / b] if abs(b) > 1e-12 else []
    else:
        disc = b * b - 4 * a * c
        roots = [(-b + s * math.sqrt(disc)) / (2 * a) for s in (-1, 1)] if disc >= 0 else []
    return [t for t in roots if 0 < t < 1]


def _unit(dx: float, dy: float) -> Point | None:
    length = math.hypot(dx, dy)
    return (dx / length, dy / length) if length > 1e-9 else None


def _start_direction(c: Sequence[Point]) -> Point | None:
    return next((u for q in c[1:] if (u := _unit(q[0] - c[0][0], q[1] - c[0][1]))), None)


def _end_direction(c: Sequence[Point]) -> Point | None:
    return next((u for q in reversed(c[:-1]) if (u := _unit(c[-1][0] - q[0], c[-1][1] - q[1]))), None)


def _drawn(sub: Subpath) -> list[list[Point]]:
    """The segments that go somewhere (a segment with all its points together has no direction)."""
    return [c for c in _controls(sub) if _start_direction(c) is not None]


def path_box(subpaths: Sequence[Subpath]) -> Box:
    """The exact box round the paths themselves (what a fill covers)."""
    box = Box()
    for sub in subpaths:
        box.add(*sub.start)
        for c in _controls(sub):
            box.add(*c[-1])
            if len(c) == 4:
                for axis in (0, 1):
                    for t in _turning_points(c[0][axis], c[1][axis], c[2][axis], c[3][axis]):
                        box.add(*_bezier(c, t))
    return box


def stroke_box(subpaths: Sequence[Subpath], width: float, cap: str = "butt", join: str = "miter",
               miter_limit: float = 4.0) -> Box:
    """The exact box round paths painted `width` wide, with their caps and joins."""
    box, h = Box(), width / 2

    def offset(p: Point, nx: float, ny: float) -> None:
        box.add(p[0] + h * nx, p[1] + h * ny)

    for sub in subpaths:
        segments = _drawn(sub)
        if not segments:
            if cap in ("round", "square"):  # a dot
                for ax, ay in _AXES:
                    offset(sub.start, ax, ay)
            continue
        for c in segments:
            for p, (ux, uy) in ((c[0], _start_direction(c)), (c[-1], _end_direction(c))):
                offset(p, -uy, ux)
                offset(p, uy, -ux)
            if len(c) == 4:
                for axis in (0, 1):
                    for t in _turning_points(c[0][axis], c[1][axis], c[2][axis], c[3][axis]):
                        p = _bezier(c, t)
                        ax, ay = (1.0, 0.0) if axis == 0 else (0.0, 1.0)
                        offset(p, ax, ay)
                        offset(p, -ax, -ay)
        joints = list(zip(segments, segments[1:]))
        if sub.closed:
            joints.append((segments[-1], segments[0]))
        for a, b in joints:
            _join_box(offset, a[-1], _end_direction(a), _start_direction(b), join, miter_limit)
        if not sub.closed:
            ends = ((segments[0][0], _start_direction(segments[0]), -1.0),
                    (segments[-1][-1], _end_direction(segments[-1]), 1.0))
            for p, (ux, uy), sign in ends:
                ox, oy = sign * ux, sign * uy  # pointing out of the line
                if cap == "square":
                    offset(p, ox - uy, oy + ux)
                    offset(p, ox + uy, oy - ux)
                elif cap == "round":
                    for ax, ay in _AXES:
                        if ax * ox + ay * oy >= 0:
                            offset(p, ax, ay)
    return box


def _join_box(offset: Callable, v: Point, a: Point, b: Point, join: str, miter_limit: float) -> None:
    """What the join at `v` (coming in along `a`, leaving along `b`) adds beyond the two sides."""
    cross, dot = a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1]
    if abs(cross) < 1e-9 and dot > 0:
        return
    side = 1.0 if cross > 0 else -1.0
    na, nb = (side * a[1], -side * a[0]), (side * b[1], -side * b[0])  # normals on the outer side
    if join == "round":
        sweep = math.atan2(na[0] * nb[1] - na[1] * nb[0], na[0] * nb[0] + na[1] * nb[1])
        for axis in _AXES:
            turn = math.atan2(na[0] * axis[1] - na[1] * axis[0], na[0] * axis[0] + na[1] * axis[1])
            if (abs(cross) < 1e-9) or (0 <= turn <= sweep) or (sweep <= turn <= 0):
                offset(v, *axis)
    elif join != "bevel":
        cos_half = math.sqrt(max(0.0, (1 + na[0] * nb[0] + na[1] * nb[1]) / 2))
        if cos_half > 1e-6 and 1 / cos_half <= miter_limit:
            k = 1 / (2 * cos_half * cos_half)
            offset(v, (na[0] + nb[0]) * k, (na[1] + nb[1]) * k)


def _rounded(p: Point) -> Point:
    return round(p[0], ROUND) + 0.0, round(p[1], ROUND) + 0.0  # + 0.0: never -0.0


def flatten(sub: Subpath, close: bool = False) -> tuple[list[Point], set[Point]]:
    """The subpath as points about FLATTEN_STEP_MM apart along its curves (straight segments keep
    only their ends), and its sharp corners. `close`: also come back to the start (a fill does,
    even when its path doesn't)."""
    segments = [list(c) for c in _controls(sub)]
    end = sub.end
    if (close or sub.closed) and math.dist(end, sub.start) > 1e-9:
        segments.append([end, sub.start])
    points = [sub.start]
    for c in segments:
        if len(c) == 2:
            points.append(c[1])
            continue
        # Wang's formula: this many equal steps keep the polyline within FLATTEN_TOL_MM.
        bend = max(math.hypot(c[0][0] - 2 * c[1][0] + c[2][0], c[0][1] - 2 * c[1][1] + c[2][1]),
                   math.hypot(c[1][0] - 2 * c[2][0] + c[3][0], c[1][1] - 2 * c[2][1] + c[3][1]))
        n = max(math.ceil(math.sqrt(0.75 * bend / FLATTEN_TOL_MM) - 1e-9),
                math.ceil(_span(c) / FLATTEN_STEP_MM - 1e-9), 1)
        n = min(n, MAX_CURVE_STEPS)
        points += [_bezier(c, i / n) for i in range(1, n)] + [c[3]]
    out: list[Point] = []
    for p in points:
        q = _rounded(p)
        if not out or q != out[-1]:
            out.append(q)
    real = [c for c in segments if _start_direction(c) is not None]
    joints = list(zip(real, real[1:]))
    if (close or sub.closed) and len(real) > 1:
        joints.append((real[-1], real[0]))
    corners = set()
    for a, b in joints:
        ua, ub = _end_direction(a), _start_direction(b)
        angle = abs(math.degrees(math.atan2(ua[0] * ub[1] - ua[1] * ub[0], ua[0] * ub[0] + ua[1] * ub[1])))
        if angle > CORNER_DEG and min(_span(a), _span(b)) >= CORNER_MIN_EDGE_MM:
            corners.add(_rounded(b[0]))
    return out, corners


def line_length(points: Sequence[Point]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def is_flat(points: Sequence[Point]) -> bool:
    """All on one straight line (or fewer than three different points): encloses nothing."""
    if len(set(points)) < 3:
        return True
    a = points[0]
    b = max(points, key=lambda p: (math.dist(a, p), p))
    length = math.dist(a, b)
    if length < 1e-6:
        return True
    return max(abs((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) for p in points) / length < 1e-3


def signed_area(ring: Sequence[Point]) -> float:
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, [*ring[1:], ring[0]]))


# ---------------------------------------------------------------- what a fill covers

Region = tuple[list[Point], list[list[Point]]]  # an outline and its holes


def canonical_ring(ring: Sequence[Point], positive: bool) -> list[Point]:
    """The ring turning one fixed way (`positive`: its signed area is above zero), starting at its
    smallest point, so the same ring comes out the same however it was drawn or GEOS made it."""
    out: list[Point] = []
    for p in ring:
        q = _rounded(p)
        if not out or q != out[-1]:
            out.append(q)
    out = ring_of(out)
    if len(out) < 3:
        return []
    if (signed_area(out) > 0) != positive:
        out.reverse()
    k = min(range(len(out)), key=lambda i: out[i])
    return out[k:] + out[:k]


def _filled(rule: str, winding: int, depth: int, any_ring: bool = True) -> bool:
    """Is a spot filled? `winding`: how often the rings go round it; `depth`: how many rings hold
    it (counting the innermost)."""
    if rule == "evenodd":
        return depth % 2 == 1
    if rule == "outer":  # DXF hatch style "outer": between the outermost ring and the next ones in
        return depth == 1
    if rule == "ignore":  # DXF hatch style "ignore": everything inside the outermost ring
        return any_ring
    return winding != 0


def _batches(tree: shapely.STRtree, geoms: np.ndarray, check: Callable[[], None] | None):
    """tree.query(geoms) a batch at a time, as (index into geoms, index into the tree) pairs of
    overlapping boxes: batches grow where there are few and shrink where there are many."""
    i, size = 0, 16
    while i < len(geoms):
        if check:
            check()
        a, b = tree.query(geoms[i : i + size])
        yield a + i, b
        i += size
        size = min(4096, max(16, size * 200_000 // max(1, len(a))))


def box_pairs(geoms: Sequence, limit: int, check: Callable[[], None] | None = None) -> int:
    """How many pairs of these have overlapping boxes, counting no further than past `limit`."""
    if len(geoms) < 2:
        return 0
    array = np.asarray(geoms, dtype=object)
    found = 0
    for a, b in _batches(shapely.STRtree(array), array, check):
        found += int(np.count_nonzero(a < b))
        if found > limit:
            break
    return found


def check_tangle(lines: Sequence[tuple[Sequence[Point], bool]], check: Callable[[], None] | None = None) -> None:
    """Refuse (points, closed) lines that cross or touch one another or themselves more than
    MAX_CROSSINGS times: pairs of their straight pieces that meet, neighbors along a line aside."""
    starts: list[Point] = []
    ends: list[Point] = []
    owner, place, size, loop = [], [], [], []
    for k, (points, closed) in enumerate(lines):
        pts = ring_of(points) if closed else list(points)
        closed = closed and len(pts) > 2
        after = [*pts[1:], pts[0]] if closed else pts[1:]
        starts += pts[: len(after)]
        ends += after
        owner += [k] * len(after)
        place += range(len(after))
        size.append(len(after))
        loop.append(closed)
    if len(starts) * (len(starts) - 1) // 2 <= MAX_CROSSINGS:  # too few pieces to meet that often
        return
    pieces = shapely.linestrings(np.stack([np.array(starts, dtype=float), np.array(ends, dtype=float)], axis=1))
    owner, place, size, loop = np.array(owner), np.array(place), np.array(size), np.array(loop)
    crossings = near = 0
    for a, b in _batches(shapely.STRtree(pieces), pieces, check):
        near += len(a)
        once = a < b
        a, b = a[once], b[once]
        gap = np.abs(place[a] - place[b])
        neighbors = (owner[a] == owner[b]) & ((gap == 1) | (loop[owner[a]] & (gap == size[owner[a]] - 1)))
        a, b = a[~neighbors], b[~neighbors]
        crossings += int(np.count_nonzero(shapely.intersects(pieces[a], pieces[b])))
        if crossings > MAX_CROSSINGS:
            raise ArtError(TANGLED)
        if near > MAX_NEAR_PAIRS:
            raise ArtError(CROWDED)


def fill_regions(rings: Sequence[list[Point]], rule: str = "nonzero", check: Callable[[], None] | None = None) -> list[Region]:
    """The areas a path's rings fill by `rule`, as outlines with holes. Rings that don't cross or
    touch keep their own points, in the file's order; others are cut up where they cross. Rings too
    crowded or tangled to work out are refused."""
    rings = [r for r in rings if not is_flat(r)]
    if not rings:
        return []
    lines = [LinearRing(r) for r in rings]
    if len(lines) * (len(lines) - 1) // 2 > MAX_BOX_PAIRS and box_pairs(lines, MAX_BOX_PAIRS, check) > MAX_BOX_PAIRS:
        raise ArtError(CROWDED)
    simple = all(line.is_simple for line in lines)
    if check:
        check()
    if simple and not _any_touch(lines):
        if check:
            check()
        return _nested(rings, rule)
    check_tangle([(r, True) for r in rings], check)
    return _noded(rings, rule, check)


def _any_touch(lines: Sequence[LinearRing]) -> bool:
    if len(lines) < 2:
        return False
    first, second = shapely.STRtree(lines).query(np.array(lines, dtype=object), predicate="intersects")
    return bool(np.any(first != second))


def _nested(rings: Sequence[list[Point]], rule: str) -> list[Region]:
    n = len(rings)
    polygons = [Polygon(r) for r in rings]
    areas = [p.area for p in polygons]
    containers: list[list[int]] = [[] for _ in range(n)]
    if n > 1:
        starts = shapely.points(np.array([r[0] for r in rings], dtype=float))
        found, holding = shapely.STRtree(polygons).query(starts, predicate="within")
        for i, j in zip(found.tolist(), holding.tolist()):
            if i != j:
                containers[i].append(j)
    parent = [min(c, key=lambda j: (areas[j], j)) if c else None for c in containers]
    turn = [1 if signed_area(r) > 0 else -1 for r in rings]
    filled = [_filled(rule, turn[i] + sum(turn[j] for j in containers[i]), len(containers[i]) + 1) for i in range(n)]
    edge = [filled[i] != (parent[i] is not None and filled[parent[i]]) for i in range(n)]
    holes: dict[int, list[int]] = {i: [] for i in range(n) if edge[i] and filled[i]}
    for h in range(n):
        if not edge[h] or filled[h]:
            continue
        p = parent[h]
        while p is not None and not edge[p]:
            p = parent[p]
        if p is not None and p in holes:
            holes[p].append(h)
    out = []
    for i in sorted(holes):
        outline = canonical_ring(rings[i], True)
        if outline:
            out.append((outline, [r for h in sorted(holes[i]) if (r := canonical_ring(rings[h], False))]))
    return out


def _noded(rings: Sequence[list[Point]], rule: str, check: Callable[[], None] | None) -> list[Region]:
    """For rings that cross or touch: cut the plane along them all, keep the pieces the rule fills."""
    cut = unary_union([LineString([*r, r[0]]) for r in rings])
    starts = np.array([p for r in rings for p in r], dtype=float)
    ends = np.array([p for r in rings for p in [*r[1:], r[0]]], dtype=float)
    owner = np.repeat(np.arange(len(rings)), [len(r) for r in rings])
    kept = []
    for face in polygonize(cut):
        if check:
            check()
        spot = face.representative_point()
        px, py = spot.x, spot.y
        left = (ends[:, 0] - starts[:, 0]) * (py - starts[:, 1]) - (px - starts[:, 0]) * (ends[:, 1] - starts[:, 1])
        up = (starts[:, 1] <= py) & (ends[:, 1] > py) & (left > 0)
        down = (starts[:, 1] > py) & (ends[:, 1] <= py) & (left < 0)
        per_ring = np.bincount(owner, weights=up.astype(float) - down.astype(float), minlength=len(rings))
        winding = int(round(float(per_ring.sum())))
        if rule == "outer":
            inside = winding % 2 == 1
        else:
            inside = _filled(rule, winding, winding % 2, any_ring=bool(np.any(per_ring != 0)))
        if inside:
            kept.append(face)
    return _ordered(unary_union(kept)) if kept else []


def _polygons(geom) -> list[Polygon]:
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    return [p for g in getattr(geom, "geoms", []) for p in _polygons(g)]


def _ordered(geom) -> list[Region]:
    """GEOS's answer in a fixed order: rings turned and started alike, pieces and holes sorted."""
    out = []
    for p in _polygons(geom):
        outline = canonical_ring(p.exterior.coords, True)
        if not outline:
            continue
        holes = sorted(r for h in p.interiors if (r := canonical_ring(h.coords, False)))
        out.append((outline, holes))
    # By each ring's own points, which are different even for mirror twins touching at their start.
    return sorted(out, key=lambda r: (r[0], r[1]))


def region_area(region: Region) -> float:
    outline, holes = region
    return abs(signed_area(outline)) - sum(abs(signed_area(h)) for h in holes)


def is_big_stroke(lines: Sequence[tuple[list[Point], bool]]) -> bool:
    """So many points that outlining it is left to a child process (see OUTLINE_IN_CHILD)."""
    return sum(len(points) for points, _ in lines) > OUTLINE_IN_CHILD


def stroke_regions(lines: Sequence[tuple[list[Point], bool]], width: float, cap: str = "butt", join: str = "miter",
                   miter_limit: float = 4.0, check: Callable[[], None] | None = None, painted=None) -> list[Region]:
    """The outline of lines painted `width` wide, as areas (for strokes too wide for a satin).
    `lines`: (points, closed) pairs. `painted`: what they cover, when a child process has worked it
    out (a big stroke, already checked for tangles)."""
    if painted is None:
        check_tangle(lines, check)  # their outlines are as hard to join as they are to cut up
        painted = widestroke.union(lines, width, cap, join, miter_limit)
    return _ordered(painted)


# ---------------------------------------------------------------- fitting pen points


def vertex_corners(points: Sequence[Point], closed: bool) -> set[Point]:
    """Sharp corners read from the points themselves (for outlines GEOS made)."""
    n = len(points)
    out = set()
    for i in range(n) if closed else range(1, n - 1):
        a, v, b = points[i - 1], points[i], points[(i + 1) % n]
        if min(math.dist(a, v), math.dist(v, b)) < CORNER_MIN_EDGE_MM:
            continue
        angle = math.atan2((v[0] - a[0]) * (b[1] - v[1]) - (v[1] - a[1]) * (b[0] - v[0]),
                           (v[0] - a[0]) * (b[0] - v[0]) + (v[1] - a[1]) * (b[1] - v[1]))
        if abs(math.degrees(angle)) > CORNER_DEG:
            out.add(v)
    return out


def _total_turn(points: Sequence[Point], closed: bool) -> float:
    """How far the line turns in all, in degrees, ignoring jitter finer than half a millimeter."""
    line = [*points, points[0]] if closed else list(points)
    pts = resample(line, 0.5)
    if closed:
        pts = ring_of(pts) if len(pts) > 1 else pts
        pts = [*pts, pts[0], pts[1]] if len(pts) > 2 else pts
    total = 0.0
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        u, v = _unit(b[0] - a[0], b[1] - a[1]), _unit(c[0] - b[0], c[1] - b[1])
        if u and v:
            total += abs(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]))
    return math.degrees(total)


def _spacing_for(points: Sequence[Point], spacing: float, closed: bool) -> float:
    """`spacing`, closer on small or tightly curved pieces, so the fitted curve stays on them."""
    length = line_length([*points, points[0]] if closed else points)
    steps = max(12 if closed else 1, math.ceil(_total_turn(points, closed) / TURN_PER_POINT_DEG - 1e-6))
    return min(spacing, max(0.5 if closed else 0.8, length / steps))


def _node(p: Point, kind: str) -> list:
    return [round(p[0], 2) + 0.0, round(p[1], 2) + 0.0, kind]


def _straight(points: Sequence[Point]) -> bool:
    a, b = points[0], points[-1]
    length = math.dist(a, b)
    if length < 1e-6:
        return False
    along = 0.0
    for p in points[1:]:
        dx, dy = p[0] - a[0], p[1] - a[1]
        if abs((b[0] - a[0]) * dy - (b[1] - a[1]) * dx) / length > STRAIGHT_MM:
            return False
        t = (dx * (b[0] - a[0]) + dy * (b[1] - a[1])) / length
        if t < along - 0.01:
            return False  # it doubles back
        along = max(along, t)
    return True


def _fit_piece(points: Sequence[Point], spacing: float) -> list[list]:
    """Pen points from one corner to the next: a straight piece needs only its two ends."""
    if _straight(points):
        return [_node(points[0], "c"), _node(points[-1], "l")]
    return to_nodes(points, _spacing_for(points, spacing, False), closed=False)


def _tidy(nodes: list[list], closed: bool) -> list[list]:
    """Without points that rounding put on top of the one before."""
    out: list[list] = []
    for n in nodes:
        if not out or (n[0], n[1]) != (out[-1][0], out[-1][1]):
            out.append(n)
    if closed and len(out) > 1 and (out[0][0], out[0][1]) == (out[-1][0], out[-1][1]):
        out.pop()
    return out


def fit_ring(ring: Sequence[Point], corners: set[Point], spacing: float) -> list[list]:
    """Pen points round a ring, with its sharp corners kept exactly."""
    n = len(ring)
    at = [i for i, p in enumerate(ring) if p in corners]
    if at:
        nodes: list[list] = []
        for k, a in enumerate(at):
            b = at[(k + 1) % len(at)]
            piece = [ring[j % n] for j in range(a, (b if b > a else b + n) + 1)]
            nodes += _fit_piece(piece, spacing)[1:]
        nodes = _tidy([nodes[-1], *nodes[:-1]], True)
        if len(nodes) >= 3:
            return nodes
    return _tidy(to_nodes(ring, _spacing_for(ring, spacing, True), closed=True), True)


def fit_line(points: Sequence[Point], corners: set[Point], closed: bool, spacing: float) -> list[list]:
    """Pen points along a line (open or closed), with its sharp corners kept exactly."""
    if closed:
        return fit_ring(ring_of(points), corners, spacing)
    at = [0, *[i for i in range(1, len(points) - 1) if points[i] in corners], len(points) - 1]
    nodes: list[list] = []
    for a, b in zip(at, at[1:]):
        part = _fit_piece(points[a : b + 1], spacing)
        nodes += part if not nodes else part[1:]
    return _tidy(nodes, False)
