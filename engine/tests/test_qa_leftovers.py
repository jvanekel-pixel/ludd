"""QA phase 4, leftovers: kept picture copies, the Advisor's picture reading, stitch-font edge cases,
fabric spacing limits and the help text's shortcuts."""

import json

import numpy as np
import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from PIL import Image

from threadline_engine import fabrics, lettering, project, trace
from threadline_engine.ai import advisor, helpdocs
from threadline_engine.lettering import LetteringError


def _png(path, color):
    im = Image.new("RGB", (40, 30), (255, 255, 255))
    im.paste(color, (0, 0, 20, 30))  # left half in `color`
    im.save(path)


def test_an_edited_picture_traces_and_saves_as_shown(tmp_path):
    pic = tmp_path / "cat.png"
    _png(pic, (0, 0, 0))
    shown = project.load_image(str(pic))  # what the canvas shows
    _png(pic, (255, 255, 255))  # edited elsewhere afterwards
    maps = trace.prepare(str(pic))
    assert maps.darkness.max() > 0.5  # still the half-black picture on screen
    packed, files = project._pack({"layout": {"items": []}, "images": [{"path": str(pic), "name": "cat.png", "x": 0, "y": 0}]})
    data = files[packed["images"][0]["embedded"]]
    assert Image.open(__import__("io").BytesIO(data)).getpixel((0, 0)) == (0, 0, 0)
    assert shown["data_url"]
    # Adding the picture again takes the new file.
    again = project.load_image(str(pic))
    assert again["data_url"] != shown["data_url"]


def test_advisor_reads_a_16_bit_grey_picture(tmp_path):
    path = tmp_path / "grey16.png"
    Image.fromarray(np.full((20, 20), 30000, dtype=np.uint16)).save(path)  # mid-grey, 16-bit
    images = [{"path": str(path), "x": 0, "y": 0, "width_mm": 20, "height_mm": 20, "visible": True}]
    crop = advisor._picture_under(images, (-5, -5, 5, 5), (32, 32))
    assert crop is not None and crop.mode == "RGB"
    assert 90 < crop.getpixel((16, 16))[0] < 150  # grey, not clipped to white


def test_advisor_skips_a_picture_it_cannot_read(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not a picture")
    images = [{"path": str(bad), "x": 0, "y": 0, "width_mm": 20, "height_mm": 20}]
    assert advisor._picture_under(images, (-5, -5, 5, 5), (32, 32)) is None


def test_font_index_holding_a_list_is_rebuilt(monkeypatch, isolated_data_dir):
    monkeypatch.setattr(lettering, "font_dirs", lambda: [])
    isolated_data_dir.mkdir(parents=True, exist_ok=True)
    (isolated_data_dir / "font-index.json").write_text("[1, 2, 3]", encoding="utf-8")
    assert lettering.list_fonts() == []
    assert json.loads((isolated_data_dir / "font-index.json").read_text(encoding="utf-8"))["files"] == {}


def _tiny_font(path):
    pen = TTGlyphPen(None)
    notdef = pen.glyph()
    pen = TTGlyphPen(None)
    pen.moveTo((100, 0)); pen.lineTo((100, 700)); pen.lineTo((250, 700)); pen.lineTo((250, 0)); pen.closePath()  # noqa: E702
    glyphs = {".notdef": notdef, "I": pen.glyph()}
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(list(glyphs))
    fb.setupCharacterMap({ord("I"): "I"})
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({".notdef": (500, 0), "I": (350, 100)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Leftover Test", "styleName": "Regular"})
    fb.setupOS2(sCapHeight=700, sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    fb.save(str(path))
    return str(path)


def test_stitch_font_saved_with_its_own_extension(tmp_path):
    font = _tiny_font(tmp_path / "Tiny.ttf")
    r = lettering.export_stitch_font({"path": font, "family": "Tiny"}, str(tmp_path / "out" / "My font"), "I")
    assert r["path"].endswith("My font.luddfont")
    r = lettering.export_stitch_font({"path": font, "family": "Tiny"}, str(tmp_path / "Old.tlfont"), "I")
    assert r["path"].endswith("Old.tlfont")


def test_stitch_font_without_a_font_is_a_plain_message():
    with pytest.raises(LetteringError, match="Pick a font"):
        lettering.export_stitch_font({}, "", "")


@pytest.mark.parametrize("kind,spacing,want", [("fill", 10.0, 5.0), ("satin", 10.0, 3.0), ("fill", 0.1, 0.2), ("satin", 0.1, 0.15)])
def test_fabric_spacing_kept_within_each_stitch_type(kind, spacing, want):
    out = fabrics.apply({"kind": kind, "params": {"spacing_mm": spacing}}, "woven")
    assert out["params"]["spacing_mm"] == want


@pytest.mark.parametrize("spacing", [0, -1.0, float("nan")])
def test_fabric_leaves_an_impossible_spacing_for_the_stitch_type_to_refuse(spacing):
    out = fabrics.apply({"kind": "fill", "params": {"spacing_mm": spacing}}, "woven")
    assert out["params"]["spacing_mm"] is spacing


def test_help_names_the_text_tool_and_text_commands_with_their_keys():
    g = helpdocs.GUIDE
    assert "Text tool (Shift+T)" in g and "Text tool (T)" not in g
    assert "Ctrl+Alt+L" in g and "Ctrl+Alt+N" in g
