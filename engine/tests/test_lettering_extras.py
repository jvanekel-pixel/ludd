"""Monogram styles and frames, and the shadow and outline that follow the text (P5-D2, P5-D3),
with the tiny font built in test_lettering.py. Also the leaf motif the laurel frame uses."""

import json
import math

import pytest
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, MultiPoint, Point, Polygon
from shapely.ops import unary_union

import invariants
from snapshot_util import check, digest_pattern
from threadline_engine import fabrics, layout, lettering
from threadline_engine.digitize import lines
from threadline_engine.digitize import stitches as dz
from threadline_engine.digitize.paths import flatten
from threadline_engine.layout import text as text_pipeline
from threadline_engine.lettering import LetteringError, extras, monogram
from threadline_engine.lettering.glyphs import Glyph
from threadline_engine.lettering.place import _centre, _move

from test_lettering import font_path, spec  # noqa: F401  (a tiny font built in the test)

RED = {"color": "#cc2222", "name": "Red", "catalog": "", "brand": ""}
BLUE = {"color": "#2222cc", "name": "Blue", "catalog": "", "brand": ""}
GREY = {"color": "#888888", "name": "Grey", "catalog": "", "brand": ""}
GREEN = {"color": "#22aa22", "name": "Green", "catalog": "", "brand": ""}

FRAMES = ["circle", "double_circle", "diamond", "square", "scallop_circle", "laurel"]
ROUND = {"circle", "double_circle", "scallop_circle", "laurel"}


def _item(font, **kw):
    return {"id": "t", "kind": "text", "text": "IOI", "font": {"path": font, "index": 0}, "size_mm": 12,
            "spacing_mm": 0, "style": "satin", "shape": {"type": "line"}, "monogram": False, "thread": RED,
            "transform": {}, "threads": [], "ops": [], **kw}


def _parts(item):
    before, letters, after, _ = text_pipeline._text_parts(item)
    return before, letters, after


def _render(item):
    return layout.render_summary({"items": [item], "merge_colors": False, "color_sort": False})


def _mono(font, text="IOI", size=25, **kw):
    return lettering.layout_text(spec(font, text=text, size_mm=size, monogram=True, **kw))[0]


def _bounds_by_letter(objs):
    """Each letter's box, in letter order."""
    found: dict = {}
    for o in objs:
        found.setdefault(o["letter"], []).extend(dz.geometry_points(o))
    return [dz.bounds(found[k]) for k in sorted(found)]


def _heights(boxes):
    return [y1 - y0 for _, y0, _, y1 in boxes]


def _area(objs):
    """What fill letters (or fill extras) cover."""
    shapes = []
    for o in objs:
        assert o["kind"] == "fill"
        g = o["geometry"]
        holes = [flatten(h, True)[0] for h in g.get("holes") or []]
        shapes.append(Polygon(flatten(g["outline"], True)[0], holes))
    return unary_union(shapes)


def _sane(obj, **kw):
    recs = dz.generate(fabrics.apply(obj, "woven"))[0]
    invariants.assert_sane(recs, **kw)
    return recs


def _sewn_lines(recs):
    return [LineString([a[:2], b[:2]]) for a, b in zip(recs, recs[1:]) if a[2] == b[2] == dz.STITCH and a[:2] != b[:2]]


def _densified(points, step=0.2):
    line = LineString(points)
    n = max(1, math.ceil(line.length / step))
    return [line.interpolate(k / n, normalized=True) for k in range(n + 1)]


# ---------------------------------------------------------------- monogram styles (P5-D2)


@pytest.mark.parametrize("text,heights", [("I", [25]), ("IO", [17.5, 25]), ("IOI", [17.5, 25, 17.5]),
                                          (" I O I ", [17.5, 25, 17.5])])
def test_monogram_one_two_three_letters(font_path, text, heights):
    objs = _mono(font_path, text)
    boxes = _bounds_by_letter(objs)
    assert _heights(boxes) == pytest.approx(heights, abs=0.05)
    for _, y0, _, y1 in boxes:  # each letter's middle on the big letter's middle
        assert (y0 + y1) / 2 == pytest.approx(0, abs=0.05)
    for a, b in zip(boxes, boxes[1:]):
        assert b[0] > a[2]  # left to right, none overlapping
    x0, _, x1, _ = dz.bounds([p for o in objs for p in dz.geometry_points(o)])
    assert (x0 + x1) / 2 == pytest.approx(0, abs=0.05)
    for style in (None, "classic", "block", "stacked"):
        with pytest.raises(LetteringError, match="one, two or three letters"):
            lettering.layout_text(spec(font_path, text="IOIX", monogram=True, monogram_style=style))


