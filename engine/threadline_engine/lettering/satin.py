"""True satin: each stroke of a letter as a satin column that follows it (P5-B1).

The letter is drawn into a picture, thinned to its middle line (as picture tracing does for drawn
lines), and the middle line is cut into strokes at its ends, junctions and sharp corners. Each
stroke becomes a satin column whose two sides follow the letter's own outline. Where strokes meet,
the longest pair that lines up runs straight through and the others stop just inside it, so the
later one covers the join. What isn't a stroke (a blob too wide for one stitch, a dot, a sliver)
is sewn first in Satin look.

Every choice between equal candidates is made by an explicit rule (lowest index, then rounded
coordinates), never by floating-point order, so a letter sews the same on every computer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from shapely.geometry import LineString, MultiPoint, Point, Polygon

from .fonts import LetteringError

PX_PER_MM = 20  # the letter is drawn this finely ...
# ... halved until the picture's longer side is at most this (20 px/mm up to letters about 24 mm
# wide, 10 to 48 mm, and so on), which keeps thinning quick at any size up to 200 mm. Big letters'
# strokes are wide, and the columns' sides are moved onto the true outline anyway.
MAX_RASTER_PX = 480
SATIN_MIN_WIDTH_MM = 0.8  # thinner strokes are sewn in Satin look
SATIN_MAX_WIDTH_MM = 7.0  # wider ones too: a stitch across them would lie loose
STEP_MM = 0.5  # rungs this far apart along a column
SNAP_MM = 0.4  # a column's side moves onto the letter's outline when that is this close
JOIN_MM = 0.4  # a stroke that stops at a junction reaches this far into the one it meets
SHRINK_MM = 0.2  # what's left over must be wider than twice this to be sewn
MIN_LEFT_MM2 = 0.5  # ... and bigger than this
STRAIGHT_DEG = 35.0  # two strokes meeting this close to a straight line are one stroke through
CORNER_DEG = 50.0  # a stroke bending more sharply than this is two strokes meeting at a corner
SPLIT_OVER_MM = 6.0  # columns wider than this somewhere get their long stitches split
COVER_MIN = 0.97  # a letter's columns and fills must cover this much of it ...
OUTSIDE_MM = 0.3  # ... and reach no further than this outside it
JOIN_COVER_MIN = 0.9  # where strokes meet, the columns alone must cover this much


class ColumnsFailed(LetteringError):
    """True satin doesn't work for this letter; it's sewn in Satin look instead."""


def _r(v: float) -> float:
    return round(float(v), 6)


@dataclass
class _Node:
    """Where a stroke ends: a free end, a junction of several, or a sharp corner (mm)."""

    kind: str  # "end" | "junction" | "corner"
    x: float
    y: float
    zone: float  # mm: the middle line is unreliable this close to the node


@dataclass
class _Seg:
    """A piece of the middle line between two nodes (or a closed loop: a, b None)."""

    pts: list[tuple[float, float, float]]  # x, y, half-width (mm)
    a: int | None
    b: int | None
    width: float = 0.0  # median width, mm

    @property
    def closed(self) -> bool:
        return self.a is None

    @property
    def length(self) -> float:
        return _r(sum(math.dist(p[:2], q[:2]) for p, q in zip(self.pts, self.pts[1:])))


@dataclass
class _Stroke:
    pts: list[tuple[float, float, float]]
    closed: bool
    ends: list[tuple[str, int | None]] = field(default_factory=list)  # (how, node) at the start and end
    through: list[int] = field(default_factory=list)  # junctions it runs straight through
    a: list[tuple[float, float]] = field(default_factory=list)
    b: list[tuple[float, float]] = field(default_factory=list)


# ---------------------------------------------------------------- picture and middle line


def _raster(shape: Polygon) -> tuple[Any, float, float, float]:
    """The letter drawn into a 0/1 picture (holes left empty): (picture, px per mm, x0, y0), where
    pixel (i, j) has its centre at (x0 + (i + 0.5) / ppm, y0 + (j + 0.5) / ppm) mm."""
    import cv2
    import numpy as np

    minx, miny, maxx, maxy = (_r(v) for v in shape.bounds)
    side = max(maxx - minx, maxy - miny)
    ppm = float(PX_PER_MM)
    while side * ppm > MAX_RASTER_PX and ppm > 1:
        ppm /= 2
    pad = 3
    x0 = math.floor(minx * ppm) / ppm - pad / ppm
    y0 = math.floor(miny * ppm) / ppm - pad / ppm
    w = int(math.ceil((maxx - x0) * ppm)) + pad + 1
    h = int(math.ceil((maxy - y0) * ppm)) + pad + 1
    img = np.zeros((h, w), np.uint8)

    def fixed(ring) -> Any:
        pts = np.array([(_r(x), _r(y)) for x, y in list(ring.coords)[:-1]], np.float64)
        # Pixel centres sit on whole numbers; 4 bits of sub-pixel precision.
        f = np.rint(((pts - (x0, y0)) * ppm - 0.5) * 16).astype(np.int32)
        return f.reshape(-1, 1, 2)

    cv2.fillPoly(img, [fixed(shape.exterior)], 1, lineType=cv2.LINE_8, shift=4)
    for hole in shape.interiors:
        cv2.fillPoly(img, [fixed(hole)], 0, lineType=cv2.LINE_8, shift=4)
    return img, ppm, x0, y0


_NB = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]


def _nbrs(on: set, p: tuple[int, int]) -> list[tuple[int, int]]:
    """p's skeleton neighbours, in a fixed order (row, then column)."""
    return [(p[0] + dx, p[1] + dy) for dx, dy in _NB if (p[0] + dx, p[1] + dy) in on]


