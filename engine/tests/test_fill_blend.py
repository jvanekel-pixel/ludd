"""Blend fills: the shape's color fades into a second (and a third) across the rows, each color its
own rows in its own thread (digitize/fills/blend.py, Phase 6 C1)."""

import json
import math
from collections import Counter

import pytest
from shapely.ops import unary_union

import invariants
from snapshot_util import SNAPSHOT_DIR, check, digest_recs_steady
from steady_util import forget_stitches, nudge_trig
from threadline_engine import layout, project
from threadline_engine.digitize import fills, stitches
from threadline_engine.digitize.fills import blend
from threadline_engine.digitize.stitches import STITCH, FillParams, fill_parts, generate, generate_parts

SIDE = 40.0
SPACING = 0.4  # the standard fill density: 100 rows across the square
BANDS = 5


def _nodes(points):
    return [[x, y, "c"] for x, y in points]


SQUARE = _nodes([(0, 0), (SIDE, 0), (SIDE, SIDE), (0, SIDE)])
HOLE = _nodes([(14, 14), (26, 14), (26, 26), (14, 26)])
BOWTIE = _nodes([(0, 0), (30, 30), (30, 0), (0, 30)])  # crosses itself: two pieces


def _thread(color):
    return {"color": color, "name": color, "catalog": "", "brand": ""}


RED, BLUE, GOLD = _thread("#cc2222"), _thread("#2222cc"), _thread("#ccaa22")


def _blend(outline=SQUARE, holes=(), others=(BLUE,), **params):
    """A blend fill with rows across (angle 0, so the turned frame is the design's), no underlay
    and no locks unless asked: rows are then easy to find."""
    p = {"pattern": "blend", "angle_deg": 0, "spacing_mm": SPACING, "underlay": [], "tie_in": False,
         "tie_off": False, "blend": [dict(t) for t in others], **params}
    return {"kind": "fill", "geometry": {"outline": outline, "holes": list(holes)}, "thread": dict(RED), "params": p}


def _area(obj):
    g = obj["geometry"]
    return unary_union(fill_parts(g["outline"], g.get("holes") or []))


def _row_heights(recs, axis=1):
    """The rows in a part's records: heights where three or more needle drops line up across."""
    seen = Counter(round(r[axis], 4) for r in recs if r[2] == STITCH)
    return sorted(y for y, n in seen.items() if n >= 3)


def _rows_by_part(obj):
    return [_row_heights(recs) for recs, _, _ in generate_parts(obj)]


