""""Don't sew what's hidden under shapes on top" (P4-A2): when layout["remove_overlap"] is on, a
drawn fill leaves out the part of itself that a shape sewn later covers, keeping a margin tucked
under the edge.

It works on the shapes, not the stitches: this "before_items" pass returns the layout with each
covered part added to the lower fill's holes, so the stitch generator sews round it, and the holes
follow the shapes as they move. Placed stitch files are neither trimmed nor count as covers
(leaving stitches out under them is P4-A1, which isn't built).
"""

from __future__ import annotations

import json
import math
from typing import Any, Callable

import shapely
from shapely import STRtree, affinity
from shapely.errors import GEOSException
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.geometry.base import BaseGeometry

from .. import fabrics, lettering
from ..digitize import fills
from ..digitize import stitches as dz
from ..digitize.patterns import polygons
from ..layout import passes
from ..layout.model import LayoutError, Transform
from ..layout.objects import OBJECT_LABEL
from ..layout.text import text_letters, text_title

KEEP_MM = 1.0  # "Keep under the edge": how far under a cover's edge the fill below keeps sewing
KEEP_RANGE_MM = (0.5, 3.0)
COVER_SPACING_MM = 0.6  # rows or satin stitches further apart than this don't hide what's under them
MIN_PIECE_MM2 = 9.0  # smaller hidden patches are sewn as before
MIN_WIDTH_MM = 2.0  # ...and so are hidden strips narrower than this
PINHOLE_MM2 = 1.0  # gaps in what covers smaller than this count as covered
EDGE_MM = 0.1  # past the fill's own edge the cut goes this much further
HAIR_MM = 0.1  # thinner slivers of fill left beside the cut are cut too
SHOWS_MM = 0.05  # a fill showing no more than this past what covers it is completely hidden
SEAM_MM = 0.01  # the halves of a cut round a hole overlap this much, so they leave no gap
SMOOTH_MM = 0.01  # outlines are followed this closely (fewer points, and much quicker)
GRID_MM = 0.001  # areas are combined on this grid, so edges that should meet do meet
DECIMALS = 4  # of the new points (mm), so every processor gets the same ones
HIDDEN_NOTE = "{} is completely hidden under {}. Delete it, or move it up in the sewing order."

# Every edit draws the design again, so what's worked out is kept: each shape's areas, and each
# fill's cut under the shapes near it. Only what changed, and what lies near it, is done again.
_areas_cache: dict[tuple[str, str], BaseGeometry | None] = {}
_cuts_cache: dict[tuple, tuple | None] = {}
_CACHE_MAX = 4096  # as layout/objects.py keeps stitches: a traced picture can be a thousand shapes
_SHAPE_KEYS = ("kind", "geometry", "params", "transform", *lettering.TEXT_SPEC_KEYS,
               "letters")  # what an item's areas depend on

# What a damaged shape can raise here. The pass leaves such a shape out; render() then meets it
# and says what's wrong with it, in the same words as with the switch off.
_DAMAGED = (dz.DigitizeError, LayoutError, GEOSException, AttributeError, IndexError, KeyError, TypeError,
            ValueError, ZeroDivisionError)


def apply(layout: dict) -> dict:
    """The "before_items" pass: the layout with the covered parts added to the lower fills' holes."""
    settings = layout.get("remove_overlap")
    if not (isinstance(settings, dict) and settings.get("enabled")):
        return layout
    keep = _keep_mm(settings.get("keep_mm"))
    items = list(layout.get("items") or [])
    fabric = layout.get("fabric")
    lower = [i for i, it in enumerate(items) if isinstance(it, dict) and it.get("kind") == "fill"]
    if not lower:
        return layout
    covers = [(j, *found) for j in range(lower[0] + 1, len(items))
              if (found := _area("cover", items[j], fabric)) is not None]  # (index, area, key)
    if not covers:
        return layout
    tree = STRtree([area for _, area, _ in covers])
    out = list(items)
    notes: list[dict] = []
    for i in lower:
        found = _area("own", items[i], fabric)
        if found is None:
            continue
        own, own_key = found
        # The shapes sewn later that come near enough to matter, in sewing order.
        near = sorted((covers[k] for k in tree.query(own.envelope.buffer(keep)) if covers[k][0] > i),
                      key=lambda c: c[0])
        if not near:
            continue
        done = _remember(_cuts_cache, (own_key, keep, *(key for _, _, key in near)),
                         lambda: _trim(items[i], own, [area for _, area, _ in near], keep))
        if done is None:
            continue
        what, value = done
        if what == "hidden":  # completely: left as it is, and said
            j = near[value][0]
            notes.append({"level": "warning", "code": f"overlap_hidden_{i}",
                          "message": HIDDEN_NOTE.format(_name(items[i], i), _name(items[j], j))})
        else:
            geometry = items[i]["geometry"]
            out[i] = {**items[i], "geometry": {**geometry, "holes": [*(geometry.get("holes") or []), *value]}}
    if not notes and all(a is b for a, b in zip(out, items)):
        return layout
    return {**layout, "items": out, passes.NOTES_KEY: [*(layout.get(passes.NOTES_KEY) or []), *notes]}


