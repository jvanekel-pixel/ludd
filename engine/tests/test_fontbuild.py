"""A stitch font made from single-letter stitch files (P5-C1): guessing each file's character,
lining the letters up on one baseline, the version 2 .luddfont and how its letters are sewn.

The letter files are made here: capitals from a font built in the test, rendered and saved as
PES, and small hand-made files where a test needs exact sizes."""

import json
import math
import string
import zipfile
from pathlib import Path

import pyembroidery as pe
import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

import invariants
from threadline_engine import design, layout, lettering, project
from threadline_engine.lettering import LetteringError, fontbuild, fontfile, stitchglyphs

from test_lettering import CAP, UPM, _rect, font_path  # noqa: F401  (a tiny outline font built in the test)

RED = {"color": "#cc2222", "name": "Red", "catalog": "", "brand": ""}
GREY = {"color": "#888888", "name": "Grey", "catalog": "", "brand": ""}


# ---------------------------------------------------------------- helpers


def _item(font, text="ABC", **kw):
    font = font if isinstance(font, dict) else {"path": str(font), "index": 0}
    return {"id": "t", "kind": "text", "text": text, "font": font, "size_mm": 12, "spacing_mm": 0, "style": "satin",
            "shape": {"type": "line"}, "monogram": False, "thread": RED, "transform": {}, "threads": [], "ops": [], **kw}


def _layout_of(item):
    return {"items": [item], "merge_colors": False, "color_sort": False}


def _stitches(item):
    """Every record the text sews, in mm: (x, y, command)."""
    r = layout.render(_layout_of(item))
    return [(x / 10, y / 10, c & pe.COMMAND_MASK) for x, y, c in r.pattern.stitches if c & pe.COMMAND_MASK != pe.END]


def _summary(item):
    return layout.render_summary(_layout_of(item))


def _block_colors(s):
    return [s["threads"][b["thread"]]["color"] for b in s["blocks"]]


def _boxes(font, text, size=12.0, **spec):
    """The box round each letter's needle drops, in letter order, and the warnings."""
    objs, warnings = lettering.layout_text({"text": text, "font": font if isinstance(font, dict) else {"path": str(font)},
                                            "size_mm": size, **spec})
    pts: dict[int, list] = {}
    for o in objs:
        pts.setdefault(o["letter"], []).extend((x, y) for x, y, k in o["geometry"]["nodes"] if k == "s")
    out = []
    for n in sorted(pts):
        xs, ys = zip(*pts[n])
        out.append((min(xs), min(ys), max(xs), max(ys)))
    return out, warnings


def _rows(w, h, x=0.0, y=0.0, step=0.5):
    """Rows to and fro filling a w x h box whose top-left corner is (x, y): its needle drops span the box exactly."""
    n = max(1, round(h / step))
    pts = []
    for k in range(n + 1):
        yy = y + h * k / n
        ends = [(x, yy), (x + w / 2, yy), (x + w, yy)]
        pts += ends if k % 2 == 0 else ends[::-1]
    return pts


def _letter_file(path: Path, runs, ext="pes") -> str:
    """A letter file made by hand: `runs` = [(thread color, [(x, y) mm, ...])], one color block each."""
    p = pe.EmbPattern()
    for n, (color, pts) in enumerate(runs):
        if n:
            p.add_stitch_absolute(pe.COLOR_CHANGE, pts[0][0] * 10, pts[0][1] * 10)
        p.add_thread(pe.EmbThread(color))
        p.add_stitch_absolute(pe.JUMP, pts[0][0] * 10, pts[0][1] * 10)
        for x, y in pts:
            p.add_stitch_absolute(pe.STITCH, x * 10, y * 10)
    p.add_stitch_absolute(pe.END, 0, 0)
    out = path.with_suffix("." + ext)
    out.parent.mkdir(parents=True, exist_ok=True)
    pe.write(p, str(out), {"version": 6} if ext == "pes" else {})
    return str(out)


def _box_file(folder: Path, stem: str, w: float, h: float, color="#000000", ext="pes", x=0.0, y=0.0) -> str:
    return _letter_file(folder / stem, [(color, _rows(w, h, x, y))], ext)


def _build(letters, name="Mine", **kw):
    """build_from_files from [(path, char)] or [(path, char, dy_mm)]: the result and the font as saved."""
    picked = [{"path": p, "char": c, **({"dy_mm": rest[0]} if rest else {})} for p, c, *rest in letters]
    r = fontbuild.build_from_files(picked, name, **kw)
    return r, json.loads(Path(r["path"]).read_text(encoding="utf-8"))


def _font_ref(path, name="Mine"):
    return {"path": str(path), "index": 0, "family": name, "style": "Stitch font", "made_of": "stitches"}


def _no_fonts_saved():
    return not list(lettering.stitch_font_dir().glob("*.luddfont"))


# ---------------------------------------------------------------- the 26 letter files


def _capital_glyph(i):
    """A distinct blocky shape for the capital `i`: a stem, a bar whose height and length vary, and
    for every third letter a second stem."""
    pen = TTGlyphPen(None)
    _rect(pen, 60, 0, 170, CAP)
    y = 20 + (i % 7) * 90
    _rect(pen, 150, y, 330 + (i % 5) * 40, y + 110)
    if i % 3 == 0:
        _rect(pen, 400, 0, 500, CAP)
    return pen.glyph()