def _classic_as_before(letters, size, spacing, glyphs_for):
    """The monogram LUDD sewed before monogram styles (copied unchanged): three letters."""
    objects = []
    letters = letters[:3]
    sizes = [size * 0.7, size, size * 0.7]
    parts = []
    for c, s in zip(letters, sizes):
        got = glyphs_for(c, s)
        parts.append(got[0] if got else Glyph([], 0.0))
    gap = size * 0.12
    widths = [p.advance - spacing for p in parts]
    total = sum(widths) + 2 * gap
    x = -total / 2
    for p, w, s in zip(parts, widths, sizes):
        dy = s / 2 - size / 2
        objects += [_move(o, lambda a, b, x0=x, dy=dy: (a + x0, b + size / 2 + dy)) for o in p.objects]
        x += w + gap
    return _centre(objects, vertical=False)


@pytest.mark.parametrize("text,spacing", [("IOI", 0.0), ("XOI", 1.5), ("OIX", -0.5), ("IZO", 0.0)])
def test_classic_monogram_is_unchanged(font_path, text, spacing):
    def glyphs_for(t, sz):
        return lettering._outline_glyphs(t, font_path, 0, sz, spacing, "satin")

    want = _classic_as_before(list(text), 25.0, spacing, glyphs_for)
    assert want
    assert monogram.layout(list(text), 25.0, spacing, glyphs_for) == want
    assert monogram.layout(list(text), 25.0, spacing, glyphs_for, "classic") == want


def test_block_and_stacked_layouts(font_path):
    block = _bounds_by_letter(_mono(font_path, "IOI", monogram_style="block"))
    assert _heights(block) == pytest.approx([25, 25, 25], abs=0.05)
    for _, y0, _, y1 in block:  # one baseline, centred top to bottom
        assert (y0, y1) == pytest.approx((-12.5, 12.5), abs=0.05)
    for a, b in zip(block, block[1:]):
        assert b[0] > a[2]
    assert (block[0][0] + block[-1][2]) / 2 == pytest.approx(0, abs=0.05)
    assert _heights(_bounds_by_letter(_mono(font_path, "IO", monogram_style="block"))) == pytest.approx([25, 25], abs=0.05)

    small = 25 * (1 - 0.06) / 2  # two small letters and the space between them are as tall as the big one
    top, bottom, big = _bounds_by_letter(_mono(font_path, "IOI", monogram_style="stacked"))
    assert _heights([top, bottom, big]) == pytest.approx([small, small, 25], abs=0.05)
    assert top[1] == pytest.approx(-12.5, abs=0.05) and bottom[3] == pytest.approx(12.5, abs=0.05)
    assert bottom[1] - top[3] == pytest.approx(25 * 0.06, abs=0.05)
    assert (top[0] + top[2]) / 2 == pytest.approx((bottom[0] + bottom[2]) / 2, abs=0.05)  # one over the other
    assert (big[1], big[3]) == pytest.approx((-12.5, 12.5), abs=0.05)
    assert big[0] - max(top[2], bottom[2]) == pytest.approx(25 * 0.12, abs=0.05)  # then the big one
    assert (min(top[0], bottom[0]) + big[2]) / 2 == pytest.approx(0, abs=0.05)

    one, then_big = _bounds_by_letter(_mono(font_path, "IO", monogram_style="stacked"))
    assert _heights([one, then_big]) == pytest.approx([small, 25], abs=0.05)
    assert (one[1] + one[3]) / 2 == pytest.approx(0, abs=0.05) and then_big[0] > one[2]
    assert _heights(_bounds_by_letter(_mono(font_path, "O", monogram_style="stacked"))) == pytest.approx([25], abs=0.05)

    assert monogram.smallest_letter(25, "classic") == pytest.approx(17.5)
    assert monogram.smallest_letter(25, "block") == pytest.approx(25)
    assert monogram.smallest_letter(25, "stacked") == pytest.approx(small)
    _, warnings = lettering.layout_text(spec(font_path, text="IOI", size_mm=12, monogram=True, monogram_style="stacked"))
    assert any("hard to stitch" in w for w in warnings)
    _, warnings = lettering.layout_text(spec(font_path, text="IOI", size_mm=7, monogram=True, monogram_style="block"))
    assert not warnings
    with pytest.raises(LetteringError, match="monogram style"):
        lettering.layout_text(spec(font_path, text="IOI", monogram=True, monogram_style="fancy"))


