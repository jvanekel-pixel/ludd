"""QA phase 4 (tests group): coverage that the review found missing or too weak.

- repeated stitch-edit moves of one stitch, with a turned or mirrored design
- the lettering text-cache key holds every input that changes the stitches
- shortest order never reorders overlapping shapes (the overlap guard really decides)
- curved glyphs (TrueType quadratic and CFF cubic), the old 'kern' table, the cap-height fallback
"""

import math

import pyembroidery as pe
import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables._k_e_r_n import KernTable_format_0
from shapely.geometry import Polygon

from threadline_engine import layout, lettering

from test_connectors import RED, square
from test_lettering import _rect, font_path  # noqa: F401  (tiny fonts built in the test)

M = pe.COMMAND_MASK


# ---------------------------------------------------------------- stitch editing: repeated moves


@pytest.fixture
def row(tmp_path):
    p = pe.EmbPattern()
    p.add_thread(pe.EmbThread("#ff0000", "Red", "1", brand="Test"))
    for x in range(0, 201, 25):
        p.stitch_abs(x, 0)
    p.end()
    f = tmp_path / "row.pes"
    pe.write(p, str(f), {"version": 6})
    return str(f)


def _stitch_at(lay_, i):
    r = layout.render(lay_)
    return next((x, y) for (x, y, c), src in zip(r.pattern.stitches, r.src_of) if src == i and c & M == pe.STITCH)


@pytest.mark.parametrize("transform, expect", [
    ({}, (3.0, -1.0)),                                    # plain: the two moves add up
    ({"rotate": 90}, (1.0, 3.0)),                         # turned 90 degrees: (3, -1) turns to (1, 3)
    ({"flip_x": True}, (-3.0, -1.0)),                     # mirrored side to side
    ({"rotate": 90, "scale_x": 2, "scale_y": 2}, (2.0, 6.0)),
])
def test_two_moves_of_one_stitch_add_up_and_follow_the_design(row, transform, expect):
    ops = [{"op": "move_stitch", "index": 4, "dx_mm": 1.0, "dy_mm": -2.0, "local": True},
           {"op": "move_stitches", "indices": [4], "dx_mm": 2.0, "dy_mm": 1.0, "local": True}]
    item = {"id": "r", "path": row, "transform": transform}
    x0, y0 = _stitch_at({"items": [item]}, 4)
    x1, y1 = _stitch_at({"items": [{**item, "ops": ops}]}, 4)
    assert ((x1 - x0) / 10, (y1 - y0) / 10) == (pytest.approx(expect[0], abs=0.01), pytest.approx(expect[1], abs=0.01))


# ---------------------------------------------------------------- text cache key


def _text(font, **kw):
    return {"id": "t", "kind": "text", "text": "IOX", "font": {"path": font, "index": 0}, "size_mm": 12,
            "spacing_mm": 0, "style": "satin", "shape": {"type": "line"}, "monogram": False,
            "thread": RED, "transform": {}, "threads": [], "ops": [], **kw}


def _stitches(item):
    r = layout.render({"items": [item], "merge_colors": False, "color_sort": False})
    return [(round(x, 2), round(y, 2), c & M) for x, y, c in r.pattern.stitches]


def test_lettering_reads_only_what_the_text_cache_key_holds(font_path, monkeypatch):  # noqa: F811
    """Every field layout_text looks at must be in the cache key; a field read but left out of the key
    would give stale letters when only that field changes."""
    seen: set[str] = set()
    real = lettering.layout_text

    class Spy(dict):
        def get(self, k, *a):
            seen.add(k)
            return super().get(k, *a)

        def __getitem__(self, k):
            seen.add(k)
            return super().__getitem__(k)

    keys: list[set[str]] = []

    def spying(spec, *a, **kw):
        keys.append(set(spec))
        return real(Spy(spec), *a, **kw)

    monkeypatch.setattr(lettering, "layout_text", spying)
    layout._text_cache.clear()
    for it in (_text(font_path), _text(font_path, text="IOI", monogram=True),
               _text(font_path, shape={"type": "arc_up", "radius_mm": 25}),
               _text(font_path, shape={"type": "path", "nodes": [[-30, 0, "c"], [30, 0, "c"]]})):
        _stitches(it)
    assert keys and seen <= set.intersection(*keys), f"read but not in the cache key: {seen - set.intersection(*keys)}"