@pytest.fixture(scope="module")
def capitals_ttf(tmp_path_factory):
    glyphs = {".notdef": TTGlyphPen(None).glyph(), "space": TTGlyphPen(None).glyph()}
    glyphs.update({c: _capital_glyph(i) for i, c in enumerate(string.ascii_uppercase)})
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(list(glyphs))
    fb.setupCharacterMap({ord(" "): "space", **{ord(c): c for c in string.ascii_uppercase}})
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({".notdef": (500, 0), "space": (300, 0), **{c: (640, 60) for c in string.ascii_uppercase}})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Capitals Test", "styleName": "Regular"})
    fb.setupOS2(sCapHeight=CAP, sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupPost()
    path = tmp_path_factory.mktemp("capitals") / "CapitalsTest.ttf"
    fb.save(str(path))
    return str(path)


@pytest.fixture(scope="module")
def letter_folder(capitals_ttf, tmp_path_factory):
    """Each capital rendered at 12 mm and saved as its own PES, placed differently in each file
    (letter files are usually centered on themselves, wherever the digitizer left them)."""
    folder = tmp_path_factory.mktemp("letters")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("THREADLINE_DATA_DIR", str(tmp_path_factory.mktemp("letters-data")))
        for n, c in enumerate(string.ascii_uppercase):
            pattern = layout.render(_layout_of(_item(capitals_ttf, c))).pattern
            dx, dy = (n % 5) * 70 - 140, (n % 3) * 90 - 90
            pattern.stitches = [[x + dx, y + dy, cmd] for x, y, cmd in pattern.stitches]
            pe.write(pattern, str(folder / f"Test_{c}_12mm.pes"), {"version": 6})
    return folder


@pytest.fixture
def stitched_font(letter_folder):
    """The 26 letter files made into a stitch font in the (temporary) data folder."""
    scan = fontbuild.scan_letter_files(str(letter_folder))
    r = fontbuild.build_from_files([{"path": f["path"], "char": f["guess"]} for f in scan["files"]], "Test Letters")
    return _font_ref(r["path"], "Test Letters")


# ---------------------------------------------------------------- guessing characters


@pytest.mark.parametrize("name,char", [
    # one character
    ("A", "A"), ("a", "a"), ("7", "7"), ("&", "&"), ("é", "é"), ("e\u0301", "é"),  # also decomposed, as macOS names files
    # marked upper case (any separator, any case)
    ("upper_a", "A"), ("uc_a", "A"), ("cap_a", "A"), ("a_upper", "A"), ("a_cap", "A"),
    ("UPPER-A", "A"), ("Uc a", "A"), ("Cap.a", "A"), ("A_Upper", "A"), ("a-CAP", "A"), ("capA", "A"),
    # marked lower case
    ("lower_a", "a"), ("lc_a", "a"), ("small_a", "a"), ("a_lower", "a"), ("a_small", "a"),
    ("LOWER-A", "a"), ("Lc A", "a"), ("A_Small", "a"), ("smallA", "a"),
    # digits spelled out
    ("zero", "0"), ("one", "1"), ("two", "2"), ("three", "3"), ("four", "4"), ("five", "5"), ("six", "6"),
    ("seven", "7"), ("eight", "8"), ("nine", "9"), ("Nine", "9"),
    # punctuation spelled out
    ("ampersand", "&"), ("and", "&"), ("period", "."), ("dot", "."), ("comma", ","), ("exclam", "!"),
    ("exclamation", "!"), ("question", "?"), ("apostrophe", "'"), ("hyphen", "-"), ("dash", "-"), ("colon", ":"),
    ("semicolon", ";"), ("quote", '"'), ("slash", "/"), ("at", "@"), ("hash", "#"), ("number", "#"), ("heart", "♥"),
    ("Heart", "♥"),
    # anything else is left for you
    ("", ""), ("flower", ""), ("Curly_A_4in", ""), ("ab", ""), ("A (1)", ""), ("preview", ""), ("100", ""),
])
def test_guess_char_table(name, char):
    assert fontbuild.guess_char(name) == char


@pytest.mark.parametrize("names,chars,prefix,suffix", [
    (["Curly_A_4in", "Curly_B_4in", "Curly_C_4in"], "ABC", "Curly_", "_4in"),
    (["Curly A 4in", "Curly b 4in", "Curly C 4in"], "AbC", "Curly ", " 4in"),
    (["RoseA4in", "RoseB4in", "RoseC4in"], "ABC", "Rose", "4in"),
    (["fonta", "fontb", "fontc"], "abc", "font", ""),
    # The words that say which case a letter is stay with it.
    (["upper_a", "upper_b", "upper_c"], "ABC", "", ""),
    (["a_lower", "b_lower", "c_lower"], "abc", "", ""),
    (["Rose_uc_a", "Rose_uc_b"], "AB", "Rose_", ""),
    (["a_cap_5in", "b_cap_5in"], "AB", "", "_5in"),
    (["capA", "capB", "capC"], "ABC", "", ""),
    # Numbers: never cut between two digits; 33 to 126 are ASCII codes.
    (["65", "66", "97", "38"], "ABa&", "", ""),
    (["Curly_65", "Curly_66", "Curly_67"], "ABC", "Curly_", ""),
    (["65_Curly", "66_Curly"], "AB", "", "_Curly"),
    (["0", "1", "2"], "012", "", ""),
    # Words are never cut in the middle.
    (["comma", "colon"], ",:", "", ""),
    (["Script_comma", "Script_colon", "Script_a"], ",:a", "Script_", ""),
    (["alpha_zero", "alpha_one"], "01", "alpha_", ""),
    (["Curly_-", "Curly_A", "Curly_!"], "-A!", "Curly_", ""),
])
def test_the_shared_prefix_and_suffix_are_removed(names, chars, prefix, suffix):
    got, p, s = fontbuild.guess_chars(names)
    assert (got, p, s) == (list(chars), prefix, suffix)


def test_nothing_is_shared_with_only_one_name():
    assert fontbuild.guess_chars(["Curly_A_4in"]) == ([""], "", "")
    assert fontbuild.guess_chars(["Curly_A", "Curly_A"]) == (["", ""], "", "")  # the same letter twice
    assert fontbuild.guess_chars(["A", "preview", "10"]) == (["A", "", ""], "", "")


# ---------------------------------------------------------------- scanning


def test_scan_lists_every_design_by_name(tmp_path):
    folder = tmp_path / "set"
    _box_file(folder, "Curly_B_4in", 6, 10, "#ff0000")
    _letter_file(folder / "Curly_a_4in", [("#000000", _rows(4, 7)), ("#ff0000", _rows(2, 2, 1, 1))])
    (folder / "Curly_C_4in.pes").write_bytes(b"not a design at all")
    (folder / "readme.txt").write_text("thanks for buying", encoding="utf-8")
    (folder / "._Curly_B_4in.pes").write_bytes(b"\x00\x05\x16\x07")  # what macOS leaves on USB sticks
    (folder / "more").mkdir()
    _box_file(folder / "more", "Curly_D_4in", 6, 10)

    scan = fontbuild.scan_letter_files(str(folder))
    files = scan["files"]
    assert [f["name"] for f in files] == ["Curly_a_4in.pes", "Curly_B_4in.pes", "Curly_C_4in.pes"]
    assert scan["common"] == {"prefix": "Curly_", "suffix": "_4in"}
    assert [f["guess"] for f in files] == ["a", "B", ""]
    a, b, bad = files
    assert (b["width_mm"], b["height_mm"], b["colors"]) == (6, 10, 1)
    assert (a["width_mm"], a["height_mm"], a["colors"]) == (4, 7, 2)
    assert a["stitches"] == len(_rows(4, 7)) + len(_rows(2, 2))
    assert a["thumb"].startswith("data:image/png;base64,") and b["thumb"].startswith("data:image/png;base64,")
    assert bad["error"] and bad["thumb"] == "" and bad["stitches"] == 0
    assert "error" not in a and "error" not in b


def test_scan_takes_the_files_you_pick(tmp_path):
    two = _box_file(tmp_path, "x_two", 5, 10)
    one = _box_file(tmp_path / "elsewhere", "x_one", 5, 10)
    scan = fontbuild.scan_letter_files(files=[two, one, two])
    assert [(f["name"], f["guess"]) for f in scan["files"]] == [("x_one.pes", "1"), ("x_two.pes", "2")]


def test_scan_says_what_is_wrong(tmp_path):
    with pytest.raises(LetteringError, match="Choose a folder"):
        fontbuild.scan_letter_files()
    with pytest.raises(LetteringError, match="Choose a folder"):
        fontbuild.scan_letter_files(files="a.pes")
    with pytest.raises(LetteringError, match="No embroidery"):
        fontbuild.scan_letter_files(str(tmp_path))
    with pytest.raises(LetteringError, match="Couldn't find"):
        fontbuild.scan_letter_files(str(tmp_path / "nowhere"))


def test_scan_refuses_a_folder_far_bigger_than_a_font(tmp_path):
    for n in range(fontbuild.MAX_LETTER_FILES + 1):
        (tmp_path / f"{n}.dst").write_bytes(b"x")
    with pytest.raises(LetteringError, match=str(fontbuild.MAX_LETTER_FILES)):
        fontbuild.scan_letter_files(str(tmp_path))


# ---------------------------------------------------------------- building


def test_26_letter_files_become_a_font(letter_folder):
    """Done-when 2: a folder of 26 single-letter PES files becomes a stitch font, and "ABC" typed
    in it sews with the letters on one baseline."""
    scan = fontbuild.scan_letter_files(str(letter_folder))
    assert [f["guess"] for f in scan["files"]] == list(string.ascii_uppercase)
    assert scan["common"] == {"prefix": "Test_", "suffix": "_12mm"}

    r = fontbuild.build_from_files([{"path": f["path"], "char": f["guess"]} for f in scan["files"]], "Test Letters")
    assert r["glyphs"] == 26
    heights = sorted(f["height_mm"] for f in scan["files"])
    assert r["cap_height_mm"] == pytest.approx((heights[12] + heights[13]) / 2, abs=0.001)  # the capitals' median
    assert r["cap_height_mm"] == pytest.approx(12, abs=0.6)  # 12 mm letters, measured round their needle drops
    assert Path(r["folder"]) == lettering.stitch_font_dir() and Path(r["path"]).parent == lettering.stitch_font_dir()
    assert Path(r["path"]).name == "Test Letters.luddfont"

    doc = fontfile._load_stitch_font(r["path"])
    assert (doc["version"], doc["name"], doc["cap_height_mm"]) == (2, "Test Letters", r["cap_height_mm"])
    assert set(doc["glyphs"]) == set(string.ascii_uppercase) and len(doc["threads"]) == 1
    g = doc["glyphs"]["A"]
    assert g["advance_mm"] > 0 and {k for _, _, k in g["stitches"]} <= {"s", "j", "t"}
    assert g["blocks"] == [[0, len(g["stitches"]), 0]]
    # Nothing about your files goes into the font: no names, no folders.
    text = Path(r["path"]).read_text(encoding="utf-8")
    assert "Test_" not in text and str(letter_folder.name) not in text

    boxes, warnings = _boxes(_font_ref(r["path"]), "ABC", size=r["cap_height_mm"])
    assert not warnings and len(boxes) == 3
    assert max(b[3] for b in boxes) - min(b[3] for b in boxes) <= 0.2
    s = _summary(_item(_font_ref(r["path"]), "ABC"))
    assert s["info"]["stitches"] > 300 and s["info"]["colors"] == 1


def test_ABC_sits_on_one_baseline(stitched_font):
    """Each letter file placed them differently; the font lines them up by their own bottoms."""
    boxes, _ = _boxes(stitched_font, "ABC", size=12)
    bottoms = [b[3] for b in boxes]
    assert max(bottoms) - min(bottoms) <= 0.2
    # Straight text puts the baseline half the letter height below the middle.
    assert bottoms == pytest.approx([6, 6, 6], abs=0.2)
    assert boxes[0][2] < boxes[1][0] and boxes[1][2] < boxes[2][0]  # left to right, not on top of each other


def test_descenders_hang(tmp_path):
    """A g whose file reaches further down than the a's hangs below the line, its top level with the a's."""
    files = [(_box_file(tmp_path, "H", 6, 10), "H"), (_box_file(tmp_path, "a_lower", 5, 7), "a"),
             (_box_file(tmp_path, "g_lower", 5, 10, y=-20), "g")]
    r, _ = _build(files)
    assert r["cap_height_mm"] == 10
    (h, a, g), _ = _boxes(r["path"], "Hag", size=10)
    assert a[3] == pytest.approx(h[3], abs=0.01)  # on the baseline
    assert g[1] == pytest.approx(a[1], abs=0.01)  # its top at the a's
    assert g[3] == pytest.approx(a[3] + 3, abs=0.01)  # so it sits lower


def test_without_small_letters_descenders_hang_at_68_percent(tmp_path):
    r, _ = _build([(_box_file(tmp_path, "H", 6, 10), "H"), (_box_file(tmp_path, "p_lower", 5, 9), "p")])
    (h, p), _ = _boxes(r["path"], "Hp", size=10)
    assert p[1] == pytest.approx(h[3] - 6.8, abs=0.01)


def test_punctuation_sits_where_it_belongs(tmp_path):
    shapes = {"H": (6, 10), "x": (5, 7), "comma": (2, 3), "semicolon": (2, 7), "apostrophe": (1, 3), "quote": (3, 3),
              "hyphen": (4, 1), "period": (2, 2), "^": (3, 2)}
    chars = {"H": "H", "x": "x", "comma": ",", "semicolon": ";", "apostrophe": "'", "quote": '"', "hyphen": "-",
             "period": ".", "^": "^"}
    r, _ = _build([(_box_file(tmp_path, f"f{n}", *shapes[k]), chars[k]) for n, k in enumerate(shapes)])
    text = "H" + "".join(chars[k] for k in shapes if k != "H")
    boxes, _ = _boxes(r["path"], text, size=10)
    box = dict(zip(text, boxes))
    base = box["H"][3]
    for ch in ",;":
        assert box[ch][3] == pytest.approx(base + 1.5, abs=0.01), ch  # hangs by 15% of the capital height
    for ch in "'\"^":
        assert box[ch][1] == pytest.approx(base - 10, abs=0.01), ch  # at the top
    assert (box["-"][1] + box["-"][3]) / 2 == pytest.approx(base - 5, abs=0.01)  # in the middle
    assert box["."][3] == pytest.approx(base, abs=0.01) and box["x"][3] == pytest.approx(base, abs=0.01)


@pytest.mark.parametrize("sizes,cap", [
    ({"H": 10, "I": 14, "7": 11}, 11),  # the median of the capitals and digits
    ({"H": 10, "I": 11, "a": 7, "b": 20}, 10.5),  # small letters don't count
    ({"a": 7, "b": 10, "d": 10.4}, 10.2),  # no capitals or digits: the tall small letters
    ({"a": 6.8, "o": 6.8}, 10),  # only small ones: they're 68% of a capital
])
def test_the_capital_height(tmp_path, sizes, cap):
    r, _ = _build([(_box_file(tmp_path, f"f{n}", 5, h), c) for n, (c, h) in enumerate(sizes.items())])
    assert r["cap_height_mm"] == pytest.approx(cap, abs=0.01)


def test_a_nudge_from_the_dialog_overrides_the_baseline(tmp_path):
    h = _box_file(tmp_path, "H", 6, 10)
    q = _box_file(tmp_path, "q_lower", 5, 10)
    r, _ = _build([(h, "H"), (q, "q", -0.5)])
    (hh, qq), _ = _boxes(r["path"], "Hq", size=10)
    assert qq[3] == pytest.approx(hh[3] - 0.5, abs=0.01)  # its bottom 0.5 mm above the baseline, not hanging


def test_letter_gap_sets_the_advance(tmp_path):
    files = [(_box_file(tmp_path, "H", 5, 10), "H"), (_box_file(tmp_path, "M", 8, 10), "M")]
    _, doc = _build(files)  # 8% of the capital height by default
    assert [doc["glyphs"][c]["advance_mm"] for c in "HM"] == pytest.approx([5.8, 8.8], abs=0.001)
    r, wide = _build(files, "Wide", gap_pct=20)
    assert [wide["glyphs"][c]["advance_mm"] for c in "HM"] == pytest.approx([7, 10], abs=0.001)
    (h, m), _ = _boxes(r["path"], "HM", size=10)
    assert m[0] - h[2] == pytest.approx(2, abs=0.01)  # the gap, between the letters
    # Letters sit in the middle of their space, so they stand straight on an arch too.
    xs = [x for x, _, _ in wide["glyphs"]["H"]["stitches"]]
    assert (min(xs), max(xs)) == pytest.approx((1, 6), abs=0.001)
    # The font's own space is a share of the capital height.
    assert wide["space_mm"] == pytest.approx(3.5, abs=0.001)


def test_duplicate_and_unassigned_are_reported_not_built(tmp_path):
    a1 = _box_file(tmp_path, "first_a", 5, 10)
    a2 = _box_file(tmp_path, "second_a", 5, 10)
    none = _box_file(tmp_path, "mystery", 5, 10)
    two = _box_file(tmp_path, "two_chars", 5, 10)
    with pytest.raises(LetteringError) as exc:
        _build([(a1, "A"), (a2, "A"), (none, ""), (two, "AB")])
    message = str(exc.value)
    for word in ("A", "first_a.pes", "second_a.pes", "mystery.pes", "two_chars.pes"):
        assert word in message, word
    assert _no_fonts_saved()
    with pytest.raises(LetteringError, match="mystery.pes"):
        _build([(a1, "A"), (none, " ")])
    assert _no_fonts_saved()


def test_a_heart_typed_as_an_emoji_is_the_same_heart(tmp_path):
    _, doc = _build([(_box_file(tmp_path, "H", 5, 10), "H"), (_box_file(tmp_path, "love", 5, 5), "♥\ufe0f")])
    assert set(doc["glyphs"]) == {"H", "♥"}


def test_build_says_what_is_wrong(tmp_path):
    h = _box_file(tmp_path, "H", 5, 10)
    bad = tmp_path / "bad.pes"
    bad.write_bytes(b"not a design")
    for letters, name, kw, words in [
        ([], "Mine", {}, "at least one"),
        ([(h, "H")], "  ", {}, "name"),
        ([(h, "H")], "Mine", {"gap_pct": 500}, "gap"),
        ([(h, "H")], "Mine", {"gap_pct": float("nan")}, "gap"),
        ([(str(bad), "H")], "Mine", {}, "bad.pes"),
        ([(str(tmp_path / "gone.pes"), "H")], "Mine", {}, "gone.pes"),
        ([(h, "H", "high")], "Mine", {}, "nudge"),
    ]:
        with pytest.raises(LetteringError, match=words):
            _build(letters, name, **kw)
    assert _no_fonts_saved()


def test_a_new_font_never_replaces_an_old_one(tmp_path):
    h = _box_file(tmp_path, "H", 5, 10)
    first, _ = _build([(h, "H")], "Mine")
    second, _ = _build([(h, "H")], "Mine")
    assert first["path"] != second["path"] and Path(first["path"]).exists()
    odd, _ = _build([(h, "H")], 'CON')  # a name Windows keeps for itself still saves
    assert Path(odd["path"]).exists()
    chosen = tmp_path / "out" / "chosen"
    r, _ = _build([(h, "H")], "Mine", dest=str(chosen))
    assert r["path"] == str(chosen) + ".luddfont" and Path(r["path"]).exists()


def test_the_same_files_make_the_same_font(stitched_font, letter_folder):
    scan = fontbuild.scan_letter_files(str(letter_folder))
    again = fontbuild.build_from_files([{"path": f["path"], "char": f["guess"]} for f in scan["files"]], "Test Letters")
    assert Path(again["path"]).read_text(encoding="utf-8") == Path(stitched_font["path"]).read_text(encoding="utf-8")


def test_a_letter_files_jumps_and_trims_are_kept_inside_the_letter(tmp_path):
    p = pe.EmbPattern()
    p.add_thread(pe.EmbThread("#000000"))
    for cmd, x, y in [(pe.JUMP, 0, 0), (pe.STITCH, 0, 0), (pe.STITCH, 30, 0), (pe.TRIM, 30, 0), (pe.JUMP, 30, 100),
                      (pe.STITCH, 30, 100), (pe.STITCH, 0, 100), (pe.STOP, 0, 100), (pe.STITCH, 0, 80),
                      (pe.TRIM, 0, 80), (pe.JUMP, 200, 200), (pe.END, 200, 200)]:
        p.add_stitch_absolute(cmd, x, y)
    path = tmp_path / "H.pes"
    pe.write(p, str(path), {"version": 6})
    _, doc = _build([(str(path), "H")])
    kinds = "".join(k for _, _, k in doc["glyphs"]["H"]["stitches"])
    assert kinds.startswith("s") and kinds.endswith("s")  # the moves before and after aren't part of the letter
    assert "t" in kinds and "j" in kinds
    assert len(doc["glyphs"]["H"]["blocks"]) == 1  # a stop doesn't start a new color
    assert doc["cap_height_mm"] == pytest.approx(10, abs=0.01)  # the trailing jump doesn't count as height


# ---------------------------------------------------------------- sewing the letters


def test_stitched_letters_are_parts_made_of_their_stitches(stitched_font):
    objs, _ = lettering.layout_text({"text": "AB", "font": stitched_font, "size_mm": 12})
    assert [(o["kind"], o["letter"], o["color_index"], "thread" in o) for o in objs] == [
        ("stitches", 0, 0, False), ("stitches", 1, 0, False)]
    for o in objs:
        recs = stitchglyphs.records(o)
        assert recs[0][2] == pe.STITCH and {c for _, _, c in recs} <= {pe.STITCH, pe.JUMP, pe.TRIM}
        assert [(x, y) for x, y, _ in recs] == [(n[0], n[1]) for n in o["geometry"]["nodes"]]


def test_stitched_text_passes_the_invariants(stitched_font):
    recs = [r for r in _stitches(_item(stitched_font, "ABC")) if r[2] in (pe.STITCH, pe.JUMP, pe.TRIM)]
    invariants.assert_sane(recs, max_stitch_mm=7.15)
    invariants.assert_deterministic(lambda: _stitches(_item(stitched_font, "ABC")))


def test_stitched_text_moves_slants_and_bends_like_any_text(stitched_font):
    item = _item(stitched_font, "ABC")
    plain = _stitches(item)
    # Moved and turned with the text, like any text: every needle drop goes with it.
    turned = _stitches({**item, "transform": {"x": 20, "y": -5, "rotate": 90}})
    assert [c for *_, c in turned] == [c for *_, c in plain]
    for (x, y, _), (mx, my, _) in zip(plain, turned):
        assert (mx, my) == pytest.approx((20 - y, x - 5), abs=0.05)
    # On an arch each letter is turned whole about its own middle: the outer ones lean outwards.
    flat, _ = lettering.layout_text({"text": "ABC", "font": stitched_font, "size_mm": 12})
    arched, _ = lettering.layout_text({"text": "ABC", "font": stitched_font, "size_mm": 12,
                                       "shape": {"type": "arc_up", "radius_mm": 25}})
    tilts = []
    for before, after in zip(flat, arched):
        a, b = before["geometry"]["nodes"], after["geometry"]["nodes"]
        assert [n[2] for n in a] == [n[2] for n in b]
        assert [math.dist(p[:2], q[:2]) for p, q in zip(a, a[1:])] == pytest.approx(
            [math.dist(p[:2], q[:2]) for p, q in zip(b, b[1:])], abs=0.01)  # turned, not stretched
        i = max(range(len(a) - 1), key=lambda k: (round(math.dist(a[k][:2], a[k + 1][:2]), 3), -k))
        angle = lambda ns: math.atan2(ns[i + 1][1] - ns[i][1], ns[i + 1][0] - ns[i][0])  # noqa: E731
        tilts.append(math.degrees(math.remainder(angle(b) - angle(a), math.tau)))
    assert tilts[0] < -5 and abs(tilts[1]) < 3 and tilts[2] > 5
    # A shear (what slant and envelopes do to every part) moves the stitches and keeps their kinds.
    k = math.tan(math.radians(15))
    sheared = lettering._move(flat[0], lambda x, y: (x - y * k, y))
    assert [n[2] for n in sheared["geometry"]["nodes"]] == [n[2] for n in flat[0]["geometry"]["nodes"]]
    assert stitchglyphs.records(sheared) == [(x - y * k, y, c) for x, y, c in stitchglyphs.records(flat[0])]
    # With Track A's slant and envelopes in (until then these render as straight text):
    slanted = _stitches({**item, "slant_deg": 15})
    if slanted != plain:  # tops lean right, by their height times tan(15°)
        assert [c for *_, c in slanted] == [c for *_, c in plain]
        pairs = [(p, s) for p, s in zip(plain, slanted) if p[2] == pe.STITCH]
        top, bottom = min(pairs, key=lambda ps: ps[0][1]), max(pairs, key=lambda ps: ps[0][1])
        lean = (top[1][0] - top[0][0]) - (bottom[1][0] - bottom[0][0])
        assert lean == pytest.approx((bottom[0][1] - top[0][1]) * k, abs=0.1)
    bent = _stitches({**item, "envelope": {"type": "bulge", "amount": 1}})
    if bent != plain:  # taller in the middle
        height = lambda recs: max(y for _, y, c in recs if c == pe.STITCH) - min(y for _, y, c in recs if c == pe.STITCH)  # noqa: E731
        assert height(bent) > height(plain) * 1.3


def _two_color_font(tmp_path, letters="AB", extra=()):
    """Letters with a red box, then a blue line over it."""
    files = []
    for n, c in enumerate(letters):
        path = _letter_file(tmp_path / f"two_{c}", [("#cc0000", _rows(5, 10)),
                                                    ("#0000cc", [(1, 2 + n), (3, 2 + n), (4, 3 + n)])])
        files.append((path, c))
    files += [(_letter_file(tmp_path / f"extra_{n}", runs), c) for n, (c, runs) in enumerate(extra)]
    r, doc = _build(files, "Two Colors")
    return r, doc


def test_two_color_font_sews_color_by_color(tmp_path):
    r, doc = _two_color_font(tmp_path)
    assert [t["color"] for t in doc["threads"]] == ["#cc0000", "#0000cc"]
    assert [b[2] for b in doc["glyphs"]["A"]["blocks"]] == [0, 1]
    objs, _ = lettering.layout_text({"text": "AB", "font": _font_ref(r["path"]), "size_mm": 10})
    assert [(o["letter"], o["color_index"], o["thread"]["color"]) for o in objs] == [
        (0, 0, "#cc0000"), (0, 1, "#0000cc"), (1, 0, "#cc0000"), (1, 1, "#0000cc")]

    s = _summary(_item(_font_ref(r["path"]), "AB", size_mm=10))
    assert _block_colors(s) == ["#cc0000", "#0000cc"]  # both red boxes, then both blue lines
    assert [(run["letters"], run["slots"]) for run in s["items"][0]["runs"]] == [([0, 1], [0]), ([0, 1], [1])]
    assert [p["letter"] for p in s["items"][0]["letters"]] == [0, 1, 0, 1]
    # Order & colors changes one of the font's colors; the text's own color doesn't repaint them.
    s = _summary(_item(_font_ref(r["path"]), "AB", size_mm=10, threads=[None, GREY]))
    assert _block_colors(s) == ["#cc0000", GREY["color"]]
    assert s["blocks"][1]["original"]["color"] == "#0000cc"
    s = _summary(_item(_font_ref(r["path"]), "AB", size_mm=10, threads=[GREY]))
    assert _block_colors(s) == [GREY["color"], "#0000cc"]


def test_a_color_only_some_letters_use_keeps_each_letters_order(tmp_path):
    # "." comes first in the folder and has only the second color: it must not move that color first.
    r, doc = _two_color_font(tmp_path, extra=[(".", [("#0000cc", _rows(2, 2))])])
    files = [(str(tmp_path / "extra_0.pes"), "."), (str(tmp_path / "two_A.pes"), "A")]
    _, again = _build(files, "Order")
    for font in (doc, again):
        assert [t["color"] for t in font["threads"]] == ["#cc0000", "#0000cc"]
        assert [b[2] for b in font["glyphs"]["."]["blocks"]] == [1]
        assert [b[2] for b in font["glyphs"]["A"]["blocks"]] == [0, 1]


def test_a_color_used_again_later_stays_later(tmp_path):
    runs = [("#cc0000", _rows(5, 10)), ("#0000cc", _rows(2, 2, 1, 1)), ("#cc0000", [(0, 0), (5, 10)])]
    _, doc = _build([(_letter_file(tmp_path / "B", runs), "B")])
    assert [t["color"] for t in doc["threads"]] == ["#cc0000", "#0000cc", "#cc0000"]
    assert [b[2] for b in doc["glyphs"]["B"]["blocks"]] == [0, 1, 2]


def test_a_one_color_font_sews_in_the_texts_thread(tmp_path):
    # Even when the files themselves were saved in different colors.
    files = [(_box_file(tmp_path, "H", 5, 10, "#123456"), "H"), (_box_file(tmp_path, "I", 3, 10, "#654321"), "I")]
    r, doc = _build(files)
    assert len(doc["threads"]) == 1 and all(g["blocks"][0][2] == 0 for g in doc["glyphs"].values())
    s = _summary(_item(_font_ref(r["path"]), "HI", size_mm=10))
    assert _block_colors(s) == [RED["color"]]
    assert [run["slots"] for run in s["items"][0]["runs"]] == [[0]]
    s = _summary(_item(_font_ref(r["path"]), "HI", size_mm=10, threads=[GREY]))
    assert _block_colors(s) == [GREY["color"]]


def test_letter_files_without_thread_colors_keep_their_color_change(tmp_path):
    """DST files carry no thread colors; two color blocks must still be two colors to the machine."""
    files = []
    for c in "AB":
        runs = [("#000000", _rows(5, 10)), ("#000000", _rows(2, 2, 1, 1))]
        files.append((_letter_file(tmp_path / c, runs, ext="dst"), c))
    r, doc = _build(files)
    assert len(doc["threads"]) == 2 and doc["threads"][0]["color"] != doc["threads"][1]["color"]
    s = _summary(_item(_font_ref(r["path"]), "AB", size_mm=10))
    assert s["info"]["colors"] == 2 and s["info"]["color_changes"] == 1


def test_the_text_can_have_spaces_and_missing_letters(stitched_font):
    boxes, warnings = _boxes(stitched_font, "A B", size=12)
    assert len(boxes) == 2 and not warnings
    assert boxes[1][0] - boxes[0][2] > 3  # a space between
    boxes, warnings = _boxes(stitched_font, "aB?", size=12)
    assert len(boxes) == 2  # a is drawn as A; ? is left out
    assert any("a as A" in w for w in warnings) and any("?" in w for w in warnings)


# ---------------------------------------------------------------- resizing


def _scaled_glyphs(font_file, text, k):
    doc = fontfile._load_stitch_font(font_file)
    return [[[round(x * k, 3), round(y * k, 3), c] for x, y, c in doc["glyphs"][ch]["stitches"]] for ch in text]


def _longest(nodes):
    return max(math.dist(a[:2], b[:2]) for a, b in zip(nodes, nodes[1:]) if b[2] == "s")


def test_sizes_within_20_percent_resize_as_they_are(stitched_font):
    cap = fontfile._load_stitch_font(stitched_font["path"])["cap_height_mm"]
    for k in (0.8, 1.0, 1.2):
        assert stitchglyphs.size_notes(stitched_font["path"], cap * k) == []
        doc = fontfile._load_stitch_font(stitched_font["path"])
        for ch in "AB":
            (part,) = stitchglyphs.letter_objects(doc, doc["glyphs"][ch], k)
            assert part["geometry"]["nodes"] == _scaled_glyphs(stitched_font["path"], ch, k)[0]
    _, warnings = lettering.layout_text({"text": "AB", "font": stitched_font, "size_mm": round(cap * 1.1, 2)})
    assert not warnings


@pytest.mark.parametrize("k", [0.6, 1.6])
def test_letters_past_20_percent_are_rebuilt(stitched_font, k):
    cap = fontfile._load_stitch_font(stitched_font["path"])["cap_height_mm"]
    (note,) = stitchglyphs.size_notes(stitched_font["path"], cap * k)
    assert "20%" in note and f"{k * 100:.0f}%" in note
    objs, warnings = lettering.layout_text({"text": "ABD", "font": stitched_font, "size_mm": cap * k})
    assert warnings == [note] if k > 1 else note in warnings  # smaller letters also warn that they're small
    resized = _scaled_glyphs(stitched_font["path"], "ABD", k)
    for part, plain in zip(objs, resized):
        nodes = part["geometry"]["nodes"]
        drops = sum(1 for n in nodes if n[2] == "s")
        plain_drops = sum(1 for n in plain if n[2] == "s")
        # Rebuilt: more stitches for a bigger letter and fewer for a smaller one, instead of the
        # same ones stretched or squeezed, and about the same size as a plain resize.
        assert drops > plain_drops * 1.2 if k > 1 else drops < plain_drops * 0.95
        if k > 1:
            assert _longest(nodes) < _longest(plain)
        for i in (0, 1):  # width and height (the parts are placed in the text; the glyphs aren't)
            want = [n[i] for n in plain if n[2] == "s"]
            got = [n[i] for n in nodes if n[2] == "s"]
            assert max(got) - min(got) == pytest.approx(max(want) - min(want), abs=0.8)
    again, _ = lettering.layout_text({"text": "ABD", "font": stitched_font, "size_mm": cap * k})
    assert again == objs


def test_a_font_made_of_shapes_gets_no_size_note(font_path, tmp_path):
    dest = tmp_path / "v1.luddfont"
    lettering.export_stitch_font({"path": font_path, "family": "Threadline Test"}, str(dest), "IOX", cap_height_mm=12)
    assert stitchglyphs.size_notes(str(dest), 30) == []
    assert stitchglyphs.size_notes(str(tmp_path / "gone.luddfont"), 30) == []


# ---------------------------------------------------------------- old fonts, the font list, projects, export


def test_version_1_fonts_still_load(font_path, tmp_path):
    dest = tmp_path / "v1.luddfont"
    lettering.export_stitch_font({"path": font_path, "family": "Threadline Test"}, str(dest), "IOX", cap_height_mm=12)
    assert json.loads(dest.read_text(encoding="utf-8"))["version"] == 1
    objs, warnings = lettering.layout_text({"text": "IO", "font": {"path": str(dest)}, "size_mm": 30})
    assert not warnings and [o["kind"] for o in objs] == ["fill", "fill"]
    assert _summary(_item(str(dest), "IOX"))["info"]["stitches"] > 100


def test_font_list_marks_stitched_fonts(stitched_font, font_path, monkeypatch):
    folder = lettering.stitch_font_dir()
    lettering.export_stitch_font({"path": font_path, "family": "Threadline Test"}, str(folder / "shapes.luddfont"), "IO")
    monkeypatch.setattr(lettering.fonts, "font_dirs", lambda: [folder])
    fonts = {f["family"]: f for f in lettering.list_fonts()}
    made = fonts["Test Letters"]
    assert (made["kind"], made["style"], made.get("made_of")) == ("stitch", "Stitch font", "stitches")
    shapes = [f for f in fonts.values() if f["family"] != "Test Letters"]
    assert shapes and all(f["kind"] == "stitch" and "made_of" not in f for f in shapes)


def test_an_older_font_index_is_rebuilt(stitched_font, isolated_data_dir, monkeypatch):
    folder = lettering.stitch_font_dir()
    monkeypatch.setattr(lettering.fonts, "font_dirs", lambda: [folder])
    path = Path(stitched_font["path"])
    stale = {"version": 3, "files": {str(path): {"mtime": path.stat().st_mtime, "entries": [
        {"family": "Test Letters", "style": "Stitch font", "index": 0, "kind": "stitch"}]}}}
    isolated_data_dir.mkdir(parents=True, exist_ok=True)
    (isolated_data_dir / "font-index.json").write_text(json.dumps(stale), encoding="utf-8")
    (made,) = lettering.list_fonts()
    assert made.get("made_of") == "stitches"
    assert lettering.INDEX_VERSION > 3


def test_project_embeds_a_stitched_font_and_reopens(stitched_font, tmp_path):
    item = _item(stitched_font, "CAB")
    before = _stitches(item)
    saved = project.save(str(tmp_path / "name.ludd"), {"title": "name", "layout": {"items": [item]}, "images": []})
    assert saved["fonts"] == 1
    with zipfile.ZipFile(saved["path"]) as z:
        manifest = json.loads(z.read("project.json"))
    assert "font_stitch_glyphs" in manifest["features"] and manifest["version"] == 2
    Path(stitched_font["path"]).unlink()

    opened = project.open_project(saved["path"])["layout"]["items"][0]
    assert opened["font"]["made_of"] == "stitches"
    assert Path(opened["font"]["path"]).is_file() and opened["font"]["path"] != stitched_font["path"]
    assert _stitches(opened) == before


def test_break_into_shapes_says_why_not(stitched_font):
    with pytest.raises(layout.LayoutError, match="Letters from a stitched font have no outlines to edit."):
        layout.text_to_shapes(_item(stitched_font, "AB"))


def test_stitched_text_passes_the_other_checks_and_hidden_removal(stitched_font):
    """Quality checks, and "Don't sew what's hidden under shapes on top" with lettering over a fill."""
    square = {"id": "f", "kind": "fill", "geometry": {"outline": [[-15, -8, "c"], [15, -8, "c"], [15, 8, "c"],
                                                                 [-15, 8, "c"]]},
              "params": {}, "thread": GREY, "transform": {}, "threads": [], "ops": []}
    lay = {"items": [square, _item(stitched_font, "ABC")], "merge_colors": False, "color_sort": False,
           "remove_overlap": {"enabled": True}}
    assert layout.render_summary(lay)["info"]["colors"] == 2
    assert layout.check(lay)["checks"] is not None


@pytest.mark.parametrize("ext", ["pes", "jef"])
def test_stitched_text_exports(tmp_path, ext):
    r, _ = _two_color_font(tmp_path)
    lay = _layout_of(_item(_font_ref(r["path"]), "ABBA", size_mm=10))
    want = layout.render_summary(lay)["info"]
    out = tmp_path / f"name.{ext}"
    layout.export(lay, str(out))
    got = design.open_design(str(out))["info"]
    assert (got["stitches"], got["colors"]) == (want["stitches"], 2)
    assert (got["width_mm"], got["height_mm"]) == pytest.approx((want["width_mm"], want["height_mm"]), abs=0.15)


@pytest.mark.parametrize("damage", [
    {"stitches": [[0, 0, "s"], [1, 0, "q"]]},
    {"stitches": [[0, 0, "s"], [float("nan"), 0, "s"]]},
    {"stitches": [[0, 0, "s"], [1, 0]]},
    {"stitches": [[0, 0, "s"], [10 ** 400, 0, "s"]]},
    {"stitches": [[0, 0, "s"], ["1", 0, "s"]]},
    {"stitches": "ssss"},
    {"stitches": [[0, 0, "s"], [1, 0, "s"]], "blocks": [[0, 5, 0]]},
    {"stitches": [[0, 0, "s"], [1, 0, "s"]], "blocks": [[0, 2, 7]]},
    {"stitches": [[0, 0, "s"], [1, 0, "s"]], "blocks": "none"},
])
def test_a_damaged_stitched_letter_says_so(tmp_path, damage):
    doc = {"format": "ludd-font", "version": 2, "name": "Broken", "cap_height_mm": 10,
           "threads": [{"color": "#000000"}, {"color": "#ff0000"}], "glyphs": {"A": {"advance_mm": 5, **damage}}}
    path = tmp_path / "broken.luddfont"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(LetteringError, match="damaged"):
        lettering.layout_text({"text": "A", "font": {"path": str(path)}, "size_mm": 10})


def test_a_stitch_font_with_damaged_threads_says_so(tmp_path):
    doc = {"format": "ludd-font", "version": 2, "name": "Broken", "cap_height_mm": 10, "threads": "red",
           "glyphs": {"A": {"advance_mm": 5, "stitches": [[0, 0, "s"], [1, 0, "s"]], "blocks": [[0, 2, 0]]}}}
    path = tmp_path / "broken.luddfont"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(LetteringError, match="damaged"):
        lettering.layout_text({"text": "A", "font": {"path": str(path)}, "size_mm": 10})