# ---------------------------------------------------------------- frames (P5-D2)


@pytest.mark.parametrize("frame_id", FRAMES)
def test_each_frame_surrounds_the_monogram(font_path, frame_id):
    margin = 4.0
    item = _item(font_path, text="IOI", monogram=True, size_mm=25, ornament={"id": frame_id, "margin_mm": margin})
    before, letters, after = _parts(item)
    assert before == []
    assert after and all(o["extra"] == "frame" and o["kind"] == "run" and o["thread"] is None for o in after)
    letter_points = [p for o in letters for p in dz.geometry_points(o)]
    x0, y0, x1, y1 = dz.bounds(letter_points)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    sewn, sewn_lines = [], []
    for o in after:
        recs = _sane(o)
        sewn += invariants.stitch_points(recs)
        sewn_lines += _sewn_lines(recs)
    if frame_id in ROUND:
        # Every letter point is inside the circle the frame's inner edge is on, `margin` from it.
        inner = min(math.dist((cx, cy), p) for p in sewn)
        farthest = max(math.dist((cx, cy), p) for p in letter_points)
        assert farthest < inner
        assert inner - farthest == pytest.approx(margin, abs=0.5)
        sx0, _, sx1, _ = dz.bounds(sewn)
        assert (sx0 + sx1) / 2 == pytest.approx(cx, abs=0.5)  # centred on the monogram
    else:
        shape = Polygon(flatten(after[0]["geometry"]["nodes"], True)[0])
        assert all(shape.contains(Point(p)) for p in letter_points)
        gap = min(MultiLineString(sewn_lines).distance(Point(p)) for p in letter_points)
        assert gap == pytest.approx(margin, abs=0.5)
        sx0, sy0, sx1, sy1 = dz.bounds(sewn)
        assert ((sx0 + sx1) / 2, (sy0 + sy1) / 2) == pytest.approx((cx, cy), abs=0.3)


def test_the_double_circle_and_scallop_frames(font_path):
    item = _item(font_path, monogram=True, size_mm=25, ornament={"id": "double_circle"})
    inner, outer = _parts(item)[2]
    radius = lambda o: max(math.hypot(x, y) for x, y in flatten(o["geometry"]["nodes"], True)[0])  # noqa: E731
    assert radius(outer) - radius(inner) == pytest.approx(2.0, abs=0.1)
    item = _item(font_path, monogram=True, size_mm=25, ornament={"id": "scallop_circle"})
    (scallop,) = _parts(item)[2]
    assert scallop["params"]["style"] == "motif" and scallop["params"]["motif"] == "scallop"
    letters = _parts(item)[1]
    cx, cy = _centre_of(letters)
    radii = [math.dist((cx, cy), p) for p in invariants.stitch_points(dz.generate(scallop)[0])]
    # Round and evenly scalloped: bumps point out from the circle its inner points are on.
    assert max(radii) - min(radii) == pytest.approx(scallop["params"]["motif_width_mm"] / 2, abs=0.1)
    ring = Polygon(flatten(scallop["geometry"]["nodes"], True)[0])
    r = math.sqrt(ring.area / math.pi)
    assert min(radii) == pytest.approx(r - scallop["params"]["motif_width_mm"] / 4, abs=0.15)


def _centre_of(letters):
    x0, y0, x1, y1 = dz.bounds([p for o in letters for p in dz.geometry_points(o)])
    return (x0 + x1) / 2, (y0 + y1) / 2


