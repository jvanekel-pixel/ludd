"""Lattices of straight lines sewn as double runs, every stretch out and back. The Blackwork fill
sews them; freestanding lace is meant to share this module.

- tile_segments() lays a lattice over a box, as segments from crossing to crossing.
- clip_segments() cuts segments to a shape, leaving out pieces under 0.8 mm.
- double_run_paths() sews segments: a graph with a node at every crossing and end, each connected
  piece walked depth first, out along every stretch and back, so each is sewn exactly twice, with a
  needle point at every node, and each path ends where it began.

Everything is in a fixed order (segments, nodes, where each piece is begun and which way it goes
first), so every computer sews the same stitches. Written from first principles for LUDD.
Coordinates are mm.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import shapely

from ..paths import Point, dist
from .motif import clip, edges, grown

LATTICES = ("diamonds", "grid", "honeycomb", "crossed")
SHORTEST_PIECE_MM = 0.8  # shorter pieces of a line inside the shape are left out
SHORTEST_STEP_MM = 0.31  # a stretch isn't split into stitches shorter than this (under 0.3 mm they're lost)
SAME_POINT_MM = 0.001  # ends and crossings this close are one node

Segment = tuple[Point, Point]


def _cells(span: float, cell: float) -> range:
    """Whole cells each way from the middle that cover `span` (and one more)."""
    n = math.ceil(span / 2 / cell) + 1
    return range(-n, n + 1)


def tile_segments(kind: str, cell_mm: float, bounds: Sequence[float]) -> list[Segment]:
    """The lattice `kind` over the box `bounds` (minx, miny, maxx, maxy), with a crossing at the
    box's middle (for honeycomb, the middle of a hexagon), as segments from crossing to crossing in
    a fixed order. Those wholly outside the box are left out.

    - grid: lines level and upright, `cell_mm` apart;
    - diamonds: the same turned 45 degrees, `cell_mm` along each side;
    - crossed: the grid, with both diagonals of every square;
    - honeycomb: hexagons `cell_mm` across the flats, their flat sides upright."""
    if kind not in LATTICES:
        raise ValueError(kind)
    minx, miny, maxx, maxy = bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    c = cell_mm
    found: list[Segment] = []
    if kind in ("grid", "crossed"):
        across, down = _cells(maxx - minx, c), _cells(maxy - miny, c)

        def at(i: float, j: float) -> Point:
            return cx + i * c, cy + j * c

        found += [(at(i, j), at(i + 1, j)) for j in down for i in across[:-1]]
        found += [(at(i, j), at(i, j + 1)) for i in across for j in down[:-1]]
        if kind == "crossed":
            for j in down[:-1]:
                for i in across[:-1]:
                    middle = at(i + 0.5, j + 0.5)
                    found += [(at(i + di, j + dj), middle) for di, dj in ((0, 0), (1, 0), (1, 1), (0, 1))]
    elif kind == "diamonds":
        half = c / math.sqrt(2)
        reach = _cells(math.hypot(maxx - minx, maxy - miny), c)

        def corner(i: int, j: int) -> Point:
            return cx + (i + j) * half, cy + (i - j) * half

        found += [(corner(i, j), corner(i + 1, j)) for j in reach for i in reach[:-1]]
        found += [(corner(i, j), corner(i, j + 1)) for i in reach for j in reach[:-1]]
    else:
        side = c / math.sqrt(3)
        across, down = _cells(maxx - minx, c), _cells(maxy - miny, 1.5 * side)

        def vertex(a: int, b: int) -> Point:
            """a counts half cells across, b half sides down, from the middle hexagon's center."""
            return cx + a * (c / 2), cy + b * (side / 2)

        for j in down:
            for i in across:
                a, b = 2 * i + j % 2, 3 * j  # the hexagon's center; three of its sides are its own
                found += [(vertex(a + 1, b - 1), vertex(a + 1, b + 1)), (vertex(a + 1, b + 1), vertex(a, b + 2)),
                          (vertex(a, b + 2), vertex(a - 1, b + 1))]
    slack = 0.02
    return [(p, q) for p, q in found
            if max(p[0], q[0]) >= minx - slack and min(p[0], q[0]) <= maxx + slack
            and max(p[1], q[1]) >= miny - slack and min(p[1], q[1]) <= maxy + slack]


