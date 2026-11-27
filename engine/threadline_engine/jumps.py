"""Optimize jumps: in each run of pieces sewn in the same thread, choose where every piece starts
and ends so the jumps between them are as short as possible, without changing the sewing order
(that decides what lies on top).

For each drawn piece, the ways it could be sewn are tried:
- a line, satin ribbon or two-sided satin: either way round;
- a closed line or ribbon (a border): starting at the point nearest the piece before, or nearest the
  piece after (it ends where it starts);
- a fill: starting at the edge nearest the piece before, or nearest the piece after, with its rows
  sewn either way.
The way chosen is the one whose start is nearest where the piece before ended and whose end is
nearest the piece after (like a magnet between the two). Lettering's first letter starts at its
edge nearest where the piece before ended. Stitch files and appliques stay as they are, but count
as neighbours, and so do shapes in a branch (the branch chooses their starts and ends). The choices are kept on the pieces (their points' order, or a
fill's start point and direction), so drawing the design afterwards costs nothing extra.
"""

from __future__ import annotations

import copy
import math
from typing import Any

import pyembroidery as pe
from shapely.geometry import LineString, Point as SPoint, Polygon

from . import layout as L
from .digitize import stitches as dz
from .digitize.paths import flatten

Pt = tuple[float, float]


def _unturn(t: Any, d: Pt) -> Pt:
    """Undo a transform's turn, resize and mirror (about the origin) on an offset `d`."""
    a = math.radians(-t.rotate)
    rx, ry = d[0] * math.cos(a) - d[1] * math.sin(a), d[0] * math.sin(a) + d[1] * math.cos(a)
    fx = -1.0 if t.flip_x else 1.0
    fy = -1.0 if t.flip_y else 1.0
    return (round(rx / (t.scale_x * fx), 3), round(ry / (t.scale_y * fy), 3))


def _to_local(it: dict[str, Any], p: Pt) -> Pt:
    """A point as shown (mm) in the item's own coordinates (its transform undone)."""
    t = L.Transform.from_dict(it.get("transform"))
    if t.is_identity():
        return p
    x0, y0, x1, y1 = dz.bounds(dz.geometry_points(it))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    a = math.radians(-t.rotate)
    dx, dy = p[0] - cx - t.x, p[1] - cy - t.y
    rx, ry = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
    fx = -1.0 if t.flip_x else 1.0
    fy = -1.0 if t.flip_y else 1.0
    return (rx / (t.scale_x * fx) + cx, ry / (t.scale_y * fy) + cy)


class EndsError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR: shown to the user as is


def set_end(it: dict[str, Any], which: str, at: list[float]) -> dict[str, Any]:
    """Where a drawn piece starts ("start", the green dot) or ends ("end", the red dot), dragged to
    `at` (mm, as shown). Returns the piece changed to suit:
    - a fill starts at the edge nearest `at`, and its rows end as near `at` as they can;
    - a closed line or ribbon (a border) starts and ends at its point nearest `at`;
    - an open line, ribbon or satin column is turned round if `at` is nearer its other end.
    """
    if which not in ("start", "end"):
        raise EndsError("Choose the start or the end")
    p = (float(at[0]), float(at[1]))
    kind = it.get("kind")
    g = it.get("geometry") or {}
    v = copy.deepcopy(it)
    if kind == "fill":
        params = dict(v.get("params") or {})
        lx, ly = _to_local(it, p)
        params["start_mm" if which == "start" else "end_mm"] = [round(lx, 3), round(ly, 3)]
        if which == "end":
            params.pop("reverse", None)  # the end point decides which way the rows go
        v["params"] = params
        return v
    if kind == "satin" and not g.get("closed"):
        # A satin (ribbon or column) starts and stops anywhere along it.
        lx, ly = _to_local(it, p)
        v["params"] = {**(v.get("params") or {}), ("start_mm" if which == "start" else "end_mm"): [round(lx, 3), round(ly, 3)]}
        return v
    if kind in ("run", "satin") and g.get("nodes"):
        nodes = g["nodes"]
        world = _world_points(it, "nodes")
        if len(world) < 2:
            raise EndsError("This line is too short to choose where it starts")
        if g.get("closed"):
            lx, ly = _to_local(it, p)
            v["params"] = {**(v.get("params") or {}), "start_mm": [round(lx, 3), round(ly, 3)]}
            return v
        here, other = (world[0], world[-1]) if which == "start" else (world[-1], world[0])
        if math.dist(p, other) < math.dist(p, here):
            v["geometry"] = {**g, "nodes": _reversed_path(nodes)}
        return v
    if kind == "satin" and g.get("rail_a") and g.get("rail_b"):
        a, b = _world_points(it, "rail_a"), _world_points(it, "rail_b")
        first = ((a[0][0] + b[0][0]) / 2, (a[0][1] + b[0][1]) / 2)
        last = ((a[-1][0] + b[-1][0]) / 2, (a[-1][1] + b[-1][1]) / 2)
        here, other = (first, last) if which == "start" else (last, first)
        if math.dist(p, other) < math.dist(p, here):
            v["geometry"] = {**g, "rail_a": _reversed_path(g["rail_a"]), "rail_b": _reversed_path(g["rail_b"])}
        return v
    raise EndsError("Only drawn lines, satins and fills can have their start and end moved")


