"""Shape operations: outlines & offsets around anything, the knife (cut a shape in two), and
merging shapes into one. Shapes go in and come out as pen points ([x, y, kind] in mm).

- offset: a ring (or rings) a set distance outside whatever is selected, following its
  stitches, so it works around lettering and stitch files as well as drawn shapes.
- split: cut a fill (or applique) along a line into two or more fills; cut a line or satin
  ribbon where the knife crosses it.
- merge: join touching or overlapping fills into one.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np
import pyembroidery as pe
import shapely
from shapely.geometry import LineString, Point as SPoint, Polygon
from shapely.ops import split as shapely_split, unary_union

from . import layout as L
from .digitize import stitches as dz
from .digitize.paths import Point, flatten

CORNER_DEG = 40
CHUNK = 40  # stitches per piece when thickening the stitches for an outline


class ShapeError(Exception):
    rpc_code = -32000


def _turns(pts: np.ndarray, k: int, closed: bool) -> np.ndarray:
    n = len(pts)
    idx = np.arange(n)
    if closed:
        a, b = pts[(idx - k) % n], pts[(idx + k) % n]
    else:
        a, b = pts[np.clip(idx - k, 0, n - 1)], pts[np.clip(idx + k, 0, n - 1)]
    v1, v2 = pts - a, b - pts
    ang = np.abs(np.arctan2(v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0], (v1 * v2).sum(axis=1)))
    if not closed:
        ang[:k] = 0
        ang[n - k :] = 0
    return ang


def to_nodes(points: Sequence[Point], spacing: float = 3.0, closed: bool = True) -> list[list[Any]]:
    """Pen points along a dense line (mm): about `spacing` apart, sharp corners kept as corners
    ("c"), the rest smooth curve points ("s")."""
    pts = [tuple(p) for p in points]
    if closed and len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 2:
        return []
    ring = pts + [pts[0]] if closed else pts
    dense = np.array(dz.resample(ring, 0.25), dtype=float)
    if closed:
        dense = dense[:-1]
    n = len(dense)
    if n < 3:
        return [[round(float(x), 2), round(float(y), 2), "c"] for x, y in dense]
    k = max(2, min(4, n // 4))
    turn, wide = _turns(dense, k, closed), _turns(dense, min(2 * k, max(1, n // 3)), closed)
    sharp = (turn > math.radians(CORNER_DEG)) & (turn > 0.75 * wide)
    corners: list[int] = []
    shift = int(np.argmin(sharp)) if closed and sharp.any() and not sharp.all() else 0
    order = np.roll(np.arange(n), -shift)
    i = 0
    while i < n:
        if sharp[order[i]]:
            j = i
            while j < n and sharp[order[j]]:
                j += 1
            run = order[i:j]
            corners.append(int(run[int(np.argmax(turn[run]))]))
            i = j
        else:
            i += 1
    corners.sort()
    seg = np.hypot(*np.diff(np.vstack([dense, dense[:1]]) if closed else dense, axis=0).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    picks: list[tuple[float, str]] = []
    if closed:
        stops = corners or [0]
        for a, b in zip(stops, stops[1:] + [stops[0]]):
            s0, s1 = cum[a], cum[b] if b > a else cum[b] + total
            m = max(1, round((s1 - s0) / spacing))
            picks.append((s0, "c" if corners else "s"))
            picks += [(s0 + (s1 - s0) * t / m, "s") for t in range(1, m)]
        if len(picks) < 3:
            picks = [(total * t / 3, "s") for t in range(3)]
        loop = np.vstack([dense, dense[:1]])
    else:
        stops = [0, *[c for c in corners if 0 < c < n - 1], n - 1]
        for a, b in zip(stops, stops[1:]):
            m = max(1, round((cum[b] - cum[a]) / spacing))
            picks.append((cum[a], "c"))
            picks += [(cum[a] + (cum[b] - cum[a]) * t / m, "s") for t in range(1, m)]
        picks.append((cum[n - 1], "c"))
        loop = dense
    sv = np.array([p[0] % total if closed else p[0] for p in picks])
    xs = np.interp(sv, cum[: len(loop)], loop[:, 0])
    ys = np.interp(sv, cum[: len(loop)], loop[:, 1])
    return [[round(float(x), 2), round(float(y), 2), kind] for x, y, (_, kind) in zip(xs, ys, picks)]


def _poly_nodes(p: Polygon, spacing: float) -> dict[str, Any]:
    out: dict[str, Any] = {"outline": to_nodes(list(p.exterior.coords), spacing)}
    # Holes as small as a fill keeps (a knife or merge used to drop holes under 2 mm² silently).
    holes = [to_nodes(list(r.coords), spacing) for r in p.interiors if Polygon(r).area >= dz.MIN_PART_MM2]
    if holes:
        out["holes"] = holes
    return out


def _parts(geom) -> list[Polygon]:
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon) and not g.is_empty]


# ---------------------------------------------------------------- outlines & offsets


def offset(layout: dict[str, Any], ids: list[str], distance_mm: float, spacing: float = 3.0,
           holes: bool = False) -> dict[str, Any]:
    """Rings `distance_mm` outside the stitches of the items `ids` (0: right on their edge).
    `holes`: also ring the inside of holes (the middle of an O). Returns {"rings": [nodes...]}."""
    if not -10 <= distance_mm <= 30:
        raise ShapeError("The distance must be between -10 and 30 mm")
    # Without "Fewer jumps & trims": its hidden travel stitches belong to the next shape and
    # would give the outline a spur reaching back to the previous one.
    r = L.render({**layout, "travel_under": False})
    want = {i for i, it in enumerate(layout.get("items") or []) if it.get("id") in set(ids)}
    if not want:
        raise ShapeError("Select something to put an outline around")
    lines = []
    run: list[tuple[float, float]] = []
    for (x, y, c), item in zip(r.pattern.stitches, r.item_of):
        if item in want and c & L.M == pe.STITCH:
            run.append((x / 10, y / 10))
            continue
        if len(run) > 1:
            lines.append(LineString(run))
        run = []
    if len(run) > 1:
        lines.append(LineString(run))
    if not lines:
        raise ShapeError("There are no stitches there to go around")
    # The area the stitches cover (closed up so letters and gaps become one shape), then grown.
    thick = 0.6  # each stitch is thickened this much so neighbouring rows join up
    # Long runs are cut into short pieces and thickened all at once: thickening one long line that
    # crosses itself many times (a dense satin or fill) is very slow; short pieces are not.
    pieces = []
    for ln in lines:
        c = np.asarray(ln.simplify(0.1).coords)
        for i in range(0, max(1, len(c) - 1), CHUNK):
            if len(c[i : i + CHUNK + 1]) > 1:
                pieces.append(c[i : i + CHUNK + 1])
    thickened = shapely.buffer(np.array([LineString(c) for c in pieces], dtype=object), thick, quad_segs=3)
    stitched = unary_union(thickened)
    area = stitched.buffer(1.5).buffer(-1.5)
    # Measure the distance from the stitches themselves, not from the thickened area.
    grown = area.buffer(distance_mm - thick, quad_segs=8)
    rings = []
    for p in sorted(_parts(grown), key=lambda g: -g.area):
        if p.area < 1.0:
            continue
        rings.append(to_nodes(list(p.exterior.coords), spacing))
    if holes:
        # Holes come from the stitches before the closing-up above, which filled in any hole
        # narrower than about 4 mm (the middle of a small O).
        for part in _parts(stitched):
            for h in part.interiors:
                hole = Polygon(h)
                if hole.area < 2.0:
                    continue  # gaps between rows, not a hole
                inner = hole.buffer(-(distance_mm - thick), quad_segs=8)
                rings += [to_nodes(list(q.exterior.coords), spacing) for q in _parts(inner) if q.area >= 1.0]
    return {"rings": [rg for rg in rings if len(rg) >= 3]}


# ---------------------------------------------------------------- knife & merge


def _world(obj: dict[str, Any]) -> dict[str, Any]:
    """The shape as it's shown: its move, turn, resize and mirror applied to its points, the same
    way the layout does it, so the knife cuts where it was drawn and merges join what's on screen.
    The results come back with no transform of their own."""
    t = L.Transform.from_dict(obj.get("transform"))
    pts = dz.geometry_points(obj)
    if t.is_identity() or not pts:
        return obj
    x0, y0, x1, y1 = dz.bounds(pts)
    return dz.transform_geometry(obj, t, ((x0 + x1) / 2, (y0 + y1) / 2))


def _fill_parts(obj: dict[str, Any]) -> list[Polygon]:
    """Every piece of a fill (an outline that crosses itself has several), biggest first."""
    g = obj.get("geometry") or {}
    return dz.fill_parts(g.get("outline") or [], g.get("holes") or [])


def _path(obj: dict[str, Any]) -> list[Point]:
    g = obj.get("geometry") or {}
    poly, _ = flatten(g.get("nodes") or [], bool(g.get("closed")))
    if g.get("closed") and poly:
        poly = poly + [poly[0]]
    return poly


def _carve_for(piece: Polygon, shapes: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """The carved lines of `shapes` (as shown) that cross a piece of fill, as its geometry keeps
    them, so a cut, trimmed or merged fill keeps its grooves."""
    kept = []
    for shape in shapes:
        for line in (shape.get("geometry") or {}).get("carve") or []:
            pts, _ = flatten(line, False)
            if len(pts) >= 2 and LineString(pts).intersects(piece):
                kept.append(line)
    return {"carve": kept} if kept else {}


def split(obj: dict[str, Any], a: Point, b: Point, spacing: float = 3.0) -> dict[str, Any]:
    """Cut a shape along the line from a to b (extended across the whole shape).
    Returns {"geometries": [geometry, ...]} in the shape's own kind, biggest first."""
    obj = _world(obj)
    kind = obj.get("kind")
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 0.5:
        raise ShapeError("Draw the cut a little longer")
    ux, uy = dx / length, dy / length
    far = 2000.0
    knife = LineString([(a[0] - ux * far, a[1] - uy * far), (b[0] + ux * far, b[1] + uy * far)])
    if kind in ("fill", "applique"):
        parts, cut = [], False
        for poly in _fill_parts(obj):
            pieces = [p for p in _parts(shapely_split(poly, knife)) if p.area >= 1.0]
            cut = cut or len(pieces) > 1
            parts += pieces
        if not cut:
            raise ShapeError("The cut doesn't cross the shape")
        carved = [obj] if kind == "fill" else []
        return {"geometries": [{**_poly_nodes(p, spacing), **_carve_for(p, carved)}
                               for p in sorted(parts, key=lambda g: -g.area)]}
    if kind in ("run", "satin") and "nodes" in (obj.get("geometry") or {}):
        path = _path(obj)
        if len(path) < 2:
            raise ShapeError("This line is too short to cut")
        line = LineString(path)
        try:
            pieces = [g for g in getattr(shapely_split(line, knife), "geoms", []) if g.length >= 0.5]
        except (ValueError, shapely.errors.GEOSException):
            raise ShapeError("The cut runs along the line; draw it across the line") from None
        g = obj.get("geometry") or {}
        if g.get("closed") and len(pieces) > 2 and knife.distance(SPoint(path[0])) > 1e-6:
            # A closed line starts and ends at its first point, which isn't a cut: the pieces either
            # side of it are one piece (one cut across a loop gives two pieces, not three).
            pieces = [LineString([*pieces[-1].coords, *list(pieces[0].coords)[1:]]), *pieces[1:-1]]
        if len(pieces) < 2:
            raise ShapeError("The cut doesn't cross the line")
        out = []
        for piece in pieces:
            geo = {"nodes": to_nodes(list(piece.coords), spacing, closed=False)}
            if "width_mm" in g:
                geo["width_mm"] = g["width_mm"]
            out.append(geo)
        return {"geometries": out}
    raise ShapeError("The knife cuts fills, lines and satin ribbons")


