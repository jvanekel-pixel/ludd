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
    assert min(xs) == pytest.approx(-1.6, abs=0.15)
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
    placed = []
    marks_abs = []
    for path, sec in zip(r["paths"], r["sections"]):
        pat = pe.read(path)
        pts = stitches_mm(pat)
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