def _keep_mm(value: Any) -> float:
    """The "Keep under the edge" a project file holds, kept within its range; the standard one if
    it isn't a number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return KEEP_MM
    if isinstance(value, float) and not math.isfinite(value):
        return KEEP_MM
    return float(min(max(value, KEEP_RANGE_MM[0]), KEEP_RANGE_MM[1]))


def _name(item: dict, index: int) -> str:
    """An item's name as render() gives it (layout/render.py)."""
    if item.get("kind") == "text":
        return item.get("name") or f"“{text_title(item)}”"
    return item.get("name") or f"{OBJECT_LABEL[item['kind']]} {index + 1}"


# ---------------------------------------------------------------- the areas, in hoop mm


def _middle(item: dict) -> tuple[float, float]:
    """The point a drawn shape turns and resizes about: the middle of its points."""
    x0, y0, x1, y1 = dz.bounds(dz.geometry_points(item))
    return (x0 + x1) / 2, (y0 + y1) / 2


def _placed(item: dict, fabric: str | None) -> dict:
    """A drawn shape as it is stitched (as layout/objects.py does it): turned, resized and moved,
    with the fabric's settings."""
    t = Transform.from_dict(item.get("transform"))
    obj = item if t.is_identity() else dz.transform_geometry(item, t, _middle(item))
    return fabrics.apply(obj, fabric)


def _outline_area(geometry: dict) -> BaseGeometry:
    parts = dz.fill_parts(geometry.get("outline") or [], geometry.get("holes") or [])
    return (parts[0] if len(parts) == 1 else shapely.union_all(parts)).simplify(SMOOTH_MM)


def _remember(cache: dict, key, make: Callable[[], Any]) -> Any:
    """cache[key], made if it isn't there yet (the oldest goes when the cache is full)."""
    if key in cache:
        return cache[key]
    value = make()
    if len(cache) >= _CACHE_MAX:
        cache.pop(next(iter(cache)))
    cache[key] = value
    return value


def _area(which: str, item: Any, fabric: str | None) -> tuple[BaseGeometry, str] | None:
    """An item's "own" area (a fill in rows, the kind trimmed) or its "cover" area, with a key
    that changes when it does; None if it has none, or is damaged (render() then says why)."""
    try:
        parts = [fabric, {k: item.get(k) for k in _SHAPE_KEYS}]
        if item.get("kind") == "text":
            parts.append(lettering.font_stamp(item.get("font") or {}))  # an edited font shows at once
        key = json.dumps(parts, sort_keys=True)
        area = _remember(_areas_cache, (which, key),
                         lambda: _rows_area(item, fabric) if which == "own" else _cover(item, fabric))
    except _DAMAGED:
        return None
    return None if area is None else (area, key)


def _rows_area(item: dict, fabric: str | None) -> BaseGeometry | None:
    """A fill sewn in rows (the only kind that is trimmed), or None."""
    obj = _placed(item, fabric)
    spec = fills.get(str((obj.get("params") or {}).get("pattern", "tatami")))
    return _outline_area(obj.get("geometry") or {}) if spec.kind == "rows" else None


def _hiding_area(obj: dict) -> BaseGeometry | None:
    """What a shape, as stitched, hides of whatever is sewn before it, or None: lines, open
    patterns, gradients and rows or satin too far apart let it show."""
    kind, geometry = obj.get("kind"), obj.get("geometry") or {}
    if kind == "applique":
        return _outline_area(geometry)  # its fabric covers everything inside its outline
    if kind == "fill":
        params = dz.FillParams.from_dict(obj.get("params"))
        spec = fills.get(params.pattern)
        if spec.kind != "rows" or "sparse_to" in spec.rows(params):  # rows that open out: a gradient
            return None
        return _outline_area(geometry) if params.spacing_mm <= COVER_SPACING_MM + 1e-9 else None
    if kind == "satin":
        params = dz.SatinParams.from_dict(obj.get("params"))
        if params.spacing_mm > COVER_SPACING_MM + 1e-9:
            return None
        if geometry.get("nodes") is not None:  # a ribbon: its two edges either side of the line
            pairs = dz.ribbon_pairs(geometry["nodes"], dz._finite(geometry, "width_mm", 3.0), params.spacing_mm,
                                    bool(geometry.get("closed")))
        else:  # a column: its two drawn sides
            pairs = dz.satin_pairs(geometry.get("rail_a") or [], geometry.get("rail_b") or [], params.spacing_mm)
        # From each stitch to the next, edge to edge (a quad that crosses over becomes its parts).
        quads = shapely.make_valid([Polygon([a0, a1, b1, b0]) for (a0, b0), (a1, b1) in zip(pairs, pairs[1:])])
        return shapely.union_all([p for q in quads for p in polygons(q)])
    return None


