"""Phase 5's lettering seams: the package, the five-step text pipeline and the new project
features. Each test puts something into a seam (an extra, a letter's own color, a stitched
letter) that a feature fills later, so none of them depends on how that feature works."""

import json

import pyembroidery as pe
import pytest
from shapely import affinity
from shapely.geometry import Polygon

from invariants import assert_sane
from threadline_engine import fabrics, layout, lettering, project
from threadline_engine.layout import text as text_pipeline
from threadline_engine.repair import overlap

from test_lettering import bounds, font_path, spec  # noqa: F401  (a tiny font built in the test)

RED = {"color": "#cc2222", "name": "Red", "catalog": "", "brand": ""}
BLUE = {"color": "#2222cc", "name": "Blue", "catalog": "", "brand": ""}
GREY = {"color": "#888888", "name": "Grey", "catalog": "", "brand": ""}


def _text(font, **kw):
    return {"id": "t", "kind": "text", "text": "IOI", "font": {"path": font, "index": 0}, "size_mm": 12,
            "spacing_mm": 0, "style": "satin", "shape": {"type": "line"}, "monogram": False, "thread": RED,
            "transform": {}, "threads": [], "ops": [], **kw}


def _render(item):
    return layout.render_summary({"items": [item], "merge_colors": False, "color_sort": False})


def _summary_threads(s):
    return [s["threads"][b["thread"]]["color"] for b in s["blocks"]]


def _square(x, y, w, **extra):
    nodes = [[x, y, "c"], [x + w, y, "c"], [x + w, y + w, "c"], [x, y + w, "c"]]
    return {"kind": "fill", "geometry": {"outline": nodes, "holes": []}, "params": {}, **extra}


def test_the_cache_keys_hold_every_text_field():
    new = {"align", "line_spacing", "slant_deg", "envelope", "vertical", "letter_edits", "monogram_style", "ornament",
           "shadow", "outline", "placeholder", "bind", "fit_width_mm"}
    old = {"text", "font", "size_mm", "spacing_mm", "style", "shape", "monogram"}
    assert old | new == set(lettering.TEXT_SPEC_KEYS)
    assert set(lettering.TEXT_SPEC_KEYS) <= set(overlap._SHAPE_KEYS)  # "Don't sew what's hidden"


def test_letters_are_numbered_by_what_they_draw(font_path):
    objs, _ = lettering.layout_text(spec(font_path, text="I ZO"))  # a space and a missing Z draw nothing
    assert [(o["letter"], o["line"]) for o in objs] == [(0, 0), (1, 0)]
    objs, _ = lettering.layout_text(spec(font_path, text="IOI", monogram=True))
    assert [o["letter"] for o in objs] == [0, 1, 2]
    objs, _ = lettering.layout_text(spec(font_path, text="III", shape={"type": "arc_up", "radius_mm": 25}))
    assert [o["letter"] for o in objs] == [0, 1, 2]


@pytest.mark.parametrize("text,style,size,warns", [
    ("I", "classic", 7, False),  # one letter alone is full size
    ("I", "stacked", 7, False),
    ("IO", "classic", 8, True),  # the small one is 5.6 mm
    ("IOI", "stacked", 12, True),  # the stacked pair are 5.6 mm
    ("IOI", "block", 7, False),
])
def test_a_monograms_small_letter_warning_counts_its_letters(font_path, text, style, size, warns):
    _, warnings = lettering.layout_text(spec(font_path, text=text, monogram=True, monogram_style=style, size_mm=size))
    assert any("hard to stitch" in w for w in warnings) is warns


def test_a_slant_hook_changes_each_shape_before_it_is_stitched(font_path):
    from shapely import affinity

    plain = lettering._outline_glyphs("IO", font_path, 0, 10, 0, "satin")
    moved = lettering._outline_glyphs("IO", font_path, 0, 10, 0, "satin",
                                      shape_map=lambda s: affinity.translate(s, 3, 0))
    for a, b in zip(plain, moved):
        assert bounds(b.objects)[0] == pytest.approx(bounds(a.objects)[0] + 3, abs=0.01)
        assert b.advance == a.advance