def test_the_laurel_is_two_leafy_branches_open_at_the_top(font_path):
    item = _item(font_path, monogram=True, size_mm=25, ornament={"id": "laurel"})
    _, letters, after = _parts(item)
    assert len(after) == 2 and all(o["params"]["motif"] == "leaf" and not o["geometry"].get("closed") for o in after)
    cx, cy = _centre_of(letters)
    sewn = [p for o in after for p in invariants.stitch_points(dz.generate(o)[0])]
    angles = [math.degrees(math.atan2(y - cy, x - cx)) % 360 for x, y in sewn]
    assert not [a for a in angles if abs(a - 270) < 20]  # open at the top (y is down)
    left, right = [p for p in sewn if p[0] < cx], [p for p in sewn if p[0] > cx]
    mirrored = MultiPoint([(2 * cx - x, y) for x, y in left])
    assert max(mirrored.distance(Point(p)) for p in right) < 1.0  # the two branches mirror each other


@pytest.mark.parametrize("margin,same_as", [(None, 4.0), (0.0, 2.0), (40.0, 15.0)])
def test_the_frame_margin_is_kept_in_range(font_path, margin, same_as):
    def frame(m):
        ornament = {"id": "circle"} if m is None else {"id": "circle", "margin_mm": m}
        return _parts(_item(font_path, monogram=True, size_mm=25, ornament=ornament))[2]

    assert frame(margin) == frame(same_as)


def test_a_frame_sews_after_the_letters_in_its_own_thread(font_path):
    item = _item(font_path, monogram=True, size_mm=25, ornament={"id": "square", "thread": BLUE})
    s = _render(item)
    assert [r["what"] for r in s["items"][0]["runs"]] == ["letters", "frame"]
    assert [s["threads"][b["thread"]]["color"] for b in s["blocks"]] == [RED["color"], BLUE["color"]]
    # Without its own thread it sews in the text's, and an Order & colors change reaches it too.
    s = _render(_item(font_path, monogram=True, size_mm=25, ornament={"id": "square"}, threads=[GREEN]))
    assert {s["threads"][b["thread"]]["color"] for b in s["blocks"]} == {GREEN["color"]}
    shapes = layout.text_to_shapes(item)["objects"]
    assert shapes[-1]["kind"] == "run" and shapes[-1]["name"] == "IOI frame 1"
    assert shapes[-1]["thread"]["color"] == BLUE["color"]


def test_frames_are_for_monograms(font_path):
    assert _parts(_item(font_path, ornament={"id": "circle"}))[2] == []
    with pytest.raises(layout.LayoutError, match="frame"):
        _render(_item(font_path, monogram=True, ornament={"id": "octagon"}))


# ---------------------------------------------------------------- shadow (P5-D3)


def test_shadow_is_only_the_part_that_shows(font_path):
    item = _item(font_path, text="IOX", shadow={"dx_mm": 0.8, "dy_mm": 0.8, "thread": GREY})
    before, letters, after = _parts(item)
    assert after == [] and before
    assert all(o["kind"] == "fill" and o["extra"] == "shadow" and o["thread"] == GREY for o in before)
    assert all(o["params"]["spacing_mm"] == 0.35 for o in before)  # satin-look fills
    covered, shadow = _area(letters), _area(before)
    assert shadow.intersection(covered).area < 0.2
    moved = affinity.translate(covered, 0.8, 0.8)
    assert shadow.difference(moved.buffer(0.05)).area < 0.05
    assert shadow.area == pytest.approx(moved.difference(covered).area, rel=0.05) and shadow.area > 10
    assert all(_area([o]).area >= 0.5 for o in before)
    for o in before:
        _sane(o)
    # Left to right, the way the letters sew (rounded, as the pieces are put in order).
    lefts = [round(dz.bounds(dz.geometry_points(o))[0], 2) for o in before]
    assert lefts == sorted(lefts)


def test_shadow_offsets(font_path):
    def shadow(**s):
        before, letters, _ = _parts(_item(font_path, text="IO", shadow={"thread": GREY, **s}))
        return before, letters

    assert shadow()[0] == shadow(dx_mm=0.8, dy_mm=0.8)[0]  # the defaults
    assert shadow(dx_mm=10, dy_mm=-10)[0] == shadow(dx_mm=3, dy_mm=-3)[0]  # each -3 to 3 mm
    assert shadow(dx_mm=0, dy_mm=0)[0] == []  # nothing would show
    before, letters = shadow(dx_mm=0, dy_mm=1.0)  # 0 is a real value: only downwards
    lx0, ly0, lx1, ly1 = dz.bounds([p for o in letters for p in dz.geometry_points(o)])
    sx0, sy0, sx1, sy1 = dz.bounds([p for o in before for p in dz.geometry_points(o)])
    assert sx0 >= lx0 - 0.05 and sx1 <= lx1 + 0.05 and sy1 == pytest.approx(ly1 + 1.0, abs=0.05) and sy0 > ly0 + 0.5