def _cover(item: dict, fabric: str | None) -> BaseGeometry | None:
    """The area an item hides from what is sewn before it, or None. Drawn shapes and lettering
    only: placed stitch files never count."""
    if item.get("kind") != "text":
        area = _hiding_area(_placed(item, fabric)) if item.get("kind") in ("fill", "satin", "applique") else None
    else:
        letters, _ = text_letters(item)
        parts = []
        for letter in letters:
            try:
                part = _hiding_area(fabrics.apply(letter, fabric))
            except dz.DigitizeError:
                continue  # a speck too small to stitch, as in the lettering
            if part is not None:
                parts.append(part)
        t = Transform.from_dict(item.get("transform"))
        area = affinity.translate(shapely.union_all(parts), t.x, t.y)  # letters aren't moved yet
    if area is None or area.is_empty:
        return None
    # On the grid once, here, so edges that should meet do meet when covers are joined.
    return shapely.set_precision(area, GRID_MM)


def _trim(item: dict, own: BaseGeometry, hiding: list[BaseGeometry], keep: float) -> tuple[str, Any] | None:
    """What to do to a fill under the areas near it that are sewn after it (`hiding`, in sewing
    order): ("hidden", which of them hides the most of it) when none of it would show, ("holes",
    the new holes for it), or None to sew it as it is."""
    try:
        cut = _cut(own, shapely.union_all(hiding), keep)
        if cut is None:
            return "hidden", _most_hiding(own, hiding)
        holes = [] if cut.is_empty else _new_holes(item, cut, own)
        return ("holes", holes) if holes else None
    except GEOSException:
        return None  # the geometry library gave up: sewn whole, as with the switch off


def _most_hiding(own: BaseGeometry, hiding: list[BaseGeometry]) -> int:
    """Which area hides the most of a fill (to 0.1 mm2); of equals, the one sewn first."""
    return min(range(len(hiding)), key=lambda k: (-round(own.intersection(hiding[k]).area, 1), k))


def _areas(geometry: BaseGeometry) -> BaseGeometry:
    """Only the areas of a result. Where edges only just touch, GEOS adds stray lines to them,
    which its next step refuses."""
    if geometry.geom_type in ("Polygon", "MultiPolygon"):
        return geometry
    return MultiPolygon(polygons(geometry))


def _both(a: BaseGeometry, b: BaseGeometry) -> BaseGeometry:
    return _areas(shapely.intersection(a, b, grid_size=GRID_MM))


def _less(a: BaseGeometry, b: BaseGeometry) -> BaseGeometry:
    return _areas(shapely.difference(a, b, grid_size=GRID_MM))


def _wider_than(area: BaseGeometry, width: float) -> BaseGeometry:
    """The parts of an area at least `width` across: shrunk by half of it and grown back, corners
    kept square, so slivers and thin tails go and nothing else changes."""
    return _both(area.buffer(-width / 2, join_style="mitre").buffer(width / 2, join_style="mitre"), area)


def _cut(own: BaseGeometry, covered: BaseGeometry, keep: float) -> BaseGeometry | None:
    """What to leave out of a fill `own` under the shapes `covered`: an empty area when there's
    nothing worth leaving out, None when the whole fill is hidden."""
    covered = MultiPolygon([Polygon(p.exterior, [r for r in p.interiors if Polygon(r).area >= PINHOLE_MM2])
                            for p in polygons(covered)])
    (x0, y0, x1, y1), (u0, v0, u1, v1) = own.bounds, covered.bounds
    reaches_round = u0 - SHOWS_MM <= x0 and v0 - SHOWS_MM <= y0 and u1 + SHOWS_MM >= x1 and v1 + SHOWS_MM >= y1
    if reaches_round and own.difference(covered.buffer(SHOWS_MM)).area < dz.MIN_PART_MM2:
        return None
    inner = covered.buffer(-keep)
    if not inner.intersects(own):
        return MultiPolygon()
    hidden = _both(inner, own)
    wide = polygons(_wider_than(hidden, MIN_WIDTH_MM))
    pieces = MultiPolygon([p for p in wide if p.area >= MIN_PIECE_MM2])
    if pieces.is_empty:
        return pieces
    stays = _wider_than(_less(own, pieces), HAIR_MM)
    if not any(p.area >= dz.MIN_PART_MM2 for p in polygons(stays)):
        return None  # nothing left that could be sewn
    # The pieces and a little past them, but for what stays sewn. Past the fill's own edge this
    # cuts nothing, but it keeps the two edges apart: edges that only just meet leave a hair of
    # fill along there (rounding), and every row crossing it is sewn as a tiny stitch.
    return _less(pieces.buffer(EDGE_MM, join_style="mitre"), stays)