def test_plain_text_is_one_run_that_takes_a_color_change(font_path):
    s = _render(_text(font_path, text="IOX", threads=[BLUE]))
    assert s["items"][0]["runs"] == [{"run": 0, "what": "letters", "letters": [0, 1, 2], "slots": [0]}]
    assert [p["run"] for p in s["items"][0]["letters"]] == [0, 0, 0]
    assert [(p["letter"], p["line"]) for p in s["items"][0]["letters"]] == [(0, 0), (1, 0), (2, 0)]
    assert _summary_threads(s) == [BLUE["color"]]
    assert s["blocks"][0]["original"]["color"] == RED["color"]
    assert s["blocks"][0]["sources"] == [{"item": 0, "block": 0}]


def test_a_letter_with_its_own_thread_starts_a_new_run(font_path, monkeypatch):
    def recolor_the_o(objects, spec_):
        return [{**o, "own_thread": BLUE} if o["letter"] == 1 else o for o in objects]

    monkeypatch.setattr(text_pipeline, "_apply_letter_edits", recolor_the_o)
    s = _render(_text(font_path))
    assert _summary_threads(s) == [RED["color"], BLUE["color"], RED["color"]]
    assert [b["sources"] for b in s["blocks"]] == [[{"item": 0, "block": n}] for n in range(3)]
    assert [(r["letters"], r["slots"]) for r in s["items"][0]["runs"]] == [([0], []), ([1], []), ([2], [])]
    assert [p["run"] for p in s["items"][0]["letters"]] == [0, 1, 2]
    src = [n for n, i in zip(s["records"]["src"], s["records"]["item"]) if i == 0 and n >= 0]
    assert src == sorted(src) and len(set(src)) == len(src)  # numbered once, in sewing order
    # The text's color changed in Order & colors leaves the O its own color.
    s = _render(_text(font_path, threads=[GREY]))
    assert _summary_threads(s) == [GREY["color"], BLUE["color"], GREY["color"]]


def test_extras_sew_before_and_after_the_letters(font_path, monkeypatch):
    seen = {}

    def fake(spec_, letters):
        seen["letters"] = [o["letter"] for o in letters]
        shadow = _square(-30, -3, 6, extra="shadow", thread=GREY)
        outline = {"kind": "run", "geometry": {"nodes": [[20, -6, "c"], [30, -6, "c"], [30, 6, "c"]]}, "params": {},
                   "extra": "outline", "thread": BLUE}
        return [shadow], [outline]

    monkeypatch.setattr(lettering.extras, "build", fake)
    item = _text(font_path)
    s = _render(item)
    assert seen["letters"] == [0, 1, 2]
    assert _summary_threads(s) == [GREY["color"], RED["color"], BLUE["color"]]
    assert [r["what"] for r in s["items"][0]["runs"]] == ["shadow", "letters", "outline"]
    assert [r["slots"] for r in s["items"][0]["runs"]] == [[], [0], []]
    assert [p["run"] for p in s["items"][0]["letters"]] == [1, 1, 1]  # only letters get dots
    shapes = layout.text_to_shapes(item)["objects"]
    assert [o["thread"]["color"] for o in shapes] == [GREY["color"], RED["color"], RED["color"], RED["color"], BLUE["color"]]
    assert shapes[0]["name"] == "IOI shadow 1" and shapes[-1]["name"] == "IOI outline 1"


def test_adding_an_extra_leaves_the_letters_stitching_alone(font_path, monkeypatch):
    def letter_stitches(s):
        letters = {i for i, it in enumerate(s["items"][0]["runs"]) if it["what"] == "letters"}
        block_of = {}
        for n, blk in enumerate(s["blocks"]):
            if {src["block"] for src in blk["sources"]} <= letters:
                for r in range(blk["start"], blk["end"]):
                    block_of[r] = n
        xs, ys, kinds = s["records"]["x"], s["records"]["y"], s["records"]["kind"]
        return [(xs[r], ys[r]) for r in block_of if kinds[r] == 0]

    item = _text(font_path)
    plain = letter_stitches(_render(item))
    monkeypatch.setattr(lettering.extras, "build",
                        lambda spec_, letters: ([_square(-40, -3, 6, extra="shadow", thread=GREY)], []))
    assert letter_stitches(_render(item)) == plain


def test_a_fonts_colors_sew_color_by_color(font_path, monkeypatch):
    def two_colors(objects, spec_):
        out = []
        for o in objects:
            out += [o, {**o, "color_index": 1, "thread": BLUE}]
        return out

    monkeypatch.setattr(text_pipeline, "_apply_letter_edits", two_colors)
    s = _render(_text(font_path))
    assert _summary_threads(s) == [RED["color"], BLUE["color"]]
    assert [(r["letters"], r["slots"]) for r in s["items"][0]["runs"]] == [([0, 1, 2], [0]), ([0, 1, 2], [1])]
    s = _render(_text(font_path, threads=[None, GREY]))  # the font's second color changed
    assert _summary_threads(s) == [RED["color"], GREY["color"]]
    assert s["blocks"][1]["original"]["color"] == BLUE["color"]


