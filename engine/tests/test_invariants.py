"""Every digitize snapshot case passes the shared invariants (invariants.py), and each helper in
invariants.py really fails on bad input.

A case that breaks a rule today keeps its stitches: it gets a named exemption below with the looser
limit and the reason. New stitch types start with the strict rules.
"""

import math

import pytest
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

import invariants
from test_digitize import SNAPSHOT_CASES
from threadline_engine.digitize.applique import STOP, AppliqueParams
from threadline_engine.digitize.paths import flatten
from threadline_engine.digitize.stitches import JUMP, STITCH, TRIM, fill_parts, generate

# One connected shape sews without lifting the needle. The other limits are assert_sane's defaults:
# no stitch over 7.15 mm, nothing more than 0.6 mm outside the shape.
STRICT = {"max_jumps": 0, "max_trims": 0}

EXEMPT = {
    "fill_bowtie": ({"max_jumps": 1, "max_trims": 1},
                    "its two lobes only touch at a point: lock off, trim, jump, lock in"),
    "applique_square": ({"max_jumps": 2},
                        "it stops twice (lay the fabric, trim it) and jumps back to the start each time"),
    "applique_with_hole_run_tack": ({"max_jumps": 5, "max_trims": 3},
                                    "it stops between its parts and trims the moves between outline and hole"),
}


def area_of(case):
    """The area a case's stitches must stay in; None for a motif line, which sews beside its line."""
    kind, g, p = case["kind"], case["geometry"], case.get("params") or {}
    if kind in ("fill", "applique"):
        area = unary_union(fill_parts(g["outline"], g.get("holes") or []))
        if kind == "applique":  # the cover satin straddles the cut edge: half its width each way
            area = area.buffer(AppliqueParams.from_dict(p).cover_width_mm / 2, join_style="mitre")
        return area
    if kind == "satin" and "nodes" in g:  # a ribbon: its line, widened
        line = LineString(flatten(g["nodes"], g.get("closed", False))[0])
        return line.buffer(g["width_mm"] / 2, cap_style="flat", join_style="mitre")
    if kind == "satin":  # a column: between its two edges
        return Polygon(flatten(g["rail_a"])[0] + flatten(g["rail_b"])[0][::-1])
    if p.get("style") == "motif":
        return None
    return LineString(flatten(g["nodes"], g.get("closed", False))[0]).buffer(0.01)


def check_case(name, limits):
    case = SNAPSHOT_CASES[name]
    invariants.assert_sane(generate(case)[0], inside=area_of(case), **limits)


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshot_case_is_sane(name):
    looser, _why = EXEMPT.get(name, ({}, ""))
    check_case(name, {**STRICT, **looser})


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshot_case_is_deterministic(name):
    invariants.assert_deterministic(lambda: generate(SNAPSHOT_CASES[name])[0])


@pytest.mark.parametrize("name", sorted(EXEMPT))
def test_each_exemption_has_a_reason_and_is_still_needed(name):
    _looser, why = EXEMPT[name]
    assert name in SNAPSHOT_CASES and why.strip() and "\n" not in why
    with pytest.raises(AssertionError):
        check_case(name, STRICT)


# ---------------------------------------------------------------- the helpers


def rows(ys, x0=0.0, x1=10.0):
    """Separate straight rows of thread, one per y, joined by jumps."""
    return [r for y in ys for r in ((x0, y, JUMP), (x0, y, STITCH), (x1, y, STITCH))]


LINE = [(0.0, 0.0, STITCH), (2.0, 0.0, STITCH), (4.0, 0.0, STITCH)]
SQUARE = box(0, 0, 10, 10)
DONUT = SQUARE.difference(box(4, 4, 6, 6))


def test_stitch_points_and_count():
    recs = [(0, 0, JUMP), (0, 0, STITCH), (3, 4, STITCH), (3, 4, TRIM), (10, 4, JUMP), (10, 4, STOP)]
    assert invariants.stitch_points(recs) == [(0, 0), (3, 4)]
    assert [invariants.count(recs, k) for k in (STITCH, JUMP, TRIM, STOP)] == [2, 2, 1, 1]


def test_longest_stitch_measures_every_move_that_ends_in_a_needle_drop():
    # 5 mm between two stitches, then 9 mm from where a jump landed; the jump itself doesn't count.
    recs = [(0, 0, STITCH), (3, 4, STITCH), (3, 4, TRIM), (50, 4, JUMP), (50, 13, STITCH)]
    assert invariants.longest_stitch(recs) == pytest.approx(9)
    assert invariants.longest_stitch([(0, 0, STITCH), (30, 0, JUMP), (30, 0, STITCH)]) == 0
    assert invariants.longest_stitch([(0, 0, STITCH)]) == 0 and invariants.longest_stitch([]) == 0


def test_assert_sane_passes_good_records():
    invariants.assert_sane(LINE)
    invariants.assert_sane(LINE, inside=box(0, -1, 4, 1), max_stitch_mm=2, max_jumps=0, max_trims=0,
                           starts_near=(0.5, 0), ends_near=(4, 0.9))
    # A stitch just outside the shape is within the tolerance.
    invariants.assert_sane([(5, 5, STITCH), (10.5, 5, STITCH)], inside=SQUARE)


