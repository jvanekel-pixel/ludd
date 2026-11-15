"""Auto-trace on synthetic cartoons: a click inside a shape gives its outline, a click on a line
gives a satin ribbon along it."""

import collections
import math
import os
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from threadline_engine import autotrace
from threadline_engine.trace import TraceError

PX_PER_MM = 8.0
SIZE = 800
HALF_MM = SIZE / PX_PER_MM / 2
PLACE = {"x": 0, "y": 0, "width_mm": SIZE / PX_PER_MM, "height_mm": SIZE / PX_PER_MM, "rotate": 0}


def mm(u, v):
    """Picture pixel to mm (picture centred on 0, 0)."""
    return [(u + 0.5) / PX_PER_MM - HALF_MM, (v + 0.5) / PX_PER_MM - HALF_MM]


@pytest.fixture
def cartoon(tmp_path):
    """A red disc with a 6 px (0.75 mm) black outline, a black-outlined blue square, and a
    loose black stroke, on white."""
    img = Image.new("RGB", (SIZE, SIZE), "white")
    d = ImageDraw.Draw(img)
    d.ellipse((100, 100, 340, 340), fill=(220, 40, 40), outline="black", width=6)
    d.rectangle((450, 450, 700, 650), fill=(40, 80, 200), outline="black", width=8)
    d.line((100, 600, 350, 760), fill="black", width=16)
    path = tmp_path / "cartoon.png"
    img.save(path)
    return str(path)


def dist_to(nodes, center):
    return [math.dist(n[:2], center) for n in nodes]


def test_click_inside_a_disc_outlines_it_to_the_middle_of_its_line_first(cartoon):
    r = autotrace.region(cartoon, PLACE, mm(220, 220), spacing_mm=3)
    fills = [c for c in r["candidates"] if c["kind"] == "fill"]
    first = fills[0]
    centre = mm(219.5, 219.5)
    # Outer radius 120 px; the line is 6 px wide drawn inward, so its middle is at about 117 px.
    radii = dist_to(first["outline"], centre)
    assert np.mean(radii) == pytest.approx(117 / PX_PER_MM, abs=0.35)
    assert max(radii) - min(radii) < 0.5
    assert first["line_width_mm"] == pytest.approx(6 / PX_PER_MM, abs=0.3)
    assert all(k == "s" for *_, k in first["outline"])  # a circle has no corners
    assert first["label"].startswith("Fill")
    assert first["color"] == "#dc2828"  # the disc's red, not its black outline


def test_points_are_about_the_spacing_apart(cartoon):
    for spacing in (2, 5):
        out = autotrace.region(cartoon, PLACE, mm(220, 220), spacing_mm=spacing)["candidates"][0]["outline"]
        gaps = [math.dist(a[:2], b[:2]) for a, b in zip(out, out[1:] + out[:1])]
        assert np.median(gaps) == pytest.approx(spacing, rel=0.15)


def test_square_keeps_its_four_corners(cartoon):
    out = autotrace.region(cartoon, PLACE, mm(575, 550), spacing_mm=4)["candidates"][0]["outline"]
    corners = [n for n in out if n[2] == "c"]
    assert len(corners) == 4
    expect = [mm(454, 454), mm(696, 454), mm(696, 646), mm(454, 646)]
    for e in expect:
        assert min(math.dist(e, c[:2]) for c in corners) < 0.6


def test_click_on_a_line_gives_a_satin_ribbon_as_wide_as_the_line(cartoon):
    r = autotrace.region(cartoon, PLACE, mm(225, 680), spacing_mm=3)
    ribbon = r["candidates"][0]
    assert ribbon["kind"] == "satin" and not ribbon["closed"]
    assert ribbon["color"] == "#000000"
    assert ribbon["width_mm"] == pytest.approx(16 / PX_PER_MM, abs=0.4)
    ends = [ribbon["nodes"][0][:2], ribbon["nodes"][-1][:2]]
    a, b = mm(100, 600), mm(350, 760)
    assert min(math.dist(ends[0], a), math.dist(ends[1], a)) < 2.0
    assert min(math.dist(ends[0], b), math.dist(ends[1], b)) < 2.0


def test_click_on_an_outline_gives_a_closed_ribbon_around_it(cartoon):
    r = autotrace.region(cartoon, PLACE, mm(102, 220), spacing_mm=3)
    ribbon = r["candidates"][0]
    assert ribbon["kind"] == "satin" and ribbon["closed"]
    assert np.mean(dist_to(ribbon["nodes"], mm(219.5, 219.5))) == pytest.approx(117 / PX_PER_MM, abs=0.4)