def test_stitched_letters_use_their_own_stitches(font_path, monkeypatch):
    part = {"kind": "stitches", "letter": 0, "line": 0,
            "geometry": {"nodes": [[0, 0, "s"], [2, 0, "s"], [2, -2, "s"], [0, -2, "s"]]}}
    monkeypatch.setattr(text_pipeline, "_apply_letter_edits", lambda objects, spec_: [part])
    monkeypatch.setattr(lettering.stitchglyphs, "records",
                        lambda o: [(n[0], n[1], pe.STITCH) for n in o["geometry"]["nodes"]])
    item = _text(font_path)
    r = layout.render({"items": [item]})
    assert [(x, y) for x, y, c in r.pattern.stitches if c == pe.STITCH] == [(0, 0), (20, 0), (20, -20), (0, -20)]
    assert r.items[0]["letters"][0]["look"] == "stitches" and len(r.items[0]["letters"][0]["ring"]) == 4
    with pytest.raises(layout.LayoutError, match="Letters from a stitched font have no outlines to edit."):
        layout.text_to_shapes(item)


def test_a_version_2_glyph_is_read_by_stitchglyphs(tmp_path, monkeypatch):
    calls = []

    def fake(font, glyph, scale):
        calls.append((glyph["advance_mm"], scale))
        return [{"kind": "stitches", "geometry": {"nodes": [[0, 0, "s"], [1 * scale, -2 * scale, "s"]]}}]

    monkeypatch.setattr(lettering.stitchglyphs, "letter_objects", fake)
    doc = {"format": "ludd-font", "version": 2, "name": "Stitched", "cap_height_mm": 10,
           "glyphs": {"A": {"advance_mm": 5, "stitches": [[0, 0, "s"]], "blocks": [[0, 1, 0]]}}, "threads": []}
    path = tmp_path / "s.luddfont"
    path.write_text(json.dumps(doc), encoding="utf-8")
    objs, _ = lettering.layout_text({"text": "A", "font": {"path": str(path)}, "size_mm": 20})
    assert calls == [(5, 2.0)] and objs[0]["kind"] == "stitches" and objs[0]["letter"] == 0


@pytest.mark.parametrize("extra,feature", [
    ({"text": "Happy\nBirthday"}, "text_layout_2"),
    ({"align": "left"}, "text_layout_2"),
    ({"line_spacing": 1.5}, "text_layout_2"),
    ({"slant_deg": 12}, "text_layout_2"),
    ({"envelope": {"type": "bulge", "amount": 0.5}}, "text_layout_2"),
    ({"vertical": True}, "text_layout_2"),
    ({"letter_edits": {"1": {"dx_mm": 1}}}, "text_layout_2"),
    ({"style": "columns"}, "text_columns"),
    ({"shadow": {"dx_mm": 0.8, "dy_mm": 0.8, "thread": GREY}}, "text_extras"),
    ({"outline": {"gap_mm": 1, "width_mm": 1.5, "style": "satin", "thread": GREY}}, "text_extras"),
    ({"monogram": True, "ornament": {"id": "circle"}}, "text_extras"),
    ({"monogram": True, "monogram_style": "stacked"}, "text_extras"),
    ({"monogram": True, "text": "AB"}, "text_extras"),
    ({"font": {"path": "x.luddfont", "made_of": "stitches"}}, "font_stitch_glyphs"),
])
def test_new_lettering_is_named_in_the_project(extra, feature):
    item = {**_text("arial.ttf"), **extra}
    assert feature in project._features({"items": [item]})
    assert feature in project.KNOWN_FEATURES


@pytest.mark.parametrize("extra", [{}, {"align": "center"}, {"line_spacing": 1.3}, {"slant_deg": 0},
                                   {"vertical": False}, {"letter_edits": {}}, {"monogram": True},
                                   {"monogram": True, "monogram_style": "classic"},
                                   {"monogram_style": "block"}, {"placeholder": True, "bind": "name", "fit_width_mm": 80}])
def test_old_lettering_needs_no_new_feature(extra):
    assert project._features({"items": [_text("arial.ttf", **extra)]}) == set()