@pytest.mark.parametrize("recs, limits, says", [
    ([], {}, "no stitches"),
    ([(0, 0, JUMP)], {}, "no stitches"),
    ([(0, 0, STITCH), (math.nan, 0, STITCH)], {}, "record 1 is not a number"),
    ([(0, 0, STITCH), (1, math.inf, JUMP)], {}, "record 1 is not a number"),
    ([(0, 0, STITCH), (1, 0, 99)], {}, "unknown command 99 at record 1"),
    ([(0, 0, STITCH), (8, 0, STITCH)], {}, r"longest stitch 8\.00 mm at record 1 \(limit 7\.15 mm\)"),
    (LINE, {"max_stitch_mm": 1.5}, r"longest stitch 2\.00 mm"),
    ([(0, 0, STITCH), (0, 0, JUMP), (1, 0, STITCH)], {"max_jumps": 0}, r"1 jumps \(limit 0\)"),
    ([(0, 0, STITCH), (0, 0, TRIM), (1, 0, STITCH)], {"max_trims": 0}, r"1 trims \(limit 0\)"),
    (LINE, {"starts_near": (3, 0)}, r"starts 3\.00 mm from \(3, 0\)"),
    (LINE, {"ends_near": (0, 0)}, r"ends 4\.00 mm from \(0, 0\)"),
    ([(5, 5, STITCH), (11, 5, STITCH)], {"inside": SQUARE}, r"outside the shape, up to 1\.00 mm out"),
    # Both needle drops are on the donut, but the thread between them crosses its hole.
    ([(3, 5, STITCH), (7, 5, STITCH)], {"inside": DONUT}, r"outside the shape, up to 1\.00 mm out"),
])
def test_assert_sane_fails_with_the_numbers(recs, limits, says):
    with pytest.raises(AssertionError, match=says):
        invariants.assert_sane(recs, **limits)


def test_assert_sane_lists_every_broken_rule():
    recs = [(0, 0, STITCH), (9, 0, STITCH), (9, 0, TRIM)]
    with pytest.raises(AssertionError) as err:
        invariants.assert_sane(recs, max_trims=0, ends_near=(0, 0))
    assert all(words in str(err.value) for words in ("longest stitch 9.00 mm", "1 trims", "ends 9.00 mm"))


def test_assert_deterministic():
    invariants.assert_deterministic(lambda: list(LINE))
    makes = iter([list(LINE), [*LINE[:2], (4.0, 0.001, STITCH)]])
    with pytest.raises(AssertionError, match="not deterministic: record 2"):
        invariants.assert_deterministic(lambda: next(makes))
    makes = iter([list(LINE), LINE[:2]])
    with pytest.raises(AssertionError, match="not deterministic: 3 records, then 2"):
        invariants.assert_deterministic(lambda: next(makes))


@pytest.mark.parametrize("name", ["run_single", "run_motif_blanket_closed", "satin_curved", "satin_ribbon_s_curve",
                                  "fill_contour", "fill_stipple", "applique_square"])
def test_assert_moves_with_shape_passes_stitches_that_move_with_their_shape(name):
    invariants.assert_moves_with_shape(SNAPSHOT_CASES[name], 13.37, -7.11)


def test_assert_moves_with_shape_moves_the_chosen_start_too():
    square = [[0, 0, "c"], [20, 0, "c"], [20, 20, "c"], [0, 20, "c"]]
    obj = {"kind": "run", "geometry": {"nodes": square, "closed": True}, "params": {"start_mm": [20, 20]}}
    invariants.assert_moves_with_shape(obj, 100, 40)
    assert obj["params"]["start_mm"] == [20, 20] and obj["geometry"]["nodes"][2] == [20, 20, "c"]  # not changed


@pytest.mark.parametrize("fake, says", [
    # Stitches that stay where they were.
    (lambda obj: ([(0, 0, STITCH), (1, 0, STITCH)], []), "didn't move with the shape: record 0"),
    # 0.02 mm of drift on the moved copy.
    (lambda obj: ([(obj["geometry"]["nodes"][0][0] * 1.001, 0, STITCH)], []), "didn't move with the shape: record 0"),
    # A different number of stitches.
    (lambda obj: ([(0, 0, STITCH)] * (1 + (obj["geometry"]["nodes"][0][0] > 1)), []),
     "didn't move with the shape: 1 records before, 2 after"),
])
def test_assert_moves_with_shape_fails_when_they_do_not(monkeypatch, fake, says):
    monkeypatch.setattr(invariants, "generate", fake)
    obj = {"kind": "run", "geometry": {"nodes": [[0, 0, "c"], [10, 0, "c"]]}}
    with pytest.raises(AssertionError, match=says):
        invariants.assert_moves_with_shape(obj, 20, 0)


def test_coverage_is_the_share_of_the_shape_within_reach_of_a_stitch_line():
    recs = rows([k + 0.5 for k in range(10)])  # rows 1 mm apart over a 10 mm square
    assert invariants.coverage(recs, SQUARE, 0.5) == pytest.approx(1, abs=0.001)
    assert invariants.coverage(recs, SQUARE, 0.25) == pytest.approx(0.5, abs=0.001)
    assert invariants.coverage(rows([0.5]), SQUARE, 0.5) == pytest.approx(0.1, abs=0.001)


def test_coverage_counts_thread_not_jumps():
    assert invariants.coverage([(0, 5, STITCH), (10, 5, JUMP)], SQUARE, 1) == 0
    assert invariants.coverage([(5, 5, STITCH)], SQUARE, 1) == 0  # one needle drop lays no thread


def test_thread_per_mm2_counts_every_pass_inside_the_shape():
    assert invariants.thread_per_mm2(rows([k + 0.5 for k in range(10)]), SQUARE) == pytest.approx(1)
    bean = [(0, 5, STITCH), (10, 5, STITCH), (0, 5, STITCH), (10, 5, STITCH)]  # three passes, same line
    assert invariants.thread_per_mm2(bean, SQUARE) == pytest.approx(0.3)
    assert invariants.thread_per_mm2([(-5, 5, STITCH), (15, 5, STITCH)], SQUARE) == pytest.approx(0.1)
    assert invariants.thread_per_mm2([(0, 5, STITCH), (10, 5, JUMP)], SQUARE) == 0
