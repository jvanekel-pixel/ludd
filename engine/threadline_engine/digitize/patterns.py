"""Decorative stitching: fill patterns other than plain tatami, and motif lines.

Fills (the shape's `pattern`):
- gradient: tatami whose rows open out from dense to sparse across the shape (shading).
- wave: tatami rows that ripple like water.
- contour: rows that follow the outline inwards, ring by ring.
- stipple: one meandering line that wanders over the shape without crossing itself
  (quilting style); made by thickening a random tree of paths and following its edge.
- cross: cross-stitch Xs on a square grid.

Lines (a running stitch's `style: "motif"`): a small pattern repeated along the line:
wave, zigzag, scallop or blanket (the applique-edge stitch).

Written from first principles for LUDD. Coordinates are mm.
"""

from __future__ import annotations

import math
import random
from typing import Sequence

from shapely.geometry import MultiLineString, Point as SPoint, Polygon
from shapely.ops import unary_union

from .paths import Point, cumulative, dist, flatten, point_at, resample, sharp_points

# Kept for importers. The lists LUDD checks against are the registries: digitize.fills.REGISTRY
# (fill patterns) and digitize.lines.MOTIF_UNITS (motifs); a new one is registered there.
FILL_PATTERNS = ("tatami", "gradient", "wave", "contour", "stipple", "cross")
MOTIFS = ("wave", "zigzag", "scallop", "blanket")