def test_background_is_offered_last(cartoon):
    cands = autotrace.region(cartoon, PLACE, mm(20, 20))["candidates"]
    assert cands and all(c["background"] for c in cands)


def test_outside_the_picture_or_bad_spacing(cartoon):
    assert autotrace.region(cartoon, PLACE, [500, 500])["candidates"] == []
    with pytest.raises(TraceError, match="spacing"):
        autotrace.region(cartoon, PLACE, mm(220, 220), spacing_mm=0.1)


def test_thin_makes_a_one_pixel_line():
    img = np.zeros((30, 60), np.uint8)
    img[10:20, 5:55] = 1
    sk = autotrace.thin(img)
    rows = np.nonzero(sk.any(axis=1))[0]
    assert len(rows) <= 2 and sk.sum() > 35


def test_fast_enough(cartoon):
    autotrace.region(cartoon, PLACE, mm(220, 220))  # first call analyses the picture
    t = time.perf_counter()
    autotrace.region(cartoon, PLACE, mm(575, 550))
    autotrace.region(cartoon, PLACE, mm(225, 680))
    # About 0.1 s each here; the limit is loose so a busy test machine doesn't fail it.
    assert (time.perf_counter() - t) / 2 < 2.0


def test_small_round_holes_stay_curves(tmp_path):
    img = Image.new("RGB", (SIZE, SIZE), "white")
    d = ImageDraw.Draw(img)
    d.ellipse((100, 100, 500, 500), fill=(250, 210, 60), outline="black", width=10)
    d.ellipse((200, 220, 260, 300), fill="black")  # an eye: about 7 x 10 mm
    path = tmp_path / "face.png"
    img.save(path)
    face = autotrace.region(str(path), PLACE, mm(300, 420), spacing_mm=3)["candidates"][0]
    assert len(face["holes"]) == 1
    assert all(k == "s" for *_, k in face["holes"][0])
    assert all(k == "s" for *_, k in face["outline"])


def test_a_thick_outline_also_offers_the_inside_edge(tmp_path):
    img = Image.new("RGB", (SIZE, SIZE), "white")
    ImageDraw.Draw(img).ellipse((100, 100, 500, 500), fill=(250, 210, 60), outline="black", width=24)  # 3 mm line
    path = tmp_path / "thick.png"
    img.save(path)
    fills = [c for c in autotrace.region(str(path), PLACE, mm(300, 300))["candidates"] if c["kind"] == "fill"]
    centre = mm(299.5, 299.5)
    r_mid, r_in = (np.mean(dist_to(f["outline"], centre)) for f in fills[:2])
    assert r_mid == pytest.approx(188 / PX_PER_MM, abs=0.4)  # 200 px outer radius, 24 px line
    assert r_in == pytest.approx(176 / PX_PER_MM, abs=0.4)


# ---------------------------------------------------------------- simplified colors, more clicks, spread


def pick(cands, gid):
    """The guess with this id, or the first fill (near-identical guesses are merged)."""
    return next((c for c in cands if c.get("id") == gid), next(c for c in cands if c["kind"] == "fill"))


def shaded_disc(tmp_path):
    """An orange disc shaded from light to dark (no outline) on white: color-distance flood fills
    stop part way; simplified colors should take the whole disc."""
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    img = np.full((SIZE, SIZE, 3), 255, np.uint8)
    inside = (xx - 300) ** 2 + (yy - 300) ** 2 <= 200**2
    t = np.clip((xx - 100) / 400, 0, 1)
    shade = np.stack([255 - 60 * t, 170 - 90 * t, 40 - 30 * t], -1).astype(np.uint8)
    img[inside] = shade[inside]
    path = tmp_path / "shaded.png"
    Image.fromarray(img).save(path)
    return str(path)


def test_simplified_colors_take_a_whole_shaded_shape(tmp_path):
    path = shaded_disc(tmp_path)
    cands = autotrace.region(path, PLACE, mm(150, 300))["candidates"]
    simple = next(c for c in cands if c["id"] == "simple")
    assert simple["area_mm2"] == pytest.approx(math.pi * (200 / PX_PER_MM) ** 2, rel=0.08)
    assert all("id" in c for c in cands)


def test_spread_changes_how_far_a_guess_reaches(tmp_path):
    path = shaded_disc(tmp_path)
    low = pick(autotrace.region(path, PLACE, mm(150, 300), spread=1)["candidates"], "middle")
    high = pick(autotrace.region(path, PLACE, mm(150, 300), spread=10)["candidates"], "middle")
    assert high["area_mm2"] > low["area_mm2"] * 1.3
    with pytest.raises(TraceError, match="Spread"):
        autotrace.region(path, PLACE, mm(150, 300), spread=11)