def clip_segments(segments: Sequence[Segment], poly) -> list[Segment]:
    """The parts of the segments inside the shape, in their order, leaving out pieces under 0.8 mm.
    The shape is grown by a hair first (motif.grown), so a line along its edge stays whole."""
    if not segments:
        return []
    area = grown(poly)
    lines = shapely.linestrings(np.asarray(segments, dtype=float))
    whole = shapely.covers(area, lines)
    touching = shapely.intersects(area, lines)
    sides = edges(area)
    out: list[Segment] = []
    for k, (a, b) in enumerate(segments):
        if whole[k]:
            pieces = [(a, b)]
        elif touching[k]:
            pieces = [(piece[0], piece[-1]) for piece in clip([a, b], area, sides)]
        else:
            continue
        out += [(p, q) for p, q in pieces if round(dist(p, q), 6) >= SHORTEST_PIECE_MM]
    return out


# ---------------------------------------------------------------- the double run


def _order(p: Point) -> tuple[float, float]:
    """Points in a fixed order: upper first, then left."""
    return round(p[1], 6), round(p[0], 6)


def _crossings(segments: list[Segment]) -> list[list[tuple[float, Point]]]:
    """For each segment, where others cross or meet it part way along: (how far along, 0 to 1,
    the point), in order along it. Worked out with plain arithmetic (not the geometry library's,
    which can miss a meeting by a last digit)."""
    cuts: list[list[tuple[float, Point]]] = [[] for _ in segments]
    a = np.array([s[0] for s in segments], dtype=float)
    b = np.array([s[1] for s in segments], dtype=float)
    low = np.minimum(a, b) - SAME_POINT_MM
    high = np.maximum(a, b) + SAME_POINT_MM
    boxes = shapely.box(low[:, 0], low[:, 1], high[:, 0], high[:, 1])
    i, j = shapely.STRtree(boxes).query(boxes)
    pairs = np.flatnonzero(i < j)
    order = np.lexsort((j[pairs], i[pairs]))
    i, j = i[pairs][order], j[pairs][order]
    r, s, q = b[i] - a[i], b[j] - a[j], a[j] - a[i]
    denom = r[:, 0] * s[:, 1] - r[:, 1] * s[:, 0]
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (q[:, 0] * s[:, 1] - q[:, 1] * s[:, 0]) / denom
        u = (q[:, 0] * r[:, 1] - q[:, 1] * r[:, 0]) / denom
    li, lj = np.hypot(r[:, 0], r[:, 1]), np.hypot(s[:, 0], s[:, 1])
    meet = (np.abs(denom) > 1e-9) & (t * li >= -SAME_POINT_MM) & ((1 - t) * li >= -SAME_POINT_MM) \
        & (u * lj >= -SAME_POINT_MM) & ((1 - u) * lj >= -SAME_POINT_MM)
    for k in np.flatnonzero(meet):
        p = (float(a[i[k], 0] + t[k] * r[k, 0]), float(a[i[k], 1] + t[k] * r[k, 1]))
        for index, along, length in ((int(i[k]), float(t[k]), float(li[k])), (int(j[k]), float(u[k]), float(lj[k]))):
            if along * length > SAME_POINT_MM and (1 - along) * length > SAME_POINT_MM:
                cuts[index].append((along, p))
    return [sorted(c) for c in cuts]


class _Nodes:
    """The graph's nodes; points within SAME_POINT_MM are one."""

    def __init__(self):
        self.at: list[Point] = []
        self._cells: dict[tuple[int, int], list[int]] = {}

    def __call__(self, p: Point) -> int:
        step = 2 * SAME_POINT_MM
        i, j = math.floor(p[0] / step), math.floor(p[1] / step)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for k in self._cells.get((i + di, j + dj), ()):
                    if dist(p, self.at[k]) <= SAME_POINT_MM:
                        return k
        self.at.append((float(p[0]), float(p[1])))
        self._cells.setdefault((i, j), []).append(len(self.at) - 1)
        return len(self.at) - 1


