"""What a text sews besides its letters: a shadow before them, and a monogram's frame and an
outline after them (P5-D3 and P5-D2). All are made from the letters' shapes each time, so they
follow the text as it's edited."""

from __future__ import annotations

import json
from typing import Any

import shapely
from shapely import affinity
from shapely.geometry import LineString, LinearRing, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import linemerge, unary_union

from ..digitize import stitches as dz
from ..digitize.paths import Point, flatten
from ..digitize.patterns import polygons
from . import glyphs, ornaments

SHADOW_MM = 0.8  # how far a shadow moves right and down unless told otherwise
SHADOW_MAX_MM = 3.0
OUTLINE_GAP_MM = 1.0
OUTLINE_MAX_GAP_MM = 5.0
OUTLINE_WIDTH_MM = 1.5
OUTLINE_WIDTHS_MM = (1.0, 4.0)
MIN_PIECE_MM2 = 0.5  # smaller pieces of a shadow are left out
SLIVER_MM = 0.08  # shadow thinner than this (where edges line up) is left out
THREAD_REACH_MM = 0.2  # how far one line of stitching covers on each side
MIN_SHADOW_LINE_MM = 1.0
SOFTEN_MM = 0.3  # rounds an outline's tight inside corners, so a satin's stitches don't bunch there
OUTLINE_NODE_MM = 1.5  # the outline's points are about this far apart: enough for small round corners
LINE_STITCH_MM = 1.8
GRID_MM = 0.001  # shapes are rounded to this before anything is chosen from them, so every computer agrees

# What recent texts sewed besides their letters, as JSON, by their settings and letters. A shadow
# takes a moment to work out (choosing its fills' stitch angles), and every redraw asks again.
_cache: dict[str, str] = {}
_CACHE_MAX = 32