def test_shift_click_adds_an_area_and_alt_click_cuts_one_out(tmp_path):
    img = Image.new("RGB", (SIZE, SIZE), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((100, 100, 300, 300), fill=(200, 40, 40))  # red
    d.rectangle((300, 100, 500, 300), fill=(40, 40, 200))  # blue, touching
    d.ellipse((160, 160, 240, 240), fill=(40, 160, 40))  # green spot in the red
    path = tmp_path / "blocks.png"
    img.save(path)
    one = pick(autotrace.region(str(path), PLACE, mm(120, 200))["candidates"], "middle")
    both = pick(autotrace.region(str(path), PLACE, mm(120, 200), add=[mm(400, 200)])["candidates"], "middle")
    assert both["area_mm2"] == pytest.approx(2 * one["area_mm2"], rel=0.1)
    # The green spot is a hole already; Alt+click on the blue cuts nothing from the red.
    assert len(one["holes"]) == 1
    cut = pick(autotrace.region(str(path), PLACE, mm(120, 200), add=[mm(400, 200)], subtract=[mm(400, 200)])["candidates"], "middle")
    assert cut["area_mm2"] == pytest.approx(one["area_mm2"], rel=0.1)


def test_ai_guesses_are_skipped_when_the_model_isnt_installed(cartoon, tmp_path, monkeypatch):
    from threadline_engine.ai import segment

    monkeypatch.setattr(segment, "model_dir", lambda: tmp_path / "no-model")
    assert segment.status()["installed"] is False
    cands = autotrace.region(cartoon, PLACE, mm(220, 220), use_ai=True)["candidates"]
    assert cands and not any(c["id"].startswith("ai") for c in cands)


def test_a_separate_added_area_is_its_own_part_and_thin_line_holes_are_filled(tmp_path):
    img = Image.new("RGB", (SIZE, SIZE), "white")
    d = ImageDraw.Draw(img)
    d.ellipse((100, 100, 500, 500), fill=(250, 210, 60), outline="black", width=10)
    d.arc((180, 250, 420, 420), 20, 160, fill="black", width=12)  # a smile: a line, not a hole
    d.rectangle((560, 560, 760, 760), fill=(60, 120, 220), outline="black", width=8)
    path = tmp_path / "face2.png"
    img.save(path)
    g = pick(autotrace.region(str(path), PLACE, mm(300, 200), add=[mm(660, 660)])["candidates"], "middle")
    assert g["holes"] == []  # the smile line is under the fill
    assert len(g["parts"]) == 1 and len(g["parts"][0]["outline"]) >= 4


# The real model is only used when you point at it (LUDD_TEST_AI_MODEL_DIR = the folder with the
# two .onnx files): collecting the tests never looks in the real user data folder, and results
# don't depend on what this computer has downloaded.
REAL_MODEL_DIR = Path(os.environ["LUDD_TEST_AI_MODEL_DIR"]) if os.environ.get("LUDD_TEST_AI_MODEL_DIR") else None


@pytest.mark.skipif(REAL_MODEL_DIR is None, reason="set LUDD_TEST_AI_MODEL_DIR to test with the real AI tracing model")
def test_ai_guesses_come_first_when_the_model_is_installed(cartoon, monkeypatch):
    from threadline_engine.ai import segment

    monkeypatch.setattr(segment, "model_dir", lambda: REAL_MODEL_DIR)
    cands = autotrace.region(cartoon, PLACE, mm(220, 220), use_ai=True)["candidates"]
    ai = [c for c in cands if c["id"].startswith("ai")]
    assert ai and cands[0]["id"].startswith("ai")
    centre = mm(219.5, 219.5)
    # One of its guesses is the disc, out to about the middle of its outline.
    assert any(abs(np.mean(dist_to(c["outline"], centre)) - 117 / PX_PER_MM) < 1.0 for c in ai)


def test_whole_picture_becomes_fills_then_satin_outlines(tmp_path):
    img = Image.new("RGB", (SIZE, SIZE), "white")
    d = ImageDraw.Draw(img)
    d.ellipse((100, 100, 500, 500), fill=(250, 210, 60), outline="black", width=10)
    d.ellipse((200, 220, 260, 300), fill="black")  # a solid pupil: a fill, not a line
    d.arc((180, 250, 420, 420), 20, 160, fill="black", width=12)
    d.rectangle((560, 560, 760, 760), fill=(60, 120, 220), outline="black", width=8)
    path = tmp_path / "face3.png"
    img.save(path)
    t = time.perf_counter()
    shapes = autotrace.digitize_all(str(path), PLACE, 3.0)["shapes"]
    took = time.perf_counter() - t
    kinds = [s["kind"] for s in shapes]
    fills = [s for s in shapes if s["kind"] == "fill"]
    colors = [s["color"] for s in fills]
    assert "#fad23c" in colors and "#3c78dc" in colors
    assert "#000000" in colors  # the pupil, as a black fill
    assert "#ffffff" not in colors  # the paper is left out
    # Fills first (biggest first), then the outlines as satins.
    assert kinds.index("satin") > max(i for i, k in enumerate(kinds) if k == "fill")
    satins = [s for s in shapes if s["kind"] == "satin"]
    assert len(satins) >= 3  # face outline, smile, square outline
    assert any(s["closed"] for s in satins)
    assert took < 20  # about 1 s here; loose so a busy test machine doesn't fail it


# ---------------------------------------------------------------- QA fixes (phase 4)


def _fills(shapes):
    from shapely.geometry import Polygon

    return [
        (s["color"], Polygon([q[:2] for q in s["outline"]], [[q[:2] for q in h] for h in s["holes"]]).buffer(0).area)
        for s in shapes
        if s["kind"] == "fill"
    ]


def _logo(path, **save):
    img = Image.new("RGB", (1000, 800), "white")
    d = ImageDraw.Draw(img)
    d.ellipse((100, 100, 500, 500), fill=(250, 210, 60), outline="black", width=10)
    d.ellipse((200, 220, 260, 300), fill="black")
    d.arc((180, 250, 420, 420), 20, 160, fill="black", width=12)
    d.rectangle((560, 460, 900, 740), fill=(60, 120, 220), outline="black", width=8)
    d.polygon([(600, 100), (900, 100), (750, 380)], fill=(200, 40, 40), outline="black")
    img.save(path, **save)
    return str(path)


LOGO_PLACE = {"x": 0, "y": 0, "width_mm": 100, "height_mm": 80, "rotate": 0}


@pytest.mark.parametrize("name,save", [("logo.png", {}), ("logo90.jpg", {"quality": 90}), ("logo50.jpg", {"quality": 50})])
def test_whole_picture_gives_one_thread_per_color_even_from_a_jpeg(tmp_path, name, save):
    shapes = autotrace.digitize_all(_logo(tmp_path / name, **save), LOGO_PLACE, 3.0)["shapes"]
    colors = {s["color"] for s in shapes}
    assert len(colors) == 4  # yellow, blue, red and one black (not a shade per outline)
    dark = {s["color"] for s in shapes if s["kind"] in ("satin", "run")}
    assert len(dark) == 1
    assert sum(s["kind"] == "run" for s in shapes) <= 4  # no row of JPEG specks


@pytest.mark.parametrize("bg", [(0, 0, 0), (35, 35, 35), (15, 25, 70), (40, 60, 120), (255, 255, 255)])
def test_leave_out_the_background_works_on_dark_backgrounds_too(tmp_path, bg):
    img = Image.new("RGB", (800, 600), bg)
    d = ImageDraw.Draw(img)
    d.ellipse((250, 150, 550, 450), fill=(250, 210, 60))  # 37.5 mm across at 8 px/mm
    d.rectangle((50, 50, 150, 120), fill=(200, 40, 40))
    img.save(tmp_path / "bg.png")
    place = {"x": 0, "y": 0, "width_mm": 100, "height_mm": 75, "rotate": 0}
    left_out = _fills(autotrace.digitize_all(str(tmp_path / "bg.png"), place, 3.0, skip_background=True)["shapes"])
    assert sorted(c for c, _ in left_out) == ["#c82828", "#fad23c"]
    disc = next(a for c, a in left_out if c == "#fad23c")
    assert disc == pytest.approx(math.pi * 18.75**2, rel=0.05)  # not grown into a dark background
    kept = _fills(autotrace.digitize_all(str(tmp_path / "bg.png"), place, 3.0, skip_background=False)["shapes"])
    assert len(kept) == 3 and max(a for _, a in kept) > 5000  # unticked: the background is a fill


def test_leave_out_the_background_keeps_shapes_that_touch_the_edge(tmp_path):
    # A badge cropped tight: the red disc touches all four edges; the white corners are paper.
    img = Image.new("RGB", (600, 600), "white")
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, 599, 599), fill=(200, 30, 30))
    d.ellipse((200, 200, 400, 400), fill="white")
    d.ellipse((260, 260, 340, 340), fill=(250, 210, 60))
    img.save(tmp_path / "badge.png")
    place = {"x": 0, "y": 0, "width_mm": 80, "height_mm": 80, "rotate": 0}
    fills = _fills(autotrace.digitize_all(str(tmp_path / "badge.png"), place, 3.0)["shapes"])
    assert [c for c, _ in fills] == ["#c81e1e", "#fad23c"]  # the disc stays; no white anywhere
    # A pale shape cut off by the left edge stays too.
    img = Image.new("RGB", (600, 600), "white")
    d = ImageDraw.Draw(img)
    d.ellipse((-150, 150, 150, 450), fill=(255, 235, 130))
    d.rectangle((300, 200, 500, 400), fill=(60, 120, 220))
    img.save(tmp_path / "pale.png")
    fills = _fills(autotrace.digitize_all(str(tmp_path / "pale.png"), place, 3.0)["shapes"])
    assert sorted(c for c, _ in fills) == ["#3c78dc", "#ffeb82"]