def _cutter(obj: dict[str, Any]) -> Polygon | None:
    """The area a shape covers, to cut out of a fill: a fill's or applique's area, a closed line's
    inside, a satin's band."""
    obj = _world(obj)
    g = obj.get("geometry") or {}
    kind = obj.get("kind")
    if kind in ("fill", "applique"):
        return unary_union(_fill_parts(obj))
    if kind == "run" and g.get("closed"):
        pts, _ = flatten(g.get("nodes") or [], True)
        return Polygon(pts).buffer(0) if len(pts) >= 3 else None
    if kind == "satin" and g.get("nodes"):
        return LineString(_path(obj)).buffer(float(g.get("width_mm", 3.0)) / 2)
    if kind == "satin" and g.get("rail_a"):
        a, _ = flatten(g["rail_a"])
        b, _ = flatten(g["rail_b"])
        return Polygon(a + b[::-1]).buffer(0)
    return None


def cut_out(target: dict[str, Any], cutters: list[dict[str, Any]], spacing: float = 3.0) -> dict[str, Any]:
    """Cut the area of `cutters` (shapes placed over a fill) out of the fill `target`: a hole where
    a cutter is inside it, a bite where it overlaps the edge. Returns {"geometries": [...]} in the
    fill's kind, biggest first (a cut right across leaves several pieces)."""
    if target.get("kind") not in ("fill", "applique"):
        raise ShapeError("Select a fill (or applique) to cut out of, and the shapes to cut with")
    shown = _world(target)
    poly = unary_union(_fill_parts(shown))
    areas = [a for a in (_cutter(c) for c in cutters) if a is not None and not a.is_empty]
    if not areas:
        raise ShapeError("Select the shapes to cut out too: fills, closed lines or satins placed over the fill")
    cut = unary_union(areas)
    if not poly.intersects(cut) or poly.intersection(cut).area < 0.5:
        raise ShapeError("The shapes on top don't overlap the fill, so there's nothing to cut out")
    rest = poly.difference(cut)
    parts = [p for p in _parts(rest) if p.area >= 1.0]
    if not parts:
        raise ShapeError("That would cut away the whole fill")
    carved = [shown] if target.get("kind") == "fill" else []
    return {"geometries": [{**_poly_nodes(p, spacing), **_carve_for(p, carved)}
                           for p in sorted(parts, key=lambda g: -g.area)]}


def merge(objs: list[dict[str, Any]], spacing: float = 3.0) -> dict[str, Any]:
    """Join fills that touch or overlap into one fill. Returns {"geometry": ...}."""
    polys = []
    shown = []
    for o in objs:
        if o.get("kind") not in ("fill", "applique"):
            raise ShapeError("Only fills (and appliques) can be merged")
        shown.append(_world(o))
        polys += _fill_parts(shown[-1])
    if len(objs) < 2:
        raise ShapeError("Select two or more fills to merge")
    joined = unary_union([p.buffer(0.05) for p in polys]).buffer(-0.05)
    parts = _parts(joined)
    if len(parts) != 1:
        raise ShapeError("These shapes don't touch, so they can't become one shape. Move them together first.")
    if len(_parts(joined.buffer(-0.1))) > 1:
        raise ShapeError("These shapes only touch at a corner. Move them so they overlap a little first.")
    carved = [s for s in shown if s.get("kind") == "fill"]
    return {"geometry": {**_poly_nodes(parts[0], spacing), **_carve_for(parts[0], carved)}}


__all__ = ["ShapeError", "cut_out", "merge", "offset", "split", "to_nodes"]