def test_small_slivers_are_left_out(font_path):
    # A shift smaller than a thread leaves only slivers under 0.5 mm2: no shadow.
    assert _parts(_item(font_path, text="IO", shadow={"dx_mm": 0.03, "dy_mm": 0.0, "thread": GREY}))[0] == []


def _rail(points):
    return [[x, y, "c"] for x, y in points]


PARTS = {
    "column": {"kind": "satin", "geometry": {"rail_a": _rail([(0, 0), (0, 10)]), "rail_b": _rail([(3, 0), (3, 10)])},
               "params": {}},
    "closed_column": {"kind": "satin", "geometry": {
        "rail_a": _rail([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]),
        "rail_b": _rail([(2, 2), (8, 2), (8, 8), (2, 8), (2, 2)])}, "params": {}},
    "ribbon": {"kind": "satin", "geometry": {"nodes": _rail([(0, 0), (0, 10)]), "width_mm": 2.0}, "params": {}},
    "closed_ribbon": {"kind": "satin", "geometry": {"nodes": _rail([(0, 0), (8, 0), (8, 8), (0, 8)]), "width_mm": 1.6,
                                                    "closed": True}, "params": {}},
    "run": {"kind": "run", "geometry": {"nodes": _rail([(0, 0), (6, 10), (12, 0)])}, "params": {}},
}


@pytest.mark.parametrize("name", sorted(PARTS))
def test_extras_follow_every_kind_of_letter_part(name):
    settings = {"shadow": {"dx_mm": 0.9, "dy_mm": 0.7, "thread": GREY},
                "outline": {"gap_mm": 1.0, "width_mm": 1.5, "style": "satin", "thread": BLUE}}
    before, after = extras.build(settings, [{**PARTS[name], "letter": 0, "line": 0}])
    assert before and after
    for o in before + after:
        _sane(o)
    if name == "run":  # a single line casts a line
        assert all(o["kind"] == "run" and o["extra"] == "shadow" for o in before)
        shadow = unary_union([LineString(flatten(o["geometry"]["nodes"])[0]) for o in before])
        line = LineString(flatten(PARTS[name]["geometry"]["nodes"])[0])
        assert shadow.difference(affinity.translate(line, 0.9, 0.7).buffer(0.1)).length < 0.5
    else:
        shadow = _area(before)
        covered = _covered(PARTS[name])
        assert shadow.intersection(covered).area < 0.2 and shadow.area > 1
        if name in ("closed_column", "closed_ribbon"):  # the shadow shows inside the ring too
            hole = Polygon(max(covered.interiors, key=lambda r: Polygon(r).area))
            assert shadow.intersection(hole).area > 1
    outline = LineString(flatten(after[0]["geometry"]["nodes"], True)[0])
    assert outline.distance(_covered(PARTS[name])) == pytest.approx(1.0 + 0.75, abs=0.2)


def _covered(part):
    g = part["geometry"]
    if part["kind"] == "run":
        return LineString(flatten(g["nodes"])[0]).buffer(0.2)
    if "nodes" in g:
        pts = flatten(g["nodes"], g.get("closed", False))[0]
        line = LineString(pts + pts[:1]) if g.get("closed") else LineString(pts)
        return line.buffer(g["width_mm"] / 2, cap_style="flat")
    a, b = flatten(g["rail_a"])[0], flatten(g["rail_b"])[0]
    if a[0] == a[-1]:
        return Polygon(a).difference(Polygon(b))
    return Polygon(a + b[::-1])


