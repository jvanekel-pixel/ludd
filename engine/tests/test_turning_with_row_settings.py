"""Turning fills with the other rows settings (carved lines, the hand-sewn look, the cross-hatch
underlay), which Phase 6's tracks built apart (docs/phases/PHASE-06-fills-and-stitch-quality.md)."""

import pytest

import invariants
from snapshot_util import digest_recs_steady
from steady_util import forget_stitches, nudge_trig
from test_fill_turning import FAN_LINES, LEAF, LEAF_LINES, PANEL, _area, _fill, _line
from threadline_engine.digitize import stitches
from threadline_engine.digitize.fills import turning
from threadline_engine.digitize.rows import carve
from threadline_engine.digitize.stitches import JUMP, TRIM, FillParams, generate, transform_geometry
from threadline_engine.layout import Transform


def _carved(obj, *lines):
    g = {**obj["geometry"], "carve": [[[x, y, "c"] for x, y in line] for line in lines]}
    return {**obj, "geometry": g}


def _along_rows(obj, x0, x1, y):
    """A stretch of the turning fill's own guide between x0 and x1, moved to pass through y at x0:
    a line that runs along the rows beside it."""
    params = FillParams.from_dict(obj["params"])
    guide = turning.guide(params, _area(obj))
    points = [(x, py) for x, py in guide.coords if x0 <= x <= x1]
    points = points[::8] + [points[-1]]
    dy = y - points[0][1]
    return [(x, py + dy) for x, py in points]


def test_a_carved_line_along_the_curved_rows_warns_wherever_the_rows_turn():
    # FAN_LINES turn the rows from -30 degrees on the left to +30 on the right (mean 0): a line
    # following them on the left runs at about -30, which the average direction would miss.
    obj = _fill(PANEL, FAN_LINES)
    along = _along_rows(obj, 3, 20, 20)
    _, warnings = generate(_carved(obj, along))
    assert carve.ALONG_WARNING in warnings


def test_a_carved_line_across_the_curved_rows_does_not_warn():
    obj = _fill(PANEL, FAN_LINES)
    # Level on the right, where the rows climb at about 30 degrees: it crosses them, although it
    # runs along the rows' average direction.
    _, warnings = generate(_carved(obj, [(32, 15), (47, 15)]))
    assert carve.ALONG_WARNING not in warnings


def test_every_row_still_has_a_needle_on_a_carved_line_across_a_turning_fill():
    obj = _carved(_fill(PANEL, FAN_LINES), [(25, 2), (25, 28)])
    recs, _ = generate(obj)
    on_line = [p for p in invariants.stitch_points(recs) if abs(p[0] - 25) <= 0.05]
    assert len(on_line) > 0.8 * 30 / 0.4  # about one for each row the line crosses


@pytest.mark.parametrize("outline,lines", [(PANEL, FAN_LINES), (LEAF, LEAF_LINES)], ids=["panel", "leaf"])
def test_a_hand_sewn_turning_fill_makes_no_extra_jumps(outline, lines):
    plain, _ = generate(_fill(outline, lines))
    by_hand, _ = generate(_fill(outline, lines, hand_pct=100))
    for kind in (JUMP, TRIM):
        assert invariants.count(by_hand, kind) <= invariants.count(plain, kind)
    obj = _fill(outline, lines, hand_pct=100)
    invariants.assert_sane(by_hand, inside=_area(obj), tolerance_mm=0.6 + 0.1 + 0.05)


# The app's own steps on its 60 x 42 mm rectangle: keep the fill's 45-degree line and draw a
# nearly level one (Shift+I) in the upper right. The rows must bend back on themselves.
RECTANGLE = [[-30, -21, "c"], [30, -21, "c"], [30, 21, "c"], [-30, 21, "c"]]
BENT_BACK = [[[-21, -21], [21, 21]], [[10.9, -13.0], [27.6, -14.3]]]


def test_a_line_that_bends_the_rows_back_on_themselves_still_fills_the_shape():
    obj = _fill(RECTANGLE, BENT_BACK, underlay=[])
    recs, warnings = generate(obj)
    assert turning.TOO_SHARP in warnings
    assert invariants.coverage(recs, _area(obj), 0.4) >= 0.97
    invariants.assert_sane(recs, inside=_area(obj), tolerance_mm=0.3)


def test_a_sharp_turn_never_lays_rows_on_top_of_each_other():
    # Rows that would loop back across their neighbors are cut where they loop: over the whole
    # shape about a plain fill's thread, and even in the crease where the rows meet no 2 mm
    # square gets 1.8 times it (1.6 as written; 3 times with the loops left in).
    obj = _fill(RECTANGLE, BENT_BACK, underlay=[])
    plain = {**obj, "params": {k: v for k, v in obj["params"].items() if k != "angle_lines"}}
    recs = generate(obj)[0]
    usual = invariants.thread_per_mm2(generate(plain)[0], _area(obj))
    assert invariants.thread_per_mm2(recs, _area(obj)) <= usual * 1.15
    assert invariants.densest_square(recs, _area(obj), 2.0) <= usual * 1.8


def _ragged_side(recs) -> str:
    """Which side of the 50 mm panel has the thinner edge: a feathered one has fewer needle
    points within 1.5 mm of it."""
    xs = [x for x, _ in invariants.stitch_points(recs)]
    left, right = sum(x < 1.5 for x in xs), sum(x > 48.5 for x in xs)
    return "left" if left < right / 2 else "right" if right < left / 2 else "neither"


@pytest.mark.parametrize("turn,side", [({}, "left"), ({"flip_x": True}, "right"), ({"rotate": 180}, "right"),
                                       ({"flip_y": True}, "left")], ids=["as drawn", "mirrored left to right",
                                                                        "turned half round", "mirrored top to bottom"])
def test_a_turning_fills_feathered_side_goes_with_the_shape(turn, side):
    # So the app never swaps left and right on a turning fill (design/layout.ts).
    obj = _fill(PANEL, FAN_LINES, feather="left", feather_mm=4, underlay=[])
    moved = transform_geometry(obj, Transform.from_dict(turn), (25.0, 15.0))
    assert _ragged_side(generate(moved)[0]) == side


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_a_turning_fills_underlay_and_rows_do_not_hang_on_the_last_digit_of_a_sine(seed, monkeypatch):
    # The leaf is the same either side of its middle, so its cross-hatch could start at either
    # of two mirror-image ends.
    cases = {
        "leaf": _fill(LEAF, LEAF_LINES, underlay=["edge", "tatami"], tie_in=True, tie_off=True),
        "panel_by_hand": _fill(PANEL, [_line(12, 15, -30), _line(38, 15, 30)], hand_pct=60, underlay=["tatami"]),
        "bent_back": _fill(RECTANGLE, BENT_BACK, underlay="auto"),  # rows cut where they loop
    }
    forget_stitches()
    plain = {name: digest_recs_steady(generate(obj)[0]) for name, obj in cases.items()}
    forget_stitches()
    try:
        nudge_trig(monkeypatch, seed, stitches, turning, rotations=True)
        for name, obj in cases.items():
            assert digest_recs_steady(generate(obj)[0]) == plain[name], name
    finally:
        monkeypatch.undo()
        forget_stitches()