def _graph(segments: Sequence[Segment]) -> tuple[list[Point], dict[int, list[int]]]:
    """The segments as a graph: its nodes (every end and crossing) and each node's neighbors, in a
    fixed order (upper first, then left). A stretch given twice is one."""
    ordered = sorted((tuple(sorted(s, key=_order)) for s in segments), key=lambda s: (_order(s[0]), _order(s[1])))
    nodes = _Nodes()
    ends = [(nodes(p), nodes(q)) for p, q in ordered]  # (ends first, so a crossing on an end is that node)
    links: dict[int, set[int]] = {}
    for (p, q), cuts in zip(ends, _crossings(ordered) if ordered else []):
        along = [p, *(nodes(point) for _, point in cuts), q]
        for here, there in zip(along, along[1:]):
            if here != there:
                links.setdefault(here, set()).add(there)
                links.setdefault(there, set()).add(here)
    return nodes.at, {k: sorted(v, key=lambda n: _order(nodes.at[n])) for k, v in links.items()}


def _steps(a: Point, b: Point, stitch_mm: float) -> list[Point]:
    """The needle points from `a` (not included) to `b`: stitches at most `stitch_mm`, in the same
    holes whichever way the stretch is sewn."""
    low, high = sorted((a, b), key=_order)
    length = dist(low, high)
    n = max(1, min(math.ceil(length / stitch_mm - 1e-9), math.floor(length / SHORTEST_STEP_MM + 1e-9)))
    inner = [(low[0] + (high[0] - low[0]) * k / n, low[1] + (high[1] - low[1]) * k / n) for k in range(1, n)]
    return [*(inner if a == low else inner[::-1]), b]


def _walk(root: int, links: dict[int, list[int]], at: list[Point], stitch_mm: float) -> list[Point]:
    """One connected piece, depth first from `root`: out along each stretch and back."""
    path = [at[root]]
    seen = {root}
    sewn: set[tuple[int, int]] = set()
    stack = [(root, iter(links[root]))]
    while stack:
        here, ahead = stack[-1]
        for there in ahead:
            stretch = (min(here, there), max(here, there))
            if stretch in sewn:
                continue
            sewn.add(stretch)
            path += _steps(at[here], at[there], stitch_mm)
            if there in seen:
                path += _steps(at[there], at[here], stitch_mm)  # a way round: straight back
                continue
            seen.add(there)
            stack.append((there, iter(links[there])))
            break
        else:
            stack.pop()
            if stack:
                path += _steps(at[here], at[stack[-1][0]], stitch_mm)
    return path


def double_run_paths(segments: Sequence[Segment], stitch_mm: float, start: Point) -> list[list[Point]]:
    """The segments sewn as double runs, one path for each connected piece, each ending where it
    began. The piece nearest `start` is sewn first, from its node nearest it; then each time the
    nearest piece, from its nearest node (of equally near nodes, the upper, then the left)."""
    at, links = _graph(segments)
    if not links:
        return []
    ids = np.array(sorted(links))
    xy = np.array([at[k] for k in ids])
    upper, left = np.round(xy[:, 1], 6), np.round(xy[:, 0], 6)
    waiting = np.ones(len(ids), dtype=bool)
    place = {int(k): i for i, k in enumerate(ids)}
    here = start
    paths: list[list[Point]] = []
    while waiting.any():
        away = np.round(np.hypot(xy[:, 0] - here[0], xy[:, 1] - here[1]), 6)
        away[~waiting] = np.inf
        near = np.flatnonzero(away == away.min())
        first = near[np.lexsort((left[near], upper[near]))[0]]
        path = _walk(int(ids[first]), links, at, stitch_mm)
        reached, to_see = {int(ids[first])}, [int(ids[first])]
        while to_see:
            for n in links[to_see.pop()]:
                if n not in reached:
                    reached.add(n)
                    to_see.append(n)
        waiting[[place[n] for n in reached]] = False
        paths.append(path)
        here = path[-1]
    return paths