def test_the_leaf_motif_has_its_own_feature():
    run = {"kind": "run", "params": {"style": "motif", "motif": "leaf"}}
    assert {"motif_lines", "motif_leaf"} <= project._features({"items": [run]})
    assert "motif_leaf" not in project._features({"items": [{**run, "params": {"style": "motif", "motif": "wave"}}]})


# ---------------------------------------------------------------- the tracks together


def _mm_blocks(item):
    """Each color block of a rendered text as (x mm, y mm, command) records."""
    r = layout.render({"items": [item], "merge_colors": False, "color_sort": False})
    return [[(x / 10, y / 10, c) for x, y, c, _, _ in b.recs] for b in r.blocks]


def test_extras_and_columns_together(font_path):
    """Spec 8: a True satin text with a shadow, an outline and a moved letter."""
    item = _text(font_path, text="IOX", style="columns", size_mm=14,
                 shadow={"dx_mm": 0.8, "dy_mm": 0.8, "thread": GREY},
                 outline={"gap_mm": 1.0, "width_mm": 1.5, "style": "satin", "thread": BLUE},
                 letter_edits={"1": {"dx_mm": 1.5, "dy_mm": -2.0}})
    s = _render(item)
    assert [r["what"] for r in s["items"][0]["runs"]] == ["shadow", "letters", "outline"]
    assert any(p["kind"] == "satin" for p in s["items"][0]["letters"])  # real columns
    assert not [w for w in s["warnings"] if "True satin" in w["message"]]
    blocks = _mm_blocks(item)
    assert len(blocks) == 3
    for recs in blocks:
        assert_sane(recs, max_stitch_mm=7.15)


def test_the_satin_angle_ignores_rounding_noise():
    """A shadow 0.8 mm thick is exactly at the sliver width: moving it mustn't change its angle,
    or Windows and Apple-chip Macs could sew it differently."""
    stem = Polygon([(0, 0), (4, 0), (4, 12), (0, 12)])
    strip = affinity.translate(stem, 0.8, 0.8).difference(stem)
    angles = {lettering._satin_angle(affinity.translate(strip, (i * 0.137) % 41.3, (i * 0.291) % 17.9))
              for i in range(60)}
    assert len(angles) == 1, angles


@pytest.mark.parametrize("fabric,level", [("towel", "heavy"), ("denim", "light")])
def test_true_satin_columns_take_the_fabrics_underlay_amount(fabric, level):
    column = {"kind": "satin", "geometry": {}, "params": {"underlay": "auto"}}
    assert fabrics.apply(column, fabric)["params"]["underlay_level"] == level
    chosen = {**column, "params": {"underlay": "auto", "underlay_level": "normal"}}
    assert fabrics.apply(chosen, fabric)["params"]["underlay_level"] == "normal"


def _stitched_font(tmp_path):
    bar = [[0, 0, "s"], [0, -5, "s"], [0, -10, "s"], [2, -10, "s"], [2, 0, "s"]]
    doc = {"format": "ludd-font", "version": 2, "name": "Bars", "cap_height_mm": 10, "space_mm": 3,
           "threads": [{"color": "#000000", "name": "Black"}],
           "glyphs": {"I": {"advance_mm": 3, "stitches": bar, "blocks": [[0, 5, 0]]}}}
    path = tmp_path / "bars.luddfont"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return str(path)


@pytest.mark.parametrize("size,transform,says", [
    (10, {}, False),
    (10, {"scale_x": 1.1, "scale_y": 1.1}, False),
    (10, {"rotate": 30}, False),
    (10, {"scale_x": 1.5, "scale_y": 1.5}, True),
    (10, {"scale_y": 0.7}, True),
    (13, {"scale_x": 1.1, "scale_y": 1.1}, True),  # together more than 20%
])
def test_stitched_letters_resized_with_the_handles_say_so(tmp_path, size, transform, says):
    item = {**_text(_stitched_font(tmp_path), text="II", size_mm=size, transform=transform),
            "font": {"path": _stitched_font(tmp_path), "made_of": "stitches"}}
    warnings = [w["message"] for w in _render(item)["warnings"]]
    assert any("handles" in w for w in warnings) is says, warnings


def test_a_text_on_two_lines_is_named_on_one_line(font_path):
    s = _render(_text(font_path, text="IO\nXI"))
    assert s["items"][0]["name"] == "“IO XI”"