def test_paper_inside_a_shape_is_not_sewn(tmp_path):
    img = Image.new("RGB", (400, 300), "white")
    d = ImageDraw.Draw(img)
    d.ellipse((60, 40, 340, 260), fill=(200, 30, 30))
    d.ellipse((120, 90, 280, 210), fill="white")  # a red ring: its middle is paper
    img.save(tmp_path / "ring.png")
    r = autotrace.digitize_all(str(tmp_path / "ring.png"), {"x": 0, "y": 0, "width_mm": 80, "height_mm": 60, "rotate": 0}, 3.0)
    assert [(s["kind"], s["color"], len(s["holes"])) for s in r["shapes"]] == [("fill", "#c81e1e", 1)]


def test_soft_edges_dont_become_hairline_fills(tmp_path):
    from PIL import ImageFilter

    img = Image.new("RGBA", (1000, 800), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((100, 100, 500, 500), fill=(250, 210, 60, 255), outline=(0, 0, 0, 255), width=10)
    d.rectangle((560, 460, 900, 740), fill=(60, 120, 220, 255))
    a = np.asarray(img).copy()
    a[..., 3] = np.asarray(Image.fromarray(a[..., 3]).filter(ImageFilter.GaussianBlur(5)))
    Image.fromarray(a).save(tmp_path / "soft.png")
    shapes = autotrace.digitize_all(str(tmp_path / "soft.png"), LOGO_PLACE, 3.0)["shapes"]
    assert sorted(c for c, _ in _fills(shapes)) == ["#3c78dc", "#fad23c"]


def test_whole_picture_ribbons_reach_the_ends_of_the_line(tmp_path):
    img = Image.new("RGB", (600, 300), "white")
    ImageDraw.Draw(img).rectangle((100, 100, 399, 123), fill="black")  # 30 x 2.4 mm, x -20 .. +10 mm
    img.save(tmp_path / "bar.png")
    s = autotrace.digitize_all(str(tmp_path / "bar.png"), {"x": 0, "y": 0, "width_mm": 60, "height_mm": 30, "rotate": 0}, 3.0)["shapes"][0]
    xs = [n[0] for n in s["nodes"]]
    assert s["kind"] == "satin"
    assert min(xs) == pytest.approx(-20, abs=0.4) and max(xs) == pytest.approx(10, abs=0.4)


def _bold(tmp_path, stem_mm):
    """An H and a square ring with strokes stem_mm wide (10 px/mm)."""
    s = int(stem_mm * 10)
    img = Image.new("RGB", (400, 300), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((40, 40, 40 + s, 260), fill="black")
    d.rectangle((220 - s, 40, 220, 260), fill="black")
    d.rectangle((40, 130 - s // 2, 220, 130 + s // 2), fill="black")
    d.rectangle((260, 40, 380, 260), fill="black")
    d.rectangle((260 + s, 40 + s, 380 - s, 260 - s), fill="white")
    img.save(tmp_path / f"bold{stem_mm}.png")
    r = autotrace.digitize_all(str(tmp_path / f"bold{stem_mm}.png"), {"x": 0, "y": 0, "width_mm": 40, "height_mm": 30, "rotate": 0}, 3.0)
    return collections.Counter(sh["kind"] for sh in r["shapes"])


@pytest.mark.parametrize("stem_mm,expect", [(2.0, "satin"), (2.5, "satin"), (3.0, "fill"), (3.6, "fill")])
def test_bold_strokes_are_one_fill_each_not_a_patchwork(tmp_path, stem_mm, expect):
    kinds = _bold(tmp_path, stem_mm)
    assert set(kinds) == {expect}
    if expect == "fill":
        assert kinds["fill"] == 2  # the H and the ring (with its hole)


def test_click_inside_a_solid_black_shape_offers_a_fill(tmp_path):
    img = Image.new("RGB", (800, 600), "white")
    ImageDraw.Draw(img).ellipse((100, 100, 400, 400), fill="black")  # 30 mm across at 10 px/mm
    img.save(tmp_path / "disc.png")
    place = {"x": 0, "y": 0, "width_mm": 80, "height_mm": 60, "rotate": 0}
    cands = autotrace.region(str(tmp_path / "disc.png"), place, [-15.0, -5.0])["candidates"]
    assert cands[0]["kind"] == "fill" and cands[0]["id"] == "dark"
    assert cands[0]["area_mm2"] == pytest.approx(math.pi * 15**2, rel=0.03)


def test_a_picture_with_no_light_pixel_doesnt_crash(tmp_path):
    Image.new("RGB", (200, 150), (10, 10, 20)).save(tmp_path / "dark.png")
    place = {"x": 0, "y": 0, "width_mm": 80, "height_mm": 60, "rotate": 0}
    r = autotrace.region(str(tmp_path / "dark.png"), place, [0, 0])
    for c in r["candidates"]:
        pts = c.get("nodes") or c["outline"]
        assert all(math.isfinite(p[0]) and math.isfinite(p[1]) for p in pts)
    assert autotrace.digitize_all(str(tmp_path / "dark.png"), place)["shapes"] == []  # all background


def test_16_bit_greyscale_traces_like_8_bit(tmp_path):
    a = Image.new("L", (400, 300), 255)
    ImageDraw.Draw(a).ellipse((50, 40, 250, 240), fill=120)
    a.save(tmp_path / "g8.png")
    Image.fromarray(np.asarray(a, dtype=np.uint16) * 257).save(tmp_path / "g16.png")
    place = {"x": 0, "y": 0, "width_mm": 100, "height_mm": 75, "rotate": 0}
    for n in ("g8.png", "g16.png"):
        shapes = autotrace.digitize_all(str(tmp_path / n), place)["shapes"]
        assert [(s["kind"], s["color"]) for s in shapes] == [("fill", "#787878")]


def test_a_too_big_picture_is_a_plain_trace_error(tmp_path, monkeypatch):
    Image.new("RGB", (100, 100), "white").save(tmp_path / "huge.png")
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    with pytest.raises(TraceError, match="too big to trace"):
        autotrace.region(str(tmp_path / "huge.png"), PLACE, [0, 0])


def test_busy_line_art_is_quick_and_a_line_is_thinned_once(tmp_path, monkeypatch):
    rng = np.random.default_rng(11)
    img = Image.new("RGB", (1200, 1200), "white")
    d = ImageDraw.Draw(img)
    for _ in range(45):
        cx, cy = rng.integers(100, 1100, 2)
        rx, ry = rng.integers(40, 200, 2)
        d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline="black", width=7)
    img.save(tmp_path / "lineart.png")
    place = {"x": 0, "y": 0, "width_mm": 100, "height_mm": 100, "rotate": 0}
    pic = autotrace.prepare(str(tmp_path / "lineart.png"))
    ys, xs = np.nonzero(pic.ink)
    at = [(int(xs[3000]) + 0.5) / pic.w * 100 - 50, (int(ys[3000]) + 0.5) / pic.h * 100 - 50]
    first = autotrace.region(str(tmp_path / "lineart.png"), place, at)["candidates"]
    calls = []
    monkeypatch.setattr(autotrace, "thin", lambda img: calls.append(1) or np.zeros(img.shape, bool))
    again = autotrace.region(str(tmp_path / "lineart.png"), place, at)["candidates"]
    assert first and again == first and calls == []  # the second click reuses the line's middle


def test_one_pixel_keeps_lines_connected_and_one_pixel_wide():
    img = np.zeros((80, 120), np.uint8)
    import cv2

    cv2.line(img, (5, 5), (110, 70), 1, 5)
    cv2.circle(img, (60, 40), 25, 1, 4)
    sk = autotrace._one_pixel(autotrace.thin(img))
    n_before = cv2.connectedComponents(img, connectivity=8)[0]
    assert cv2.connectedComponents(sk.astype(np.uint8), connectivity=8)[0] == n_before
    # No pixel left that could go without splitting its neighbours.
    codes = autotrace._codes(sk)
    assert not (sk & autotrace._REMOVABLE[codes]).any()


def test_ai_that_cant_run_falls_back_to_the_usual_guesses(cartoon, monkeypatch):
    from threadline_engine.ai import segment

    def broken(*_a, **_k):
        raise RuntimeError("[ONNXRuntimeError] : 7 : INVALID_PROTOBUF")

    monkeypatch.setattr(segment, "available", lambda: True)
    monkeypatch.setattr(segment, "masks", broken)
    r = autotrace.region(cartoon, PLACE, mm(220, 220), use_ai=True)
    assert r["candidates"] and r["candidates"][0]["kind"] == "fill"
    assert "couldn't run" in r["ai_error"] and "ONNX" not in r["ai_error"]
    assert "ai_error" not in autotrace.region(cartoon, PLACE, mm(220, 220))


def test_ai_reading_of_a_picture_goes_with_the_picture(monkeypatch):
    """An edited picture is analysed again (autotrace's cache checks the file's time); the AI's
    reading is kept on that analysis, so the new picture is read again too."""
    from threadline_engine.ai import segment

    reads = []

    class Input:
        name, shape = "image", [1024, 1024, 3]

    class Enc:
        def get_inputs(self):
            return [Input()]

        def run(self, _out, feed):
            reads.append(1)
            return [np.full((1, 4), float(feed["image"].mean()), np.float32)]

    monkeypatch.setattr(segment, "_sessions", lambda force=False: (Enc(), None))

    class P:
        def __init__(self, v):
            self.rgb = np.full((60, 80, 3), v, np.uint8)

    old, new = P(10), P(200)
    e1, _ = segment._embedding(old)
    segment._embedding(old)
    e2, _ = segment._embedding(new)  # same size, same path: still read again
    assert len(reads) == 2 and not np.allclose(e1, e2)


class _Resp:
    def __init__(self, body, length=None, cut=False):
        self.body, self.cut = body, cut
        self.headers = {"Content-Length": str(length if length is not None else len(body))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n):
        import http.client

        if not self.body:
            if self.cut:
                raise http.client.IncompleteRead(b"x" * 10)
            return b""
        out, self.body = self.body[:n], self.body[n:]
        return out


@pytest.mark.parametrize("resp,why", [
    (lambda: _Resp(b"x" * 100, length=5000), "cut off"),  # shorter than the server said
    (lambda: _Resp(b"x" * 100, cut=True), "cut off"),  # chunked body broken off
])
def test_model_download_that_breaks_off_is_a_plain_error_and_leaves_nothing(tmp_path, monkeypatch, resp, why):
    import urllib.request

    from threadline_engine.ai import segment

    monkeypatch.setattr(segment, "model_dir", lambda: tmp_path / "m")
    monkeypatch.setattr(segment, "_runtime", lambda: None)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: resp())
    with pytest.raises(segment.SegmentError, match=why):
        segment.download()
    assert list((tmp_path / "m").iterdir()) == []


def test_model_download_offline_says_check_the_connection(tmp_path, monkeypatch):
    import urllib.error
    import urllib.request

    from threadline_engine.ai import segment

    def offline(*a, **k):
        raise urllib.error.URLError(ConnectionRefusedError(10061, "refused"))

    monkeypatch.setattr(segment, "model_dir", lambda: tmp_path / "m")
    monkeypatch.setattr(segment, "_runtime", lambda: None)
    monkeypatch.setattr(urllib.request, "urlopen", offline)
    with pytest.raises(segment.SegmentError, match="internet connection"):
        segment.download()


def test_model_download_needs_onnx_runtime_first(tmp_path, monkeypatch):
    import urllib.request

    from threadline_engine.ai import segment

    def no_runtime():
        raise segment.SegmentError("AI tracing isn't available on this computer")

    fetched = []
    monkeypatch.setattr(segment, "model_dir", lambda: tmp_path / "m")
    monkeypatch.setattr(segment, "_runtime", no_runtime)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: fetched.append(1))
    with pytest.raises(segment.SegmentError, match="isn't available"):
        segment.download()
    assert fetched == []


def test_model_files_are_pinned_to_a_revision_with_checksums():
    """QA decision 2: not the moving "main" branch, and every file has a SHA-256."""
    import re

    from threadline_engine.ai import segment

    for name, url, sha in segment.FILES.values():
        assert f"/resolve/{segment.REVISION}/" in url and "/main/" not in url and url.endswith(name)
        assert re.fullmatch(r"[0-9a-f]{64}", sha)
    assert re.fullmatch(r"[0-9a-f]{40}", segment.REVISION)


def _fake_model(monkeypatch, tmp_path, bodies):
    """Two tiny stand-in model files with the right checksums, served instead of the real download."""
    import hashlib
    import urllib.request

    from threadline_engine.ai import segment

    files = {k: (f"{k}.onnx", f"https://example.test/{k}.onnx", hashlib.sha256(b).hexdigest()) for k, b in bodies.items()}
    served = {url: bodies[k] for k, (_, url, _) in files.items()}
    monkeypatch.setattr(segment, "FILES", files)
    monkeypatch.setattr(segment, "model_dir", lambda: tmp_path / "m")
    monkeypatch.setattr(segment, "_runtime", lambda: None)
    monkeypatch.setattr(segment, "_sessions", lambda force=False: None)
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, **k: _Resp(served[req.full_url]))
    return segment


