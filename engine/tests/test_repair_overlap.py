""""Don't sew what's hidden under shapes on top" (P4-A2, repair/overlap.py): a drawn fill leaves out
what a shape sewn later covers, keeping a margin tucked under its edge."""

import base64
import json
import math
import random

import numpy as np
import pyembroidery as pe
import pytest
import shapely
from shapely import affinity
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

import invariants
from snapshot_util import check, digest_pattern
from test_lettering import font_path  # noqa: F401  (a tiny font built in the test: I, O and X)
from threadline_engine import layout
from threadline_engine.digitize import stitches as dz
from threadline_engine.digitize.stitches import fill_parts
from threadline_engine.layout import LayoutError, passes
from threadline_engine.repair import overlap

RED = {"color": "#cc2222", "name": "Red", "catalog": "", "brand": ""}
BLUE = {"color": "#2222cc", "name": "Blue", "catalog": "", "brand": ""}
GREEN = {"color": "#22aa22", "name": "Green", "catalog": "", "brand": ""}
HIDDEN = "{} is completely hidden under {}. Delete it, or move it up in the sewing order."


def _nodes(points, kind="c"):
    return [[x, y, kind] for x, y in points]


def _rect(x0, y0, x1, y1):
    return _nodes([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _shape(i, kind, geometry, thread, params=None, **extra):
    return {"id": i, "kind": kind, "geometry": geometry, "params": params or {}, "thread": thread,
            "transform": {}, "threads": [], "ops": [], **extra}


def _square(i, x, y, w, thread=RED, params=None, **extra):
    return _shape(i, "fill", {"outline": _rect(x, y, x + w, y + w)}, thread, params, **extra)


def _ribbon(i, points, width, thread=BLUE, closed=False, params=None, kind="c"):
    return _shape(i, "satin", {"nodes": _nodes(points, kind), "width_mm": width, "closed": closed}, thread, params)


def _text(i, font, thread=BLUE, transform=None, **extra):
    return {"id": i, "kind": "text", "text": "IO", "font": {"path": font, "index": 0}, "size_mm": 40, "spacing_mm": 0,
            "style": "fill", "shape": {"type": "line"}, "monogram": False, "thread": thread,
            "transform": transform or {}, "threads": [], "ops": [], **extra}


def _layout(*items, on=True, keep=1.0, **extra):
    """A layout sewn in this order; `on` None leaves the key out, as every older project does."""
    lay = {"items": list(items), "merge_colors": False, "color_sort": False, "basting": {"enabled": False}, **extra}
    if on is not None:
        lay["remove_overlap"] = {"enabled": on, "keep_mm": keep}
    return lay


def _pair(lower, upper, **kw):
    """The same two (or more) shapes rendered with the switch off and on."""
    return (layout.render(_layout(lower, upper, **{**kw, "on": False})),
            layout.render(_layout(lower, upper, **{**kw, "on": True})))


def _item_recs(r, item):
    """The records of one item, in sewing order: (x, y, command, src)."""
    return [(x, y, k, src) for blk in r.blocks for x, y, k, it, src in blk.recs if it == item]


def _mm_recs(r, item):
    return [(x / 10, y / 10, k) for x, y, k, _ in _item_recs(r, item)]


def _thread_xy(r, item, step=0.1):
    """Points every `step` mm along an item's thread (not along its jumps), in mm."""
    segs = np.array([(a[0], a[1], b[0], b[1]) for blk in r.blocks for a, b in zip(blk.recs, blk.recs[1:])
                     if a[2] == b[2] == pe.STITCH and a[3] == b[3] == item], dtype=float).reshape(-1, 4) / 10
    n = np.maximum(1, np.ceil(np.hypot(segs[:, 2] - segs[:, 0], segs[:, 3] - segs[:, 1]) / step)).astype(int) + 1
    i = np.repeat(np.arange(len(segs)), n)
    t = (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)) / np.repeat(n - 1, n)
    return np.column_stack([segs[i, 0] + (segs[i, 2] - segs[i, 0]) * t, segs[i, 1] + (segs[i, 3] - segs[i, 1]) * t])


def _depth(xy, area):
    """How far inside `area` each point is (0 outside it), mm."""
    inside = shapely.contains_xy(area, xy[:, 0], xy[:, 1])
    out = np.zeros(len(xy))
    out[inside] = shapely.distance(area.boundary, shapely.points(xy[inside]))
    return out


def _deepest(r, item, area):
    return float(_depth(_thread_xy(r, item), area).max(initial=0.0))


def _near(r, item, at, within):
    """Does the item's thread come within `within` mm of the point `at`?"""
    xy = _thread_xy(r, item)
    return bool((np.hypot(xy[:, 0] - at[0], xy[:, 1] - at[1]) <= within).any())


def _box_of(nodes):
    return Polygon([n[:2] for n in nodes])


def _holes(lay, item=0):
    """The holes the pass gives one item, as it would render it (those with an area: three points)."""
    return [h for h in overlap.apply(lay)["items"][item]["geometry"].get("holes") or [] if len(h) >= 3]


def _notes(r):
    return [w["message"] for w in r.warnings if w["code"].startswith("overlap")]


def _same_item(a, b, item=0):
    assert _item_recs(a, item) == _item_recs(b, item)


def _letter_area(text_item):
    letters, _ = layout.text_letters(text_item)
    t = text_item.get("transform") or {}
    parts = [p for o in letters for p in fill_parts(o["geometry"]["outline"], o["geometry"].get("holes") or [])]
    return affinity.translate(unary_union(parts), t.get("x", 0), t.get("y", 0))


# ---------------------------------------------------------------- off


def test_off_by_default_changes_nothing(monkeypatch):
    items = [_square("a", 0, 0, 40), _square("b", 11, 9, 20, BLUE),
             _ribbon("c", [(-5, 34), (45, 34)], 8, GREEN)]
    without = layout.render_summary(_layout(*items, on=None))
    for lay in (_layout(*items, on=False), _layout(*items, on=False, keep=3.0),
                {**_layout(*items, on=None), "remove_overlap": None},
                {**_layout(*items, on=None), "remove_overlap": "yes"}):
        assert layout.render_summary(lay) == without, lay.get("remove_overlap")
    # ...exactly what it was before the pass existed...
    monkeypatch.setattr(passes, "BEFORE_ITEMS", [])
    assert layout.render_summary(_layout(*items, on=None)) == without
    monkeypatch.undo()
    # ...and the switch is what changes it.
    assert layout.render_summary(_layout(*items, on=True))["records"] != without["records"]


# ---------------------------------------------------------------- under a cover


@pytest.mark.parametrize("keep", [0.5, 1.0, 2.0])
def test_lower_fill_stops_under_the_cover(keep):
    lower, upper = _square("a", 0, 0, 40), _square("b", 10, 10, 20, BLUE)
    off, on = _pair(lower, upper, keep=keep)
    cover = _box_of(upper["geometry"]["outline"])
    assert _deepest(off, 0, cover) > 9  # sewn right through the middle without the switch
    assert _deepest(on, 0, cover) <= keep + 0.4
    # What isn't covered is still sewn, nowhere outside the shape and with no long stitches.
    recs = _mm_recs(on, 0)
    outline = _box_of(lower["geometry"]["outline"])
    invariants.assert_sane(recs, inside=outline.buffer(0.1), tolerance_mm=0.2)
    assert invariants.coverage(recs, outline.difference(cover), 0.4) > 0.97
    # The shape on top sews just as before.
    _same_item(off, on, 1)


@pytest.mark.parametrize("keep", [0.5, 1.0, 2.0])
def test_margin_is_kept(keep):
    lower, upper = _square("a", 0, 0, 40), _square("b", 11.3, 8.7, 20, BLUE)
    on = layout.render(_layout(lower, upper, keep=keep))
    cover = _box_of(upper["geometry"]["outline"])
    xy = _thread_xy(on, 0)
    depth = _depth(xy, cover)
    xy, depth = xy[depth > 0], depth[depth > 0]
    # All the way round: next to every point of the upper outline, the thread below reaches in.
    ring = cover.exterior
    for k in range(int(ring.length / 0.5)):
        p = ring.interpolate(k * 0.5)
        close = np.hypot(xy[:, 0] - p.x, xy[:, 1] - p.y) <= keep + 1.0
        assert close.any() and depth[close].max() >= keep - 0.3, (round(p.x, 2), round(p.y, 2))


def _over_limit(lay, area):
    """The density map's cells wholly inside `area` that are over its limit (their values)."""
    h = layout.check(lay, heatmap=True)["heatmap"]
    data = np.frombuffer(base64.b64decode(h["data"]), np.uint8).reshape(h["height"], h["width"])
    return [int(data[j, i]) for j in range(h["height"]) for i in range(h["width"])
            if data[j, i] > h["limit"] and area.contains(box(h["x"] + i, h["y"] + j, h["x"] + i + 1, h["y"] + j + 1))]


@pytest.mark.parametrize("at", [(10, 10), (11.3, 8.7)])
def test_density_under_the_overlap_is_within_the_limit(at):
    """Inside the upper square, past the keep margin, no cell is over the limit. (In the margin
    itself both shapes sew, on purpose, so cells there can be over it.)"""
    lower, upper = _square("a", 0, 0, 40), _square("b", *at, 20, BLUE)
    cover = _box_of(upper["geometry"]["outline"])
    past_margin = cover.buffer(-(1.0 + 0.1), join_style="mitre")  # the margin and half the pull compensation
    assert len(_over_limit(_layout(lower, upper, on=False), past_margin)) > 20
    assert _over_limit(_layout(lower, upper), past_margin) == []


# ---------------------------------------------------------------- what covers


@pytest.mark.parametrize("pattern", ["stipple", "contour", "cross", "spiral", "gradient"])
def test_open_patterns_and_gradients_cover_nothing(pattern):
    lower = _square("a", 0, 0, 40)
    off, on = _pair(lower, _square("b", 10, 10, 20, BLUE, {"pattern": pattern}))
    _same_item(off, on)
    assert _holes(_layout(lower, _square("b", 10, 10, 20, BLUE, {"pattern": pattern}))) == []


def test_only_rows_kind_fills_are_trimmed():
    for lower in (_square("a", 0, 0, 40, params={"pattern": "stipple"}),
                  _square("a", 0, 0, 40, params={"pattern": "spiral"}),
                  _ribbon("a", [(0, 20), (40, 20)], 10, RED),
                  _shape("a", "applique", {"outline": _rect(0, 0, 40, 40)}, RED)):
        upper = _square("b", 10, 10, 20, BLUE)
        _same_item(*_pair(lower, upper))
    for pattern in ("wave", "gradient"):  # rows, so what's hidden of them is left out
        lower = _square("a", 0, 0, 40, params={"pattern": pattern})
        assert len(_holes(_layout(lower, _square("b", 10, 10, 20, BLUE)))) == 1, pattern


def test_only_shapes_sewn_later_cover():
    big, small = _square("a", 0, 0, 40), _square("b", 10, 10, 20, BLUE)
    # The small one first: the big one is on top of it, so the big one is sewn whole.
    off, on = _pair(small, big)
    _same_item(off, on, 1)


@pytest.mark.parametrize("kind", ["fill", "satin"])
def test_cover_spacing_counts_after_the_fabric_preset(kind):
    """0.55 mm rows are 0.55 mm on woven cotton but 0.61 mm on knit, which hides too little."""
    def cover(spacing):
        if kind == "fill":
            return _square("b", 10, 10, 20, BLUE, {"spacing_mm": spacing})
        return _ribbon("b", [(10, 20), (30, 20)], 10, BLUE, params={"spacing_mm": spacing})

    lower = _square("a", 0, 0, 40)
    assert _holes(_layout(lower, cover(0.55), fabric="woven"))
    assert not _holes(_layout(lower, cover(0.55), fabric="knit"))
    assert not _holes(_layout(lower, cover(0.7), fabric="woven"))


def test_satins_cover_between_their_two_edges():
    lower = _square("a", 0, 0, 40)
    # A wide ribbon across the middle: what's under it, 1 mm in from each edge, is left out.
    on = layout.render(_layout(lower, _ribbon("b", [(-4, 20), (44, 20)], 8, BLUE)))
    assert _deepest(on, 0, box(-4, 16, 44, 24)) <= 1.4
    # A satin drawn as two sides does the same.
    column = _shape("b", "satin", {"rail_a": _nodes([(5, 5), (35, 8)]), "rail_b": _nodes([(5, 14), (35, 17)])}, BLUE)
    on = layout.render(_layout(lower, column))
    assert _deepest(on, 0, Polygon([(5, 5), (35, 8), (35, 17), (5, 14)])) <= 1.4
    # A narrow one hides too little to be worth a hole.
    assert not _holes(_layout(lower, _ribbon("b", [(-4, 20), (44, 20)], 3.5, BLUE)))


@pytest.mark.parametrize("ring", ["fill", "satin"])
def test_a_ring_on_top_leaves_the_middle_sewn(ring):
    """The hidden part of a ring has a hole of its own: the middle stays sewn."""
    lower = _square("a", 0, 0, 40)
    if ring == "fill":
        cover = _shape("b", "fill", {"outline": _rect(5, 5, 35, 35), "holes": [_rect(14, 14, 26, 26)]}, BLUE)
        area = box(5, 5, 35, 35).difference(box(14, 14, 26, 26))
    else:
        points = [(20 + 12 * math.cos(2 * math.pi * k / 12), 20 + 12 * math.sin(2 * math.pi * k / 12))
                  for k in range(12)]
        cover = _ribbon("b", points, 8, BLUE, closed=True, kind="s")
        area = Point(20, 20).buffer(16, 64).difference(Point(20, 20).buffer(8, 64))
    on = layout.render(_layout(lower, cover))
    assert _deepest(on, 0, area) <= 1.5
    assert _near(on, 0, (20, 20), 0.5) and _near(on, 0, (1.5, 1.5), 0.5)
    assert invariants.coverage(_mm_recs(on, 0), box(16, 16, 24, 24), 0.4) > 0.97


def test_lettering_and_applique_count_as_covers(font_path):  # noqa: F811
    lower = _shape("a", "fill", {"outline": _rect(-32, -26, 32, 26)}, RED)
    words = _text("b", font_path)
    off, on = _pair(lower, words)
    letters = _letter_area(words)
    assert _deepest(off, 0, letters) > 3.5 and _deepest(on, 0, letters) <= 1.4
    assert not _near(on, 0, (-20, 0), 2.0) and not _near(on, 0, (-2.9, 0), 2.0)  # under the I and the O
    assert _near(on, 0, (8.6, 0), 0.5)  # the middle of the O isn't covered, so it's still sewn
    # An applique's fabric covers everything inside its outline, not only its stitched border.
    patch = _shape("b", "applique", {"outline": _rect(8, 8, 32, 32)}, BLUE)
    lower = _square("a", 0, 0, 40)
    off, on = _pair(lower, patch)
    assert _deepest(on, 0, box(8, 8, 32, 32)) <= 1.4 and not _near(on, 0, (20, 20), 9.0)
    # A hole in an applique is cut out of its fabric, so what's under the hole still sews.
    patch = _shape("b", "applique", {"outline": _rect(5, 5, 35, 35), "holes": [_rect(14, 14, 26, 26)]}, BLUE)
    on = layout.render(_layout(lower, patch))
    assert _near(on, 0, (20, 20), 0.5) and not _near(on, 0, (9.5, 20), 2.0)


def test_runs_and_stitch_files_cover_nothing(tmp_path):
    """Removing under a placed stitch file (P4-A1) isn't built: A2 trims only under drawn shapes."""
    p = pe.EmbPattern()
    p.add_thread(pe.EmbThread("#0000ff", "Blue"))
    for row in range(41):  # a solid 20 mm square of stitches, 0.5 mm rows
        for x in (0, 50, 100, 150, 200):
            p.stitch_abs(x if row % 2 == 0 else 200 - x, row * 5)
    p.end()
    path = tmp_path / "bought.pes"
    pe.write(p, str(path))
    lower = _square("a", 0, 0, 40)
    for upper in ({"id": "f", "path": str(path), "transform": {"x": 10, "y": 10}},
                  _shape("r", "run", {"nodes": _nodes([(-2, 20), (42, 20)])}, BLUE, {"style": "motif", "motif_width_mm": 8})):
        _same_item(*_pair(lower, upper))


# ---------------------------------------------------------------- what is left out


@pytest.mark.parametrize("upper, keep", [
    (_square("b", 39, 5, 30, BLUE), 1.0),    # overlapping by 1 mm
    (_square("b", 39, 5, 30, BLUE), 0.5),    # ...which would hide a strip 0.5 mm wide
    (_square("b", 37.5, 5, 30, BLUE), 1.0),  # a strip 1.5 mm wide (45 mm2: too narrow, not too small)
    (_square("b", 10, 10, 4.9, BLUE), 1.0),  # 2.9 mm square: wide enough, but under 9 mm2
])
def test_slivers_are_ignored(upper, keep):
    lower = _square("a", 0, 0, 40)
    off, on = _pair(lower, upper, keep=keep)
    _same_item(off, on)
    assert _holes(_layout(lower, upper, keep=keep)) == []


@pytest.mark.parametrize("upper", [_square("b", 36.5, 5, 30, BLUE), _square("b", 10, 10, 5.5, BLUE)])
def test_pieces_just_big_enough_are_left_out(upper):
    assert len(_holes(_layout(_square("a", 0, 0, 40), upper))) == 1


def test_follows_the_cover_when_it_moves():
    lower, upper = _square("a", 0, 0, 40), _square("b", 5, 9, 20, BLUE)
    moved = {**upper, "transform": {"x": 10}}
    (first,), (second,) = _holes(_layout(lower, upper)), _holes(_layout(lower, moved))
    assert [n[2:] for n in second] == [n[2:] for n in first]
    assert [n[0] for n in second] == pytest.approx([n[0] + 10 for n in first], abs=0.001)
    assert [n[1] for n in second] == pytest.approx([n[1] for n in first], abs=0.001)
    before, after = layout.render(_layout(lower, upper)), layout.render(_layout(lower, moved))
    assert not _near(before, 0, (10, 19), 2.0) and _near(after, 0, (10, 19), 0.5)  # uncovered again
    assert _near(before, 0, (30, 19), 0.5) and not _near(after, 0, (30, 19), 2.0)  # now covered


def test_turned_resized_and_mirrored_fill_stays_where_it_was():
    """The new holes are given in the fill's own frame. Adding them must not move the middle that
    frame turns and resizes about, even where a curve bulges past the fill's points and the cover
    runs off its edge."""
    nodes = _nodes([(0, 0), (30, 4), (34, 24), (14, 33), (-4, 20)], "s")
    lower = _shape("a", "fill", {"outline": nodes}, RED)
    lower["transform"] = {"x": 3, "y": -2, "rotate": 32, "scale_x": 1.3, "scale_y": 0.8, "flip_x": True}
    x0, y0, x1, y1 = dz.bounds(dz.geometry_points(lower))
    placed = dz.transform_geometry(lower, layout.Transform.from_dict(lower["transform"]), ((x0 + x1) / 2, (y0 + y1) / 2))
    outline = fill_parts(placed["geometry"]["outline"])[0]
    cx, cy = outline.centroid.x, outline.centroid.y
    upper = _square("b", cx - 4, cy - 12, 40, BLUE)  # runs off the right and the bottom
    off, on = _pair(lower, upper)
    assert on.items[0]["center_mm"] == pytest.approx(off.items[0]["center_mm"], abs=1e-6)
    assert _deepest(on, 0, _box_of(upper["geometry"]["outline"])) <= 1.4
    invariants.assert_sane(_mm_recs(on, 0), inside=outline.buffer(0.1), tolerance_mm=0.4)
    assert invariants.coverage(_mm_recs(on, 0), outline.difference(_box_of(upper["geometry"]["outline"])), 0.4) > 0.95


@pytest.mark.parametrize("turn", [0, 13, 45, 57, 73])
def test_a_cover_running_off_the_edge_leaves_no_rim(turn):
    """Where the cover runs past the fill's edge, the fill is cut right off there. A hair of fill
    left along the edge (turned edges don't meet exactly) is sewn as rows of tiny stitches, far
    under the cover."""
    lower, upper = _square("a", 0, 0, 40), _square("b", 20.3, -17.7, 80, BLUE)
    lower["transform"] = {"rotate": turn}
    on = layout.render(_layout(lower, upper, fabric="stretch"))  # the widest pull compensation
    assert _deepest(on, 0, _box_of(upper["geometry"]["outline"])) <= 1.4


def _turned(outline, kind="c", **transform):
    return _shape("a", "fill", {"outline": _nodes(outline, kind)}, RED, transform=transform)


# Found by trying random designs: where edges only just touch, GEOS adds stray lines to a result,
# which its next step refuses. The fill was then quietly sewn whole.
STRAY_LINES = {
    "satin over a turned curve": (0.5, None, [
        _turned([(70.613038, 38.657814), (65.888026, 53.090176), (48.278785, 47.333137), (51.072936, 33.134231),
                 (65.468682, 29.880036)], "s", rotate=171.932577, scale_x=1.27991, scale_y=1.223152, x=-1.00262,
                y=0.211178),
        {**_ribbon("b", [(68.684944, 48.04826), (41.714164, 75.01904), (14.743384, 48.04826), (41.714164, 21.07748)],
                   4.779638),
         "transform": {"rotate": -164.181651, "scale_x": 0.919011, "scale_y": 1.249481, "flip_x": True,
                       "x": -0.947916, "y": -0.196847}}]),
    "two fills over a square": (3.0, "knit", [
        _turned([(26.745032, 41.389671), (61.222131, 41.389671), (61.222131, 75.86677), (26.745032, 75.86677)]),
        _shape("b", "fill", {"outline": _nodes([(68.688139, 37.097559), (56.682752, 46.514268), (43.676394, 47.336161),
                                                (36.439661, 26.552657), (55.611896, 26.77718)], "s")}, BLUE),
        _shape("c", "fill", {"outline": _rect(35.192067, 39.737099, 48.574829, 53.119861),
                             "holes": [_rect(39.652988, 44.19802, 44.113909, 48.65894)]}, GREEN,
               transform={"rotate": 44.38121, "scale_x": 0.912226, "scale_y": 1.33193, "x": -2.314745,
                          "y": 0.785824})]),
}


@pytest.mark.parametrize("case", sorted(STRAY_LINES))
def test_edges_that_only_just_touch_are_still_trimmed(case):
    keep, fabric, items = STRAY_LINES[case]
    assert _holes(_layout(*items, keep=keep, fabric=fabric))


def test_a_pinhole_in_a_cover_leaves_no_dot_of_fill_under_it():
    """A speck of a gap in what's on top (a tight satin ring's middle, shapes that only just
    meet) isn't a reason to sew a patch of fill under it."""
    speck = _shape("b", "fill", {"outline": _rect(5, 5, 35, 35), "holes": [_rect(19.6, 19.6, 20.4, 20.4)]}, BLUE)
    on = layout.render(_layout(_square("a", 0, 0, 40), speck))
    assert not _near(on, 0, (20, 20), 3.0)


# ---------------------------------------------------------------- wholly hidden


def test_fully_hidden_fill_is_kept_with_a_note():
    lower, upper = _square("a", 15, 15, 10), _square("b", 0, 0, 40, BLUE)
    off, on = _pair(lower, upper)
    _same_item(off, on)  # left alone: still sewn, as before
    assert _notes(on) == [HIDDEN.format("Fill 1", "Fill 2")]
    assert not _notes(off)
    note = next(w for w in on.warnings if w["code"].startswith("overlap"))
    assert note["level"] == "warning"
    # Named as render() names them: the item's own name, if it has one.
    named = layout.render(_layout({**lower, "name": "Patch"}, {**upper, "name": "Big square"}))
    assert _notes(named) == [HIDDEN.format("Patch", "Big square")]


def test_every_hidden_fill_gets_its_own_note():
    same = _square("a", 0, 0, 30)  # the same shape on top: nothing of the lower one shows
    r = layout.render(_layout(same, _square("b", 4, 4, 10, GREEN), _square("c", 0, 0, 30, BLUE)))
    assert _notes(r) == [HIDDEN.format("Fill 1", "Fill 3"), HIDDEN.format("Fill 2", "Fill 3")]
    codes = [w["code"] for w in r.warnings if w["code"].startswith("overlap")]
    assert len(set(codes)) == 2
    assert _item_recs(r, 0) and _item_recs(r, 1)


def test_the_note_names_the_shape_that_hides_most_of_it():
    lower = _square("a", 10, 10, 20)
    left = _shape("l", "fill", {"outline": _rect(5, 5, 19.5, 35)}, GREEN)  # hides 9.5 mm of its width
    right = _shape("r", "fill", {"outline": _rect(17, 5, 42, 35)}, BLUE)  # hides 13 mm of it
    r = layout.render(_layout(lower, left, right))
    assert _notes(r) == [HIDDEN.format("Fill 1", "Fill 3")]
    # Two that hide just as much of it: the one sewn first.
    r = layout.render(_layout(lower, _square("b", 0, 0, 40, GREEN), _square("c", 0, 0, 40, BLUE)))
    assert _notes(r)[0] == HIDDEN.format("Fill 1", "Fill 2")


def test_hidden_under_lettering_is_named_like_the_lettering(font_path):  # noqa: F811
    dot = _square("a", -22, -5, 4)  # inside the I
    r = layout.render(_layout(dot, _text("b", font_path)))
    assert _notes(r) == [HIDDEN.format("Fill 1", "“IO”")]


# ---------------------------------------------------------------- settings and safety


@pytest.mark.parametrize("stored, used", [(0.1, 0.5), (-4, 0.5), (0.5, 0.5), (2.25, 2.25), (9, 3.0), (10 ** 400, 3.0),
                                          (None, 1.0), ("2", 1.0), (True, 1.0), (math.nan, 1.0), (math.inf, 1.0)])
def test_keep_mm_is_held_to_its_range_whatever_the_project_holds(stored, used):
    lower, upper = _square("a", 0, 0, 40), _square("b", 11, 9, 20, BLUE)
    assert _holes(_layout(lower, upper, keep=used))
    assert _holes(_layout(lower, upper, keep=stored)) == _holes(_layout(lower, upper, keep=used))


def test_the_pass_changes_a_copy_never_the_layout_it_was_given(font_path):  # noqa: F811
    lay = _layout(_square("a", 0, 0, 40), _square("b", 11, 9, 20, BLUE), _text("c", font_path, GREEN))
    before = json.dumps(lay, sort_keys=True)
    out = overlap.apply(lay)
    assert out is not lay and out["items"][0]["geometry"]["holes"]
    assert json.dumps(lay, sort_keys=True) == before
    assert out["items"][2] is lay["items"][2]  # nothing on top of it: the very same item
    # Its own holes stay, and the new one comes after them.
    own = _rect(2, 2, 6, 6)
    lower = _shape("a", "fill", {"outline": _rect(0, 0, 40, 40), "holes": [own]}, RED)
    holes = _holes(_layout(lower, _square("b", 11, 9, 20, BLUE)))
    assert holes[0] == own and len(holes) == 2


@pytest.mark.parametrize("bad", [
    _square("b", 11, 9, 20, BLUE, {"spacing_mm": "wide"}),
    _shape("b", "fill", {"outline": [[0, 0, "c"], [1, 1, "c"]]}, BLUE),
    _ribbon("b", [(0, 0), (30, 0)], 99, BLUE),
    {"id": "b", "kind": "text", "text": "  ", "font": {"path": "font.ttf"}, "size_mm": 10, "thread": BLUE},
    _square("b", 11, 9, 20, BLUE, transform={"scale_x": 0}),
])
def test_a_broken_shape_on_top_is_reported_as_always(bad):
    lower = _square("a", 0, 0, 40)
    with pytest.raises(LayoutError) as without:
        layout.render(_layout(lower, bad, on=None))
    with pytest.raises(LayoutError) as with_it:
        layout.render(_layout(lower, bad))
    assert str(with_it.value) == str(without.value)


# ---------------------------------------------------------------- snapshots


def _case(name, font):
    """The snapshot designs. Their numbers are uneven, away from zero, and the shapes on top are
    turned, so no stitch lands exactly where rounding could go either way."""
    if name == "fill_under_text":
        lower = _shape("a", "fill", {"outline": _rect(3.0131, 5.0277, 67.0131, 57.0277)}, RED)
        return _layout(lower, _text("b", font, transform={"x": 35.3719, "y": 30.8163, "rotate": 7}))
    lower = _square("a", 3.0131, 5.0277, 40)
    if name == "square_under_square":
        upper = _square("b", 14.3173, 13.7291, 20, BLUE)
        upper["transform"] = {"rotate": 7}
        return _layout(lower, upper)
    patch = _shape("b", "applique", {"outline": _rect(12.3131, 12.1277, 36.7131, 36.9277)}, BLUE)
    patch["transform"] = {"rotate": -11}
    return _layout(lower, patch)


SNAPSHOTS = ("square_under_square", "fill_under_text", "fill_under_applique")


def _thread_mm(r, item):
    xy = [(x / 10, y / 10, k) for x, y, k, _ in _item_recs(r, item)]
    return sum(math.dist(a[:2], b[:2]) for a, b in zip(xy, xy[1:]) if a[2] == b[2] == pe.STITCH)


@pytest.mark.parametrize("name", SNAPSHOTS)
def test_snapshots(name, font_path):  # noqa: F811
    lay = _case(name, font_path)
    r = layout.render(lay)
    off = layout.render({**lay, "remove_overlap": {"enabled": False, "keep_mm": 1.0}})
    assert _thread_mm(r, 0) < 0.9 * _thread_mm(off, 0)  # the case really hides something
    check("repair_overlap", name, digest_pattern(r.pattern))


@pytest.mark.parametrize("name", SNAPSHOTS)
def test_snapshot_stitches_do_not_turn_on_the_last_digit(name, font_path):  # noqa: F811
    """Processors round the last digit differently (an Apple-chip Mac did in Phase 3), so nudging
    every shape by a billionth of a millimetre must give the same stitches."""
    lay = _case(name, font_path)
    want = digest_pattern(layout.render(lay).pattern)
    rng = random.Random(7)
    for _ in range(4):
        items = []
        for it in lay["items"]:
            t = it.get("transform") or {}
            nudge = {"x": t.get("x", 0) + rng.uniform(-1e-9, 1e-9), "y": t.get("y", 0) + rng.uniform(-1e-9, 1e-9)}
            items.append({**it, "transform": {**t, **nudge}})
        assert digest_pattern(layout.render({**lay, "items": items}).pattern) == want
