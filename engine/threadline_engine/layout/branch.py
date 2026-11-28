"""Branching (P7-B1): drawn shapes in one thread, sewn as one path with one start and one end.

Items with the same `branch` id are a branch. Drawn lines, satins and fills sewn in the branch's
thread (the one most of its members sew in) can be in one; a member in another thread, a blend (more
than one thread), an applique, lettering or a stitch file is left out with a note, and a branch of one
is ignored. Members next to each other in the sewing order are routed together, at the place of the
first; a member sewn apart from the rest starts a path of its own, with a note.

Two steps, both cached:
1. `plan` (before any item is made, `prepared_items`): the order of the members (overlapping ones
   keep theirs; the rest the order with the smallest gaps between neighbours), and where each one
   starts and ends, written on copies of the items (a fill's `start_mm` / `end_mm`, a closed line's
   `start_mm`, an open line turned round).
2. The "after_items" pass `apply`: the members' blocks become one block in that order, joined from
   the last stitch of one to the first of the next. A join under 0.3 mm needs nothing; one up to
   REACH_MM is a single stitch onto where the next shape starts; a longer one runs in small
   stitches under what is sewn later (the cover of every block sewn at or after the next member),
   straight or along its edges, each end reaching that cover over at most REACH_MM. With no such
   way it is a jump (trimmed when over 3 mm), with a note. Where the thread runs on, the lock
   stitches at that join are left out (the member is made again with that lock off).

Everything here gives a fixed answer on every computer: distances are compared rounded to
DECIMALS, and ties go to the lower member, then the lower point index.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pyembroidery as pe
import shapely
from shapely.errors import GEOSException
from shapely.geometry import LineString, Point as SPoint
from shapely.ops import nearest_points, substring

from ..digitize import stitches as dz
from ..digitize.paths import flatten
from ..digitize.patterns import polygons
from . import passes
from .files import _apply_ops
from .joins import _blocks_overlap, _cover
from .model import Block, LayoutError, Transform, _mm, _thread_key
from .objects import DEFAULT_THREAD, OBJECT_LABEL, _object_blocks

Pt = tuple[float, float]

BRANCH_KINDS = ("run", "satin", "fill")
REACH_MM = 1.0  # a join's ends may reach the cover over this much (and a join this short is one stitch)
DECIMALS = 3  # distances are compared rounded to this many decimals (mm): near ties are ties
SAMPLE_MM = 0.5  # an outline's points are tried this far apart for where a member enters and leaves
INSIDE_MM = 0.001  # a reached point is stepped this far past the cover's edge, so it lies inside once rounded
CLOSE_MM = 0.31  # the covers of later blocks are merged closed by this much: stitching that meets leaves no slit
EXACT_MAX = 8  # branches this big or smaller get the best order by exact search
SWAPS_MAX = 200  # bigger ones: nearest first, then at most this many two-swap improvements

_JOIN_HELP = ("Shapes join best where fills touch or overlap, or where a line starts right at the end of the one "
              "before. Move them that way, put a shape sewn later over that spot, or ")
CUT_NOTE = ("Branch: the thread can't get from {a} to {b} hidden under stitching (nothing sewn later covers the "
            "whole way between them), so it is cut there. " + _JOIN_HELP + "leave the cut.")
JUMP_NOTE = ("Branch: the thread can't get from {a} to {b} hidden under stitching (nothing sewn later covers the "
             "whole way between them), so the needle jumps there and leaves a short thread on top. " + _JOIN_HELP
             + "snip that thread after sewing.")
LEFT_OUT = {
    "thread": "{name} is in a branch but sews in a different thread, so it is sewn on its own. "
              "Give it the branch's thread, or take it out of the branch (Alt+Shift+U).",
    "blend": "{name} is in a branch but sews in more than one thread, so it is sewn on its own. "
             "Take it out of the branch (Alt+Shift+U), or sew it in one thread.",
    "applique": "{name} is an applique, which can't be in a branch, so it is sewn on its own. "
                "Take it out of the branch (Alt+Shift+U).",
    "kind": "{name} can't be in a branch (only drawn lines, satins and fills can), so it is sewn on its own. "
            "Take it out of the branch (Alt+Shift+U).",
    "apart": "{name} is in a branch with {first} but something else is sewn between them, so it starts a path "
             "of its own. Select the branch's shapes and use Branch (Alt+Shift+B) to put them together.",
}


# ---------------------------------------------------------------- who is in a branch


def _bid(it: Any) -> str | None:
    b = it.get("branch") if isinstance(it, dict) else None
    return b if isinstance(b, str) and b else None


def _thread_of(it: dict[str, Any]) -> tuple[str, str, str]:
    """The thread an item sews in, as its block gets it (layout/objects.py)."""
    over = (it.get("threads") or [None])[0]
    t = over if isinstance(over, dict) and over else {**DEFAULT_THREAD, **(it.get("thread") or {})}
    return _thread_key({k: str(t.get(k) or "") for k in ("color", "name", "catalog", "brand")})


def _is_blend(it: dict[str, Any]) -> bool:
    p = it.get("params") or {}
    return it.get("kind") == "fill" and p.get("pattern") == "blend"


def _name(it: dict[str, Any], idx: int) -> str:
    """An item's name the way the app shows it (layout/render.py)."""
    if it.get("name"):
        return str(it["name"])
    kind = it.get("kind", "file")
    if kind == "text":
        from .text import text_title

        return f"“{text_title(it)}”"
    if kind in OBJECT_LABEL:
        return f"{OBJECT_LABEL[kind]} {idx + 1}"
    return Path(str(it.get("path") or "")).name or f"Design {idx + 1}"


