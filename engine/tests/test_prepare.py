"""Cut-stops, recoloring and machine checks."""

import json
import math

import pyembroidery as pe
import pytest

from threadline_engine import design, profiles
from threadline_engine.prepare import CutStops, Options, add_cut_stops, prepare, travels

M = pe.COMMAND_MASK


def two_islands(gap_x=300, trim=True, color_change_between=False) -> pe.EmbPattern:
    """Two runs of stitches in one color, joined by a jump (+trim) of `gap_x` / 10 mm."""
    p = pe.EmbPattern()
    p.add_thread(pe.EmbThread("#ff0000", "Red", "1", brand="Test"))
    p.add_thread(pe.EmbThread("#00ff00", "Green", "2", brand="Test"))
    for x in range(0, 100, 20):
        p.stitch_abs(x, 0)
    if color_change_between:
        p.color_change()
    if trim:
        p.trim()
    p.move_abs(80 + gap_x, 0)
    for x in range(80 + gap_x, 180 + gap_x, 20):
        p.stitch_abs(x, 0)
    p.end()
    return p


def kinds(p):
    return [c & M for *_, c in p.stitches]


def test_trim_becomes_stop_with_ties():
    p = two_islands()
    assert add_cut_stops(p, CutStops(enabled=True, min_jump_mm=3)) == 1
    k = kinds(p)
    assert pe.TRIM not in k
    assert k.count(pe.STOP) == 1
    s = k.index(pe.STOP)
    stop = p.stitches[s]
    assert (stop[0], stop[1]) == (80, 0)  # stops where the first island ended
    # Tie-off: back 0.7 mm along the incoming direction, then return.
    assert p.stitches[s - 2][:2] == [73.0, 0.0] and p.stitches[s - 1][:2] == [80, 0]
    # Tie-in after landing at 380: forward toward the next stitch, then back.
    first = next(i for i in range(s, len(k)) if k[i] == pe.STITCH)
    assert [st[:2] for st in p.stitches[first : first + 3]] == [[380, 0], [387.0, 0.0], [380, 0]]


def test_stitch_positions_kept_in_order():
    p = two_islands()
    before = [(x, y) for x, y, c in p.stitches if c & M == pe.STITCH]
    add_cut_stops(p, CutStops(enabled=True, tie=False))
    after = [(x, y) for x, y, c in p.stitches if c & M == pe.STITCH]
    assert after == before


def test_short_jumps_and_untrimmed_jumps_left_alone():
    short = two_islands(gap_x=20)  # 2 mm
    assert add_cut_stops(short, CutStops(enabled=True, min_jump_mm=3)) == 0
    assert pe.TRIM in kinds(short)

    untrimmed = two_islands(trim=False)
    assert add_cut_stops(untrimmed, CutStops(enabled=True)) == 0
    assert add_cut_stops(untrimmed, CutStops(enabled=True, include_untrimmed=True)) == 1


def test_travel_after_color_change_is_not_converted():
    p = two_islands(color_change_between=True)
    assert add_cut_stops(p, CutStops(enabled=True)) == 0


def test_cut_stops_survive_pes_and_read_as_same_color(tmp_path):
    src = tmp_path / "in.pes"
    pe.write(two_islands(), str(src), {"version": 6})
    out = tmp_path / "out.pes"
    report = design.export(
        str(src), str(out), {"machine": "brother-pe550d", "cut_stops": {"enabled": True}}
    )
    assert report["stops_added"] == 1
    back = design.open_design(str(out))
    assert back["info"]["stops"] == 1
    assert back["info"]["color_changes"] == 0

    # In the PEC block the stop is a color change to the same palette color,
    # which is what makes a Brother machine cut there.
    raw = out.read_bytes()
    pec = int.from_bytes(raw[8:12], "little")
    n = raw[pec + 48] + 1
    palette = list(raw[pec + 49 : pec + 49 + n])
    assert n == 2 and palette[0] == palette[1]


def test_recolor_applies_on_export(tmp_path):
    src = tmp_path / "in.pes"
    pe.write(two_islands(), str(src), {"version": 6})
    out = tmp_path / "out.pes"
    new = {"color": "#123456", "name": "Navy", "catalog": "1043", "brand": "Madeira Rayon"}
    design.export(str(src), str(out), {"threads": [new]})
    t = design.open_design(str(out))["threads"][0]
    assert (t["color"], t["name"], t["catalog"], t["brand"]) == ("#123456", "Navy", "1043", "Madeira Rayon")
    # The source file is untouched.
    assert design.open_design(str(src))["threads"][0]["name"] == "Red"


def test_preview_reports_without_writing(tmp_path):
    src = tmp_path / "in.pes"
    pe.write(two_islands(), str(src), {"version": 6})
    r = design.preview_export(str(src), {"machine": "brother-pe550d", "cut_stops": {"enabled": True}}, "pes")
    assert r["stops_added"] == 1
    assert r["info"]["stops"] == 1
    assert list(tmp_path.iterdir()) == [src]