VARIANTS = {
    "text": {"text": "OXI"},
    "font": "other font",
    "size": {"size_mm": 15},
    "spacing": {"spacing_mm": 2},
    "style": {"style": "fill"},
    "shape type": {"shape": {"type": "arc_up", "radius_mm": 30}},
    "shape radius": {"shape": {"type": "arc_up", "radius_mm": 45}},
    "drawn line": {"shape": {"type": "path", "nodes": [[-40, 0, "c"], [40, 10, "c"]]}},
    "drawn line moved": {"shape": {"type": "path", "nodes": [[-40, 0, "c"], [40, 20, "c"]]}},
    "monogram": {"text": "IOI", "monogram": True},
}


@pytest.mark.parametrize("name", sorted(VARIANTS))
def test_text_cache_never_returns_stale_letters(name, font_path, tmp_path):  # noqa: F811
    """Change one input after the text is cached: the stitches equal a fresh render with empty caches
    (and differ from before, so the input really matters)."""
    v = VARIANTS[name]
    base = _text(font_path, text="IOI") if name == "monogram" else _text(font_path)
    if v == "other font":
        # Same letters, other shapes (a round O, wider bars), in another file.
        other = _save_font(tmp_path / "other.ttf", glyphs_tt={"I": _block(300), "O": _tt_circle(), "X": _block(500)},
                           cmap={ord("I"): "I", ord("O"): "O", ord("X"): "X"})
        changed = {**base, "font": {"path": other, "index": 0}}
    else:
        changed = {**base, **v}
    layout._text_cache.clear()
    layout._object_cache.clear()
    try:
        before = _stitches(base)
    except layout.LayoutError:
        before = None
    try:
        warm = _stitches(changed)
    except layout.LayoutError as exc:
        warm = str(exc)
    layout._text_cache.clear()
    layout._object_cache.clear()
    try:
        cold = _stitches(changed)
    except layout.LayoutError as exc:
        cold = str(exc)
    assert warm == cold
    assert warm != before


# ---------------------------------------------------------------- shortest order: the overlap guard


def test_shortest_order_never_puts_an_overlapping_shape_ahead(monkeypatch):
    """d sits on top of b. Nearest-first alone would sew d before b (which would bury d under b);
    the overlap guard keeps b first while still reordering the rest."""
    items = [square("a", 0, 0, 5, RED), square("b", 60, 0, 20, RED), square("c", 20, 0, 5, RED), square("d", 62, 2, 5, RED)]
    got = layout.optimize_order({"items": items})
    assert got["order"] == ["a", "c", "b", "d"] and got["saved_mm"] > 0
    # Without the guard the order is different: this test fails if the guard stops working.
    monkeypatch.setattr(layout.joins, "_blocks_overlap", lambda a, b: False)
    unguarded = layout.optimize_order({"items": items})["order"]
    assert unguarded.index("d") < unguarded.index("b")


def test_shortest_order_keeps_every_overlapping_pair_in_order():
    """A row of shapes where neighbours overlap, mixed with separate ones: no overlapping pair swaps."""
    items = [square("a", 0, 0, 5, RED), square("b", 50, 0, 10, RED), square("c", 15, 0, 5, RED),
             square("d", 55, 5, 10, RED), square("e", 30, 0, 5, RED), square("f", 60, 10, 10, RED)]
    order = layout.optimize_order({"items": items})["order"]
    pos = {k: order.index(k) for k in order}
    for first, later in (("b", "d"), ("d", "f")):
        assert pos[first] < pos[later]
    assert sorted(order) == list("abcdef")


# ---------------------------------------------------------------- glyph curves, kern table, cap height

UPM = 1000
R = 350  # circle radius, font units: a 700-unit tall O


def _tt_circle():
    """An O drawn with 8 quadratic curves (TrueType), centred at (R, R)."""
    pen = TTGlyphPen(None)
    on = [(R + R * math.cos(math.radians(a)), R + R * math.sin(math.radians(a))) for a in range(0, 360, 45)]
    rr = R / math.cos(math.radians(22.5))
    off = [(R + rr * math.cos(math.radians(a + 22.5)), R + rr * math.sin(math.radians(a + 22.5))) for a in range(0, 360, 45)]
    pen.moveTo(on[0])
    for k in range(8):
        pen.qCurveTo(off[k], on[(k + 1) % 8])
    pen.closePath()
    return pen.glyph()