def _thread_key(it: dict[str, Any]) -> tuple:
    t = {**(it.get("thread") or {}), **((it.get("threads") or [None])[0] or {})}
    return (str(t.get("color", "")).lower(), t.get("brand", ""), t.get("catalog", ""))


def _reversed_path(nodes: list, closed: bool = False) -> list:
    """A path's points the other way round (a point's kind belongs to the stretch coming into it)."""
    n = len(nodes)
    out = []
    for i in range(n):
        j = n - 1 - i
        kind = nodes[(j + 1) % n][2] if closed else (nodes[j + 1][2] if j + 1 < n else nodes[j][2])
        out.append([nodes[j][0], nodes[j][1], kind])
    return out


def _world_points(it: dict[str, Any], key: str) -> list[Pt]:
    """An item's points for `key` as shown (its transform applied)."""
    t = L.Transform.from_dict(it.get("transform"))
    obj = it
    if not t.is_identity():
        pts = dz.geometry_points(it)
        x0, y0, x1, y1 = dz.bounds(pts)
        obj = dz.transform_geometry(it, t, ((x0 + x1) / 2, (y0 + y1) / 2))
    return [(float(n[0]), float(n[1])) for n in (obj.get("geometry") or {}).get(key) or []]


def _nearest_index(pts: list[Pt], p: Pt) -> int:
    return min(range(len(pts)), key=lambda k: math.dist(pts[k], p))


def _variants(it: dict[str, Any], before: Pt | None, after_shape: Any) -> list[dict[str, Any]]:
    """The ways a drawn piece could be sewn (copies of it), the way it is now first."""
    kind = it.get("kind")
    g = it.get("geometry") or {}
    out = [it]

    def with_geometry(**patch: Any) -> dict[str, Any]:
        v = copy.deepcopy(it)
        v["geometry"] = {**g, **patch}
        params = dict(v.get("params") or {})
        params.pop("start_mm", None)
        params.pop("end_mm", None)
        v["params"] = params
        return v

    # Start where the piece before ended, or at this piece's point nearest the piece after.
    own_pts = _world_points(it, "outline" if kind == "fill" else "nodes")
    targets: list[Pt] = [before] if before else []
    if after_shape is not None and own_pts:
        targets.append(min(own_pts, key=lambda q: after_shape.distance(SPoint(q))))

    if kind in ("run", "satin") and g.get("nodes"):
        nodes = g["nodes"]
        if g.get("closed"):
            world = _world_points(it, "nodes")
            for t in targets:
                k = _nearest_index(world, t)
                if k:
                    out.append(with_geometry(nodes=nodes[k:] + nodes[:k]))
        else:
            out.append(with_geometry(nodes=_reversed_path(nodes)))
    elif kind == "satin" and g.get("rail_a"):
        out.append(with_geometry(rail_a=_reversed_path(g["rail_a"]), rail_b=_reversed_path(g["rail_b"])))
    elif kind == "fill":
        world = _world_points(it, "outline")
        local = g.get("outline") or []
        for t in targets:
            k = _nearest_index(world, t)
            for rev in (False, True):
                v = copy.deepcopy(it)
                v["params"] = {**(it.get("params") or {}), "start_mm": [float(local[k][0]), float(local[k][1])], "reverse": rev}
                v["params"].pop("end_mm", None)  # the rows' direction chooses the end here
                out.append(v)
        v = copy.deepcopy(it)
        v["params"] = {**(it.get("params") or {}), "reverse": not (it.get("params") or {}).get("reverse", False)}
        v["params"].pop("end_mm", None)
        out.append(v)
    return out


def _shape_of(it: dict[str, Any]) -> Any:
    """What a piece covers, to measure how near another piece ends to it."""
    kind = it.get("kind")
    try:
        if kind in ("fill", "applique"):
            pts = _world_points(it, "outline")
            return Polygon(pts).buffer(0) if len(pts) >= 3 else None
        if kind in ("run", "satin") and (it.get("geometry") or {}).get("nodes"):
            pts = _world_points(it, "nodes")
            poly, _ = flatten([[x, y, "s"] for x, y in pts], bool((it.get("geometry") or {}).get("closed")))
            return LineString(poly) if len(poly) >= 2 else None
        if kind == "satin":
            a = _world_points(it, "rail_a")
            b = _world_points(it, "rail_b")
            return Polygon(a + b[::-1]).buffer(0) if len(a) + len(b) >= 3 else None
    except (ValueError, TypeError):
        return None
    return None


