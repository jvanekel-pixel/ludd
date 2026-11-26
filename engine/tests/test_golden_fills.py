"""Golden round trips for Phase 6: each new fill pattern and stitch option, drawn on a 30 mm
shape, saved as PES (the owner's Brother) and JEF, reopens with the same stitches and colors; and
the options sewn together stay sane (docs/phases/PHASE-06-fills-and-stitch-quality.md, section 8)."""

import pytest
from shapely.geometry import LineString, Point, Polygon

from invariants import assert_deterministic, assert_sane
from threadline_engine import design, layout
from threadline_engine.digitize.stitches import STITCH, generate


def c(x, y, kind="c"):
    return [x, y, kind]


SQUARE = [c(0, 0), c(30, 0), c(30, 30), c(0, 30)]
RED = {"color": "#cc2222", "name": "Red", "catalog": "", "brand": ""}
YELLOW = {"color": "#eecc22", "name": "Yellow", "catalog": "", "brand": ""}
BLUE = {"color": "#2255cc", "name": "Blue", "catalog": "", "brand": ""}
HEART_UNIT = [[0, 0], [0.25, -0.35], [0.5, -0.15], [0.75, -0.35], [1, 0]]


def fill(outline=SQUARE, carve=None, **params):
    geometry = {"outline": outline, **({"carve": carve} if carve else {})}
    return {"id": "f", "kind": "fill", "geometry": geometry, "thread": RED, "params": params}


CARVE = [[c(4, 6, "s"), c(15, 18, "s"), c(26, 9, "s")]]

CASES = {
    "blend_two": fill(pattern="blend", blend=[YELLOW]),
    "blend_three": fill(pattern="blend", blend=[YELLOW, BLUE]),
    "motif": fill(pattern="motif"),
    "motif_of_your_own": fill(pattern="motif", motif="user:hill", motif_unit=HEART_UNIT),
    "maze": fill(pattern="maze"),
    "ripple": fill(pattern="ripple"),
    "mesh": fill(pattern="mesh"),
    "weave_brick": fill(weave="brick"),
    "weave_twill": fill(weave="twill"),
    "weave_smooth": fill(weave="smooth"),
    "weave_random": fill(weave="random"),
    "carved": fill(carve=CARVE),
    "feathered": fill(feather="both", feather_mm=3),
    "hand_fill": fill(hand_pct=60),
    "hand_satin": {"id": "s", "kind": "satin", "thread": RED, "params": {"hand_pct": 60},
                   "geometry": {"nodes": [c(0, 0, "s"), c(15, 8, "s"), c(30, 0, "s")], "width_mm": 4}},
    "hand_line": {"id": "r", "kind": "run", "thread": RED, "params": {"hand_pct": 60, "style": "bean"},
                  "geometry": {"nodes": [c(0, 0, "s"), c(15, 8, "s"), c(30, 0, "s")]}},
    "turning": fill(angle_lines=[[[5, 8], [12, 8]], [[18, 22], [23, 27]]]),
}


@pytest.mark.parametrize("ext", ["pes", "jef"])
@pytest.mark.parametrize("name", sorted(CASES))
def test_round_trip(name, ext, tmp_path):
    lay = {"items": [CASES[name]]}
    sewn = layout.render_summary(lay)
    out = tmp_path / f"{name}.{ext}"
    layout.export(lay, str(out))
    back = design.open_design(str(out))
    assert back["info"]["stitches"] == sewn["info"]["stitches"]
    assert back["info"]["colors"] == sewn["info"]["colors"]
    assert back["info"]["width_mm"] == pytest.approx(sewn["info"]["width_mm"], abs=0.2)
    assert back["info"]["height_mm"] == pytest.approx(sewn["info"]["height_mm"], abs=0.2)


def test_blend_with_twill_a_carved_line_and_a_feathered_side_sews_sanely():
    obj = fill([c(0, 0), c(40, 0), c(40, 30), c(0, 30)], carve=[[c(5, 5), c(35, 25)]],
               pattern="blend", blend=[YELLOW], weave="twill", feather="right", angle_deg=0)
    recs, _ = generate(obj)
    assert_sane(recs, inside=Polygon([(0, 0), (40, 0), (40, 30), (0, 30)]), tolerance_mm=0.6)
    assert_deterministic(lambda: generate(obj)[0])
    blocks = layout.render({"items": [obj]}).blocks
    assert [b.thread["color"] for b in blocks] == [RED["color"], YELLOW["color"]]
    # Both colors drop their needles on the carved line wherever a row crosses it.
    line = LineString([(5, 5), (35, 25)])
    for b in blocks:
        points = [(r[0] / 10, r[1] / 10) for r in b.recs if r[2] == STITCH]
        on_line = [p for p in points if line.distance(Point(p)) <= 0.05]
        assert len(on_line) >= 15, b.thread["color"]  # without the carved line, at most one does
