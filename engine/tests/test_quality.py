"""M7: fabric presets and quality checks."""

import base64
import math

import pyembroidery as pe
import pytest

from threadline_engine import fabrics, layout, quality
from threadline_engine.digitize.stitches import STITCH, SatinParams, auto_satin_underlay, generate, satin, width_comp


def sq(x0, y0, x1, y1):
    return [[x0, y0, "c"], [x1, y0, "c"], [x1, y1, "c"], [x0, y1, "c"]]


def fill_item(id_, outline, **params):
    return {"id": id_, "kind": "fill", "name": id_, "geometry": {"outline": outline}, "params": params}


def satin_item(id_, y0, width, length=30):
    return {"id": id_, "kind": "satin", "name": id_, "params": {},
            "geometry": {"rail_a": [[0, y0, "c"], [length, y0, "c"]], "rail_b": [[0, y0 + width, "c"], [length, y0 + width, "c"]]}}


def codes(lay, **kw):
    return [c["code"].split("_")[0] for c in layout.check(lay, **kw)["checks"]]


# ---------------------------------------------------------------- fabrics


def test_fabric_fills_in_what_the_user_left_automatic():
    obj = {"kind": "satin", "params": {"spacing_mm": 0.4}}
    knit = fabrics.apply(obj, "knit")["params"]
    assert knit["pull_comp_mm"] == 0.35 and knit["underlay"] == "auto" and knit["underlay_level"] == "heavy"
    assert knit["spacing_mm"] == pytest.approx(0.4 / 0.9, abs=1e-3)  # knits are sewn a little lighter
    mine = fabrics.apply({"kind": "satin", "params": {"pull_comp_mm": 0.5, "underlay": ["center"]}}, "knit")["params"]
    assert mine["pull_comp_mm"] == 0.5 and mine["underlay"] == ["center"]  # the user's choice wins
    assert fabrics.apply({"kind": "run", "params": {}}, "knit") == {"kind": "run", "params": {}}


def test_unknown_fabric_falls_back_to_woven():
    assert fabrics.get("velvet-unicorn")["id"] == "woven"
    assert "topping" in fabrics.advice("towel").lower()


def test_automatic_underlay_grows_with_width_and_fabric():
    assert auto_satin_underlay(1.5, "normal") == ("center",)
    assert auto_satin_underlay(3, "normal") == ("edge",)
    assert auto_satin_underlay(6, "normal") == ("edge", "zigzag")
    assert len(auto_satin_underlay(3, "heavy")) > len(auto_satin_underlay(3, "light"))


def test_wider_columns_get_more_pull_compensation():
    assert width_comp(0.2, 4) == pytest.approx(0.2)
    assert width_comp(0.2, 8) > width_comp(0.2, 4) > width_comp(0.2, 1)


def test_thin_satin_is_widened_and_says_so():
    rails = ([[0, 0, "c"], [20, 0, "c"]], [[0, 0.4, "c"], [20, 0.4, "c"]])
    recs, warnings = satin(*rails, SatinParams(underlay=(), pull_comp_mm=0, auto_widen=True))
    ys = [r[1] for r in recs]
    assert max(ys) - min(ys) == pytest.approx(1.0, abs=0.01)  # 0.4 mm became 1 mm, about the middle
    assert (max(ys) + min(ys)) / 2 == pytest.approx(0.2)
    assert any("Widened" in w for w in warnings)


def test_fabric_changes_the_stitches_in_a_layout():
    items = [fill_item("f", sq(0, 0, 20, 20))]
    woven = layout.render_summary({"items": items, "fabric": "woven"})["info"]["stitches"]
    towel = layout.render_summary({"items": items, "fabric": "towel"})["info"]["stitches"]
    assert towel > woven  # towels get denser fill so loops don't poke through


# ---------------------------------------------------------------- checks


def test_a_clean_design_has_no_warnings():
    assert codes({"items": [fill_item("a", sq(0, 0, 20, 20))]}) == []


def test_stacked_layers_are_too_dense():
    stack = [fill_item(f"l{i}", sq(0, 0, 20, 20)) for i in range(3)]
    found = layout.check({"items": stack})["checks"]
    dense = next(c for c in found if c["code"] == "dense")
    assert dense["why"] and dense["fix"] and 0 <= dense["at"][0] <= 20


def test_shapes_that_almost_touch_show_a_gap():
    def lay(gap):
        return {"items": [fill_item("Left", sq(0, 0, 20, 20)), fill_item("Right", sq(20 + gap, 0, 40 + gap, 20), angle_deg=-45)]}
    gap = next(c for c in layout.check(lay(0.3))["checks"] if c["code"].startswith("gap"))
    assert gap["message"] == "Left and Right almost touch" and gap["item_id"] == "Left"
    assert "gap" not in codes(lay(-0.5))  # overlapping on purpose
    assert "gap" not in codes(lay(3))  # clearly apart


def test_wide_satin_makes_long_loose_stitches():
    assert "long" in codes({"items": [satin_item("s", 0, 9)]})


def test_needle_hitting_one_spot():
    p = pe.EmbPattern()
    for i in range(30):
        p.stitch_abs(i % 2 * 3, 0)  # 0.3 mm back and forth in one square millimetre
    p.end()
    assert "needle_hits" in [c["code"] for c in quality.check(p)["checks"]]


def test_heatmap_covers_the_design():
    h = layout.check({"items": [fill_item("a", sq(0, 0, 20, 10))]}, heatmap=True)["heatmap"]
    data = base64.b64decode(h["data"])
    assert len(data) == h["width"] * h["height"]
    assert h["x"] <= 0 and h["y"] <= 0 and h["x"] + h["width"] >= 20
    assert 0 < max(data) < h["limit"]  # one normal fill is below the warning level


def test_export_preview_includes_checks_and_fabric_advice():
    stack = [fill_item(f"l{i}", sq(0, 0, 20, 20)) for i in range(3)]
    r = layout.preview_export({"items": stack, "fabric": "fleece"}, None, "pes")
    assert any(w["code"] == "dense" for w in r["warnings"])
    assert "Cut-away" in r["fabric_advice"]


def test_a_gap_is_reported_once_for_stacked_copies():
    items = [fill_item(f"L{i}", sq(0, 0, 20, 20)) for i in range(3)] + [fill_item("R", sq(20.3, 0, 40, 20), angle_deg=-45)]
    assert codes({"items": items}).count("gap") == 1


def test_a_border_over_a_fill_edge_is_not_a_hotspot():
    """A satin border laid over the edge of a fill is normal practice, not too dense."""
    border = {"id": "b", "kind": "satin", "params": {},
              "geometry": {"rail_a": [[-2, -2, "c"], [42, -2, "c"]], "rail_b": [[-2, 2, "c"], [42, 2, "c"]]}}
    assert "dense" not in codes({"items": [fill_item("f", sq(0, 0, 40, 30)), border]})