def test_stitched_letters_get_a_frame_but_no_shadow_or_outline():
    nodes = [[40, 40, "j"], [0, 0, "s"], [5, 0, "s"], [5, -8, "s"], [0, -8, "s"], [0, -8, "t"], [-40, -40, "j"]]
    part = {"kind": "stitches", "geometry": {"nodes": nodes}, "letter": 0, "line": 0}
    before, after = extras.build({"shadow": {"thread": GREY}, "outline": {"thread": BLUE}, "monogram": True,
                                  "ornament": {"id": "circle"}}, [part])
    assert before == [] and [o["extra"] for o in after] == ["frame"]
    radius = max(math.dist((2.5, -4), (x, y)) for x, y, *_ in after[0]["geometry"]["nodes"])
    assert radius == pytest.approx(math.hypot(2.5, 4) + 4, abs=0.05)  # round its stitches, not its jumps


def test_no_extras_unless_asked(font_path):
    assert extras.build({"shadow": None, "outline": None, "ornament": None, "monogram": True},
                        _mono(font_path)) == ([], [])


# ---------------------------------------------------------------- outline (P5-D3)


def test_shadow_sews_before_outline_after(font_path):
    item = _item(font_path, text="IO", monogram=True, size_mm=20, ornament={"id": "circle", "thread": GREEN},
                 shadow={"dx_mm": 0.8, "dy_mm": 0.8, "thread": GREY},
                 outline={"gap_mm": 1.0, "width_mm": 1.5, "style": "satin", "thread": BLUE})
    s = _render(item)
    assert [r["what"] for r in s["items"][0]["runs"]] == ["shadow", "letters", "frame", "outline"]
    assert [s["threads"][b["thread"]]["color"] for b in s["blocks"]] == [
        GREY["color"], RED["color"], GREEN["color"], BLUE["color"]]


@pytest.mark.parametrize("style,gap,width", [("run", 1.0, 1.5), ("satin", 1.0, 1.5), ("satin", 2.5, 3.0),
                                             ("run", 0.0, 1.5), ("satin", 0.0, 1.0)])
def test_outline_follows_the_gap(font_path, style, gap, width):
    item = _item(font_path, text="IOX", outline={"gap_mm": gap, "width_mm": width, "style": style, "thread": BLUE})
    before, letters, after = _parts(item)
    assert before == [] and after
    covered = _area(letters)
    reach = gap + (width / 2 if style == "satin" else 0)  # a satin's near edge is `gap` from the letters
    for o in after:
        g = o["geometry"]
        assert o["extra"] == "outline" and o["thread"] == BLUE and g["closed"]
        if style == "satin":
            assert o["kind"] == "satin" and g["width_mm"] == width
            assert all(n[2] == "s" for n in g["nodes"])  # a mitred corner would spike into the letters
        else:
            assert o["kind"] == "run" and o["params"]["style"] == "triple"
        pts = flatten(g["nodes"], True)[0]
        for p in _densified(pts + pts[:1]):
            d = covered.distance(p) if reach else covered.boundary.distance(p)
            assert reach - 0.2 <= d <= reach + 0.2, (round(p.x, 2), round(p.y, 2), round(d, 2))
        recs = _sane(o)
        if style == "satin" and gap:
            # Its stitches keep the gap too, corners included (a little pull compensation aside).
            nearest = min(covered.distance(Point(p)) for p in invariants.stitch_points(recs))
            assert nearest >= gap - 0.35, round(nearest, 2)


def test_outline_defaults_and_ranges(font_path):
    def outline(**o):
        return _parts(_item(font_path, text="IO", outline={"thread": BLUE, **o}))[2]

    assert outline() == outline(gap_mm=1.0, width_mm=1.5, style="satin")
    assert outline(gap_mm=9, width_mm=9) == outline(gap_mm=5, width_mm=4)
    assert outline(gap_mm=-1, width_mm=0.2) == outline(gap_mm=0, width_mm=1)
    with pytest.raises(layout.LayoutError, match="must be a number"):
        outline(gap_mm="wide")


def test_outline_follows_the_text_as_it_is_edited(font_path):
    def box(text):
        after = _parts(_item(font_path, text=text, outline={"style": "run", "thread": BLUE}))[2]
        return dz.bounds([p for o in after for p in dz.geometry_points(o)])

    assert box("IOXOI")[2] - box("IOXOI")[0] > box("IO")[2] - box("IO")[0] + 10
    # Letters far apart each get their own line, sewn left to right.
    item = _item(font_path, text="I I", spacing_mm=6, outline={"style": "run", "gap_mm": 0.5, "thread": BLUE})
    after = _parts(item)[2]
    assert len(after) == 2
    assert dz.bounds(dz.geometry_points(after[0]))[2] < dz.bounds(dz.geometry_points(after[1]))[0]


