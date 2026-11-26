"""True satin letters (P5-B1) and small letters (P5-B2), with a font built in the test (I, O, T,
L, X, a thin l and a square blob), so they run the same on any machine."""

import math

import pytest
import shapely
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from shapely import affinity
from shapely.geometry import MultiPoint, Point, Polygon, box

from invariants import assert_sane
from snapshot_util import check, digest_pattern
from test_lettering import _rect
from threadline_engine import layout, lettering
from threadline_engine.digitize import stitches as dz
from threadline_engine.lettering import glyphs, satin
from threadline_engine.lettering.fonts import _glyph_shapes, _load

UPM = 1000
CAP = 700
SIZE = 12.0
K = SIZE / CAP  # mm per font unit at 12 mm


def _poly(pen, pts):
    pen.moveTo(pts[0])
    for p in pts[1:]:
        pen.lineTo(p)
    pen.closePath()


def _ellipse(cx, cy, rx, ry, clockwise=True, n=64):
    pts = [(round(cx + rx * math.cos(2 * math.pi * i / n)), round(cy + ry * math.sin(2 * math.pi * i / n))) for i in range(n)]
    return pts[::-1] if clockwise else pts


@pytest.fixture(scope="module")
def font(tmp_path_factory):
    """I (a bar), O (an oval ring), T, L, X (two crossing slanted bars), l (a hairline) and B (a
    square blob 10 mm wide at 12 mm), plus space."""
    glyphs_ = {}

    def glyph(name, draw):
        pen = TTGlyphPen(None)
        draw(pen)
        glyphs_[name] = pen.glyph()

    glyph(".notdef", lambda pen: None)
    glyph("I", lambda pen: _rect(pen, 100, 0, 250, CAP))

    def o(pen):
        _poly(pen, _ellipse(325, 350, 275, 350))
        _poly(pen, _ellipse(325, 350, 135, 210, clockwise=False))

    glyph("O", o)

    def t(pen):
        _rect(pen, 50, 580, 600, CAP)  # the bar
        _rect(pen, 270, 0, 380, 600)  # the stem, overlapping it

    glyph("T", t)

    def ell(pen):
        _rect(pen, 100, 0, 240, CAP)
        _rect(pen, 100, 0, 520, 130)

    glyph("L", ell)

    def x(pen):  # both bars clockwise, so where they overlap is filled once (not a hole)
        _poly(pen, [(50, 0), (460, 700), (600, 700), (190, 0)])
        _poly(pen, [(460, 0), (50, 700), (190, 700), (600, 0)])

    glyph("X", x)
    glyph("l", lambda pen: _rect(pen, 100, 0, 140, CAP))
    glyph("B", lambda pen: _rect(pen, 50, 0, 50 + round(10 / K), round(10 / K)))
    glyph("space", lambda pen: None)

    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(list(glyphs_))
    cmap = {ord(c): c for c in "IOTLXlB"}
    cmap[ord(" ")] = "space"
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs_)
    widths = {".notdef": 500, "I": 350, "O": 650, "T": 650, "L": 570, "X": 650, "l": 240, "B": 700, "space": 300}
    lsb = {"I": 100, "L": 100, "l": 100}  # each glyph's drawn left edge, so shapes sit where drawn
    fb.setupHorizontalMetrics({k: (v, lsb.get(k, 50 if k not in (".notdef", "space") else 0)) for k, v in widths.items()})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Satin Test", "styleName": "Regular"})
    fb.setupOS2(sCapHeight=CAP, sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    path = tmp_path_factory.mktemp("fonts") / "SatinTest.ttf"
    fb.save(str(path))
    return str(path)


def shapes_of(font, ch, size=SIZE):
    lf = _load(font, 0)
    return _glyph_shapes(lf, lf.cmap[ord(ch)], size / lf.cap)


def letter(font, ch, size=SIZE):
    """The letter's single shape and its true satin objects."""
    (shape,) = shapes_of(font, ch, size)
    return shape, glyphs._glyph_objects([shape], "columns", size)


def satins(objs):
    return [o for o in objs if o["kind"] == "satin"]


def fills(objs):
    return [o for o in objs if o["kind"] == "fill"]


def rails(o):
    g = o["geometry"]
    return [(n[0], n[1]) for n in g["rail_a"]], [(n[0], n[1]) for n in g["rail_b"]]


def column_area(o):
    a, b = rails(o)
    return shapely.union_all([MultiPoint([a[i], a[i + 1], b[i + 1], b[i]]).convex_hull for i in range(len(a) - 1)])


def fill_area(o):
    g = o["geometry"]
    return Polygon([(n[0], n[1]) for n in g["outline"]], [[(n[0], n[1]) for n in h] for h in g.get("holes") or []])


def area_of(objs):
    return shapely.union_all([column_area(o) if o["kind"] == "satin" else fill_area(o) for o in objs])


def at(u, v):
    """A font-unit point in mm (y down) at 12 mm."""
    return (u * K, -v * K)


def test_I_is_one_column_as_wide_as_its_stem(font):
    _, objs = letter(font, "I")
    assert len(satins(objs)) == 1 and not fills(objs)
    a, b = rails(satins(objs)[0])
    stem = 150 * K
    assert all(abs(math.dist(p, q) - stem) <= 0.2 for p, q in zip(a, b))
    assert satins(objs)[0]["params"]["underlay"] == "auto"
    assert satins(objs)[0]["params"]["spacing_mm"] == 0.36 and satins(objs)[0]["params"]["comp_by_width"] is True


def test_O_is_one_closed_column(font):
    _, objs = letter(font, "O")
    assert len(satins(objs)) == 1
    a, b = rails(satins(objs)[0])
    assert math.dist(a[0], a[-1]) <= 0.3 and math.dist(b[0], b[-1]) <= 0.3
    assert len(a) > 20  # it goes all the way round


def test_T_is_two_strokes_and_the_join_is_covered(font):
    shape, objs = letter(font, "T")
    cols = satins(objs)
    assert len(cols) == 2
    both = shapely.union_all([column_area(o) for o in cols])
    # Where the stem meets the bar: the bar's depth over the stem, and a millimetre of the stem below it.
    x0, _ = at(270, 0)
    x1, _ = at(380, 0)
    _, y_top = at(0, CAP)
    _, y_bar = at(0, 580)
    join = box(x0, y_top, x1, y_bar + 1.0).intersection(shape)
    assert join.difference(both).area < 0.05


def test_L_keeps_its_corner_full(font):
    shape, objs = letter(font, "L")
    assert len(satins(objs)) == 2
    x0, y0 = at(100, 0)
    x1, y1 = at(240, 130)
    corner = box(x0, y1, x1, y0).intersection(shape)
    gaps = corner.difference(area_of(objs))
    parts = getattr(gaps, "geoms", [gaps])
    assert all(p.area <= 0.3 for p in parts)


def test_X_crossing_is_covered_once_through(font):
    shape, objs = letter(font, "X")
    cols = satins(objs)
    centre = at(325, 350)
    through = [o for o in cols if column_area(o).buffer(1e-6).contains(Point(centre).buffer(0.3))]
    assert len(through) == 1  # one stroke runs straight through the crossing
    others = [o for o in cols if o is not through[0]]
    assert len(others) == 2  # the other stroke's two halves meet it
    over = column_area(through[0])
    for o in others:
        meet = column_area(o).intersection(over)
        assert meet.area > 0.1  # they reach into it, so the join is covered ...
        assert not column_area(o).contains(Point(centre))  # ... but stop before sewing the crossing again
    crossing = Point(centre).buffer(1.5).intersection(shape)
    assert crossing.difference(area_of(cols)).area < 0.05


@pytest.mark.parametrize("ch", list("IOTLX"))
def test_columns_cover_the_letter(font, ch):
    shape, objs = letter(font, ch)
    assert satins(objs)
    sewn = area_of(objs)
    assert sewn.intersection(shape).area >= 0.97 * shape.area
    assert sewn.difference(shape.buffer(0.3)).area < 1e-3


def test_wide_blob_stays_a_fill(font):
    shape, objs = letter(font, "B")
    assert shape.bounds[2] - shape.bounds[0] == pytest.approx(10, abs=0.05)
    assert objs and not satins(objs)


@pytest.mark.parametrize("ch", list("IOTLX"))
def test_columns_pass_the_invariants(font, ch):
    shape, objs = letter(font, ch)
    for o in objs:
        recs, _ = dz.generate(o)
        assert_sane(recs, inside=shape, max_stitch_mm=7.15)


def test_columns_ignore_rounding_noise(font):
    """The same letter nudged by rounding-sized amounts gives exactly the same columns (ties are
    broken by rule, not by floating-point order)."""
    for ch in "IOTLX":
        (shape,) = shapes_of(font, ch)
        plain = satin.columns(shape, SIZE)
        noisy = Polygon([(x + 3e-9 * ((i % 3) - 1), y - 2e-9 * ((i % 2) * 2 - 1)) for i, (x, y) in enumerate(shape.exterior.coords[:-1])],
                        [list(h.coords)[:-1] for h in shape.interiors])
        assert satin.columns(noisy, SIZE) == plain, ch


def test_columns_follow_a_slanted_letter(font):
    (shape,) = shapes_of(font, "I")
    slanted = affinity.skew(shape, xs=-12, origin=(0, 0))
    objs = satin.columns(slanted, SIZE)
    assert len(satins(objs)) == 1
    a, _ = rails(satins(objs)[0])
    top, bottom = min(a, key=lambda p: p[1]), max(a, key=lambda p: p[1])
    assert top[0] > bottom[0] + 1  # the column leans with the letter


def _item(font, **kw):
    return {"id": "t", "kind": "text", "text": "IOT", "font": {"path": font, "index": 0}, "size_mm": SIZE,
            "spacing_mm": 0, "style": "columns", "shape": {"type": "line"}, "monogram": False,
            "thread": {"color": "#cc2222", "name": "Red", "catalog": "", "brand": ""},
            "transform": {}, "threads": [], "ops": [], **kw}


def _plain(items):
    return {"items": items, "merge_colors": False, "color_sort": False, "basting": {"enabled": False}}


def test_true_satin_text_lays_out_and_renders(font):
    objs, warnings = lettering.layout_text({"text": "IOT", "font": {"path": font, "index": 0}, "size_mm": SIZE, "style": "columns"})
    assert not warnings
    assert len(satins(objs)) == 4 and {o["letter"] for o in objs} == {0, 1, 2}
    s = layout.render_summary(_plain([_item(font)]))
    parts = s["items"][0]["letters"]
    assert {p["kind"] for p in parts} == {"satin"} and s["info"]["stitches"] > 200


def test_break_into_shapes_gives_satin_objects(font):
    item = _item(font)
    shapes = layout.text_to_shapes(item)["objects"]
    assert len(shapes) == 4 and all(o["kind"] == "satin" and o["geometry"]["rail_a"] for o in shapes)
    lay = _plain([{"id": f"s{i}", **o, "transform": {}, "threads": [], "ops": []} for i, o in enumerate(shapes)])
    as_text = layout.render_summary(_plain([item]))
    as_shapes = layout.render_summary(lay)
    assert as_shapes["info"]["bounds_mm"] == pytest.approx(as_text["info"]["bounds_mm"], abs=0.3)
    assert as_shapes["info"]["stitches"] == pytest.approx(as_text["info"]["stitches"], abs=6)


def test_stitch_font_ignores_columns(font, tmp_path):
    dest = tmp_path / "fonts" / "test.luddfont"
    lettering.export_stitch_font({"path": font, "family": "Satin Test"}, str(dest), "IOT", cap_height_mm=SIZE)
    sf = {"path": str(dest)}
    as_satin = lettering.layout_text({"text": "IOT", "font": sf, "size_mm": 10, "style": "satin"})
    as_columns = lettering.layout_text({"text": "IOT", "font": sf, "size_mm": 10, "style": "columns"})
    assert as_columns == as_satin
    assert not satins(as_columns[0])


@pytest.mark.parametrize("style", ["columns", "satin", "fill"])
def test_small_letters_have_no_underlay(font, style):
    objs, _ = lettering.layout_text({"text": "IOT", "font": {"path": font, "index": 0}, "size_mm": 5, "style": style})
    assert objs and all(o["params"]["underlay"] == [] for o in objs)
    big, _ = lettering.layout_text({"text": "IOT", "font": {"path": font, "index": 0}, "size_mm": 6, "style": style})
    assert all(o["params"]["underlay"] != [] for o in big)
    # Left out stays left out on any fabric (an empty list is not "automatic").
    from threadline_engine import fabrics

    assert all(fabrics.apply(o, "knit")["params"]["underlay"] == [] for o in objs)


def test_small_letter_warning_text(font):
    _, warnings = lettering.layout_text({"text": "IOT", "font": {"path": font, "index": 0}, "size_mm": 5, "style": "columns"})
    assert ("Letters 5 mm tall are hard to stitch clearly; underlay is left out so they stay thin. "
            "6 mm or more is safer.") in warnings


def test_thin_stroke_warning(font):
    _, warnings = lettering.layout_text({"text": "ll", "font": {"path": font, "index": 0}, "size_mm": SIZE, "style": "columns"})
    want = [w for w in warnings if w.startswith("This font's strokes are only")]
    assert want == ["This font's strokes are only 0.7 mm wide at this size, so they sew as a single line. "
                    "Use a bolder font or bigger letters."]
    _, warnings = lettering.layout_text({"text": "IOT", "font": {"path": font, "index": 0}, "size_mm": SIZE, "style": "satin"})
    assert not any(w.startswith("This font's strokes") for w in warnings)


def test_a_letter_that_fails_falls_back_to_satin_look_whole(font, monkeypatch):
    def broken(shape, size_mm):
        raise satin.ColumnsFailed("test")

    monkeypatch.setattr(satin, "columns", broken)
    objs, warnings = lettering.layout_text({"text": "IOT", "font": {"path": font, "index": 0}, "size_mm": SIZE, "style": "columns"})
    assert objs and not satins(objs) and all(o["kind"] == "fill" for o in objs)
    assert "3 letters couldn't be sewn as True satin, so they are sewn in Satin look." in warnings


SNAPSHOTS = {
    "I_12": dict(text="I"),
    "O_12": dict(text="O"),
    "T_12": dict(text="T"),
    "IOT_columns": dict(text="IOT"),
    "small_5mm": dict(text="IOT", size_mm=5),
}


@pytest.mark.parametrize("name", sorted(SNAPSHOTS))
def test_snapshots(font, name):
    r = layout.render(_plain([_item(font, **SNAPSHOTS[name])]))
    check("lettering_satin", name, digest_pattern(r.pattern))