def _key(p: tuple[int, int]) -> tuple[int, int]:
    return (p[1], p[0])


def _prune(on: set, dt: Any) -> set:
    """Take off whiskers: pieces from a line end to a junction shorter than the line is wide
    there (thinning leaves them at a stroke's square end and a letter's outer corners). All the
    whiskers found in a pass go at once, so both forks at a square end go together."""
    from .. import autotrace as at
    import numpy as np

    for _ in range(4):
        ends = sorted((p for p in on if len(_nbrs(on, p)) == 1), key=_key)
        kill: set = set()
        for e in ends:
            path = [e]
            seen = {e}
            prev, cur = None, e
            while True:
                nxt = [q for q in _nbrs(on, cur) if q != prev and q not in seen]
                if prev is not None:  # ignore a diagonal shortcut back next to where we came from
                    nxt = [q for q in nxt if max(abs(q[0] - prev[0]), abs(q[1] - prev[1])) > 1] or nxt
                if len(nxt) != 1:
                    break
                nxt_p = nxt[0]
                if len(_nbrs(on, nxt_p)) > 2:  # reached a junction
                    if len(path) < 2 * float(dt[nxt_p[1], nxt_p[0]]):
                        kill |= set(path)
                    break
                prev, cur = cur, nxt_p
                path.append(cur)
                seen.add(cur)
        if not kill:
            break
        img = np.zeros(dt.shape, bool)
        for x, y in on - kill:
            img[y, x] = True
        img = at._one_pixel(img)
        ys, xs = np.nonzero(img)
        on = set(zip(xs.tolist(), ys.tolist()))
    return on


def _smooth(pts: list[tuple[float, float, float]], closed: bool, k: int = 2) -> list[tuple[float, float, float]]:
    """Each point averaged with its neighbours (5 samples); a line's ends stay put."""
    n = len(pts)
    if n < 3:
        return pts
    out = []
    for i in range(n):
        if closed:
            idx = [(i + d) % n for d in range(-k, k + 1)]
        else:
            r = min(k, i, n - 1 - i)
            idx = list(range(i - r, i + r + 1))
        out.append((sum(pts[j][0] for j in idx) / len(idx), sum(pts[j][1] for j in idx) / len(idx),
                    sum(pts[j][2] for j in idx) / len(idx)))
    return out