def _save_font(path, glyphs_tt=None, charstrings=None, cmap=None, cap=700, kern=None):
    names = [".notdef", *(glyphs_tt or charstrings or {})]
    fb = FontBuilder(UPM, isTTF=charstrings is None)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap(cmap)
    if charstrings is None:
        fb.setupGlyf({".notdef": TTGlyphPen(None).glyph(), **glyphs_tt})
    else:
        empty = T2CharStringPen(500, None).getCharString()
        fb.setupCFF("LuddCurveTest", {"FullName": "LUDD Curve Test"}, {".notdef": empty, **charstrings}, {})
    fb.setupHorizontalMetrics({n: (800, 0) for n in names})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "LUDD Curve Test", "styleName": "Regular"})
    fb.setupOS2(sCapHeight=cap, sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    if kern:
        t = newTable("kern")
        t.version = 0
        sub = KernTable_format_0()
        sub.version, sub.coverage, sub.format, sub.tupleIndex = 0, 1, 0, None
        sub.kernTable = dict(kern)
        t.kernTables = [sub]
        fb.font["kern"] = t
    fb.save(str(path))
    return str(path)


def _is_round(objs, size_mm=10):
    """The letter outline is a circle of diameter size_mm: every point on it, area within 1%."""
    (o,) = objs
    pts = [(n[0], n[1]) for n in o["geometry"]["outline"]]
    xs, ys = zip(*pts)
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    r = size_mm / 2
    assert len(pts) > 24  # flattened into many short pieces, not 8 corners
    assert all(abs(math.dist(p, (cx, cy)) - r) < 0.08 for p in pts)
    assert Polygon(pts).area == pytest.approx(math.pi * r * r, rel=0.01)  # an octagon would be 10% short


def test_truetype_quadratic_curves_are_flattened_onto_the_curve(tmp_path):
    f = _save_font(tmp_path / "round.ttf", glyphs_tt={"O": _tt_circle()}, cmap={ord("O"): "O"})
    objs, _ = lettering.layout_text({"text": "O", "font": {"path": f, "index": 0}, "size_mm": 10, "style": "fill"})
    _is_round(objs)


def test_cff_cubic_curves_are_flattened_onto_the_curve(tmp_path):
    k = 0.5523 * R
    pen = T2CharStringPen(800, None)
    pen.moveTo((2 * R, R))
    pen.curveTo((2 * R, R + k), (R + k, 2 * R), (R, 2 * R))
    pen.curveTo((R - k, 2 * R), (0, R + k), (0, R))
    pen.curveTo((0, R - k), (R - k, 0), (R, 0))
    pen.curveTo((R + k, 0), (2 * R, R - k), (2 * R, R))
    pen.closePath()
    f = _save_font(tmp_path / "round.otf", charstrings={"O": pen.getCharString()}, cmap={ord("O"): "O"})
    objs, _ = lettering.layout_text({"text": "O", "font": {"path": f, "index": 0}, "size_mm": 10, "style": "fill"})
    _is_round(objs)


def _block(w=600, h=700):
    pen = TTGlyphPen(None)
    _rect(pen, 50, 0, w, h)
    return pen.glyph()


def test_the_old_kern_table_is_used_when_there_is_no_gpos(tmp_path):
    f = _save_font(tmp_path / "kern.ttf", glyphs_tt={"A": _block(), "V": _block()}, cmap={ord("A"): "A", ord("V"): "V"},
                   kern={("A", "V"): -200})
    lf = lettering._load(f, 0)
    assert not lf.gpos and lf.kern_pair("A", "V") == -200 and lf.kern_pair("V", "A") == 0

    def width(text):
        objs, _ = lettering.layout_text({"text": text, "font": {"path": f, "index": 0}, "size_mm": 10, "style": "fill"})
        xs = [n[0] for o in objs for n in o["geometry"]["outline"]]
        return max(xs) - min(xs)

    assert width("VA") - width("AV") == pytest.approx(200 * 10 / 700, abs=0.05)


def test_cap_height_falls_back_to_the_font_field_then_seven_tenths_of_the_em(tmp_path):
    """No H to measure: the font's cap-height field is used; without that too, 0.7 of the em."""
    def height(path):
        objs, _ = lettering.layout_text({"text": "I", "font": {"path": path, "index": 0}, "size_mm": 10, "style": "fill"})
        ys = [n[1] for o in objs for n in o["geometry"]["outline"]]
        return max(ys) - min(ys)

    glyph = {"I": _block(200, 350)}
    with_field = _save_font(tmp_path / "field.ttf", glyphs_tt=glyph, cmap={ord("I"): "I"}, cap=500)
    assert height(with_field) == pytest.approx(10 * 350 / 500, abs=0.05)
    without = _save_font(tmp_path / "none.ttf", glyphs_tt=glyph, cmap={ord("I"): "I"}, cap=0)
    assert height(without) == pytest.approx(10 * 350 / 700, abs=0.05)