def _runs(items: list) -> tuple[list[tuple[str, list[int]]], list[dict]]:
    """The paths to plan: (branch id, member indices in layout order) for each run of two or more
    members sewn next to each other; and the notes about members left out or sewn apart. A
    branch's thread is the one most of its members sew in (a tie: the thread of the one listed
    first), so recoloring one member leaves out that member, not the others."""
    notes: list[dict] = []
    votes: dict[str, dict[tuple, list[int]]] = {}  # branch -> thread -> [members in it, first index]
    for idx, it in enumerate(items):
        b = _bid(it)
        if b and it.get("kind") in BRANCH_KINDS and not _is_blend(it):
            v = votes.setdefault(b, {}).setdefault(_thread_of(it), [0, idx])
            v[0] += 1
    thread = {b: max(ts, key=lambda t: (ts[t][0], -ts[t][1])) for b, ts in votes.items()}
    ok: dict[int, str] = {}
    for idx, it in enumerate(items):
        b = _bid(it)
        if not b:
            continue
        kind = it.get("kind", "file")
        why = ("applique" if kind == "applique" else "kind" if kind not in BRANCH_KINDS else
               "blend" if _is_blend(it) else "thread" if _thread_of(it) != thread.get(b) else None)
        if why is None:
            ok[idx] = b
        elif sum(1 for o in items if _bid(o) == b) > 1:
            notes.append({"level": "warning", "code": f"branch_{why}_{idx}",
                          "message": LEFT_OUT[why].format(name=_name(it, idx))})
    pieces: list[tuple[str, list[int]]] = []
    for idx in sorted(ok):
        if pieces and pieces[-1][0] == ok[idx] and pieces[-1][1][-1] == idx - 1:
            pieces[-1][1].append(idx)
        else:
            pieces.append((ok[idx], [idx]))
    counts: dict[str, int] = {}
    for b in ok.values():
        counts[b] = counts.get(b, 0) + 1
    runs: list[tuple[str, list[int]]] = []
    first_of: dict[str, int] = {}
    for b, members in pieces:
        if counts[b] < 2:
            continue  # a branch of one is ignored
        if b in first_of:
            notes.append({"level": "warning", "code": f"branch_apart_{members[0]}", "message": LEFT_OUT["apart"].format(
                name=_name(items[members[0]], members[0]), first=_name(items[first_of[b]], first_of[b]))})
        else:
            first_of[b] = members[0]
        if len(members) > 1:
            runs.append((b, members))
    return runs, notes


# ---------------------------------------------------------------- shapes, in hoop mm


def _rd(v: float) -> float:
    return round(v, DECIMALS)


def _placed(it: dict[str, Any]) -> dict[str, Any]:
    """An item with its transform applied to its points (as it sews)."""
    t = Transform.from_dict(it.get("transform"))
    if t.is_identity():
        return it
    x0, y0, x1, y1 = dz.bounds(dz.geometry_points(it))
    return dz.transform_geometry(it, t, ((x0 + x1) / 2, (y0 + y1) / 2))


def _sampled(poly: list[Pt], closed: bool) -> list[Pt]:
    """A polyline's points, with more every SAMPLE_MM along each stretch (in order)."""
    pts = list(poly) + ([poly[0]] if closed and poly else [])
    out: list[Pt] = []
    for a, b in zip(pts, pts[1:]):
        n = max(1, math.ceil(round(math.dist(a, b) / SAMPLE_MM, 6)))  # the same on every computer
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]
    if not closed and pts:
        out.append(pts[-1])
    return out or list(poly)