def polygons(geom) -> list[Polygon]:
    """The polygons in a shapely result (a Polygon, MultiPolygon or collection), biggest first."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    found = [g for part in getattr(geom, "geoms", []) for g in polygons(part)]
    return sorted(found, key=lambda g: -g.area)


_polys = polygons


def nearest_rotation(ring: list[Point], pos: Point | None) -> list[Point]:
    """A closed ring re-started at the point nearest `pos` (so the needle doesn't travel far)."""
    if not pos or len(ring) < 3:
        return ring
    body = ring[:-1] if ring[0] == ring[-1] else ring
    k = min(range(len(body)), key=lambda i: dist(body[i], pos))
    out = body[k:] + body[:k]
    return out + [out[0]]


_nearest_rotation = nearest_rotation


# ---------------------------------------------------------------- contour


def contour_paths(poly: Polygon, spacing: float, stitch: float, start: Point | None = None) -> list[list[Point]]:
    """Rings following the outline inwards (and around holes), `spacing` apart.

    Each piece is finished before the next: its outside ring, then the pieces it shrinks into
    (one lobe at a time), then the rings round its holes from the innermost back out to the hole's
    edge. So the needle only steps across one row between rings, instead of travelling back and
    forth between lobes and holes on top of the rings already sewn. Rings keep their corners."""
    paths: list[list[Point]] = []
    pos = start
    base = poly.simplify(0.02)  # a wobbly outline with thousands of points buffers very slowly
    if base.is_empty or not base.is_valid:
        base = poly

    def ring_path(coords) -> list[Point]:
        ring = nearest_rotation([(float(x), float(y)) for x, y in coords], pos)
        return resample(ring, stitch, sharp_points(ring))

    def add(coords) -> None:
        nonlocal pos
        pts = ring_path(coords)
        if len(pts) >= 3:
            paths.append(pts)
            pos = pts[-1]

    def nearest(group: list):
        return min(group, key=lambda g: g.exterior.distance(SPoint(pos)) if pos else 0.0)

    # Depth-first without recursion (a big shape is hundreds of rings deep).
    stack: list[tuple[str, object]] = [("pieces", polygons(base.buffer(-spacing / 2, join_style=1)))]
    while stack:
        what, item = stack.pop()
        if what == "pieces":
            group = list(item)  # type: ignore[arg-type]
            if not group:
                continue
            piece = nearest(group)  # the next piece is whichever is nearest the needle
            group.remove(piece)
            stack.append(("pieces", group))
            add(piece.exterior.coords)
            stack.append(("holes", piece))
            inner = [g.simplify(0.01) for g in polygons(piece.buffer(-spacing, join_style=1))]
            stack.append(("pieces", [g for g in inner if not g.is_empty]))
        else:
            for hole in sorted(item.interiors, key=lambda r: r.distance(SPoint(pos)) if pos else 0.0):  # type: ignore[union-attr]
                add(hole.coords)
    return paths


# ---------------------------------------------------------------- stipple


def stipple_paths(poly: Polygon, size: float, stitch: float, seed: int = 0, start: Point | None = None) -> list[list[Point]]:
    """Meandering lines over the shape, one per part that a line can reach: a random tree on a grid
    of `size` cells, thickened, and its outline followed. A line never crosses itself and keeps
    about `size` / 2 from its neighbours. Parts joined only by a neck too narrow for a loop get
    their own line (joined by travel), instead of being left bare."""
    inner = poly.buffer(-size * 0.45)
    if inner.is_empty:
        return []
    minx, miny, maxx, maxy = poly.bounds
    cols, rows = int((maxx - minx) / size) + 1, int((maxy - miny) / size) + 1
    cells = {(i, j) for i in range(cols) for j in range(rows)
             if inner.contains(SPoint(minx + (i + 0.5) * size, miny + (j + 0.5) * size))}
    if not cells:
        return []
    rng = random.Random(seed)
    lines = []
    lone = []
    seen: set[tuple[int, int]] = set()

    def centre(c: tuple[int, int]) -> Point:
        return (minx + (c[0] + 0.5) * size, miny + (c[1] + 0.5) * size)

    for root in sorted(cells):
        if root in seen:
            continue
        seen.add(root)
        stack = [root]
        grew = False
        while stack:  # randomised depth-first search: long, winding branches
            c = stack[-1]
            nb = [(c[0] + dx, c[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            nb = [n for n in nb if n in cells and n not in seen]
            if not nb:
                stack.pop()
                continue
            n = rng.choice(nb)
            seen.add(n)
            stack.append(n)
            lines.append((centre(c), centre(n)))
            grew = True
        if not grew:
            lone.append(SPoint(centre(root)))  # a cell on its own still gets a small loop
    parts = []
    if lines:
        parts.append(unary_union(MultiLineString(lines)).buffer(size * 0.25, quad_segs=4))
    parts += [p.buffer(size * 0.25, quad_segs=4) for p in lone]
    shapes = polygons(unary_union(parts)) if parts else []
    paths: list[list[Point]] = []
    pos = start
    remaining = list(shapes)
    while remaining:
        # Biggest first; then whichever part is nearest the needle.
        shape = remaining[0] if not paths else min(remaining, key=lambda g: g.exterior.distance(SPoint(pos)))
        remaining.remove(shape)
        ring = list(shape.exterior.coords)
        # Round the corners off (Chaikin), so it reads as a free-flowing quilting line.
        for _ in range(2):
            smooth = []
            for a, b in zip(ring, ring[1:]):
                smooth += [(0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]), (0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1])]
            ring = smooth + [smooth[0]]
        if paths:
            ring = nearest_rotation(ring, pos)
        line = resample(ring, stitch)
        if len(line) >= 3:
            paths.append(line)
            pos = line[-1]
    return paths


def stipple_path(poly: Polygon, size: float, stitch: float, seed: int = 0) -> list[Point]:
    """The stipple line over the biggest part of the shape (see stipple_paths for all parts)."""
    paths = stipple_paths(poly, size, stitch, seed)
    return paths[0] if paths else []


# ---------------------------------------------------------------- cross-stitch


def cross_paths(poly: Polygon, size: float) -> list[list[Point]]:
    """Cross-stitch: an X in every grid square that's wholly inside the shape.

    Each run of touching squares in a row is one path: going out, one diagonal per square as a
    zigzag (/ \\ / ...); one short step up the last square's side turns the needle, and coming back
    the zigzag lays the other diagonals, finishing every X and ending beside where it began. So
    there are no bars between the crosses. Runs are sewn nearest first (from any corner), so the
    needle mostly steps straight up to the next run instead of travelling back across finished
    crosses. Paths are returned in sewing order."""
    minx, miny, maxx, maxy = poly.bounds
    runs: list[tuple[float, list[float]]] = []
    y = miny
    while y + size <= maxy + 1e-9:
        x = minx
        row: list[list[float]] = []
        while x + size <= maxx + 1e-9:
            if poly.contains(Polygon([(x, y), (x + size, y), (x + size, y + size), (x, y + size)])):
                if row and abs(x - row[-1][-1] - size) < 1e-6:
                    row[-1].append(x)
                else:
                    row.append([x])
            x += size
        runs += [(y, r) for r in row]
        y += size

    def run_path(y: float, run: list[float]) -> list[Point]:
        def zigzag(up_first: bool) -> list[Point]:
            """Corner points along the run left to right, alternating bottom and top."""
            pts = [(run[0], y + (0 if up_first else size))]
            for k, cx in enumerate(run):
                pts.append((cx + size, y + (size if (k % 2 == 0) == up_first else 0)))
            return pts

        return zigzag(True) + zigzag(False)[::-1]

    options = []
    for y, run in runs:
        left = run_path(y, run)
        x0, x1 = run[0], run[-1] + size
        right = [(x0 + x1 - px, py) for px, py in left]  # the same, started from the right
        # ...and both started from the top, for when the needle is working down the shape.
        options.append([left, right, *[[(px, 2 * y + size - py) for px, py in p] for p in (left, right)]])
    paths: list[list[Point]] = []
    remaining = list(range(len(options)))
    pos: Point | None = None
    while remaining:
        k, path = min(((k, p) for k in remaining for p in options[k]),
                      key=lambda kp: dist(pos, kp[1][0]) if pos else 0.0)
        remaining.remove(k)
        paths.append(path)
        pos = path[-1]
    return paths


# ---------------------------------------------------------------- gradient & wave (tatami variants)


def gradient_ys(miny: float, maxy: float, dense: float, sparse: float) -> list[float]:
    """Row positions from `miny` to `maxy` whose spacing opens out from `dense` to `sparse`."""
    ys = []
    y = miny + dense / 2
    span = max(maxy - miny, 1e-6)
    while y < maxy:
        ys.append(y)
        t = (y - miny) / span
        y += dense + (sparse - dense) * t
    return ys


def wave_offset(x: float, height: float, length: float) -> float:
    return height / 2 * math.sin(2 * math.pi * x / length)


# ---------------------------------------------------------------- motif lines


def _motif_unit(name: str) -> list[tuple[float, float]]:
    """One repeat of a motif: (along 0..1, across -0.5..0.5), from the registry in digitize.lines."""
    from .lines import MOTIF_UNITS  # here, not at the top: lines -> fills -> fills.builtin imports this module

    if name not in MOTIF_UNITS:
        raise ValueError(name)
    return list(MOTIF_UNITS[name])


def _to_one_side(unit: Sequence[tuple[float, float]], side: str) -> list[tuple[float, float]]:
    """One repeat moved wholly to the left or right of its line: its flat side, the edge nearest
    where a repeat starts and ends (v -0.5 for the blanket stitch, whose teeth are the rest), lies
    on the line, and the rest points away. Left is the left hand walking the line the way it was
    drawn: along -n, with n = (-ty, tx). A built-in motif drawn between v -0.5 and 0.5 goes to
    -(v + 0.5) or +(v + 0.5)."""
    vs = [v for _, v in unit]
    low, high = min(vs), max(vs)
    base = (unit[0][1] + unit[-1][1]) / 2
    flat = high if high - base < base - low - 1e-9 else low  # (a motif centered on its line: v low)
    sign = -1.0 if side == "left" else 1.0
    return [(u, sign * abs(v - flat)) for u, v in unit]


def motif_repeats(length: float, repeat_mm: float) -> int:
    """How many repeats a motif line `length` mm long takes, each as near `repeat_mm` as whole
    repeats allow. The ratio is rounded to a millionth first, so a line exactly half a repeat over
    (38 mm of a 4 mm motif) takes as many on every computer, whatever the last digit of its length
    came out as."""
    return max(1, round(round(length / repeat_mm, 6)))


def motif_points(nodes: Sequence, name: str, repeat_mm: float, width_mm: float, closed: bool = False,
                 unit: Sequence[tuple[float, float]] | None = None, side: str = "center") -> list[Point]:
    """A motif repeated along the line: each repeat `repeat_mm` long and `width_mm` wide. `unit`:
    one repeat to use instead of the built-in `name` (a motif of your own). `side`: "center" (as
    drawn, about the line), or "left" or "right" of it (see _to_one_side)."""
    poly, _ = flatten(nodes, closed)
    if closed and poly:
        poly = poly + [poly[0]]
    if len(poly) < 2:
        return list(poly)
    cum = cumulative(poly)
    total = cum[-1]
    n = motif_repeats(total, repeat_mm)
    step = total / n
    unit = _motif_unit(name) if unit is None else list(unit)
    if side != "center" and unit:
        unit = _to_one_side(unit, side)
    out: list[Point] = []
    eps = min(0.2, total / 100)
    for k in range(n):
        for i, (u, v) in enumerate(unit):
            if k and i == 0:
                continue  # the end of one repeat is the start of the next
            s = min(total, (k + u) * step)
            p = point_at(poly, cum, s)
            a = point_at(poly, cum, max(0.0, s - eps))
            b = point_at(poly, cum, min(total, s + eps))
            if closed and (s < 1e-9 or s > total - 1e-9):
                # The seam of a closed line: use the direction across it (in on one side, out on
                # the other), so the motif's start and end meet instead of leaving a gap.
                a, b = point_at(poly, cum, total - eps), point_at(poly, cum, eps)
            tx, ty = b[0] - a[0], b[1] - a[1]
            tl = math.hypot(tx, ty) or 1.0
            nx, ny = -ty / tl, tx / tl
            out.append((p[0] + nx * v * width_mm, p[1] + ny * v * width_mm))
    return out


__all__ = ["FILL_PATTERNS", "MOTIFS", "contour_paths", "cross_paths", "gradient_ys", "motif_points", "nearest_rotation",
           "polygons", "stipple_path", "stipple_paths", "wave_offset"]