def test_model_download_keeps_files_that_match_their_checksum(tmp_path, monkeypatch):
    segment = _fake_model(monkeypatch, tmp_path, {"encoder": b"aaa", "decoder": b"bbb"})
    assert segment.download()["installed"] is True
    assert (tmp_path / "m" / "encoder.onnx").read_bytes() == b"aaa"


def test_model_download_throws_away_a_file_with_the_wrong_checksum(tmp_path, monkeypatch):
    segment = _fake_model(monkeypatch, tmp_path, {"encoder": b"aaa", "decoder": b"bbb"})
    name, url, _ = segment.FILES["decoder"]
    segment.FILES["decoder"] = (name, url, "0" * 64)  # the server's copy is no longer the expected one
    with pytest.raises(segment.SegmentError, match="checksum"):
        segment.download()
    assert not (tmp_path / "m" / "decoder.onnx").exists()
    assert not list((tmp_path / "m").glob("*.part"))


def test_model_download_replaces_an_earlier_unpinned_file(tmp_path, monkeypatch):
    segment = _fake_model(monkeypatch, tmp_path, {"encoder": b"aaa", "decoder": b"bbb"})
    (tmp_path / "m").mkdir()
    (tmp_path / "m" / "encoder.onnx").write_bytes(b"from the old moving main branch")
    segment.download()
    assert (tmp_path / "m" / "encoder.onnx").read_bytes() == b"aaa"


