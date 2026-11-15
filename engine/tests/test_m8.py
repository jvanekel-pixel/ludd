"""M8: applique, knockdown, splitting across hoopings."""

import math
import xml.etree.ElementTree as ET

import pyembroidery as pe
import pytest

from threadline_engine import design, layout, split
from threadline_engine.digitize.stitches import generate

HOOP = {"width_mm": 100, "height_mm": 100}  # the PE550D's 4" x 4"


def sq(x0, y0, x1, y1):
    return [[x0, y0, "c"], [x1, y0, "c"], [x1, y1, "c"], [x0, y1, "c"]]


def stitches_mm(pattern):
    return [(x / 10, y / 10) for x, y, c in pattern.stitches if (c & pe.COMMAND_MASK) == pe.STITCH]


# ---------------------------------------------------------------- applique


def test_applique_sews_placement_tackdown_cover_with_two_stops():
    recs, warnings = generate({"kind": "applique", "geometry": {"outline": sq(0, 0, 40, 30)}, "params": {}})
    stops = [i for i, r in enumerate(recs) if r[2] == pe.STOP]
    assert len(stops) == 2 and not warnings
    xs = [r[0] for r in recs if r[2] == pe.STITCH]
    # The cover straddles the edge: 3 mm wide, so 1.5 mm out (plus pull compensation)...
    assert min(xs) == pytest.approx(-1.6, abs=0.03)
    # ...and every part after a stop starts with a move, never a long sewn stitch.
    for i in stops:
        assert recs[i + 1][2] == pe.JUMP


def test_applique_without_placement_line_has_one_stop():
    recs, _ = generate({"kind": "applique", "geometry": {"outline": sq(0, 0, 40, 30)}, "params": {"placement": False}})
    assert sum(1 for r in recs if r[2] == pe.STOP) == 1


def test_applique_cut_file_is_real_size(tmp_path):
    lay = {"items": [{"id": "a", "kind": "applique", "name": "Heart", "geometry": {"outline": sq(10, 10, 50, 40)}, "params": {}},
                     {"id": "b", "kind": "fill", "geometry": {"outline": sq(60, 0, 70, 10)}, "params": {}}]}
    r = layout.export_applique_svg(lay, str(tmp_path / "cut"))
    assert r["pieces"] == 1 and r["path"].endswith("cut.svg")
    root = ET.parse(r["path"]).getroot()
    assert root.get("width") == "50.00mm" and root.get("height") == "40.00mm"  # 40 x 30 piece + 5 mm margins
    with pytest.raises(layout.LayoutError, match="no applique"):
        layout.applique_svg({"items": lay["items"][1:]})


def test_applique_shows_in_a_layout_and_exports_to_pes(tmp_path):
    lay = {"items": [{"id": "a", "kind": "applique", "geometry": {"outline": sq(0, 0, 30, 30)}, "params": {}}]}
    s = layout.render_summary(lay)
    assert s["info"]["stops"] == 2 and s["items"][0]["kind"] == "applique"
    layout.export(lay, str(tmp_path / "a.pes"))
    assert design.open_design(str(tmp_path / "a.pes"))["info"]["stitches"] > 100


# ---------------------------------------------------------------- knockdown


def test_knockdown_goes_first_and_covers_the_design_with_a_margin():
    items = [{"id": "a", "kind": "fill", "geometry": {"outline": sq(0, 0, 20, 20)}, "params": {}}]
    plain = layout.render_summary({"items": items})
    kd = layout.render_summary({"items": items, "knockdown": {"enabled": True, "margin_mm": 2}})
    assert kd["info"]["colors"] == plain["info"]["colors"] + 1
    first = kd["blocks"][0]
    assert "Knockdown" in kd["threads"][first["thread"]]["name"]
    b = kd["info"]["bounds_mm"] if "bounds_mm" in kd["info"] else None
    assert kd["info"]["width_mm"] > plain["info"]["width_mm"] + 3  # the margin all round


# ---------------------------------------------------------------- splitting