def test_extras_are_the_same_every_time(font_path):
    item = _item(font_path, text="IOX", monogram=True, ornament={"id": "laurel"}, shadow={"thread": GREY},
                 outline={"thread": BLUE})
    first = json.dumps(_parts(item))
    layout._text_cache.clear()
    extras._cache.clear()
    assert json.dumps(_parts(item)) == first
    assert json.dumps(_parts(item)) == first  # and from the cache


def test_a_cached_extra_is_a_fresh_copy(font_path):
    letters = _mono(font_path, "IO")
    settings = {"shadow": {"thread": dict(GREY)}, "outline": {"thread": dict(BLUE)}}
    before, after = extras.build(settings, letters)
    before[0]["geometry"]["outline"].clear()
    after[0]["thread"]["color"] = "#000000"
    again_before, again_after = extras.build(settings, letters)
    assert again_before[0]["geometry"]["outline"] and again_after[0]["thread"]["color"] == BLUE["color"]
    moved = [{**o, "geometry": {**o["geometry"], "outline": [[x + 1, y, k] for x, y, k in o["geometry"]["outline"]],
                                "holes": []}} for o in letters]
    assert extras.build(settings, moved)[0] != again_before  # other letters, other extras


def test_break_into_shapes_includes_the_extras(font_path):
    item = _item(font_path, text="IO", shadow={"thread": GREY}, outline={"thread": BLUE})
    names = [o["name"] for o in layout.text_to_shapes(item)["objects"]]
    assert names[0] == "IO shadow 1" and names[-1] == "IO outline 1" and "IO 1" in names


# ---------------------------------------------------------------- the leaf motif


def test_the_leaf_motif():
    assert list(lines.MOTIF_UNITS)[:4] == ["wave", "zigzag", "scallop", "blanket"] and "leaf" in lines.MOTIF_UNITS
    unit = lines.MOTIF_UNITS["leaf"]
    assert unit[0] == (0.0, 0.0) and unit[-1] == (1.0, 0.0)  # repeats join along the stem
    assert all(0 <= u <= 1 and -0.5 <= v <= 0.5 for u, v in unit)
    assert max(v for _, v in unit) == 0.5
    # The same on both sides of the line, so a laurel's two branches mirror each other.
    assert sorted((round(u, 3), round(v, 3)) for u, v in unit) == sorted((round(u, 3), round(-v, 3)) for u, v in unit)
    recs = dz.generate({"kind": "run", "geometry": {"nodes": [[0, 0, "c"], [40, 0, "c"]]},
                        "params": {"style": "motif", "motif": "leaf"}})[0]
    invariants.assert_sane(recs, inside=LineString([(0, 0), (40, 0)]).buffer(1.25, cap_style="flat"))
    ys = [y for _, y in invariants.stitch_points(recs)]
    assert max(ys) - min(ys) == pytest.approx(2.5, abs=0.01)


# ---------------------------------------------------------------- snapshots


SNAPSHOTS = {
    "monogram_block": lambda f: _item(f, text="IOX", monogram=True, size_mm=20, monogram_style="block"),
    "monogram_scallop_frame": lambda f: _item(f, text="IOI", monogram=True, size_mm=25,
                                              ornament={"id": "scallop_circle", "thread": BLUE}),
    # Not 0.8: that's also the sliver width _satin_angle counts, and a strip exactly that wide could
    # round differently on another computer.
    "shadow": lambda f: _item(f, text="IOX", shadow={"dx_mm": 0.87, "dy_mm": 0.73, "thread": GREY}),
    "outline_satin": lambda f: _item(f, text="IOX", outline={"gap_mm": 1.0, "width_mm": 1.5, "style": "satin",
                                                             "thread": BLUE}),
}


@pytest.mark.parametrize("name", sorted(SNAPSHOTS))
def test_snapshots(name, font_path):
    r = layout.render({"items": [SNAPSHOTS[name](font_path)], "merge_colors": False, "color_sort": False,
                       "basting": {"enabled": False}})
    check("lettering_extras", name, digest_pattern(r.pattern))
