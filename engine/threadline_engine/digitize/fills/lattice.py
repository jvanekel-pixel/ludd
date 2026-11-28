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
    n = math.ceil(round(span / 2 / cell, 6)) + 1
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
    with np.errstate(invalid="ignore"):
        meet = (np.abs(denom) > 1e-9) & (t * li >= -SAME_POINT_MM) & ((1 - t) * li >= -SAME_POINT_MM) \
            & (u * lj >= -SAME_POINT_MM) & ((1 - u) * lj >= -SAME_POINT_MM)
        # Only a meeting part way along one of the two cuts anything (a lattice's lines meet at ends).
        part_way_i = (t * li > SAME_POINT_MM) & ((1 - t) * li > SAME_POINT_MM)
        part_way_j = (u * lj > SAME_POINT_MM) & ((1 - u) * lj > SAME_POINT_MM)
    for k in np.flatnonzero(meet & (part_way_i | part_way_j)):
        p = (float(a[i[k], 0] + t[k] * r[k, 0]), float(a[i[k], 1] + t[k] * r[k, 1]))
        if part_way_i[k]:
            cuts[i[k]].append((float(t[k]), p))
        if part_way_j[k]:
            cuts[j[k]].append((float(u[k]), p))
    return [sorted(c) for c in cuts]


class _Nodes:
    """The graph's nodes; points within SAME_POINT_MM are one."""

    def __init__(self):
        self.at: list[Point] = []
        self._exact: dict[Point, int] = {}
        self._cells: dict[tuple[int, int], list[int]] = {}

    def __call__(self, p: Point) -> int:
        found = self._exact.get(p)  # a lattice's shared ends are the very same numbers
        if found is not None:
            return found
        step = 2 * SAME_POINT_MM
        i, j = math.floor(p[0] / step), math.floor(p[1] / step)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for k in self._cells.get((i + di, j + dj), ()):
                    if dist(p, self.at[k]) <= SAME_POINT_MM:
                        self._exact[p] = k
                        return k
        self.at.append(p)
        self._cells.setdefault((i, j), []).append(len(self.at) - 1)
        self._exact[p] = len(self.at) - 1
        return len(self.at) - 1


def _graph(segments: Sequence[Segment]) -> tuple[list[Point], list[tuple[float, float]], dict[int, list[int]]]:
    """The segments as a graph: its nodes (every end and crossing), each node's place in the fixed
    order (upper first, then left) and its neighbors in that order. A stretch given twice is one."""
    turned = []
    for a, b in segments:
        a, b = (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))
        ka, kb = _order(a), _order(b)
        turned.append((ka, kb, a, b) if ka <= kb else (kb, ka, b, a))
    ordered = [(a, b) for _, _, a, b in sorted(turned)]
    nodes = _Nodes()
    ends = [(nodes(p), nodes(q)) for p, q in ordered]  # (ends first, so a crossing on an end is that node)
    links: dict[int, set[int]] = {}
    for (p, q), cuts in zip(ends, _crossings(ordered) if ordered else []):
        along = [p, *(nodes(point) for _, point in cuts), q]
        for here, there in zip(along, along[1:]):
            if here != there:
                links.setdefault(here, set()).add(there)
                links.setdefault(there, set()).add(here)
    keys = [_order(p) for p in nodes.at]
    return nodes.at, keys, {k: sorted(v, key=keys.__getitem__) for k, v in links.items()}


class _Stretches:
    """The needle points along a stretch between two nodes: stitches at most `stitch_mm`, in the
    same holes whichever way it is sewn."""

    def __init__(self, at: list[Point], keys: list[tuple[float, float]], stitch_mm: float):
        self.at, self.keys, self.stitch_mm = at, keys, stitch_mm

    def __call__(self, a: int, b: int) -> list[Point]:
        """From node `a` (not included) to node `b`."""
        low, high = (a, b) if self.keys[a] <= self.keys[b] else (b, a)
        (x0, y0), (x1, y1) = self.at[low], self.at[high]
        length = math.hypot(x1 - x0, y1 - y0)
        n = max(1, min(math.ceil(round(length / self.stitch_mm, 6)), math.floor(round(length / SHORTEST_STEP_MM, 6))))
        inner = [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(1, n)]
        return [*(inner if a == low else inner[::-1]), self.at[b]]


def _walk(root: int, links: dict[int, list[int]], at: list[Point], stretch: _Stretches) -> list[Point]:
    """One connected piece, depth first from `root`: out along each stretch and back."""
    path = [at[root]]
    seen = {root}
    sewn: set[tuple[int, int]] = set()
    stack = [(root, iter(links[root]))]
    while stack:
        here, ahead = stack[-1]
        for there in ahead:
            pair = (here, there) if here < there else (there, here)
            if pair in sewn:
                continue
            sewn.add(pair)
            path += stretch(here, there)
            if there in seen:
                path += stretch(there, here)  # a way round: straight back
                continue
            seen.add(there)
            stack.append((there, iter(links[there])))
            break
        else:
            stack.pop()
            if stack:
                path += stretch(here, stack[-1][0])
    return path


def double_run_paths(segments: Sequence[Segment], stitch_mm: float, start: Point) -> list[list[Point]]:
    """The segments sewn as double runs, one path for each connected piece, each ending where it
    began. The piece nearest `start` is sewn first, from its node nearest it; then each time the
    nearest piece, from its nearest node (of equally near nodes, the upper, then the left)."""
    at, keys, links = _graph(segments)
    if not links:
        return []
    stretch = _Stretches(at, keys, stitch_mm)
    ids = np.array(sorted(links))
    xy = np.array([at[k] for k in ids])
    upper, left = np.array([keys[k][0] for k in ids]), np.array([keys[k][1] for k in ids])
    waiting = np.ones(len(ids), dtype=bool)
    place = {int(k): i for i, k in enumerate(ids)}
    here = start
    paths: list[list[Point]] = []
    while waiting.any():
        away = np.round(np.hypot(xy[:, 0] - here[0], xy[:, 1] - here[1]), 6)
        away[~waiting] = np.inf
        near = np.flatnonzero(away == away.min())
        first = near[np.lexsort((left[near], upper[near]))[0]]
        path = _walk(int(ids[first]), links, at, stretch)
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