def _bands(ys, lo=0.0, hi=SIDE, bands=BANDS):
    width = (hi - lo) / bands
    out = [0] * bands
    for y in ys:
        out[min(bands - 1, int((y - lo) // width))] += 1
    return out


def test_registered_as_a_rows_pattern_with_parts():
    spec = fills.get("blend")
    assert spec.kind == "rows" and spec.parts is not None and not spec.tatami_underlay
    assert FillParams.from_dict({"pattern": "blend", "underlay": "auto"}).underlay == ()


def test_two_parts_in_two_threads():
    parts = generate_parts(_blend())
    assert [slot for _, _, slot in parts] == [0, 1]
    r = layout.render({"items": [{"id": "a", **_blend()}]})
    assert [b.thread["color"] for b in r.blocks] == ["#cc2222", "#2222cc"]
    assert [b.sources for b in r.blocks] == [[(0, 0)], [(0, 1)]]


def _one_color_rows():
    return _row_heights(generate({**_blend(), "params": {**_blend()["params"], "pattern": "tatami", "blend": []}})[0])


def test_combined_density_is_even(capsys):
    """Done-when 2: both colors' rows together, band by band, as many as one color's would be."""
    plain = _bands(_one_color_rows())
    rows = _rows_by_part(_blend())
    both = _bands(rows[0] + rows[1])
    worst = max(abs(b - p) / p for b, p in zip(both, plain))
    with capsys.disabled():
        print(f"\nblend rows per band {both}, one color {plain}, worst {worst:.1%}")
    assert worst <= 0.15, (both, plain)


@pytest.mark.parametrize("scale", [0.6, 2.0])
def test_combined_density_holds_on_a_resized_shape(scale):
    """Spacing is a length: on a shape resized with the handles, the blend keeps the density a one
    color fill of the same size has. Through the whole layout, as the app renders it."""
    def rows(params, slot):
        item = {"id": "a", **_blend(), "transform": {"scale_x": scale, "scale_y": scale}}
        item["params"] = {**item["params"], **params}
        blocks = layout.render({"items": [item]}).blocks
        return [y / 10 for b in blocks for y in _row_heights(b.recs) if b.sources[0][1] == slot or slot is None]

    lo, hi = SIDE / 2 - SIDE * scale / 2, SIDE / 2 + SIDE * scale / 2
    plain = _bands(rows({"pattern": "tatami", "blend": []}, None), lo, hi)
    both = _bands(rows({}, None), lo, hi)
    assert sum(plain) == pytest.approx(SIDE * scale / SPACING, abs=1)
    assert max(abs(b - p) / p for b, p in zip(both, plain)) <= 0.15, (both, plain)
    first, second = _bands(rows({}, 0), lo, hi), _bands(rows({}, 1), lo, hi)
    assert first[0] > first[-1] and second[0] < second[-1]


def test_each_color_fades_the_right_way():
    first, second = (_bands(ys) for ys in _rows_by_part(_blend()))
    assert all(a > b for a, b in zip(first, first[1:])), first
    assert all(a < b for a, b in zip(second, second[1:])), second


def test_flip_runs_the_colors_the_other_way():
    rows = _rows_by_part(_blend())
    flipped = _rows_by_part(_blend(blend_flip=True))
    for ys, fs in zip(rows, flipped):
        assert _bands(fs) == _bands(ys)[::-1]
    first = _bands(flipped[0])
    assert all(a < b for a, b in zip(first, first[1:])), first


def _meeting(rows):
    """Where color 2 first has more rows than color 1, as one of ten bands."""
    first, second = (_bands(ys, bands=10) for ys in rows)
    return next(k for k in range(10) if second[k] > first[k])


def test_balance_shifts_the_meeting_point():
    middle = _rows_by_part(_blend())
    more_second = _rows_by_part(_blend(blend_balance=0.8))
    more_first = _rows_by_part(_blend(blend_balance=-0.8))
    assert _meeting(more_second) < _meeting(middle) < _meeting(more_first)
    assert len(more_second[1]) > len(middle[1]) > len(more_first[1])
    assert len(more_second[0]) < len(middle[0]) < len(more_first[0])


def test_balance_is_checked():
    with pytest.raises(stitches.DigitizeError, match="Balance must be between -1 and 1"):
        generate(_blend(blend_balance=1.5))


def test_three_colors_peak_at_start_middle_end():
    rows = _rows_by_part(_blend(others=(BLUE, GOLD)))
    assert len(rows) == 3
    peaks = [max(range(BANDS), key=lambda k: _bands(ys)[k]) for ys in rows]
    assert peaks == [0, 2, 4]
    plain = _bands(_one_color_rows())
    both = _bands([y for ys in rows for y in ys])
    assert max(abs(b - p) / p for b, p in zip(both, plain)) <= 0.15, (both, plain)
    r = layout.render({"items": [{"id": "a", **_blend(others=(BLUE, GOLD))}]})
    assert [b.thread["color"] for b in r.blocks] == ["#cc2222", "#2222cc", "#ccaa22"]


def _all_heights_cases():
    for colors in (1, 2, 3, 4):
        for balance in (-1.0, -0.3, 0.0, 0.6, 1.0):
            for spacing in (0.2, 0.4, 0.75, 1.5, 3.0):
                for size in (3.0, 10.0, 40.0, 41.6, 100.0):
                    for flip in (False, True):
                        yield colors, balance, spacing, size, flip


def _heights(colors, balance, spacing, size, flip, miny=-7.0):
    params = FillParams.from_dict({"pattern": "blend", "spacing_mm": spacing, "blend_balance": balance,
                                   "blend": [dict(BLUE)] * (colors - 1), "blend_flip": flip})
    return blend.row_heights(miny, miny + size, params, colors)


def test_rows_never_coincide():
    """No two rows of different colors within 0.14 mm, for any number of colors, balance, density
    or size; and every row lies inside the shape's height, each color's lowest first."""
    for colors, balance, spacing, size, flip in _all_heights_cases():
        rows = _heights(colors, balance, spacing, size, flip)
        assert len(rows) == colors
        tagged = sorted((y, c) for c, ys in enumerate(rows) for y in ys)
        for (y0, c0), (y1, c1) in zip(tagged, tagged[1:]):
            assert c0 == c1 or y1 - y0 >= 0.14, (colors, balance, spacing, size, flip, y0, y1)
        for ys in rows:
            assert ys == sorted(ys) and all(-7.0 < y < -7.0 + size for y in ys)
    rows = _rows_by_part(_blend())
    tagged = sorted((y, c) for c, ys in enumerate(rows) for y in ys)
    assert all(c0 == c1 or y1 - y0 >= 0.14 for (y0, c0), (y1, c1) in zip(tagged, tagged[1:]))


def test_no_lone_rows():
    """Every row of a color has another of that color within 4 mm (a lone thread across the other
    color would show)."""
    found_sparse = False
    for colors, balance, spacing, size, flip in _all_heights_cases():
        rows = _heights(colors, balance, spacing, size, flip)
        assert any(rows), (colors, balance, spacing, size, flip)  # never an empty shape
        if sum(1 for ys in rows if ys) < 2:
            continue  # one color alone (or a shape too small to blend): no other color to cross
        for ys in rows:
            if len(ys) == 1:
                raise AssertionError((colors, balance, spacing, size, flip, ys))
            for i, y in enumerate(ys):
                gaps = [abs(y - ys[j]) for j in (i - 1, i + 1) if 0 <= j < len(ys)]
                assert min(gaps) <= 4.0 + 1e-9, (colors, balance, spacing, size, flip, y)
                found_sparse |= min(gaps) > 3.0
    assert found_sparse  # the cases do reach rows nearly far enough apart to drop
    for ys in _rows_by_part(_blend(spacing_mm=1.5)):
        assert all(min(abs(y - z) for z in ys if z != y) <= 4.0 for y in ys)


def test_a_lone_row_is_dropped():
    """At a wide spacing the first rows of the second color lie far apart: those more than 4 mm
    from any other are left out rather than sewn as a lone thread."""
    params = FillParams.from_dict({"pattern": "blend", "spacing_mm": 1.0, "blend": [dict(BLUE)]})
    second = blend.row_heights(0.0, 40.0, params, 2)[1]
    assert second[0] > blend.fade_heights(0.0, 40.0, params, 2)[1][0]


def test_swap_reverses():
    """Swapping the colors (as the panel does: the threads in the other order, the balance
    negated) mirrors the blend: at balance 0 each thread's rows are the mirror image of where they
    were; with a balance each color keeps the share of the shape it had."""
    ab, ba = _rows_by_part(_blend()), _rows_by_part({**_blend(others=(RED,)), "thread": dict(BLUE)})
    for ours, theirs in ((ab[0], ba[1]), (ab[1], ba[0])):
        # Rows moved apart from another color's (by up to 0.15 mm) move up, whichever way the fade runs.
        assert all(min(abs(SIDE - y - z) for z in theirs) <= 0.16 for y in ours)
        assert abs(len(ours) - len(theirs)) <= 1
    tilted = _rows_by_part(_blend(blend_balance=0.6))
    swapped = _rows_by_part({**_blend(others=(RED,), blend_balance=-0.6), "thread": dict(BLUE)})
    assert abs(len(tilted[0]) - len(swapped[1])) <= 1 and abs(len(tilted[1]) - len(swapped[0])) <= 1


def test_color_sort_keeps_the_two_parts_in_order():
    """With "sew each color once" on, the blend's second color doesn't jump ahead of its first to
    join a shape in that color sewn earlier."""
    blue_square = {"id": "b", "kind": "fill", "geometry": {"outline": _nodes([(60, 0), (80, 0), (80, 20), (60, 20)])},
                   "thread": dict(BLUE), "params": {"underlay": []}}
    item = {"id": "a", **_blend()}
    r = layout.render({"items": [blue_square, item], "color_sort": True})
    order = [(b.sources[0], b.thread["color"]) for b in r.blocks]
    assert [s for s, _ in order] == [(0, 0), (1, 0), (1, 1)]
    # A red shape after the blend may join the blend's red, but never ahead of it.
    red_after = {**blue_square, "id": "c", "thread": dict(RED)}
    r = layout.render({"items": [item, red_after], "color_sort": True})
    srcs = [s for b in r.blocks for s in b.sources]
    assert srcs.index((0, 0)) < srcs.index((0, 1))


def test_order_and_colors_can_recolor_each_part():
    item = {"id": "a", **_blend(), "threads": [None, _thread("#00cc00")]}
    r = layout.render({"items": [item]})
    assert [b.thread["color"] for b in r.blocks] == ["#cc2222", "#00cc00"]


def test_one_color_still_sews_and_says_what_to_do():
    obj = _blend(others=())
    parts = generate_parts(obj)
    assert [slot for _, _, slot in parts] == [0]
    assert blend.ONE_COLOR in parts[0][1]
    plain = _one_color_rows()
    assert _rows_by_part(obj)[0] == pytest.approx(plain)


def test_a_shape_in_pieces_fades_once_across_all_of_them():
    """Two pieces side by side across the fade: the fade runs over both together, so the second
    color's rows are not restarted in each piece."""
    obj = _blend(BOWTIE, angle_deg=90)
    parts = generate_parts(obj)
    assert [slot for _, _, slot in parts] == [0, 1]
    first = _row_heights(parts[0][0], axis=0)
    second = _row_heights(parts[1][0], axis=0)
    # In the turned frame (90 degrees) rows run up the shape and the fade runs across x, from
    # x = 30 back to 0 (the turned frame's y is -x).
    assert sum(1 for x in first if x > 15) > sum(1 for x in first if x < 15)
    assert sum(1 for x in second if x < 15) > sum(1 for x in second if x > 15)
    for recs, _, _ in parts:
        invariants.assert_sane(recs, inside=_area(obj), tolerance_mm=0.4)


def test_holes_stay_empty_and_both_colors_sew_round_them():
    obj = _blend(holes=[HOLE])
    for recs, _, _ in generate_parts(obj):
        invariants.assert_sane(recs, inside=_area(obj), tolerance_mm=0.4)


def test_an_edge_run_is_sewn_in_the_first_color_only():
    obj = _blend(underlay=["edge", "tatami"])
    first, second = generate_parts(obj)
    plain_first, plain_second = generate_parts(_blend())
    assert len(first[0]) > len(plain_first[0])
    assert second[0] == plain_second[0]


def test_start_and_end_points():
    obj = _blend(start_mm=[0, 0], end_mm=[SIDE, SIDE])
    parts = generate_parts(obj)
    first, last = parts[0][0], parts[-1][0]
    assert math.dist(first[0][:2], (0, 0)) <= 2.0
    assert math.dist(invariants.stitch_points(last)[-1], (SIDE, SIDE)) <= 1.0


def test_reverse_sews_each_color_from_the_other_end():
    plain, back = generate_parts(_blend()), generate_parts(_blend(reverse=True))
    for (a, _, _), (b, _, _) in zip(plain, back):
        assert a != b and sorted(a) == sorted(b)


def test_weave_applies_to_each_color():
    plain, twill = _rows_by_part(_blend()), _rows_by_part(_blend(weave="twill"))
    assert plain == twill  # the same rows
    assert generate_parts(_blend())[0][0] != generate_parts(_blend(weave="twill"))[0][0]  # other needle points


@pytest.mark.parametrize("name", ["two_colors", "three_colors", "holes"])
def test_invariants(name):
    obj = {"two_colors": _blend(angle_deg=30), "three_colors": _blend(others=(BLUE, GOLD), angle_deg=-60),
           "holes": _blend(holes=[HOLE], angle_deg=45, underlay="auto")}[name]
    recs = generate(obj)[0]
    invariants.assert_sane(recs, inside=_area(obj), tolerance_mm=0.4)
    invariants.assert_deterministic(lambda: generate(obj)[0])
    for dx, dy in [(10, -7.5), (0.1234, 33.333), (-250.7, 100.9)]:
        invariants.assert_moves_with_shape(obj, dx, dy)
    assert invariants.coverage(recs, _area(obj), 0.6) >= 0.97


def test_project_names_the_feature():
    assert "fill_blend" in project._features({"items": [_blend()]})


SNAPSHOT_CASES = {
    "two_colors": _blend(angle_deg=45, underlay="auto", tie_in=True, tie_off=True),
    "three_colors": _blend(others=(BLUE, GOLD), angle_deg=20, underlay="auto"),
    "balance_0_6": _blend(blend_balance=0.6, angle_deg=-30),
    "blend_twill": _blend(weave="twill", angle_deg=60, holes=[HOLE]),
}


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshots(name):
    check("fill_blend", name, digest_recs_steady(generate(SNAPSHOT_CASES[name])[0]))


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_snapshots_do_not_hang_on_the_last_digit_of_a_sine(seed, monkeypatch):
    path = SNAPSHOT_DIR / "fill_blend.json"
    if not path.exists():
        pytest.skip("snapshots not recorded yet")
    recorded = json.loads(path.read_text(encoding="utf-8"))
    forget_stitches()
    try:
        nudge_trig(monkeypatch, seed, stitches, rotations=True)
        for name in sorted(SNAPSHOT_CASES):
            assert digest_recs_steady(generate(SNAPSHOT_CASES[name])[0]) == recorded[name], name
    finally:
        monkeypatch.undo()
        forget_stitches()