def _graph(shape: Polygon) -> tuple[list[_Node], list[_Seg]]:
    """The letter's middle line as nodes and the pieces between them (mm)."""
    from .. import autotrace as at
    import cv2
    import numpy as np

    img, ppm, x0, y0 = _raster(shape)
    if not img.any():
        return [], []
    dt = np.round(cv2.distanceTransform(img, cv2.DIST_L2, cv2.DIST_MASK_PRECISE), 3)
    skel = at._one_pixel(at.thin(img))
    ys, xs = np.nonzero(skel)
    on = _prune(set(zip(xs.tolist(), ys.tolist())), dt)
    if not on:
        return [], []

    def mm(p: tuple[float, float]) -> tuple[float, float]:
        return x0 + (p[0] + 0.5) / ppm, y0 + (p[1] + 0.5) / ppm

    def half(p: tuple[int, int]) -> float:
        return max(float(dt[p[1], p[0]]) - 0.5, 0.5) / ppm

    deg = {p: len(_nbrs(on, p)) for p in on}
    # Junction pixels that touch are one junction.
    jpix = sorted((p for p in on if deg[p] >= 3), key=_key)
    cluster: dict[tuple[int, int], int] = {}
    groups: list[list[tuple[int, int]]] = []
    for p in jpix:
        if p in cluster:
            continue
        cluster[p] = len(groups)
        todo, grp = [p], [p]
        while todo:
            q = todo.pop()
            for s in _nbrs(on, q):
                if deg[s] >= 3 and s not in cluster:
                    cluster[s] = len(groups)
                    grp.append(s)
                    todo.append(s)
        groups.append(sorted(grp, key=_key))
    node_of: dict[tuple[int, int], int] = dict(cluster)
    raw_nodes: list[list[tuple[int, int]]] = list(groups)
    for p in sorted((p for p in on if deg[p] <= 1), key=_key):
        node_of[p] = len(raw_nodes)
        raw_nodes.append([p])

    # Pieces between nodes.
    pix_segs: list[tuple[list[tuple[int, int]], int | None, int | None]] = []
    used_edges: set = set()
    visited: set = set()
    for n, group in enumerate(raw_nodes):
        for start in group:
            for nb in _nbrs(on, start):
                if node_of.get(nb) == n or frozenset((start, nb)) in used_edges or nb in visited:
                    continue
                path = [start, nb]
                used_edges.add(frozenset((start, nb)))
                prev, cur = start, nb
                while cur not in node_of:
                    visited.add(cur)
                    nxt = [q for q in _nbrs(on, cur) if q != prev and frozenset((cur, q)) not in used_edges
                           and not (q in node_of and node_of[q] == n and len(path) < 3)]
                    if not nxt:
                        break
                    used_edges.add(frozenset((cur, nxt[0])))
                    prev, cur = cur, nxt[0]
                    path.append(cur)
                pix_segs.append((path, n, node_of.get(cur)))
    # Rings with no node at all (an O).
    for p in sorted(on - visited - set(node_of), key=_key):
        if p in visited:
            continue
        loop = [p]
        visited.add(p)
        prev, cur = None, p
        while True:
            nxt = [q for q in _nbrs(on, cur) if q != prev and q not in visited]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            visited.add(cur)
            loop.append(cur)
        if len(loop) > 8:
            pix_segs.append((loop, None, None))

    # Junctions joined by a piece shorter than they are wide are one junction (two strokes crossing
    # at a slant thin to two forks a little apart).
    parent = list(range(len(raw_nodes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def reach(i: int) -> float:
        return max(float(dt[q[1], q[0]]) for q in raw_nodes[i])

    merged_away: set[int] = set()
    for k, (path, a, b) in enumerate(pix_segs):
        if a is None or b is None or a == b:
            continue
        if len(raw_nodes[a]) and len(raw_nodes[b]) and deg[raw_nodes[a][0]] >= 3 and deg[raw_nodes[b][0]] >= 3:
            if len(path) <= max(reach(a), reach(b)) * 1.5:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
                merged_away.add(k)
    members: dict[int, list[tuple[int, int]]] = {}
    for i, grp in enumerate(raw_nodes):
        members.setdefault(find(i), []).extend(grp)
    for k in sorted(merged_away):
        path, a, _ = pix_segs[k]
        members[find(a)].extend(path)

    nodes: list[_Node] = []
    node_index: dict[int, int] = {}
    for root in sorted(members):
        pix = sorted(set(members[root]), key=_key)
        cx = sum(p[0] for p in pix) / len(pix)
        cy = sum(p[1] for p in pix) / len(pix)
        kind = "junction" if deg[raw_nodes[root][0]] >= 3 else "end"
        zone = max(math.hypot(p[0] - cx, p[1] - cy) + float(dt[p[1], p[0]]) for p in pix) / ppm
        x, y = mm((cx, cy))
        node_index[root] = len(nodes)
        nodes.append(_Node(kind, _r(x), _r(y), _r(zone)))

    segs: list[_Seg] = []
    for k, (path, a, b) in enumerate(pix_segs):
        if k in merged_away:
            continue
        closed = a is None
        pts = [(*mm(p), half(p)) for p in path]
        pts = [(_r(x), _r(y), _r(h)) for x, y, h in _smooth(pts, closed)]
        na = node_index[find(a)] if a is not None else None
        nb = node_index[find(b)] if b is not None else None
        if not closed and nb is None:
            nb = na  # (a walk that ran out: treat as ending where it began)
        segs.append(_Seg(pts, na, nb))
    for s in segs:
        hs = [p[2] for p in s.pts if all(math.dist(p[:2], (nodes[n].x, nodes[n].y)) > nodes[n].zone
                                         for n in (s.a, s.b) if n is not None and nodes[n].kind == "junction")]
        hs = sorted(hs or [p[2] for p in s.pts])
        s.width = _r(2 * hs[len(hs) // 2])
    return nodes, segs


def _arc(pts: list[tuple[float, float, float]]) -> list[float]:
    out = [0.0]
    for p, q in zip(pts, pts[1:]):
        out.append(out[-1] + math.dist(p[:2], q[:2]))
    return out


def _at(pts, cum, s: float) -> tuple[float, float, float]:
    import bisect

    s = min(max(s, 0.0), cum[-1])
    i = min(max(bisect.bisect_left(cum, s - 1e-12), 1), len(cum) - 1)
    seg = cum[i] - cum[i - 1]
    t = (s - cum[i - 1]) / seg if seg > 1e-12 else 0.0
    p, q = pts[i - 1], pts[i]
    return tuple(p[k] + (q[k] - p[k]) * t for k in range(3))  # type: ignore[return-value]


def _split_corners(nodes: list[_Node], segs: list[_Seg]) -> list[_Seg]:
    """Cut pieces at sharp corners (an L's), adding a corner node there."""
    out: list[_Seg] = []
    for s in segs:
        pts = s.pts
        cum = _arc(pts)
        total = cum[-1]
        turns = []
        for i in range(1, len(pts) - 1):
            d = max(pts[i][2] * 1.2, 0.75)
            if not s.closed and (cum[i] < d or cum[i] > total - d):
                continue
            if s.closed and total < 4 * d:
                continue
            p0 = _at(pts, cum, cum[i] - d) if not s.closed or cum[i] >= d else _at(pts, cum, cum[i] - d + total)
            p2 = _at(pts, cum, cum[i] + d) if not s.closed or cum[i] + d <= total else _at(pts, cum, cum[i] + d - total)
            a1 = math.atan2(pts[i][1] - p0[1], pts[i][0] - p0[0])
            a2 = math.atan2(p2[1] - pts[i][1], p2[0] - pts[i][0])
            turn = abs((a2 - a1 + math.pi) % (2 * math.pi) - math.pi)
            if math.degrees(turn) > CORNER_DEG:
                turns.append((round(-turn, 6), i, d))
        cuts: list[int] = []
        for _, i, d in sorted(turns):  # sharpest first, then lowest index
            if all(abs(cum[i] - cum[j]) > 2 * d for j in cuts):
                cuts.append(i)
        if not cuts:
            out.append(s)
            continue
        cuts.sort()
        ids = []
        for i in cuts:
            ids.append(len(nodes))
            nodes.append(_Node("corner", pts[i][0], pts[i][1], _r(pts[i][2] * 1.0)))
        if s.closed:
            # A closed loop cut at corners: pieces between consecutive cuts, round the loop.
            ring = pts[:-1] if math.dist(pts[0][:2], pts[-1][:2]) < 1e-9 else pts
            n = len(ring)
            for k, i in enumerate(cuts):
                j = cuts[(k + 1) % len(cuts)]
                piece = [ring[m % n] for m in range(i, (j if j > i else j + n) + 1)]
                out.append(_Seg(piece, ids[k], ids[(k + 1) % len(cuts)], s.width))
        else:
            bounds = [0, *cuts, len(pts) - 1]
            ends = [s.a, *ids, s.b]
            for k in range(len(bounds) - 1):
                out.append(_Seg(pts[bounds[k] : bounds[k + 1] + 1], ends[k], ends[k + 1], s.width))
    return out


# ---------------------------------------------------------------- strokes


def _direction_from(seg: _Seg, at_start: bool, node: _Node) -> tuple[float, float] | None:
    """The way a piece leaves a node (unit vector), measured past the node's unreliable zone."""
    pts = seg.pts if at_start else seg.pts[::-1]
    cum = _arc(pts)
    s0 = next((cum[i] for i, p in enumerate(pts) if math.dist(p[:2], (node.x, node.y)) >= node.zone), None)
    if s0 is None:
        s0 = 0.0
    s1 = min(cum[-1], s0 + max(1.0, 2 * pts[0][2]))
    if s1 - s0 < 0.2:
        s0, s1 = 0.0, cum[-1]
    p, q = _at(pts, cum, s0), _at(pts, cum, s1)
    dx, dy = q[0] - p[0], q[1] - p[1]
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d > 1e-9 else None


def _options(nodes: list[_Node], segs: list[_Seg]) -> dict[int, list[tuple]]:
    """For each node where pieces meet, the ways to join them, best first: a pair that lines up
    runs straight through (the longest pair first), else one piece runs on to the letter's edge
    (the longest first) and the rest stop inside it. Ties: the lower piece numbers."""
    ends_at: dict[int, list[tuple[int, int]]] = {}  # node -> [(seg, 0 start | 1 end)]
    for k, s in enumerate(segs):
        if s.closed:
            continue
        ends_at.setdefault(s.a, []).append((k, 0))  # type: ignore[arg-type]
        ends_at.setdefault(s.b, []).append((k, 1))  # type: ignore[arg-type]
    out: dict[int, list[tuple]] = {}
    for n in sorted(ends_at):
        here = ends_at[n]
        node = nodes[n]
        if len(here) == 1 or node.kind == "end":
            out[n] = [("free", tuple(here))]
            continue
        dirs = {e: _direction_from(segs[e[0]], e[1] == 0, node) for e in here}
        pairs = []
        for i, e in enumerate(here):
            for f in here[i + 1 :]:
                if e[0] == f[0] or dirs[e] is None or dirs[f] is None:
                    continue
                dot = -(dirs[e][0] * dirs[f][0] + dirs[e][1] * dirs[f][1])
                if math.degrees(math.acos(max(-1.0, min(1.0, dot)))) <= STRAIGHT_DEG:
                    pairs.append((-round(segs[e[0]].length + segs[f[0]].length, 3), e, f))
        caps = sorted((-round(segs[e[0]].length, 3), e) for e in here)
        out[n] = ([("through", e, f, tuple(here)) for _, e, f in sorted(pairs)]
                  + [("cap", e, tuple(here)) for _, e in caps]
                  + [("free", tuple(here))])  # last: every stroke on to the edge (a sharp point)
    return out


def _strokes(nodes: list[_Node], segs: list[_Seg], choice: dict[int, int] | None = None) -> list[_Stroke]:
    """Join pieces that run straight through a junction into one stroke, and say for every stroke
    end whether it is capped (reaches the letter's edge) or stops inside another stroke. `choice`
    picks another way to join at a node (an index into _options)."""
    choice = choice or {}
    link: dict[tuple[int, int], tuple[int, int]] = {}
    how: dict[tuple[int, int], tuple[str, int]] = {}
    for n, opts in _options(nodes, segs).items():
        pick = opts[min(choice.get(n, 0), len(opts) - 1)]
        if pick[0] == "free":
            for e in pick[1]:
                how[e] = ("cap", n)
        elif pick[0] == "through":
            _, e, f, here = pick
            link[e], link[f] = f, e
            for g in here:
                if g not in (e, f):
                    how[g] = ("stop", n)
        else:
            _, first, here = pick
            for g in here:
                how[g] = ("cap", n) if g == first else ("stop", n)

    out: list[_Stroke] = []
    done: set[int] = set()
    for k, s in enumerate(segs):
        if k in done:
            continue
        if s.closed:
            done.add(k)
            out.append(_Stroke(list(s.pts), True))
            continue
        # Walk back to the start of the chain this piece is in.
        cur, side = k, 0
        seen = {k}
        loop = False
        while (cur, side) in link:
            nk, nside = link[(cur, side)]
            cur, side = nk, 1 - nside
            if cur in seen:
                loop = True
                break
            seen.add(cur)
        if loop:
            cur, side = k, 0
        # Now (cur, side) is a free end of the chain: walk forward.
        pts: list[tuple[float, float, float]] = []
        joins: list[int] = []  # nodes passed through
        start_end = (cur, side)
        while True:
            done.add(cur)
            piece = segs[cur].pts if side == 0 else segs[cur].pts[::-1]
            if pts:
                pts += piece[1:]
            else:
                pts = list(piece)
            far = (cur, 1 - side)
            if far not in link:
                break
            nk, nside = link[far]
            joins.append(segs[cur].b if side == 0 else segs[cur].a)  # type: ignore[arg-type]
            if nk in done:
                break  # back where it began: a closed stroke through a junction
            cur, side = nk, nside
        closed = loop
        pts = _clear_zones(pts, [nodes[j] for j in joins])
        st = _Stroke(pts, closed, through=joins)
        if not closed:
            st.ends = [how.get(start_end, ("cap", -1)), how.get(far, ("cap", -1))]
        out.append(st)
    return out


def _clear_zones(pts, through: list[_Node]):
    """Inside a junction the middle line wanders: there the stroke runs straight from where it
    enters to where it leaves."""
    for node in through:
        c = (node.x, node.y)
        inside = [i for i, p in enumerate(pts) if math.dist(p[:2], c) < node.zone]
        if not inside or len(inside) >= len(pts) - 1:
            continue
        i0, i1 = inside[0], inside[-1]
        if i0 == 0 or i1 == len(pts) - 1:
            continue
        pts = pts[:i0] + pts[i1 + 1 :]
    return pts


def _trim_end(pts, node: _Node, at_start: bool):
    """The stroke's points up to where it enters the node's unreliable zone."""
    seq = pts if at_start else pts[::-1]
    c = (node.x, node.y)
    zone = node.zone if node.kind != "end" else max(seq[0][2], 0.0)
    i = 0
    while i < len(seq) - 2 and math.dist(seq[i][:2], c) < zone:
        i += 1
    seq = seq[i:]
    return seq if at_start else seq[::-1]


def _end_dir(seq) -> tuple[float, float]:
    """The direction a line leaves its first point backwards (unit), from about 1 mm of it."""
    cum = _arc(seq)
    q = _at(seq, cum, min(cum[-1], max(1.0, 2 * seq[0][2])))
    dx, dy = seq[0][0] - q[0], seq[0][1] - q[1]
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d > 1e-9 else (0.0, 0.0)


def _cap(seq, shape: Polygon, boundary, node: _Node | None):
    """Extend the line from its first point straight on to the letter's edge."""
    d = _end_dir(seq)
    if d == (0.0, 0.0):
        return seq
    p = seq[0]
    reach = (node.zone if node is not None else 0.0) + 2 * p[2] + 0.5
    ray = LineString([(p[0], p[1]), (p[0] + d[0] * reach, p[1] + d[1] * reach)])
    hit = ray.intersection(boundary)
    ts = sorted(_r(math.dist((p[0], p[1]), (g.x, g.y))) for g in _points(hit))
    t = next((t for t in ts if t > 1e-6), None)
    if t is None:
        t = reach if shape.contains(Point(ray.coords[-1])) else 0.0
    if t < 0.05:
        return seq
    return [(_r(p[0] + d[0] * t), _r(p[1] + d[1] * t), p[2]), *seq]


def _points(geom) -> list[Point]:
    if geom.is_empty:
        return []
    if geom.geom_type == "Point":
        return [geom]
    if geom.geom_type == "LineString":
        return [Point(c) for c in geom.coords]
    return [q for g in getattr(geom, "geoms", []) for q in _points(g)]


def _stop(seq, area, shape: Polygon) -> list | None:
    """Extend the line from its first point on into `area` (the column of the stroke it meets)
    until its end stitch is JOIN_MM inside it: the middle, and each end of the stitch unless that
    end is on the letter's edge, where being inside the column at all is enough (an L's corner).
    Where strokes meet at a sharp angle the ends can't both get there: then the middle alone, and
    the letter's own checks decide. None if even the middle never gets there."""
    d = _end_dir(seq)
    p = seq[0]
    if d == (0.0, 0.0):
        return None
    deep = area.buffer(-JOIN_MM)
    loose = area.buffer(0.02)
    inner = shape.buffer(-JOIN_MM)
    n = (-d[1], d[0])
    h = p[2]
    s = 0.0
    middle_only = None
    while s <= 6 * max(h, 0.5) + 2.0:
        q = (p[0] + d[0] * s, p[1] + d[1] * s)
        if deep.contains(Point(q)):
            if middle_only is None:
                middle_only = (s, q)
            ends = [Point(q[0] + n[0] * h, q[1] + n[1] * h), Point(q[0] - n[0] * h, q[1] - n[1] * h)]
            if all(deep.contains(e) or (loose.contains(e) and not inner.contains(e)) for e in ends):
                return seq if s == 0 else [(_r(q[0]), _r(q[1]), h), *seq]
        elif middle_only is not None:
            break  # through and out the other side
        s = round(s + 0.05, 6)
    if middle_only is None:
        return None
    s, q = middle_only
    return seq if s == 0 else [(_r(q[0]), _r(q[1]), h), *seq]


def _resample(pts, closed: bool):
    """Points every STEP_MM along the line (ends kept), carrying the half-width."""
    if closed:
        pts = [*pts, pts[0]]
    cum = _arc(pts)
    total = cum[-1]
    n = max(1, round(total / STEP_MM))
    out = [_at(pts, cum, total * i / n) for i in range(n + 1)]
    out = [(_r(x), _r(y), _r(h)) for x, y, h in out]
    return out[:-1] if closed else out


def _rails(st: _Stroke, shape: Polygon, boundary) -> None:
    """The column's two sides: the middle line moved out by the half-width on each side, then
    moved onto the letter's outline where that is close (or where the side fell outside it)."""
    pts = _resample(st.pts, st.closed)
    n = len(pts)
    if n < 2:
        raise ColumnsFailed("a stroke too short for a column")
    a, b = [], []
    for i, (x, y, h) in enumerate(pts):
        if st.closed:
            p0, p1 = pts[(i - 1) % n], pts[(i + 1) % n]
        else:
            p0, p1 = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        tx, ty = p1[0] - p0[0], p1[1] - p0[1]
        tl = math.hypot(tx, ty)
        if tl < 1e-9:
            raise ColumnsFailed("a stroke folds back on itself")
        nx, ny = -ty / tl, tx / tl
        for side, rail in ((1, a), (-1, b)):
            q = (x + side * nx * h, y + side * ny * h)
            near = boundary.interpolate(boundary.project(Point(q)))
            gap = math.dist(q, (near.x, near.y))
            same_side = ((near.x - x) * nx + (near.y - y) * ny) * side > 0
            if same_side and (gap <= SNAP_MM or not shape.covers(Point(q))):
                q = (near.x, near.y)
            rail.append((_r(q[0]), _r(q[1])))
    if st.closed:
        a.append(a[0])
        b.append(b[0])
    for _ in range(5):  # a wide notch takes a few rungs
        before = len(a)
        a, b = _notches(a, b, shape, boundary)
        if len(a) == before:
            break
    st.a, st.b = a, b


def _notches(a, b, shape: Polygon, boundary):
    """Where a side cuts across a notch in the outline (the crotch of an r) between two rungs,
    add a rung there with that side on the outline, so the column doesn't sew over the notch."""
    inside = shape.buffer(OUTSIDE_MM / 3)
    out_a, out_b = [a[0]], [b[0]]
    for i in range(len(a) - 1):
        for rail, other in ((a, b), (b, a)):
            m = ((rail[i][0] + rail[i + 1][0]) / 2, (rail[i][1] + rail[i + 1][1]) / 2)
            if inside.contains(Point(m)):
                continue
            near = boundary.interpolate(boundary.project(Point(m)))
            q = (_r(near.x), _r(near.y))
            o = (_r((other[i][0] + other[i + 1][0]) / 2), _r((other[i][1] + other[i + 1][1]) / 2))
            out_a.append(q if rail is a else o)
            out_b.append(o if rail is a else q)
            break
        out_a.append(a[i + 1])
        out_b.append(b[i + 1])
    return out_a, out_b


def _area(a, b):
    """A column's area: the union of its rungs' quadrilaterals."""
    import shapely

    quads = [MultiPoint([a[i], a[i + 1], b[i + 1], b[i]]).convex_hull for i in range(len(a) - 1)]
    return shapely.union_all([q for q in quads if q.geom_type == "Polygon"]).buffer(0)


# ---------------------------------------------------------------- the letter


MAX_TRIES = 8  # ways of joining strokes tried before a letter is given up on


class _NodeFailed(ColumnsFailed):
    """A join between strokes didn't work; another way of joining there may."""

    def __init__(self, message: str, node: int):
        super().__init__(message)
        self.node = node


def columns(shape: Polygon, size_mm: float) -> list[dict[str, Any]]:
    """The objects that sew one letter shape (mm, y down) as true satin: a satin column for each
    stroke, and satin-look fills, sewn first, for what isn't a stroke. Raises ColumnsFailed when
    the columns don't cover the letter well (the caller sews it in Satin look instead).

    Where a join between strokes fails its check, the next way of joining there is tried (in a
    fixed order), up to MAX_TRIES times."""
    import shapely

    shape = shapely.set_precision(shape, 1e-6).buffer(0)
    if shape.is_empty or shape.geom_type != "Polygon":
        raise ColumnsFailed("not one shape")
    nodes, segs = _graph(shape)
    keep = [s for s in segs if SATIN_MIN_WIDTH_MM <= s.width <= SATIN_MAX_WIDTH_MM and len(s.pts) >= 2]
    # A free-standing piece no longer than it is wide is a dot, not a stroke.
    keep = [s for s in keep if s.closed or not (nodes[s.a].kind == "end" and nodes[s.b].kind == "end"  # type: ignore[index]
                                                and s.length < s.width)]
    keep = _split_corners(nodes, keep)
    options = _options(nodes, keep)
    choice: dict[int, int] = {}
    for _ in range(MAX_TRIES):
        try:
            return _build(shape, size_mm, nodes, keep, choice)
        except _NodeFailed as exc:
            n = exc.node
            if choice.get(n, 0) + 1 >= len(options.get(n, [])):
                raise
            choice[n] = choice.get(n, 0) + 1
    raise ColumnsFailed("no way of joining the strokes works")


def _build(shape: Polygon, size_mm: float, nodes: list[_Node], keep: list[_Seg], choice: dict[int, int]) -> list[dict[str, Any]]:
    import shapely

    from ..digitize import stitches as dz
    from .glyphs import SMALL_TEXT_MM, _fill_object

    boundary = shape.boundary
    strokes = _strokes(nodes, keep, choice)

    # Each stroke's middle line, out of the junctions' unreliable zones and on to the letter's
    # edge at its capped ends; then every column's sides as if its stops ended there.
    for st in strokes:
        pts = st.pts
        if not st.closed:
            for idx, (kind, n) in enumerate(st.ends):
                if n is not None and n >= 0 and len(pts) > 2:
                    pts = _trim_end(pts, nodes[n], idx == 0)
            if len(pts) < 2:
                raise ColumnsFailed("a stroke vanished inside a junction")
            for idx, (kind, n) in enumerate(st.ends):
                if kind == "cap":
                    node = nodes[n] if n is not None and n >= 0 else None
                    pts = _cap(pts, shape, boundary, node) if idx == 0 else _cap(pts[::-1], shape, boundary, node)[::-1]
        st.pts = pts
        _rails(st, shape, boundary)
    # Which stroke each stop meets: the one capped at that node, or running through it.
    owner: dict[int, int] = {}
    for i, st in enumerate(strokes):
        for kind, n in st.ends:
            if kind == "cap" and n is not None and n >= 0:
                owner.setdefault(n, i)
        for n in st.through:
            owner.setdefault(n, i)
    first_areas = [_area(st.a, st.b) for st in strokes]
    for st in strokes:
        if not any(k == "stop" for k, _ in st.ends):
            continue
        pts = st.pts
        for idx, (kind, n) in enumerate(st.ends):
            if kind != "stop" or n is None:
                continue
            j = owner.get(n)
            if j is None:
                raise _NodeFailed("a junction with nothing to meet", n)
            got = _stop(pts if idx == 0 else pts[::-1], first_areas[j], shape)
            if got is None:
                raise _NodeFailed("a stroke can't reach the one it meets", n)
            pts = got if idx == 0 else got[::-1]
        st.pts = pts
        _rails(st, shape, boundary)

    cols = [st for st in strokes if st.a]
    if not cols:
        return [_fill_object(shape, "satin", size_mm)]
    covered = shapely.union_all([_area(st.a, st.b) for st in cols])

    for n in sorted(owner):  # every place where columns meet: the columns alone must cover it
        node = nodes[n]
        meeting = sum(1 for st in cols for _, m in st.ends if m == n) + sum(1 for st in cols if n in st.through)
        if node.kind == "end" or meeting < 2:
            continue
        disc = Point(node.x, node.y).buffer(max(node.zone, 0.3)).intersection(shape)
        if disc.area > 1e-6 and disc.intersection(covered).area < JOIN_COVER_MIN * disc.area:
            raise _NodeFailed("a join between strokes is left bare", n)

    # What the columns leave: sewn first, in Satin look, when it's big enough to matter.
    left = shape.difference(covered).buffer(-SHRINK_MM, join_style="mitre")
    fills = []
    if not left.is_empty:
        grown = left.buffer(2 * SHRINK_MM, join_style="mitre").intersection(shape)
        parts = [g for g in getattr(grown, "geoms", [grown]) if g.geom_type == "Polygon" and g.area > MIN_LEFT_MM2]
        parts.sort(key=lambda g: (_r(g.bounds[0]), _r(g.bounds[1]), _r(g.area)))
        fills = parts
    sewn = shapely.union_all([covered, *fills])

    # The letter's own check: if it fails, the caller sews the whole letter in Satin look.
    if sewn.intersection(shape).area < COVER_MIN * shape.area:
        raise ColumnsFailed("the columns leave too much of the letter bare")
    if sewn.difference(shape.buffer(OUTSIDE_MM)).area > 1e-3:
        raise ColumnsFailed("a column reaches outside the letter")
    for st in cols:
        pairs = dz.satin_pairs([[*p, "c"] for p in st.a], [[*p, "c"] for p in st.b], 0.36)
        if dz._crossing_rungs(pairs) >= 3:
            raise ColumnsFailed("a column's sides cross")

    small = size_mm < SMALL_TEXT_MM
    out = [_fill_object(g, "satin", size_mm) for g in fills]
    for st in _order(cols):
        widest = max(math.dist(p, q) for p, q in zip(st.a, st.b))
        params: dict[str, Any] = {"spacing_mm": 0.36, "comp_by_width": True, "underlay": [] if small else "auto"}
        if widest > SPLIT_OVER_MM:
            params["split_mm"] = 7.0
        out.append({"kind": "satin", "geometry": {"rail_a": [[x, y, "c"] for x, y in st.a],
                                                  "rail_b": [[x, y, "c"] for x, y in st.b]}, "params": params})
    return out


def _order(cols: list[_Stroke]) -> list[_Stroke]:
    """Left to right by their start; each starts at its end nearest where the last one finished
    (a closed one at its point nearest it). Ties: lower x, then lower y, then the earlier stroke."""
    def ends(st):
        return [st.a[0], st.a[-1]] if not st.closed else st.a[:-1]

    def mid(st, i):
        return ((st.a[i][0] + st.b[i][0]) / 2, (st.a[i][1] + st.b[i][1]) / 2)

    todo = sorted(range(len(cols)), key=lambda i: (min(_r(p[0]) for p in ends(cols[i])),
                                                   min(_r(p[1]) for p in ends(cols[i])), i))
    out: list[_Stroke] = []
    here: tuple[float, float] | None = None
    for i in todo:
        st = cols[i]
        n = len(st.a)
        if st.closed:
            idx = list(range(n - 1))
            if here is None:
                k = min(idx, key=lambda j: (_r(mid(st, j)[0]), _r(mid(st, j)[1]), j))
            else:
                k = min(idx, key=lambda j: (_r(math.dist(mid(st, j), here)), j))
            a = st.a[k:-1] + st.a[:k] + [st.a[k]]
            b = st.b[k:-1] + st.b[:k] + [st.b[k]]
            st.a, st.b = a, b
        else:
            first, last = mid(st, 0), mid(st, n - 1)
            if here is None:
                flip = (_r(last[0]), _r(last[1])) < (_r(first[0]), _r(first[1]))
            else:
                flip = _r(math.dist(last, here)) < _r(math.dist(first, here))
            if flip:
                st.a, st.b = st.a[::-1], st.b[::-1]
        here = mid(st, len(st.a) - 1)
        out.append(st)
    return out