def build(spec: dict[str, Any], letters: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(before, after): extra shapes sewn before the letters (a shadow) and after them (a
    monogram's frame, then an outline).

    `spec` is what the letters were laid out from (lettering.TEXT_SPEC_KEYS; missing ones are
    None). `letters` are the letter parts as they will be sewn, single-letter changes included,
    in the text's own unturned frame (mm). Each extra is a shape like a letter part (kind,
    geometry, params) with what it is ("extra": "shadow", "outline" or "frame") and its
    "thread" (None: the text's)."""
    shadow, outline = _setting(spec, "shadow"), _setting(spec, "outline")
    ornament = _setting(spec, "ornament") if spec.get("monogram") else None
    if not (shadow or outline or ornament):
        return [], []
    key = json.dumps([shadow, outline, ornament, [(o.get("kind"), o.get("geometry")) for o in letters]], sort_keys=True)
    made = _cache.get(key)
    if made is None:
        made = json.dumps(_make(letters, shadow, outline, ornament))
        if len(_cache) >= _CACHE_MAX:
            _cache.pop(next(iter(_cache)))
        _cache[key] = made
    before, after = json.loads(made)  # fresh copies each time
    return before, after


def _make(letters: list[dict[str, Any]], shadow: dict[str, Any] | None, outline: dict[str, Any] | None,
          ornament: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    before: list[dict[str, Any]] = []
    after: list[dict[str, Any]] = []
    if ornament:
        after += ornaments.frame(_letter_points(letters), ornament)
    # Letters made of stitches (a stitched font) have no outlines to cast a shadow or draw a line round.
    if (shadow or outline) and not any(o.get("kind") == "stitches" for o in letters):
        areas, lines = _letter_shapes(letters)
        if areas or lines:
            if shadow:
                before = _shadow(areas, lines, shadow)
            if outline:
                after += _outline(areas, lines, outline)
    return before, after


def _setting(spec: dict[str, Any], key: str) -> dict[str, Any] | None:
    v = spec.get(key)
    return v if isinstance(v, dict) and v else None


def _mm(d: dict[str, Any], key: str, default: float, lo: float, hi: float) -> float:
    """A distance setting kept in range (0 is a real value; missing gives the default)."""
    return min(max(dz._finite(d, key, default), lo), hi)


def _thread(d: dict[str, Any]) -> dict[str, Any] | None:
    return dict(d["thread"]) if isinstance(d.get("thread"), dict) else None


# ---------------------------------------------------------------- the letters' shapes


def _part_shapes(part: dict[str, Any]) -> tuple[list[Polygon], list[LineString]]:
    """What one letter part covers: its areas, or for a line, the line itself."""
    kind, g = part.get("kind"), part.get("geometry") or {}
    if kind == "run":
        pts, _ = flatten(g.get("nodes") or [], bool(g.get("closed")))
        return ([], [LineString(pts)]) if len(pts) > 1 else ([], [])
    if kind == "satin" and g.get("nodes") is not None:  # a ribbon: a line and a width
        closed = bool(g.get("closed"))
        pts, _ = flatten(g["nodes"], closed)
        if len(pts) < 2:
            return [], []
        line = LinearRing(pts) if closed and len(pts) > 3 else LineString(pts)
        half = dz._finite(g, "width_mm", 3.0) / 2
        return polygons(line.buffer(half, cap_style="flat", join_style="round")), []
    if kind == "satin":  # a column: the strip between its two edges
        pairs = dz.satin_pairs(g.get("rail_a") or [], g.get("rail_b") or [], 0.4)
        strips = []
        for (a0, b0), (a1, b1) in zip(pairs, pairs[1:]):
            strips += polygons(shapely.make_valid(Polygon([a0, a1, b1, b0])))
        return polygons(unary_union(strips)), []
    outline = g.get("outline") or []
    if len(outline) < 3:
        return [], []
    shell, _ = flatten(outline, True)
    holes = [flatten(h, True)[0] for h in g.get("holes") or [] if len(h) >= 3]
    return dz.valid_parts(shell, holes), []


def _letter_shapes(letters: list[dict[str, Any]]) -> tuple[list[Polygon], list[LineString]]:
    areas: list[Polygon] = []
    lines: list[LineString] = []
    for part in letters:
        a, b = _part_shapes(part)
        areas += a
        lines += b
    return areas, lines


def _letter_points(letters: list[dict[str, Any]]) -> list[Point]:
    """Points all round the letters, for a frame to go round. A stitched letter's are where its
    needle goes down."""
    points: list[Point] = []
    for part in letters:
        if part.get("kind") == "stitches":
            nodes = (part.get("geometry") or {}).get("nodes") or []
            drops = [n for n in nodes if len(n) > 2 and n[2] == "s"] or nodes
            points += [(float(n[0]), float(n[1])) for n in drops]
            continue
        areas, lines = _part_shapes(part)
        points += [(x, y) for a in areas for x, y in a.exterior.coords]
        points += [(x, y) for line in lines for x, y in line.coords]
    return points


# ---------------------------------------------------------------- choosing the same on every computer


def _on_grid(geom: BaseGeometry) -> BaseGeometry:
    return shapely.set_precision(geom, GRID_MM)


def _place_key(bounds: tuple[float, float, float, float]) -> tuple[float, ...]:
    """Left to right, then top to bottom."""
    return tuple(round(v, 2) for v in bounds)


def _from_first_corner(ring) -> list[Point]:
    """A closed ring started at its leftmost (then topmost) point."""
    pts = list(ring.coords)[:-1]
    k = min(range(len(pts)), key=lambda i: (round(pts[i][0], 3), round(pts[i][1], 3), i))
    return pts[k:] + pts[:k] + [pts[k]]


def _ordered(geom: BaseGeometry) -> list[Polygon]:
    """The pieces of a shape, left to right, each ring turned the same way and started at the
    same point."""
    out = []
    for p in polygons(_on_grid(geom)):
        p = orient(p, 1.0)
        holes = sorted((_from_first_corner(h) for h in p.interiors), key=lambda h: (round(h[0][0], 2), round(h[0][1], 2)))
        out.append(Polygon(_from_first_corner(p.exterior), holes))
    return sorted(out, key=lambda p: _place_key(p.bounds))


def _line_pieces(geom: BaseGeometry) -> list[LineString]:
    parts = [g for g in getattr(geom, "geoms", [geom]) if g.geom_type == "LineString" and not g.is_empty]
    if len(parts) > 1:
        merged = linemerge(parts)
        parts = [g for g in getattr(merged, "geoms", [merged]) if not g.is_empty]
    return parts


# ---------------------------------------------------------------- shadow


def _shadow(areas: list[Polygon], lines: list[LineString], shadow: dict[str, Any]) -> list[dict[str, Any]]:
    """The letters moved right and down, less the letters themselves: only what shows is sewn
    (satin-look fills; a single line's shadow is a line)."""
    dx = _mm(shadow, "dx_mm", SHADOW_MM, -SHADOW_MAX_MM, SHADOW_MAX_MM)
    dy = _mm(shadow, "dy_mm", SHADOW_MM, -SHADOW_MAX_MM, SHADOW_MAX_MM)
    if not (dx or dy):
        return []
    thread = _thread(shadow)
    covered = _on_grid(unary_union(areas + [line.buffer(THREAD_REACH_MM) for line in lines]))
    out: list[dict[str, Any]] = []
    if areas:
        showing = affinity.translate(_on_grid(unary_union(areas)), dx, dy).difference(covered)
        # Where edges line up, the difference leaves slivers thinner than a thread.
        opened = showing.buffer(-SLIVER_MM / 2, join_style="mitre").buffer(SLIVER_MM / 2, join_style="mitre")
        for piece in _ordered(opened.intersection(showing)):
            # Measured as _fill_object simplifies it, with a hair to spare, so none is too small to stitch.
            if piece.simplify(0.03).area >= MIN_PIECE_MM2 * 1.01:
                out.append({**glyphs._fill_object(piece, "satin"), "extra": "shadow", "thread": thread})
    for line in lines:
        showing = affinity.translate(line, dx, dy).difference(covered)
        for piece in _line_pieces(_on_grid(showing)):
            if piece.length >= MIN_SHADOW_LINE_MM:
                nodes = [[round(x, 3), round(y, 3), "c"] for x, y in piece.simplify(0.05).coords]
                out.append({"kind": "run", "geometry": {"nodes": nodes}, "params": {"stitch_mm": LINE_STITCH_MM},
                            "extra": "shadow", "thread": thread})
    return sorted(out, key=lambda o: _place_key(dz.bounds(dz.geometry_points(o))))


# ---------------------------------------------------------------- outline


def _outline(areas: list[Polygon], lines: list[LineString], outline: dict[str, Any]) -> list[dict[str, Any]]:
    """A line round the letters, `gap` away from them: a satin (its inner edge at the gap) or a
    triple run (on the gap). One for each group of letters the gap doesn't join; the insides of
    letters aren't outlined."""
    from .. import shapeops  # here: shapeops needs the layout package, which needs this one

    gap = _mm(outline, "gap_mm", OUTLINE_GAP_MM, 0.0, OUTLINE_MAX_GAP_MM)
    run = outline.get("style") == "run"
    width = _mm(outline, "width_mm", OUTLINE_WIDTH_MM, *OUTLINE_WIDTHS_MM)
    thread = _thread(outline)
    covered = unary_union(areas + [line.buffer(THREAD_REACH_MM) for line in lines])
    if run:
        grown = covered.buffer(gap, quad_segs=16) if gap else covered
    else:
        reach = gap + width / 2  # the satin's centre line
        grown = covered.buffer(reach + SOFTEN_MM, quad_segs=16).buffer(-SOFTEN_MM, quad_segs=16)
    out: list[dict[str, Any]] = []
    for piece in _ordered(grown):
        nodes = shapeops.to_nodes(list(piece.exterior.coords), OUTLINE_NODE_MM, closed=True)
        if len(nodes) < 3:
            continue
        if run:
            shape = {"kind": "run", "geometry": {"nodes": nodes, "closed": True},
                     "params": {"style": "triple", "stitch_mm": LINE_STITCH_MM}}
        else:  # the fabric preset chooses its spacing, underlay and pull compensation
            # Every point smooth: a satin's mitred corner spikes into the gap (and the letters).
            nodes = [[x, y, "s"] for x, y, _ in nodes]
            shape = {"kind": "satin", "geometry": {"nodes": nodes, "width_mm": width, "closed": True}, "params": {}}
        out.append({**shape, "extra": "outline", "thread": thread})
    return out