@dataclass
class _Member:
    idx: int
    item: dict[str, Any]
    mode: str  # "fill", "closed" (a border) or "open" (a line or satin with two ends)
    shape: Any  # what it covers (jumps._shape_of's measure), for the gaps between members
    points: list[Pt]  # the outline, sampled (fill, closed); the two ends (open)


def _member(idx: int, it: dict[str, Any]) -> _Member | None:
    try:
        w = _placed(it)
        g = w.get("geometry") or {}
        kind = it.get("kind")
        if kind == "fill":
            poly, _ = flatten(g.get("outline") or [], True)
            if len(poly) < 3:
                return None
            shape = shapely.Polygon(poly).buffer(0)
            return _Member(idx, it, "fill", shape, _sampled(poly, True))
        if g.get("nodes"):
            closed = bool(g.get("closed"))
            poly, _ = flatten(g["nodes"], closed)
            if len(poly) < 2:
                return None
            shape = LineString(poly + ([poly[0]] if closed else []))
            if kind == "satin" and _mm(g.get("width_mm")):
                shape = shape.buffer(float(g["width_mm"]) / 2, quad_segs=2)
            return _Member(idx, it, "closed" if closed else "open", shape,
                           _sampled(poly, True) if closed else [poly[0], poly[-1]])
        a, b = g.get("rail_a") or [], g.get("rail_b") or []
        if kind == "satin" and len(a) >= 2 and len(b) >= 2:
            ra, rb = flatten(a)[0], flatten(b)[0]
            shape = shapely.Polygon(ra + rb[::-1]).buffer(0)
            mid = lambda p, q: ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)  # noqa: E731
            return _Member(idx, it, "open", shape, [mid(ra[0], rb[0]), mid(ra[-1], rb[-1])])
    except (LayoutError, dz.DigitizeError, GEOSException, TypeError, ValueError, IndexError):
        return None
    return None


def _distance(shape: Any, p: Pt) -> float:
    return _rd(shape.distance(SPoint(p)))