# ---------------------------------------------------------------- the new holes, in the shape's frame


def _rings(cut: BaseGeometry, own: BaseGeometry) -> list:
    """The cut as plain rings, since a hole in a fill is a single ring. A piece with a hole of its
    own where the fill is (the hidden part of a ring on top) is cut through that hole into halves
    that overlap a little, so what is inside it stays sewn."""
    rings = []
    todo = polygons(cut.simplify(0.001))
    while todo:
        piece = todo.pop(0)
        holes = [r for r in piece.interiors if own.intersection(Polygon(r)).area >= PINHOLE_MM2 / 4]
        if not holes:
            rings.append(piece.exterior)
            continue
        # Through the middle of one hole (the leftmost, then topmost; holes alike in all four of
        # their bounds share the same middle), across its longer side.
        hole = min(holes, key=lambda r: tuple(round(v, 2) for v in r.bounds))
        x0, y0, x1, y1 = piece.bounds
        hx0, hy0, hx1, hy1 = hole.bounds
        if hx1 - hx0 >= hy1 - hy0:
            at = round((hx0 + hx1) / 2, 2)
            halves = (box(x0 - 1, y0 - 1, at + SEAM_MM / 2, y1 + 1), box(at - SEAM_MM / 2, y0 - 1, x1 + 1, y1 + 1))
        else:
            at = round((hy0 + hy1) / 2, 2)
            halves = (box(x0 - 1, y0 - 1, x1 + 1, at + SEAM_MM / 2), box(x0 - 1, at - SEAM_MM / 2, x1 + 1, y1 + 1))
        todo += [p for half in halves for p in polygons(piece.intersection(half))]
    return rings


def _to_own_frame(item: dict) -> Callable[[float, float], tuple[float, float]]:
    """From hoop mm back to the shape's own frame: dz.transform_geometry undone."""
    t = Transform.from_dict(item.get("transform"))
    if t.is_identity():
        return lambda x, y: (x, y)
    cx, cy = _middle(item)
    a = math.radians(t.rotate)
    ca, sa = math.cos(a), math.sin(a)
    fx = -1.0 if t.flip_x else 1.0
    fy = -1.0 if t.flip_y else 1.0

    def back(x: float, y: float) -> tuple[float, float]:
        dx, dy = x - cx - t.x, y - cy - t.y
        return (dx * ca + dy * sa) * fx / t.scale_x + cx, (dy * ca - dx * sa) * fy / t.scale_y + cy

    return back


def _hole(ring, back: Callable[[float, float], tuple[float, float]]) -> list[list]:
    """A ring as one of the shape's holes: rounded corner points, starting at the topmost (then
    leftmost) one and always going round the same way, so the same shapes give the same stitches
    on every computer (the order a geometry library lists them in can differ)."""
    points: list[tuple[float, float]] = []
    for x, y in list(ring.coords)[:-1]:
        u, v = back(x, y)
        p = (round(u, DECIMALS) + 0.0, round(v, DECIMALS) + 0.0)  # + 0.0: never -0.0
        if not points or p != points[-1]:
            points.append(p)
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1])) < 0:
        points.reverse()

    def order(i: int) -> tuple:  # topmost, then leftmost; where a ring touches itself, then by the next
        (x, y), (u, v) = points[i], points[(i + 1) % len(points)]
        return y, x, v, u

    first = min(range(len(points)), key=order)
    return [[x, y, "c"] for x, y in points[first:] + points[:first]]


def _new_holes(item: dict, cut: BaseGeometry, own: BaseGeometry) -> list[list]:
    """The cut as holes to add to the fill's own, in its frame."""
    back = _to_own_frame(item)
    new = sorted((_hole(ring, back) for ring in _rings(cut, own)), key=lambda h: [(p[1], p[0]) for p in h])
    new = [h for h in new if len(h) >= 3]
    if not new:
        return new
    # render() turns and resizes a shape about the middle of all its points, holes included. New
    # holes reaching past the old points would move that middle, and the whole fill with it, so
    # a "hole" of two points opposite reaches as far the other way. It cuts nothing: a hole
    # needs three points.
    x0, y0, x1, y1 = dz.bounds(dz.geometry_points(item))
    hx0, hy0, hx1, hy1 = dz.bounds([(p[0], p[1]) for h in new for p in h])
    wider, taller = max(x0 - hx0, hx1 - x1, 0.0), max(y0 - hy0, hy1 - y1, 0.0)
    if wider or taller:
        new.append([[x0 - wider, y0 - taller, "c"], [x1 + wider, y1 + taller, "c"]])
    return new
