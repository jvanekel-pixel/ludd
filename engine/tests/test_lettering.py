"""Lettering with a font built in the test, so it runs the same on any machine."""

import json
import math

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from threadline_engine import design, layout, lettering
from threadline_engine.lettering import LetteringError

UPM = 1000
CAP = 700


def _rect(pen, x0, y0, x1, y1, clockwise=True):
    pts = [(x0, y0), (x0, y1), (x1, y1), (x1, y0)] if clockwise else [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    pen.moveTo(pts[0])
    for p in pts[1:]:
        pen.lineTo(p)
    pen.closePath()


@pytest.fixture(scope="module")
def font_path(tmp_path_factory):
    """A tiny TrueType font: I (bar), O (square ring with a hole), X (two overlapping bars), space."""
    glyphs = {}
    pen = TTGlyphPen(None)
    glyphs[".notdef"] = pen.glyph()
    pen = TTGlyphPen(None)
    _rect(pen, 100, 0, 250, CAP)
    glyphs["I"] = pen.glyph()
    pen = TTGlyphPen(None)
    _rect(pen, 50, 0, 600, CAP)  # outer, clockwise (TrueType fill direction)
    _rect(pen, 200, 150, 450, 550, clockwise=False)  # hole, the other way round
    glyphs["O"] = pen.glyph()
    pen = TTGlyphPen(None)
    _rect(pen, 50, 300, 600, 420)  # horizontal bar
    _rect(pen, 270, 0, 380, CAP)  # vertical bar overlapping it, same direction: union, not a hole
    glyphs["X"] = pen.glyph()
    pen = TTGlyphPen(None)
    glyphs["space"] = pen.glyph()

    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(list(glyphs))
    fb.setupCharacterMap({ord("I"): "I", ord("O"): "O", ord("X"): "X", ord(" "): "space"})
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({".notdef": (500, 0), "I": (350, 100), "O": (650, 50), "X": (650, 50), "space": (300, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Threadline Test", "styleName": "Regular"})
    fb.setupOS2(sCapHeight=CAP, sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    path = tmp_path_factory.mktemp("fonts") / "ThreadlineTest.ttf"
    fb.save(str(path))
    return str(path)


def spec(font_path, **kw):
    return {"text": "IO", "font": {"path": font_path, "index": 0}, "size_mm": 10, "style": "satin", **kw}


def bounds(objects):
    pts = [(n[0], n[1]) for o in objects for key in ("outline",) for n in o["geometry"][key]]
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)


def test_letters_become_fills_with_holes(font_path):
    objs, warnings = lettering.layout_text(spec(font_path))
    assert not warnings
    assert len(objs) == 2  # I and O
    holes = sorted(len(o["geometry"].get("holes") or []) for o in objs)
    assert holes == [0, 1]
    x0, y0, x1, y1 = bounds(objs)
    assert y1 - y0 == pytest.approx(10, abs=0.05)  # cap height = letter size
    assert (x0 + x1) / 2 == pytest.approx(0, abs=0.05) and (y0 + y1) / 2 == pytest.approx(0, abs=0.05)  # centred


def test_overlapping_strokes_are_merged_not_holed(font_path):
    objs, _ = lettering.layout_text(spec(font_path, text="X"))
    assert len(objs) == 1 and not objs[0]["geometry"].get("holes")


def test_satin_look_crosses_strokes(font_path):
    (bar,), _ = lettering.layout_text(spec(font_path, text="I"))
    # A tall thin bar: stitches across it (horizontal), long enough to be single stitches.
    assert bar["params"]["angle_deg"] == 0
    assert 6.5 <= bar["params"]["stitch_mm"] < 7  # under the long-stitch warning
    (fill,), _ = lettering.layout_text(spec(font_path, text="I", style="fill"))
    assert fill["params"]["stitch_mm"] == 3.5


def test_spacing_and_unknown_characters(font_path):
    tight = bounds(lettering.layout_text(spec(font_path, text="II"))[0])
    loose = bounds(lettering.layout_text(spec(font_path, text="II", spacing_mm=3))[0])
    assert (loose[2] - loose[0]) - (tight[2] - tight[0]) == pytest.approx(3, abs=0.05)
    # Characters the font doesn't have are skipped rather than failing.
    assert len(lettering.layout_text(spec(font_path, text="IZ"))[0]) == 1


def test_arcs_and_circles(font_path):
    line = lettering.layout_text(spec(font_path, text="IIIII"))[0]
    up = lettering.layout_text(spec(font_path, text="IIIII", shape={"type": "arc_up", "radius_mm": 25}))[0]
    down = lettering.layout_text(spec(font_path, text="IIIII", shape={"type": "arc_down", "radius_mm": 25}))[0]
    # On an arc the letters fan out: the outer letters sit lower (arc up) or higher (arc down).
    def centre_y(o):
        ys = [n[1] for n in o["geometry"]["outline"]]
        return (min(ys) + max(ys)) / 2

    assert centre_y(up[0]) > centre_y(up[2]) and centre_y(down[0]) < centre_y(down[2])
    assert all(abs(centre_y(o)) < 0.1 for o in line)
    # Each letter is turned to follow the circle: the end letters are tilted.
    def tilt(o):
        ns = o["geometry"]["outline"]
        return math.atan2(ns[1][1] - ns[0][1], ns[1][0] - ns[0][0])

    assert abs(tilt(up[0]) - tilt(up[4])) > 0.3
    _, warn = lettering.layout_text(spec(font_path, text="I" * 40, shape={"type": "circle", "radius_mm": 5}))
    assert any("longer than the circle" in w for w in warn)


def test_monogram_has_a_bigger_middle_letter(font_path):
    objs, _ = lettering.layout_text(spec(font_path, text="IOI", monogram=True))
    heights = [max(n[1] for n in o["geometry"]["outline"]) - min(n[1] for n in o["geometry"]["outline"]) for o in objs]
    assert heights[1] == pytest.approx(10, abs=0.05) and heights[0] == pytest.approx(7, abs=0.05)
    with pytest.raises(LetteringError, match="three letters"):
        lettering.layout_text(spec(font_path, text="IOIX", monogram=True))  # one to three letters


def test_validation_and_small_text_warning(font_path):
    with pytest.raises(LetteringError, match="Type some text"):
        lettering.layout_text(spec(font_path, text="  "))
    with pytest.raises(LetteringError, match="Choose a font"):
        lettering.layout_text({"text": "I", "font": {}})
    _, warn = lettering.layout_text(spec(font_path, size_mm=4))
    assert any("hard to stitch" in w for w in warn)


def test_text_in_a_layout_stitches_and_exports(font_path, tmp_path):
    item = {"id": "t", "kind": "text", **spec(font_path, text="IOX"), "thread": {"color": "#ff0000", "name": "Red"},
            "transform": {"x": 5}, "threads": [], "ops": []}
    s = layout.render_summary({"items": [item], "merge_colors": False, "color_sort": False, "basting": {"enabled": False}})
    assert s["items"][0]["kind"] == "text" and s["items"][0]["name"] == "“IOX”"
    assert s["info"]["colors"] == 1 and s["info"]["stitches"] > 100
    assert (s["info"]["bounds_mm"][0] + s["info"]["bounds_mm"][2]) / 2 == pytest.approx(5, abs=0.3)
    out = tmp_path / "name.pes"
    layout.export({"items": [item], "merge_colors": False, "color_sort": False, "basting": {"enabled": False}}, str(out))
    assert design.open_design(str(out))["info"]["stitches"] == s["info"]["stitches"]


def test_stitch_font_round_trip(font_path, tmp_path):
    dest = tmp_path / "fonts" / "test.luddfont"
    r = lettering.export_stitch_font({"path": font_path, "family": "Threadline Test"}, str(dest), "IOX ", cap_height_mm=12)
    assert r["glyphs"] == 3
    data = json.loads(dest.read_text())
    assert data["format"] == "ludd-font" and set(data["glyphs"]) == {"I", "O", "X"}
    # The stitch font draws the same letters as the outline font, scaled to any size.
    from_stitch, _ = lettering.layout_text({"text": "IO", "font": {"path": str(dest)}, "size_mm": 10})
    from_outline, _ = lettering.layout_text(spec(font_path))
    assert bounds(from_stitch) == pytest.approx(bounds(from_outline), abs=0.05)


def test_font_list_includes_user_fonts(font_path, isolated_data_dir):
    import shutil

    d = isolated_data_dir / "fonts"
    d.mkdir(parents=True)
    shutil.copy(font_path, d / "ThreadlineTest.ttf")
    fonts = lettering.list_fonts()
    assert any(f["family"] == "Threadline Test" and f["kind"] == "outline" for f in fonts)


def test_missing_font_file_falls_back_to_the_installed_family(font_path, isolated_data_dir):
    """A project from another computer names its font by family; use the one installed here."""
    import shutil

    d = isolated_data_dir / "fonts"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(font_path, d / "ThreadlineTest.ttf")

    gone = {"path": "C:/nowhere/ThreadlineTest.ttf", "family": "Threadline Test", "style": "Regular"}
    assert lettering.resolve_font(gone)["path"] != gone["path"]
    with pytest.raises(lettering.LetteringError, match="isn't installed"):
        lettering.resolve_font({"path": "C:/nowhere/x.ttf", "family": "No Such Font"})


def test_text_follows_a_drawn_line(font_path):
    font = {"path": font_path, "index": 0}
    from threadline_engine.digitize import stitches as dz

    straight = {"type": "path", "nodes": [[-60, 0, "c"], [60, 0, "c"]]}
    objs, _ = lettering.layout_text({"text": "IO", "font": font, "size_mm": 10, "shape": straight})
    ys = [p[1] for o in objs for p in dz.geometry_points(o)]
    assert min(ys) == pytest.approx(-10, abs=1.5) and max(ys) == pytest.approx(0, abs=0.6)  # standing on the line
    # Up a slope: the letters turn with it.
    slope = {"type": "path", "nodes": [[-60, 60, "c"], [60, -60, "c"]]}
    objs2, _ = lettering.layout_text({"text": "IO", "font": font, "size_mm": 10, "shape": slope})
    xs2 = [p[0] for o in objs2 for p in dz.geometry_points(o)]
    ys2 = [p[1] for o in objs2 for p in dz.geometry_points(o)]
    assert max(xs2) - min(xs2) < 20 and max(ys2) - min(ys2) > 8
    with pytest.raises(lettering.LetteringError, match="line"):
        lettering.layout_text({"text": "IO", "font": font, "size_mm": 10, "shape": {"type": "path", "nodes": [[0, 0, "c"]]}})


def test_qa_c7_missing_font_is_shown_in_a_stand_in_with_a_warning(font_path, monkeypatch):
    stand_in = {"family": "Threadline Test", "style": "Regular", "path": font_path, "index": 0, "kind": "outline"}
    monkeypatch.setattr(lettering.fonts, "list_fonts", lambda: [stand_in])
    missing = {"path": "C:/nowhere/Fancy.ttf", "index": 0, "family": "Fancy Script", "style": "Regular"}
    objs, warnings = lettering.layout_text({"text": "IO", "font": missing, "size_mm": 10, "style": "satin"})
    assert objs
    assert any("Fancy Script" in w and "isn't installed" in w for w in warnings)


def test_text_longer_than_its_line_warns(font_path):
    line = {"type": "path", "nodes": [[0, 0, "c"], [8, 0, "c"]]}
    _, warnings = lettering.layout_text(spec(font_path, text="IOIOIO", shape=line))
    assert any("longer than its line" in w for w in warnings)
    roomy = {"type": "path", "nodes": [[0, 0, "c"], [200, 0, "c"]]}
    _, warnings = lettering.layout_text(spec(font_path, text="IO", shape=roomy))
    assert not any("longer than its line" in w for w in warnings)


# ---------------------------------------------------------------- QA phase 4 (lettering)


@pytest.fixture(scope="module")
def font2_path(tmp_path_factory):
    """A second test font: H (capital height 700, but the font claims 800), A and V kerned in GPOS,
    Q hanging below the baseline, a ring with an island inside its hole, and two bars wound opposite ways."""
    def glyph(*rects):
        pen = TTGlyphPen(None)
        for r in rects:
            _rect(pen, *r)
        return pen.glyph()

    glyphs = {
        ".notdef": TTGlyphPen(None).glyph(),
        "H": glyph((50, 0, 150, CAP), (450, 0, 550, CAP), (150, 300, 450, 400)),
        "A": glyph((50, 0, 550, CAP)),
        "V": glyph((50, 0, 550, CAP)),
        "Q": glyph((50, -200, 600, CAP)),
        "ring": glyph((0, 0, 800, CAP), (100, 100, 700, 600, False), (250, 250, 550, 450)),
        "bars": glyph((0, 0, 300, CAP), (450, 0, 750, CAP, False)),
        "space": TTGlyphPen(None).glyph(),
    }
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(list(glyphs))
    fb.setupCharacterMap({ord("H"): "H", ord("A"): "A", ord("V"): "V", ord("Q"): "Q", 0xA9: "ring", 0xB1: "bars", ord(" "): "space"})
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({k: (900, 0) for k in glyphs})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "LUDD Test Two", "styleName": "Regular"})
    fb.setupOS2(sCapHeight=800, sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    fb.addOpenTypeFeatures("feature kern { pos A V -200; } kern;")
    path = tmp_path_factory.mktemp("fonts2") / "LuddTestTwo.ttf"
    fb.save(str(path))
    return str(path)


def _f2(font2_path, **kw):
    return {"text": "H", "font": {"path": font2_path, "index": 0}, "size_mm": 10, "style": "fill", **kw}


def _area(objs):
    from shapely.geometry import Polygon

    return sum(Polygon([(n[0], n[1]) for n in o["geometry"]["outline"]], [[(n[0], n[1]) for n in h] for h in o["geometry"].get("holes") or []]).area
               for o in objs)


def _text_item(spec_, **kw):
    return {"id": "t", "kind": "text", "spacing_mm": 0, "shape": {"type": "line"}, "monogram": False, **spec_,
            "thread": {"color": "#ff0000", "name": "Red"}, "transform": kw.pop("transform", {}), "threads": [], "ops": [], **kw}


def _render(it):
    import pyembroidery as pe

    r = layout.render({"items": [it], "merge_colors": False, "color_sort": False, "basting": {"enabled": False}})
    return [(x / 10, y / 10) for x, y, k in r.pattern.stitches if k & pe.COMMAND_MASK == pe.STITCH]


def test_qa_letter_height_is_the_drawn_capital_not_the_fonts_claim(font2_path):
    objs, _ = lettering.layout_text(_f2(font2_path))
    _, y0, _, y1 = bounds(objs)
    assert y1 - y0 == pytest.approx(10, abs=0.05)


def test_qa_gpos_kerning_is_used(font2_path):
    lf = lettering._load(font2_path, 0)
    assert lf.kern_pair("A", "V") == -200 and lf.kern_pair("V", "A") == 0
    av = bounds(lettering.layout_text(_f2(font2_path, text="AV"))[0])
    va = bounds(lettering.layout_text(_f2(font2_path, text="VA"))[0])
    assert (va[2] - va[0]) - (av[2] - av[0]) == pytest.approx(200 * 10 / 700, abs=0.05)


def test_qa_letters_follow_the_non_zero_winding_rule(font2_path):
    scale = 10 / 700  # size 10 mm on a 700-unit capital
    ring, _ = lettering.layout_text(_f2(font2_path, text="©"))
    assert _area(ring) == pytest.approx((800 * 700 - 600 * 500 + 300 * 200) * scale**2, rel=0.01)  # the island is kept
    bars, _ = lettering.layout_text(_f2(font2_path, text="±"))
    assert _area(bars) == pytest.approx(2 * 300 * 700 * scale**2, rel=0.01)  # the bar wound the other way is kept


def test_qa_missing_characters_are_named_and_nothing_drawable_is_refused(font_path):
    objs, warnings = lettering.layout_text(spec(font_path, text="I日O"))
    assert len(objs) == 2 and any("日" in w and "left out" in w for w in warnings)
    with pytest.raises(LetteringError, match="none of these letters"):
        lettering.layout_text(spec(font_path, text="日語"))


def test_qa_text_is_cleaned_before_layout():
    assert lettering._clean_text("é") == "é"
    assert lettering._clean_text("A\nB\tC​") == "A\nB C"


def test_qa_straight_text_keeps_its_baseline(font2_path):
    """A letter that hangs below the line (Q) doesn't lift the others: names line up file to file."""
    h = bounds(lettering.layout_text(_f2(font2_path, text="HH"))[0])
    hq = bounds(lettering.layout_text(_f2(font2_path, text="HQ"))[0])
    assert hq[1] == pytest.approx(h[1], abs=0.01) and hq[3] > h[3] + 2


def test_qa_circle_goes_all_the_way_round(font_path):
    arch, _ = lettering.layout_text(spec(font_path, text="III", shape={"type": "arc_up", "radius_mm": 20}))
    ring, _ = lettering.layout_text(spec(font_path, text="III", shape={"type": "circle", "radius_mm": 20}))
    centre_y = lambda o: sum(n[1] for n in o["geometry"]["outline"]) / len(o["geometry"]["outline"])  # noqa: E731
    assert max(centre_y(o) for o in arch) - min(centre_y(o) for o in arch) < 5  # an arch stays at the top
    assert max(centre_y(o) for o in ring) - min(centre_y(o) for o in ring) > 20  # a circle spreads them round


def test_qa_smile_letters_do_not_collide(font_path):
    from shapely.geometry import Polygon

    objs, _ = lettering.layout_text(spec(font_path, text="OOOOO", shape={"type": "arc_down", "radius_mm": 15}))
    ps = [Polygon([(n[0], n[1]) for n in o["geometry"]["outline"]]) for o in objs]
    assert sum(a.intersection(b).area for i, a in enumerate(ps) for b in ps[i + 1:]) < 0.01


def test_qa_stitch_angle_turns_with_the_letters(font_path):
    # Round a circle: each letter's angle follows its turn (upright I has 0).
    objs, _ = lettering.layout_text(spec(font_path, text="III", shape={"type": "circle", "radius_mm": 10}))
    assert sorted(o["params"]["angle_deg"] for o in objs) == pytest.approx([0, 60, 120], abs=0.5)
    turned = lettering.turn_with({"kind": "fill", "params": {"angle_deg": 0}}, lettering._Turn(90))
    assert turned["params"]["angle_deg"] == 90
    # Lettering turned with the Turn handle still sews short stitches across the bar.
    st = _render(_text_item(spec(font_path, text="I"), transform={"rotate": 90}))
    assert max(math.dist(a, b) for a, b in zip(st, st[1:])) < 3.5


def test_qa_moving_text_moves_the_same_stitches(font_path):
    a = _render(_text_item(spec(font_path, text="IO")))
    b = _render(_text_item(spec(font_path, text="IO"), transform={"x": 10, "y": -4}))
    assert len(a) == len(b)
    assert all(math.isclose(p[0] + 10, q[0], abs_tol=0.02) and math.isclose(p[1] - 4, q[1], abs_tol=0.02) for p, q in zip(a, b))


def test_qa_text_on_a_line_reads_upright_whichever_way_it_was_drawn(font_path):
    from threadline_engine.digitize import stitches as dz

    for nodes in ([[-40, 0, "c"], [40, 0, "c"]], [[40, 0, "c"], [-40, 0, "c"]]):
        objs, _ = lettering.layout_text(spec(font_path, shape={"type": "path", "nodes": nodes}))
        ys = [p[1] for o in objs for p in dz.geometry_points(o)]
        assert max(ys) == pytest.approx(0, abs=0.6) and min(ys) < -9  # standing on the line, not hanging under it
    # A closed line: the text stands outside it, centred at the top, whichever way it was drawn.
    ring = [[30 * math.cos(i * math.pi / 12), 30 * math.sin(i * math.pi / 12), "c"] for i in range(24)]
    for nodes in (ring, ring[::-1]):
        objs, _ = lettering.layout_text(spec(font_path, shape={"type": "path", "nodes": nodes, "closed": True}))
        pts = [p for o in objs for p in dz.geometry_points(o)]
        assert all(math.hypot(*p) > 29 for p in pts) and max(p[1] for p in pts) < -25
    with pytest.raises(LetteringError, match="too short"):
        lettering.layout_text(spec(font_path, shape={"type": "path", "nodes": [[0, 0, "c"], [0, 0, "c"]]}))


def test_qa_small_monogram_side_letters_warn(font_path):
    _, warnings = lettering.layout_text(spec(font_path, text="IOI", monogram=True, size_mm=8))
    assert any("hard to stitch" in w for w in warnings)


def test_qa_damaged_stitch_fonts_give_a_clear_message(isolated_data_dir, tmp_path):
    bar = {"kind": "fill", "geometry": {"outline": [[0, 0, "c"], [2, 0, "c"], [2, -10, "c"], [0, -10, "c"]]}, "params": {}}
    good = {"format": "ludd-font", "name": "Mine", "cap_height_mm": 10, "glyphs": {"I": {"advance_mm": 4, "objects": [bar]}}}
    bad_node = {"kind": "fill", "geometry": {"outline": [["x", 0, "c"]]}}
    cases = {
        "binary.luddfont": b"\xff\xfe\x00",
        "list.luddfont": json.dumps([1, 2]).encode(),
        "cap.luddfont": json.dumps({**good, "cap_height_mm": "tall"}).encode(),
        "node.luddfont": json.dumps({**good, "glyphs": {"I": {"advance_mm": 4, "objects": [bad_node]}}}).encode(),
    }
    for name, data in cases.items():
        p = tmp_path / name
        p.write_bytes(data)
        with pytest.raises(LetteringError):
            lettering.layout_text({"text": "I", "font": {"path": str(p)}, "size_mm": 10})
    # A wrong-typed name doesn't break the font list for every other font.
    d = isolated_data_dir / "fonts"
    d.mkdir(parents=True)
    (d / "numbered.luddfont").write_text(json.dumps({**good, "name": 12}))
    (d / "broken.luddfont").write_bytes(b"\xff")
    fonts = lettering.list_fonts()
    assert [f["family"] for f in fonts if f["kind"] == "stitch"] == ["12"]


def test_qa_stitch_font_case_and_accent_fallback(font2_path, tmp_path):
    dest = tmp_path / "caps.luddfont"
    lettering.export_stitch_font({"path": font2_path, "family": "Two"}, str(dest), "HAV")
    objs, warnings = lettering.layout_text({"text": "hÁ", "font": {"path": str(dest)}, "size_mm": 10})
    assert len(objs) == 2  # h drawn as H, Á as A
    assert any("nearest letter" in w and "h as H" in w for w in warnings)
    # Kerning comes along into the stitch font.
    assert json.loads(dest.read_text())["kern"] == {"AV": pytest.approx(-200 * 12 / 700, abs=0.001)}


def test_qa_save_as_stitch_font_goes_where_ludd_looks(font2_path, isolated_data_dir):
    r = lettering.export_stitch_font({"path": font2_path, "family": "LUDD Test Two"}, "", "", style="satin")
    assert r["glyphs"] == 6 and r["folder"] == str(isolated_data_dir / "fonts")
    assert any(f["kind"] == "stitch" and f["path"] == r["path"] for f in lettering.list_fonts())
    again = lettering.export_stitch_font({"path": font2_path, "family": "LUDD Test Two"}, "", "", style="satin")
    assert again["path"] != r["path"]  # never replaces one you may have fine-tuned
    with pytest.raises(LetteringError, match="already a stitch font"):
        lettering.export_stitch_font({"path": r["path"]}, "", "")


def test_qa_an_edited_stitch_font_shows_at_once(font_path, tmp_path):
    import os

    dest = tmp_path / "edit_me.luddfont"
    lettering.export_stitch_font({"path": font_path, "family": "T"}, str(dest), "IO")
    it = _text_item({"text": "II", "font": {"path": str(dest)}, "size_mm": 10, "style": "satin"})

    def width():
        xs = [p[0] for p in _render(it)]
        return max(xs) - min(xs)

    before = width()
    d = json.loads(dest.read_text())
    d["glyphs"]["I"]["advance_mm"] += 20
    dest.write_text(json.dumps(d))
    st = os.stat(dest)
    os.utime(dest, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
    assert width() > before + 15


def _text(font_path, **kw):
    return {"id": "t", "kind": "text", **spec(font_path, text="IOX"), "thread": {"color": "#ff0000", "name": "Red"},
            "transform": {"x": 5}, "threads": [], "ops": [], **kw}


def test_each_letter_has_its_start_and_end_on_the_design(font_path):
    """The design shows every letter's kind and its start and end dots; letters hand over to each
    other (each starts where the one before ended)."""
    s = layout.render_summary({"items": [_text(font_path)], "merge_colors": False, "color_sort": False, "basting": {"enabled": False}})
    parts = s["items"][0]["letters"]
    assert len(parts) >= 3 and all(p["kind"] == "fill" and p["look"] == "satin" for p in parts)
    assert all(len(p["ring"]) >= 3 and len(p["start"]) == 2 and len(p["end"]) == 2 for p in parts)
    # Short hand-overs: each letter starts close to where the one before ended.
    hops = [math.dist(a["end"], b["start"]) for a, b in zip(parts, parts[1:])]
    assert max(hops) < 6  # the letters are 1.2 mm apart; the hops are short, not a letter's width


def test_a_letters_start_and_end_can_be_chosen(font_path):
    """Dragging a letter's dots keeps the point (in the text's own frame) on the item; the letter
    starts and stops there, also after the text is moved."""
    plain = layout.render_summary({"items": [_text(font_path)], "merge_colors": False, "color_sort": False, "basting": {"enabled": False}})
    o = plain["items"][0]["letters"][1]
    xs = [p[0] for p in o["ring"]]
    ys = [p[1] for p in o["ring"]]
    target = (max(xs), (min(ys) + max(ys)) / 2)  # the O's right side, middle (as shown, x + 5)
    local = [target[0] - 5, target[1]]
    chosen = _text(font_path, letters={str(o["index"]): {"end_mm": local}})
    s = layout.render_summary({"items": [chosen], "merge_colors": False, "color_sort": False, "basting": {"enabled": False}})
    end = s["items"][0]["letters"][1]["end"]
    assert math.dist(end, target) < 1.0


def test_lettering_breaks_into_shapes_in_place(font_path):
    item = _text(font_path)
    shapes = layout.text_to_shapes(item)["objects"]
    assert len(shapes) >= 3 and all(o["kind"] == "fill" and o["thread"]["color"] == "#ff0000" for o in shapes)
    lay = {"items": [{"id": f"s{i}", **o, "transform": {}, "threads": [], "ops": []} for i, o in enumerate(shapes)],
           "merge_colors": False, "color_sort": False, "basting": {"enabled": False}}
    as_text = layout.render_summary({"items": [item], "merge_colors": False, "color_sort": False, "basting": {"enabled": False}})
    as_shapes = layout.render_summary(lay)
    assert as_shapes["info"]["bounds_mm"] == pytest.approx(as_text["info"]["bounds_mm"], abs=0.3)
    # The same stitches as the lettering (no fabric preset on either).
    assert as_shapes["info"]["stitches"] == pytest.approx(as_text["info"]["stitches"], abs=6)