def _ends(it: dict[str, Any], idx: int, fabric: str | None) -> tuple[Pt, Pt] | None:
    """Where a drawn piece's stitching starts and ends (mm, as shown)."""
    try:
        blocks, _, _ = L._object_blocks(it, idx, fabric)
    except L.LayoutError:
        return None
    pts = [(r[0] / 10, r[1] / 10) for b in blocks for r in b.recs if r[2] == pe.STITCH]
    return (pts[0], pts[-1]) if pts else None


def _first_letter_moved(it: dict[str, Any], idx: int, fabric: str | None, before: Pt,
                        now: tuple[Pt, Pt]) -> tuple[dict[str, Any], tuple[Pt, Pt]] | None:
    """Lettering whose first letter starts at its edge nearest `before` (where the piece before
    ended), as a chosen start in the text's own frame (letters["0"].start_mm, as its green dot
    keeps it), with its new ends; None if that doesn't make the jump shorter."""
    t = L.Transform.from_dict(it.get("transform"))
    local = _unturn(t, (before[0] - t.x, before[1] - t.y))
    letters = dict(it.get("letters") or {})
    letters["0"] = {**(letters.get("0") or {}), "start_mm": [local[0], local[1]]}
    v = {**it, "letters": letters}
    try:
        blocks = L._text_block(v, idx, fabric)[0]
    except (L.LayoutError, dz.DigitizeError):
        return None
    pts = [(r[0] / 10, r[1] / 10) for b in blocks for r in b.recs if r[2] == pe.STITCH]
    if not pts or math.dist(before, pts[0]) >= math.dist(before, now[0]) - 0.05:
        return None
    return v, (pts[0], pts[-1])


def optimize_jumps(layout: dict[str, Any]) -> dict[str, Any]:
    """Choose each drawn piece's start and end so jumps within a thread are shortest.
    Returns {"changes": {id: {"geometry": …}, {"params": …} or, for lettering, {"letters": …}},
    "before_mm", "after_mm"}. Shapes in a branch are left to it."""
    items = list(layout.get("items") or [])
    fabric = layout.get("fabric")
    r = L.render(layout)
    # Where every item (stitch files and lettering too) starts and ends now, from the render.
    own: dict[int, list[Pt]] = {}
    for (x, y, k), it, src in zip(r.pattern.stitches, r.item_of, r.src_of):
        if it >= 0 and src >= 0 and k & L.M == pe.STITCH:
            own.setdefault(it, []).append((x / 10, y / 10))
    ends_now = {i: (pts[0], pts[-1]) for i, pts in own.items()}
    keys = [_thread_key(it) for it in items]

    def jumps(ends: dict[int, tuple[Pt, Pt]]) -> float:
        total = 0.0
        for i in range(1, len(items)):
            if keys[i] == keys[i - 1] and i in ends and i - 1 in ends:
                total += math.dist(ends[i - 1][1], ends[i][0])
        return total

    chosen = dict(ends_now)
    changes: dict[str, dict[str, Any]] = {}
    # Shapes sewn in a branch start and end where their branch needs them (layout/branch.py).
    from .layout.branch import plans

    in_branch = {i for p in plans(layout)[0] for i in p.run}
    for i, it in enumerate(items):
        if it.get("kind") == "text" and i in chosen and i > 0 and keys[i - 1] == keys[i] and i - 1 in chosen:
            moved = _first_letter_moved(it, i, fabric, chosen[i - 1][1], chosen[i])
            if moved is not None:
                items[i], chosen[i] = moved
                changes[str(it.get("id", i))] = {"letters": moved[0]["letters"]}
            continue
        if it.get("kind") not in ("run", "satin", "fill") or i not in chosen or i in in_branch:
            continue
        before = chosen[i - 1][1] if i > 0 and keys[i - 1] == keys[i] and i - 1 in chosen else None
        nxt = items[i + 1] if i + 1 < len(items) and keys[i + 1] == keys[i] else None
        after_shape = _shape_of(nxt) if nxt is not None else None
        after_start = ends_now.get(i + 1, (None, None))[0] if nxt is not None and nxt.get("kind") not in ("run", "satin", "fill") else None
        if before is None and after_shape is None and after_start is None:
            continue

        def cost(e: tuple[Pt, Pt]) -> float:
            c = math.dist(before, e[0]) if before else 0.0
            if after_start is not None:
                c += math.dist(e[1], after_start)
            elif after_shape is not None:
                c += after_shape.distance(SPoint(e[1]))
            return c

        best, best_ends, best_cost = it, chosen[i], cost(chosen[i])
        for v in _variants(it, before, after_shape)[1:]:
            e = _ends(v, i, fabric)
            if e is None:
                continue
            c = cost(e)
            if c < best_cost - 0.05:
                best, best_ends, best_cost = v, e, c
        if best is not it:
            items[i] = best
            chosen[i] = best_ends
            changes[str(it.get("id", i))] = (
                {"params": best["params"]} if best.get("params") != it.get("params") else {"geometry": best["geometry"]}
            )
    return {"changes": changes, "before_mm": round(jumps(ends_now), 1), "after_mm": round(jumps(chosen), 1)}


__all__ = ["optimize_jumps"]