def wide_design():
    """160 x 60 mm: two fills and a satin that crosses the middle. Too wide for a 4" hoop."""
    return {"items": [
        {"id": "l", "kind": "fill", "geometry": {"outline": sq(0, 0, 45, 60)}, "params": {}, "thread": {"color": "#ff0000"}},
        {"id": "r", "kind": "fill", "geometry": {"outline": sq(115, 0, 160, 60)}, "params": {}, "thread": {"color": "#0000ff"}},
        {"id": "s", "kind": "satin", "params": {}, "thread": {"color": "#00aa00"},
         "geometry": {"rail_a": [[5, 28, "c"], [155, 28, "c"]], "rail_b": [[5, 32, "c"], [155, 32, "c"]]}},
    ]}


def test_split_plan_for_a_wide_design():
    p = layout.split_plan(wide_design(), HOOP)
    assert (p["cols"], p["rows"]) == (2, 1)
    for s in p["sections"]:
        x0, y0, x1, y1 = s["window_mm"]
        assert x1 - x0 == pytest.approx(98) and y1 - y0 == pytest.approx(98)
    a, b = p["sections"]
    assert a["marks"] == b["marks"] and len(a["marks"]) == 2  # the same crosses in both hoopings


def test_a_design_that_fits_is_one_hooping():
    p = layout.split_plan({"items": [wide_design()["items"][0]]}, HOOP)
    assert len(p["sections"]) == 1 and not p["sections"][0]["marks"]