def big_square(mm: float) -> pe.EmbPattern:
    p = pe.EmbPattern()
    p.add_thread(pe.EmbThread("#000000", "Black"))
    u = mm * 10
    for x, y in [(0, 0), (u, 0), (u, u), (0, u), (0, 0)]:
        p.stitch_abs(x, y)
    p.end()
    return p


def codes(p, opts, ext="pes"):
    return {w["code"]: w["level"] for w in prepare(p, Options.from_dict(opts), ext)[1]["warnings"]}


def test_hoop_checks():
    pe550 = {"machine": "brother-pe550d"}
    assert "hoop_too_big" not in codes(big_square(99.9), pe550)
    assert codes(big_square(120), pe550)["hoop_too_big"] == "error"

    wide = pe.EmbPattern()
    wide.add_thread(pe.EmbThread("#000000"))
    for x, y in [(0, 0), (1300, 0), (1300, 1200), (0, 1200)]:
        wide.stitch_abs(x, y)
    wide.end()
    # 130 x 120 mm doesn't fit Janome A (126 x 110) either way; 120 x 130 fits SQ14.
    assert codes(wide, {"machine": "janome-generic", "hoop": "a"}, "jef")["hoop_too_big"] == "error"
    assert "hoop_too_big" not in codes(wide, {"machine": "janome-generic", "hoop": "sq14"}, "jef")


def test_hoop_rotate_hint():
    p = pe.EmbPattern()
    p.add_thread(pe.EmbThread("#000000"))
    for x, y in [(0, 0), (1200, 0), (1200, 1000), (0, 1000)]:  # 120 x 100 in a 126 x 110 hoop: fits
        p.stitch_abs(x, y)
    p.end()
    assert "hoop_rotate" not in codes(p, {"machine": "janome-generic", "hoop": "a"}, "jef")
    q = pe.EmbPattern()
    q.add_thread(pe.EmbThread("#000000"))
    for x, y in [(0, 0), (1000, 0), (1000, 1200), (0, 1200)]:  # 100 x 120: only fits rotated
        q.stitch_abs(x, y)
    q.end()
    assert codes(q, {"machine": "janome-generic", "hoop": "a"}, "jef")["hoop_rotate"] == "warning"


def test_format_and_trim_hints():
    p = two_islands()
    c = codes(p, {"machine": "brother-pe550d"}, "jef")
    assert c["format"] == "warning"
    assert c["trims_ignored"] == "info"
    c2 = codes(p, {"machine": "brother-pe550d", "cut_stops": {"enabled": True}})
    assert "trims_ignored" not in c2 and c2["stops_added"] == "info"
    assert "trims_ignored" not in codes(p, {"machine": "janome-generic"}, "jef")


def test_max_colors_limit(isolated_data_dir):
    d = isolated_data_dir / "machines"
    d.mkdir(parents=True)
    (d / "tiny.json").write_text(json.dumps({
        "id": "tiny", "name": "Tiny", "formats": ["pes"], "cuts": "color_change", "max_colors": 1,
        "hoops": [{"id": "h", "width_mm": 100, "height_mm": 100}],
    }))
    c = codes(two_islands(), {"machine": "tiny", "cut_stops": {"enabled": True}})
    assert c["max_colors"] == "error"


def test_user_profiles_and_bad_files(isolated_data_dir):
    d = isolated_data_dir / "machines"
    d.mkdir(parents=True)
    (d / "broken.json").write_text("{nope")
    (d / "override.json").write_text(json.dumps({
        "id": "brother-pe550d", "name": "My PE550D", "formats": ["pes"], "cuts": "color_change",
        "hoops": [{"id": "4x4", "width_mm": 100, "height_mm": 100}, {"id": "small", "width_mm": 50, "height_mm": 50}],
    }))
    ms = {m["id"]: m for m in profiles.list_machines()}
    assert ms["brother-pe550d"]["name"] == "My PE550D" and not ms["brother-pe550d"]["builtin"]
    assert [h["id"] for h in ms["brother-pe550d"]["hoops"]] == ["4x4", "small"]
    assert ms["janome-generic"]["builtin"]
    with pytest.raises(profiles.ProfileError):
        profiles.get_machine("nope")


def test_travels_skips_leading_jump():
    p = pe.EmbPattern()
    p.move_abs(100, 100)
    p.stitch_abs(100, 100)
    p.stitch_abs(150, 100)
    p.end()
    assert list(travels(p.stitches)) == []


def test_ties_never_land_far_from_the_stitch():
    p = two_islands()
    add_cut_stops(p, CutStops(enabled=True))
    pts = [(x, y) for x, y, c in p.stitches if c & M == pe.STITCH]
    steps = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    assert max(steps) <= 300 + 1e-6  # only the original travel is long
