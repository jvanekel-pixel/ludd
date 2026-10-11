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
    assert bar["params"]["stitch_mm"] >= 7
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
        lettering.layout_text(spec(font_path, text="IO", monogram=True))


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