def _square_fill(id_, x0, y0, x1, y1):
    pts = [[x0, y0, "l"], [x1, y0, "l"], [x1, y1, "l"], [x0, y1, "l"]]
    return {"id": id_, "kind": "fill", "geometry": {"outline": pts}, "params": {}, "thread": {"color": "#000000"}}


def test_guesses_fit_around_shapes_already_drawn(tmp_path, monkeypatch):
    """A click next to a shape already traced: the guess comes cut around it (tucked a little under),
    with the whole guess offered after it; a click on a drawn shape leaves the guesses whole."""
    img = Image.new("RGB", (SIZE, SIZE), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((100, 100, 500, 500), fill=(200, 40, 40), outline="black", width=6)
    path = tmp_path / "red.png"
    img.save(path)
    plain = pick(autotrace.region(str(path), PLACE, mm(150, 300))["candidates"], "middle")
    # A shape already drawn over the right half of the red square.
    a, b = mm(300, 100), mm(520, 520)
    drawn = _square_fill("x1", a[0], a[1], b[0], b[1])
    seen = []
    from threadline_engine.ai import segment

    monkeypatch.setattr(segment, "available", lambda: True)
    monkeypatch.setattr(segment, "masks", lambda pic, pos, neg: seen.append(neg) or [])
    r = autotrace.region(str(path), PLACE, mm(150, 300), taken=[drawn], use_ai=True)["candidates"]
    fitted = next(c for c in r if c["kind"] == "fill")
    assert fitted.get("fitted") and "fitted around your shapes" in fitted["label"]
    assert fitted["area_mm2"] == pytest.approx(plain["area_mm2"] / 2, rel=0.12)
    # It tucks under the drawn shape rather than stopping short of it.
    assert max(n[0] for n in fitted["outline"]) > a[0] + 0.1
    whole = next(c for c in r if c["id"].endswith("-whole"))
    assert whole["area_mm2"] == pytest.approx(plain["area_mm2"], rel=0.05)
    assert r.index(whole) > r.index(fitted)
    # The AI is told the drawn shape is "not this".
    assert seen and len(seen[0]) == 1
    # Clicking on the drawn shape itself: nothing is fitted.
    again = autotrace.region(str(path), PLACE, mm(400, 300), taken=[drawn])["candidates"]
    assert not any(c.get("fitted") for c in again)