def _nearest(points: list[Pt], target: Any, along: bool = False) -> int:
    """The index of the point nearest `target` (a shape). Ties: the lowest index, or with `along`
    the one a third of the way along those tied: where two shapes touch along an edge, away from
    its corners, and off its middle, where a symmetric fill would have two equally good ways to go
    (which the last digit of a sine would then choose between)."""
    d = [_rd(target.distance(SPoint(p))) for p in points]
    low = min(d)
    tied = [k for k, v in enumerate(d) if v == low]
    return tied[len(tied) // 3] if along else tied[0]


# ---------------------------------------------------------------- the order


def _order_cost(seq: list[int], gap: list[list[int]]) -> int:
    return sum(gap[a][b] for a, b in zip(seq, seq[1:]))


def _valid(seq: list[int], before: list[set[int]], first: int | None, last: int | None) -> bool:
    if first is not None and seq[0] != first or last is not None and seq[-1] != last:
        return False
    seen: set[int] = set()
    for j in seq:
        if before[j] - seen:
            return False
        seen.add(j)
    return True


def _best_order(n: int, gap: list[list[int]], before: list[set[int]], first: int | None, last: int | None) -> list[int]:
    """Member positions in sewing order: the order the overlaps allow with the smallest total gap.
    Exact up to EXACT_MAX members (the first such order in index order wins a tie); above that,
    nearest first, then two-swaps that make it strictly shorter."""
    if n <= EXACT_MAX:
        best: list[Any] = [None, None]

        def dfs(seq: list[int], cost: int) -> None:
            if best[0] is not None and cost >= best[0]:
                return
            if len(seq) == n:
                best[0], best[1] = cost, list(seq)
                return
            placed = set(seq)
            for j in range(n):
                if j in placed or before[j] - placed:
                    continue
                if not seq and first is not None and j != first:
                    continue
                if last is not None and j == last and len(seq) < n - 1:
                    continue
                seq.append(j)
                dfs(seq, cost + (gap[seq[-2]][j] if len(seq) > 1 else 0))
                seq.pop()

        dfs([], 0)
        if best[1] is not None:
            return best[1]
        return list(range(n))  # (cannot happen: layout order always obeys the overlaps)
    seq: list[int] = []
    left = set(range(n))
    while left:
        ready = [j for j in sorted(left) if not before[j] - set(seq)
                 and (seq or first is None or j == first) and (j != last or len(left) == 1)]
        if not ready:
            ready = [j for j in sorted(left) if not before[j] - set(seq)] or sorted(left)
        j = min(ready, key=lambda k: (gap[seq[-1]][k] if seq else 0, k))
        seq.append(j)
        left.discard(j)
    if not _valid(seq, before, first, last):
        seq = list(range(n))
    swaps = 0
    better = True
    while better and swaps < SWAPS_MAX:
        better = False
        cost = _order_cost(seq, gap)
        for p, q in itertools.combinations(range(n), 2):
            trial = list(seq)
            trial[p], trial[q] = trial[q], trial[p]
            if _valid(trial, before, first, last):
                c = _order_cost(trial, gap)
                if c < cost:
                    seq, cost, better = trial, c, True
                    swaps += 1
                    if swaps >= SWAPS_MAX:
                        break
    return seq


# ---------------------------------------------------------------- the plan


@dataclass
class Plan:
    branch: str
    run: list[int]  # member item indices, in layout order
    order: list[int]  # the same, in sewing order
    prepared: dict[int, dict[str, Any]] = field(default_factory=dict)  # item index -> the copy to sew


_plan_cache: dict[str, tuple[list[Plan], list[dict]]] = {}
_join_cache: dict[bytes, tuple] = {}
_CACHE_MAX = 256


def _remember(cache: dict, key: Any, value: Any) -> Any:
    if len(cache) >= _CACHE_MAX:
        cache.pop(next(iter(cache)))
    cache[key] = value
    return value


def _dots(layout: dict[str, Any], b: str) -> tuple[Pt | None, Pt | None]:
    entry = (layout.get("branches") or {}).get(b) if isinstance(layout.get("branches"), dict) else None
    entry = entry if isinstance(entry, dict) else {}
    return dz._start_point(entry.get("start_mm")), dz._start_point(entry.get("end_mm"))


def plans(layout: dict[str, Any]) -> tuple[list[Plan], list[dict]]:
    """Every path to sew as one, and the notes about members left out or sewn apart. Cached by
    the members (their geometry, settings, transforms and threads), where they sit in the sewing
    order, the branches' dots and the fabric."""
    items = layout.get("items") or []
    if not any(_bid(it) for it in items):
        return [], []
    key = json.dumps({"items": [it if _bid(it) else None for it in items], "fabric": layout.get("fabric"),
                      "branches": layout.get("branches")}, sort_keys=True, default=str)
    hit = _plan_cache.get(key)
    if hit is not None:
        return hit
    runs, notes = _runs(items)
    out: list[Plan] = []
    for b, run in runs:
        plan = _plan(b, run, items, layout.get("fabric"), _dots(layout, b))
        if plan is not None:
            out.append(plan)
    return _remember(_plan_cache, key, (out, notes))


def _plan(b: str, run: list[int], items: list, fabric: str | None, dots: tuple[Pt | None, Pt | None]) -> Plan | None:
    members = [_member(i, items[i]) for i in run]
    if any(m is None for m in members):
        return None  # a broken shape: render says what's wrong with it, branch or not
    try:
        made = [_object_blocks(items[i], i, fabric)[0] for i in run]
    except LayoutError:
        return None
    if any(len([blk for blk in bl if blk.recs]) != 1 for bl in made):
        return None
    blocks = [next(blk for blk in bl if blk.recs) for bl in made]
    n = len(run)
    before = [{i for i in range(j) if _blocks_overlap(blocks[i], blocks[j])} for j in range(n)]
    gap = [[0 if i == j else round(members[i].shape.distance(members[j].shape) * 10 ** DECIMALS) for j in range(n)]
           for i in range(n)]
    start, end = dots
    has_after = [any(i in before[j] for j in range(n)) for i in range(n)]
    first = last = None
    if start is not None:
        free = [i for i in range(n) if not before[i]]
        first = min(free, key=lambda i: (_distance(members[i].shape, start), i))
    if end is not None:
        free = [i for i in range(n) if not has_after[i] and i != first]
        if free:
            last = min(free, key=lambda i: (_distance(members[i].shape, end), i))
    order = _best_order(n, gap, before, first, last)
    prepared: dict[int, dict[str, Any]] = {}
    exit_at: Pt | None = start
    for pos, k in enumerate(order):
        m = members[k]
        nxt = members[order[pos + 1]].shape if pos + 1 < n else (SPoint(end) if end is not None else None)
        prev = SPoint(exit_at) if exit_at is not None else None
        prepared[m.idx], exit_at = _entered(m, prev, nxt)
    return Plan(b, run, [members[k].idx for k in order], prepared)


def _entered(m: _Member, prev: Any, nxt: Any) -> tuple[dict[str, Any], Pt | None]:
    """A copy of the member made to start nearest where the thread comes from (`prev`, a point)
    and to end nearest where it goes (`nxt`, a shape or point); and where it ends."""
    from ..jumps import _to_local, can_turn, turned_round

    it = m.item
    if m.mode == "open":
        e0, e1 = m.points[0], m.points[-1]

        def cost(a: Pt, z: Pt) -> float:
            return (_distance(prev, a) if prev is not None else 0.0) + (_distance(nxt, z) if nxt is not None else 0.0)

        # A line whose curve would change turned round is sewn the way it was drawn.
        turn = cost(e1, e0) < cost(e0, e1) and can_turn(it)
        v = turned_round(it) if turn else copy.deepcopy(it)
        params = dict(v.get("params") or {})
        params.pop("start_mm", None)
        params.pop("end_mm", None)
        v["params"] = params
        return v, (e0 if turn else e1)
    v = copy.deepcopy(it)
    params = dict(v.get("params") or {})
    pts = m.points
    if m.mode == "closed":
        target = prev if prev is not None else nxt
        if target is None:
            return it, None
        k = _nearest(pts, target, along=prev is None)
        lx, ly = _to_local(it, pts[k])
        params["start_mm"] = [round(lx, 4), round(ly, 4)]
        params.pop("end_mm", None)
        v["params"] = params
        return v, pts[k]
    # A fill: it starts on the edge nearest where the thread comes from, and its rows end as near
    # the next member as they can.
    if prev is not None:
        lx, ly = _to_local(it, pts[_nearest(pts, prev)])
        params["start_mm"] = [round(lx, 4), round(ly, 4)]
    out: Pt | None = None
    if nxt is not None:
        out = pts[_nearest(pts, nxt, along=True)]
        lx, ly = _to_local(it, out)
        params["end_mm"] = [round(lx, 4), round(ly, 4)]
        params.pop("reverse", None)
    if prev is None and nxt is None:
        return it, None
    v["params"] = params
    return v, out


def prepared_items(layout: dict[str, Any]) -> list:
    """The items to sew: branch members replaced by copies that start and end where their branch
    needs them. `layout["items"]` itself when there is nothing to change."""
    items = layout.get("items") or []
    found, _ = plans(layout)
    if not found:
        return items
    out = list(items)
    for plan in found:
        for idx, v in plan.prepared.items():
            out[idx] = v
    return out


# ---------------------------------------------------------------- joins


def _stitches(blk: Block) -> list:
    return [r for r in blk.recs if r[2] == pe.STITCH]


def _reach(p: Pt, zone: Any) -> Pt | None:
    """`p` if the zone holds it, else the zone's nearest point if it is within REACH_MM, stepped
    INSIDE_MM further in along the way from `p` (rounded to 0.0001 mm, the nearest point itself can
    land just outside, past the 1e-6 mm a Zone allows, and the join would then be a cut)."""
    sp = SPoint(p)
    if zone.covers(sp):
        return p
    d = zone.distance(sp)
    if _rd(d) > REACH_MM:
        return None
    q = nearest_points(zone, sp)[0]
    k = 1 + INSIDE_MM / d if d > 1e-9 else 1.0
    return (round(p[0] + (q.x - p[0]) * k, 4), round(p[1] + (q.y - p[1]) * k, 4))


def _ring_key(ring: LineString) -> tuple:
    return min((round(x, 3), round(y, 3)) for x, y in ring.coords)


def _edge_route(a: Pt, b: Pt, z: dz.Zone) -> list[Pt] | None:
    """The shortest way from a to b along one edge of the zone (0.3 mm in, else 0.05 mm),
    staying inside it; equally long ways are told apart by their points, not by the order the
    geometry library gives the edges in."""
    for inset in (0.3, 0.05):
        best: tuple | None = None
        for line in sorted(z.rings(inset), key=_ring_key):
            total = line.length
            sa, sb = line.project(SPoint(a)), line.project(SPoint(b))

            def arc(s0: float, s1: float) -> list[Pt]:
                if s0 <= s1:
                    return list(substring(line, s0, s1).coords)
                return list(substring(line, s0, total).coords) + list(substring(line, 0, s1).coords)[1:]

            for path in (arc(sa, sb), arc(sb, sa)[::-1]):
                route = [a, *path, b]
                ls = LineString(route)
                if z.cover.covers(ls):
                    k = (round(ls.length, 6), [(round(x, 4), round(y, 4)) for x, y in route])
                    if best is None or k < best[0]:
                        best = (k, route)
        if best is not None:
            return best[1]
    return None


def _join(a: Pt, b: Pt, zone_of: Callable[[], Any]) -> tuple[str, list[Pt]]:
    """How the thread gets from a (one member's last stitch) to b (the next one's first):
    ("on", route) running on (route empty: nothing needed), or ("cut", []). `zone_of()` gives the
    zone the join may hide in; it is only asked for when the join is longer than REACH_MM (closing
    it is the costly part of planning, and a short join never looks at it)."""
    d = math.dist(a, b)
    if d < dz.MIN_STITCH_MM:
        return "on", []
    if d <= REACH_MM:
        return "on", [a, b]
    zone = zone_of()
    if zone is None or zone.is_empty:
        return "cut", []
    try:
        pa, pb = _reach(a, zone), _reach(b, zone)
        if pa is None or pb is None:
            return "cut", []
        for piece in sorted(polygons(zone), key=lambda g: _ring_key(g.exterior)):
            z = dz.Zone(piece)
            if not (z.cover.covers(SPoint(pa)) and z.cover.covers(SPoint(pb))):
                continue
            inner = [pa, pb] if z.cover.covers(LineString([pa, pb])) else _edge_route(pa, pb, z)
            if inner:
                route = [a, *inner, b]
                return "on", [p for k, p in enumerate(route) if k == 0 or math.dist(p, route[k - 1]) > 1e-9]
    except GEOSException:
        return "cut", []
    return "cut", []


def _zone(covers: list) -> Any:
    """What the blocks in `covers` hide, as one shape. Each cover lies 0.3 mm inside its own
    stitching (joins._cover), so two blocks whose stitching meets leave a 0.6 mm slit between their
    covers; merged, the union is closed by CLOSE_MM, which bridges that slit (stitching up to about
    0.02 mm apart) and nothing wider."""
    found = [c for c in covers if c is not None]
    if not found:
        return None
    return _closed(found, len(found) == 1)


def _closed(found: list, alone: bool) -> Any:
    """`found` merged and closed by CLOSE_MM, as _zone does; `alone`: the whole set it was taken
    from is one cover, which _zone leaves as it is."""
    if not found:
        return None
    try:
        if alone:
            return found[0]
        return shapely.union_all(found).buffer(CLOSE_MM, quad_segs=2).buffer(-CLOSE_MM, quad_segs=2)
    except GEOSException:
        return None


# The closing only ever merges covers lying near each other, so a join's zone is made from the
# covers near its ends and from whatever those are linked to (the zone near a join is then the same
# shape as the whole closed zone there, at a fraction of the cost). A closed cover lies within
# CLOSE_MM of its cover, and the zone closes the later blocks' closed covers once more, so covers
# 4 x CLOSE_MM apart (plus a margin) can end up merged, and the zone lies within 2 x CLOSE_MM of
# its covers: a join's end can reach it from covers REACH_MM + 2 x CLOSE_MM away.
LINK_MM = 4 * CLOSE_MM + 0.05
NEAR_MM = REACH_MM + 2 * CLOSE_MM + 0.05


def _linked(covers: list) -> list[int]:
    """For each cover, the smallest index of the covers linked to it (through others) within LINK_MM:
    a group that does not depend on the order the geometry library finds the pairs in."""
    group = list(range(len(covers)))

    def root(k: int) -> int:
        while group[k] != k:
            group[k] = group[group[k]]
            k = group[k]
        return k

    idx = [k for k, c in enumerate(covers) if c is not None]
    if len(idx) > 1:
        geoms = [covers[k] for k in idx]
        pairs = shapely.STRtree(geoms).query(geoms, predicate="dwithin", distance=LINK_MM)
        for i, j in zip(pairs[0].tolist(), pairs[1].tolist()):
            ra, rb = root(idx[i]), root(idx[j])
            if ra != rb:
                group[max(ra, rb)] = min(ra, rb)
    return [root(k) for k in range(len(covers))]


def _route_recs(route: list[Pt]) -> list[list]:
    """Running stitches along a join (in 0.1 mm records), belonging to no item."""
    if len(route) < 2:
        return []
    if len(route) == 2 and math.dist(*route) <= REACH_MM:
        pts = [route[1]]
    else:
        pts = [(x, y) for x, y, _ in dz._route_stitches(route[0], route)]
    return [[x * 10, y * 10, pe.STITCH, -1, -1] for x, y in pts]


def _remade(it: dict[str, Any], idx: int, fabric: str | None, jt_mm: float | None) -> Block | None:
    """A member's block made again (its lock left out where the thread runs on), as render makes it."""
    try:
        blocks = _object_blocks(it, idx, fabric)[0]
    except LayoutError:
        return None
    blocks = [blk for blk in _apply_ops(blocks, it.get("ops") or [], jt_mm, [], generated=True) if blk.recs]
    return blocks[0] if len(blocks) == 1 else None


class BranchBlock(Block):
    """The block of a branch sewn as one path, with what the app shows about it (BranchInfo)."""

    info: dict[str, Any]


def _branch_block(thread, recs, sources, original, info) -> BranchBlock:
    blk = BranchBlock(thread, recs, sources, original, True)
    blk.info = info
    return blk


def apply(blocks: list[Block], layout: dict[str, Any], warnings: list[dict]) -> list[Block]:
    """The "after_items" pass: each planned path's member blocks become one block."""
    found, notes = plans(layout)
    warnings += notes
    if not found:
        return blocks
    items = layout.get("items") or []
    fabric = layout.get("fabric")
    jt_mm = _mm(layout.get("jumps_to_trims")) if layout.get("jumps_to_trims") is not None else None
    for plan in found:
        where = {blk.sources[0][0]: n for n, blk in enumerate(blocks)
                 if len(blk.sources) == 1 and blk.sources[0][0] in plan.run and not isinstance(blk, BranchBlock)}
        order = [i for i in plan.order if i in where]
        if len(order) < 2:
            continue
        spots = sorted(where[i] for i in order)
        if spots != list(range(spots[0], spots[0] + len(spots))):
            continue  # not sewn together after all (a pass moved something): leave them as they are
        seq = [blocks[where[i]] for i in order]
        later = blocks[spots[-1] + 1:]
        joins, routes = _joins(seq, later)
        # Where the thread runs on, the locks at that join are left out.
        for pos, i in enumerate(order):
            off_in = pos > 0 and joins[pos - 1] == "on"
            off_out = pos + 1 < len(order) and joins[pos] == "on"
            if not (off_in or off_out):
                continue
            v = plan.prepared.get(i, items[i])
            params = dict(v.get("params") or {})
            if off_in:
                params["tie_in"] = False
            if off_out:
                params["tie_off"] = False
            again = _remade({**v, "params": params}, i, fabric, jt_mm)
            if again is not None:
                seq[pos] = Block(seq[pos].thread, again.recs, seq[pos].sources, seq[pos].original, True)
        recs: list[list] = list(seq[0].recs)
        hidden = 0.0
        cuts = 0
        for pos in range(1, len(seq)):
            sa, sb = _stitches(Block({}, recs))[-1], _stitches(seq[pos])[0]
            if joins[pos - 1] == "on":
                route = routes[pos - 1]
                recs += _route_recs(route)
                hidden += sum(math.dist(p, q) for p, q in zip(route, route[1:]))
            else:
                d = math.hypot(sb[0] - sa[0], sb[1] - sa[1]) / 10
                names = (_name(items[order[pos - 1]], order[pos - 1]), _name(items[order[pos]], order[pos]))
                if d > dz.TRIM_TRAVEL_MM:
                    recs.append([sa[0], sa[1], pe.TRIM, sa[3], -1])
                    cuts += 1
                recs.append([sb[0], sb[1], pe.JUMP, sb[3], -1])
                note = CUT_NOTE if d > dz.TRIM_TRAVEL_MM else JUMP_NOTE
                warnings.append({"level": "warning", "code": f"branch_cut_{order[0]}_{pos}",
                                 "message": note.format(a=names[0], b=names[1])})
            recs += seq[pos].recs
        pts = _stitches(Block({}, recs))
        info = {"id": plan.branch, "items": [str(items[i].get("id", i)) for i in order],
                "start": [round(pts[0][0] / 10, 3), round(pts[0][1] / 10, 3)],
                "end": [round(pts[-1][0] / 10, 3), round(pts[-1][1] / 10, 3)],
                "hidden_mm": round(hidden, 2), "cuts": cuts}
        merged = _branch_block(seq[0].thread, recs, [s for blk in seq for s in blk.sources], seq[0].original, info)
        blocks = blocks[:spots[0]] + [merged] + blocks[spots[-1] + 1:]
    return blocks


def _joins(seq: list[Block], later: list[Block]) -> tuple[list[str], list[list[Pt]]]:
    """For each join: "on" or "cut", and its route (mm). Cached by the stitches involved."""
    key = hashlib.sha1(repr(([_stitch_key(b) for b in seq], [_stitch_key(b) for b in later])).encode()).digest()
    hit = _join_cache.get(key)
    if hit is not None:
        return hit
    covers = [_cover(b) for b in seq] + [_cover(b) for b in later]
    n = len(seq)
    idx = [k for k, c in enumerate(covers) if c is not None]
    later_count = sum(1 for k in idx if k >= n)
    state: dict[str, Any] = {}  # the groups and the tree, made only if some join needs a zone

    def zone_of(pos: int, a: Pt, b: Pt) -> Any:
        """_zone([*covers[pos:n], _zone(covers[n:])]) near a and b: the same pieces there."""
        if not state:
            state["group"] = _linked(covers)
            state["tree"] = shapely.STRtree([covers[k] for k in idx])
        group, tree = state["group"], state["tree"]
        near = {group[idx[j]] for p in (a, b)
                for j in tree.query(SPoint(p), predicate="dwithin", distance=NEAR_MM).tolist()}
        keep = [k for k in idx if group[k] in near]  # in the covers' own order, as _zone takes them
        inner = _closed([covers[k] for k in keep if k >= n], later_count == 1)
        found = [covers[k] for k in keep if pos <= k < n] + ([inner] if inner is not None else [])
        total = sum(1 for k in idx if pos <= k < n) + (1 if later_count else 0)
        return _closed(found, total == 1)

    kinds: list[str] = []
    routes: list[list[Pt]] = []
    for pos in range(1, len(seq)):
        sa, sb = _stitches(seq[pos - 1])[-1], _stitches(seq[pos])[0]
        a, b = (sa[0] / 10, sa[1] / 10), (sb[0] / 10, sb[1] / 10)
        kind, route = _join(a, b, lambda pos=pos, a=a, b=b: zone_of(pos, a, b))
        kinds.append(kind)
        routes.append(route)
    return _remember(_join_cache, key, (kinds, routes))


def _stitch_key(blk: Block) -> str:
    return hashlib.sha1(str([(round(r[0], 3), round(r[1], 3), r[2]) for r in blk.recs]).encode()).hexdigest()


def infos(blocks: list[Block]) -> list[dict[str, Any]]:
    """What the app shows about each branch (BranchInfo), in sewing order."""
    return [blk.info for blk in blocks if isinstance(blk, BranchBlock)]


# ---------------------------------------------------------------- the Branch command


def branch_plan(layout: dict[str, Any], ids: list) -> dict[str, Any]:
    """Can the shapes `ids` be sewn as one path? {ok, reason, order}: `order` is every item's id,
    the shapes moved next to each other at the place of the first (what the app applies)."""
    items = list(layout.get("items") or [])
    wanted = {str(i) for i in ids or []}
    chosen = [k for k, it in enumerate(items) if str(it.get("id", k)) in wanted]

    def no(reason: str) -> dict[str, Any]:
        return {"ok": False, "reason": reason, "order": []}

    for k in chosen:
        kind = items[k].get("kind", "file")
        what = {"text": "lettering", "applique": "an applique", "file": "a stitch file"}.get(kind)
        if what is None and kind not in BRANCH_KINDS:
            what = "not a drawn shape"
        if what:
            return no(f"{_name(items[k], k)} is {what}, which can't be in a branch. Only drawn lines, satins and "
                      "fills can: take it out of the selection.")
    if len(chosen) < 2:
        return no("Select two or more drawn shapes (lines, satins or fills) to sew as one path.")
    for k in chosen:
        if _is_blend(items[k]):
            return no(f"{_name(items[k], k)} sews in more than one thread (a blend), and a branch sews in one. "
                      "Take it out of the selection, or sew it in one thread.")
    threads = {_thread_of(items[k]) for k in chosen}
    if len(threads) > 1:
        other = next(k for k in chosen if _thread_of(items[k]) != _thread_of(items[chosen[0]]))
        return no(f"These shapes are sewn in more than one thread ({_name(items[chosen[0]], chosen[0])} and "
                  f"{_name(items[other], other)} differ). A branch sews in one thread: give them the same thread first.")
    # The members move up to the first one; whatever was sewn between them goes after them. That
    # can't put a member on top of something it used to be under.
    between = [k for k in range(chosen[0], chosen[-1]) if k not in chosen]
    if between:
        from .render import render  # (render imports this module)

        r = render(layout)
        own: dict[int, list] = {}
        for (x, y, c), item in zip(r.pattern.stitches, r.item_of):
            if item >= 0:
                own.setdefault(item, []).append([x, y, c & pe.COMMAND_MASK, item, -1])
        blk = {k: Block({}, own.get(k, [])) for k in [*between, *chosen]}
        for k in between:
            for m in chosen:
                if m > k and _blocks_overlap(blk[k], blk[m]):
                    return no(f"{_name(items[k], k)} is sewn between these shapes and overlaps {_name(items[m], m)}: "
                              "move it first.")
    rest = [k for k in range(len(items)) if k not in chosen]
    head = [k for k in rest if k < chosen[0]]
    order = head + chosen + [k for k in rest if k > chosen[0]]
    return {"ok": True, "reason": "", "order": [str(items[k].get("id", k)) for k in order]}


def forget() -> None:
    """Empty what is kept (for tests)."""
    _plan_cache.clear()
    _join_cache.clear()


passes.register_pass("after_items", "branch", apply)