def test_split_files_fit_the_hoop_and_line_up(tmp_path):
    """M8 acceptance (on screen): each file fits the hoop; put back together at their hooping
    positions they sew every stitch of the original, and the alignment marks coincide."""
    lay = wide_design()
    r = layout.export_split(lay, str(tmp_path / "banner.pes"), HOOP)
    assert [p.split("\\")[-1].split("/")[-1] for p in r["paths"]] == ["banner 1 of 2.pes", "banner 2 of 2.pes"]
    original = stitches_mm(layout.render(lay).pattern)
    blocks, plan, _, _ = split.plan(layout.render(lay).pattern, HOOP["width_mm"], HOOP["height_mm"], 10.0)
    placed = []
    marks_abs = []
    for path, sec, part in zip(r["paths"], r["sections"], plan):
        pat = pe.read(path)
        # A PES file has its top-left corner at (0, 0) (as Brother machines read it): put it back
        # where the hooping has it, centred on the hoop.
        bx, by, _, _ = split.section_pattern(blocks, part).bounds()
        pts = [(x + bx / 10, y + by / 10) for x, y in stitches_mm(pat)]
        # Fits the 4" hoop's sewing field (PES stores 0.1 mm; allow its rounding).
        assert max(abs(x) for x, _ in pts) <= 49.05 and max(abs(y) for _, y in pts) <= 49.05
        x0, y0, x1, y1 = sec["window_mm"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        placed += [(x + cx, y + cy) for x, y in pts]
        marks_abs.append(sorted((round(m[0], 1), round(m[1], 1)) for m in sec["marks"]))
    # Every original stitch is sewn by one of the hoopings, in the same place (0.1 mm rounding).
    grid = {(round(x * 5), round(y * 5)) for x, y in placed}
    missing = [p for p in original if not any((round(p[0] * 5) + dx, round(p[1] * 5) + dy) in grid
                                              for dx in (-1, 0, 1) for dy in (-1, 0, 1))]
    assert not missing
    assert marks_abs[0] == marks_abs[1]


def test_cut_runs_meet_on_the_seam():
    p = pe.EmbPattern()
    p.add_thread(pe.EmbThread("#000000", "Black"))
    for x in range(0, 1601, 25):  # a 160 mm line of 2.5 mm stitches
        p.add_stitch_absolute(pe.STITCH, x, 0)
    p.end()
    blocks, sections, grid, bounds = split.plan(p, 100, 100, 10)
    a, b = sections
    seam = a.cell[2]
    ends = [run[-1] for _, run, cut in a.runs if cut]
    starts = [run[0] for _, run, cut in b.runs if cut]
    assert ends and starts and ends[0] == starts[0] and ends[0][0] == pytest.approx(seam)


def test_overlap_too_big_is_explained():
    with pytest.raises(split.SplitError, match="overlap"):
        layout.split_plan(wide_design(), HOOP, overlap_mm=60)


def _count(pat, k):
    return sum(1 for *_, c in pat.stitches if c & pe.COMMAND_MASK == k)


def test_split_keeps_applique_stops(tmp_path):
    """QA C1: an applique too big for the hoop keeps its placement and tack-down stops in every hooping."""
    sq = [[-90, -30, "c"], [90, -30, "c"], [90, 30, "c"], [-90, 30, "c"]]
    lay = {"items": [{"id": "a", "kind": "applique", "geometry": {"outline": sq}, "params": {}}]}
    assert _count(layout.render(lay).pattern, pe.STOP) == 2
    r = layout.export_split(lay, str(tmp_path / "app.pes"), HOOP)
    assert len(r["paths"]) == 3  # 180 mm with windows overlapping by 10 mm
    for path in r["paths"]:
        assert _count(pe.read(path), pe.STOP) == 2


def test_split_never_sews_a_lower_layer_over_a_higher_one():
    """QA C5: a red base and a blue top crossing the seam: no red stitch is sewn in a later hooping
    on top of the blue, wherever the two hoopings' windows overlap."""
    def sq(a, b, c, d):
        return [[a, b, "c"], [c, b, "c"], [c, d, "c"], [a, d, "c"]]

    def fill(i, ol, col):
        return {"id": i, "kind": "fill", "geometry": {"outline": ol}, "params": {}, "thread": {"color": col, "name": col}}

    for top in (sq(60, 20, 80, 40), sq(66, 20, 80, 40)):
        lay = {"items": [fill("dotL", sq(0, 0, 4, 4), "#00ff00"), fill("dotR", sq(146, 0, 150, 4), "#00ff00"),
                         fill("base", sq(64, 10, 145, 50), "#ff0000"), fill("top", top, "#0000ff")]}
        blocks, sections, _, _ = split.plan(layout.render(lay).pattern, 100, 100, 10)
        # Blue (the top) as sewn, hooping by hooping: no red may land inside it in a LATER hooping.
        blue = [(s.index, split._bounds(run)) for s in sections for bi, run, _ in s.runs if blocks[bi][0]["color"] == "#0000ff"]
        for s in sections:
            for bi, run, _ in s.runs:
                if blocks[bi][0]["color"] != "#ff0000":
                    continue
                inside = [p for p in run for k, b in blue
                          if s.index > k and b[0] + 0.5 < p[0] < b[2] - 0.5 and b[1] + 0.5 < p[1] < b[3] - 0.5]
                assert not inside, f"red sewn over blue in hooping {s.index + 1}"


def test_qa_c8_applique_holes_are_placed_tacked_covered_and_cut():
    from threadline_engine.digitize.stitches import generate

    n = lambda pts: [[x, y, "c"] for x, y in pts]  # noqa: E731
    sq = n([(0, 0), (40, 0), (40, 40), (0, 40)])
    hole = n([(15, 15), (25, 15), (25, 25), (15, 25)])
    solid, _ = generate({"kind": "applique", "geometry": {"outline": sq}, "params": {}})
    holed, _ = generate({"kind": "applique", "geometry": {"outline": sq, "holes": [hole]}, "params": {}})
    assert holed != solid
    near_hole = [1 for x, y, k in holed if k == pe.STITCH and 13 < x < 27 and 13 < y < 27]
    assert len(near_hole) > 50  # placement, tack-down and satin round the hole's edge
    assert sum(1 for *_, k in holed if k == pe.STOP) == 2  # still two stops, after all edges
    svg, count = layout.applique_svg({"items": [{"id": "a", "kind": "applique", "geometry": {"outline": sq, "holes": [hole]}, "params": {}}]})
    assert count == 1 and svg.count(" Z") == 2  # one piece, cut on its outline and its hole


# ---------------------------------------------------------------- phase 4 (QA medium and low findings)

def _red_fill(i, ol):
    return {"id": i, "kind": "fill", "name": i, "geometry": {"outline": ol}, "params": {}, "thread": {"color": "#ff0000", "name": "r"}}


def test_qa4_overlap_setting_is_the_real_overlap_between_hoopings():
    for width in (150, 180, 260):
        d = {"items": [_red_fill("a", sq(0, 0, width, 60))]}
        for ov in (6, 10, 20, 30):
            p = layout.split_plan(d, HOOP, ov)
            ws = sorted(s["window_mm"] for s in p["sections"])
            for a, b in zip(ws, ws[1:]):
                assert a[2] - b[0] >= ov - 1e-6  # neighbouring windows overlap by at least the setting
    # And it changes the plan: more overlap, more hoopings.
    d = {"items": [_red_fill("a", sq(0, 0, 150, 60))]}
    assert layout.split_plan(d, HOOP, 6)["cols"] < layout.split_plan(d, HOOP, 30)["cols"]


def test_qa4_hoopings_with_nothing_to_sew_are_left_out():
    d = {"items": [_red_fill("tl", sq(0, 0, 40, 40)), _red_fill("br", sq(120, 120, 160, 160))]}
    p = layout.split_plan(d, HOOP, 10)
    assert len(p["sections"]) == 2 and all(s["stitches"] for s in p["sections"])
    assert all(s["marks"] for s in p["sections"])  # still crosses to line them up


def test_qa4_alignment_crosses_sit_on_bare_fabric_when_there_is_room():
    d = {"items": [_red_fill("a", sq(0, 0, 150, 60))]}
    r = layout.render(d)
    blocks, sections, grid, bounds = split.plan(r.pattern, 100, 100, 10)
    area = layout._stitched_area(r.blocks)
    from shapely.geometry import box
    marks = [m for s in sections for m in s.marks_start + s.marks_end]
    assert marks
    for x, y in marks:
        a = split.MARK_ARM_MM
        assert not area.intersects(box(x - a, y - a, x + a, y + a))


def test_qa4_single_stitch_dots_survive_a_split(tmp_path):
    p = pe.EmbPattern()
    p.add_thread(pe.EmbThread("#ff0000", "R"))
    for x in range(0, 1601, 25):
        p.stitch_abs(x, 0)
    for x in (100, 500, 900, 1300):
        p.trim()
        p.move_abs(x, 300)
        p.stitch_abs(x, 300)
    p.end()
    blocks, sections, grid, bounds = split.plan(p, 100, 100, 10)
    dots = 0
    for s in sections:
        cx, cy = s.center
        dots += sum(1 for x, y in stitches_mm(split.section_pattern(blocks, s)) if abs(y + cy - 30) < 0.05)
    assert dots >= 4


def test_qa4_seam_lock_stitches_only_where_the_thread_is_cut():
    d = {"items": [_red_fill("a", sq(0, 0, 150, 60))]}
    r = layout.render(d)
    blocks, sections, grid, bounds = split.plan(r.pattern, 100, 100, 10)
    whole = len(stitches_mm(r.pattern))
    marks = sum(len(s.marks_start) + len(s.marks_end) for s in sections) * 7
    parts = sum(len(stitches_mm(split.section_pattern(blocks, s))) for s in sections)
    assert parts - marks - whole < whole * 0.04  # was about +9% with locks on every cut row


def test_qa4_cut_pieces_that_end_in_a_trim_are_locked():
    p = pe.EmbPattern()
    p.add_thread(pe.EmbThread("#000000", "Black"))
    for x in range(0, 1601, 25):  # one 160 mm line: each half ends at the seam, then nothing follows
        p.add_stitch_absolute(pe.STITCH, x, 0)
    p.end()
    blocks, sections, grid, bounds = split.plan(p, 100, 100, 10)
    a = sections[0]
    sewn = stitches_mm(split.section_pattern(blocks, a))
    line = [pt for _, run, cut in a.runs if cut for pt in run]
    assert len(sewn) > len(line)  # lock stitches added at the cut end
