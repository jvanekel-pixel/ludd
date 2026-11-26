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


def _plain(obj):
    """The same object as a one-color tatami fill."""
    return {**obj, "params": {**obj["params"], "pattern": "tatami", "blend": []}}


def _one_color_rows(obj=None, axis=1):
    return _row_heights(generate(_plain(obj or _blend()))[0], axis)


DENSITY_CASES = {"two colors": {}, "three colors": {"others": (BLUE, GOLD)},
                 "balance +0.8": {"blend_balance": 0.8}, "balance -0.8": {"blend_balance": -0.8},
                 "flipped two colors": {"blend_flip": True},
                 "flipped three colors": {"others": (BLUE, GOLD), "blend_flip": True},
                 "flipped balance +0.8": {"blend_balance": 0.8, "blend_flip": True},
                 "flipped balance -0.8": {"blend_balance": -0.8, "blend_flip": True},
                 "flipped four colors +0.8": {"others": (BLUE, GOLD, RED), "blend_balance": 0.8, "blend_flip": True}}


@pytest.mark.parametrize("spacing", [0.4, 0.8, 1.5, 3.0])
@pytest.mark.parametrize("case", sorted(DENSITY_CASES))
def test_combined_density_is_even(case, spacing, capsys):
    """Done-when 2: all the colors' rows together, band by band, as many as one color's would be;
    and no two neighbouring rows (of any colors) closer or further apart than the spacing allows:
    no pairs piled up, no stripes of bare fabric. The colors are all sewn, with no warning."""
    obj = _blend(spacing_mm=spacing, **DENSITY_CASES[case])
    plain_rows = _one_color_rows(obj)
    plain = _bands(plain_rows)
    parts = generate_parts(obj)
    rows = [_row_heights(recs) for recs, _, _ in parts]
    together = sorted(y for ys in rows for y in ys)
    both = _bands(together)
    worst = max(abs(b - p) / p for b, p in zip(both, plain))
    gaps = [(b - a) / spacing for a, b in zip(together, together[1:])]
    with capsys.disabled():
        print(f"\nblend {case} at {spacing} mm: rows per band {both}, one color {plain}, worst {worst:.1%}, "
              f"gaps {min(gaps):.3f} to {max(gaps):.3f} x spacing, rows per color {[len(ys) for ys in rows]}")
    assert worst <= 0.15, (both, plain)
    assert 0.8 <= min(gaps) and max(gaps) <= 1.2, (min(gaps), max(gaps))
    assert together == plain_rows  # exactly the one-color fill's rows
    assert [slot for _, _, slot in parts] == list(range(len(rows))) and all(rows)
    assert not any(w.startswith("This shape has too few rows") for _, said, _ in parts for w in said)


def test_no_bare_band_at_a_wide_spacing():
    """A 40 mm square at 2.5 mm: all 16 rows of a one-color fill are sewn, shared by the two
    colors, with no band of bare fabric between them."""
    obj = _blend(spacing_mm=2.5)
    rows = _rows_by_part(obj)
    together = sorted(rows[0] + rows[1])
    assert len(together) == 16 and together == _one_color_rows(obj)
    assert max(b - a for a, b in zip(together, together[1:])) == pytest.approx(2.5)
    assert together[0] == pytest.approx(1.25) and SIDE - together[-1] == pytest.approx(1.25)
    assert all(_bands(together)) and len(rows[0]) >= 2 and len(rows[1]) >= 2


@pytest.mark.parametrize("extra", [{}, {"weave": "twill"}, {"carve": True}, {"feather": "both"},
                                   {"hand_pct": 100}, {"reverse": True}, {"others": (BLUE, GOLD), "spacing_mm": 1.5}])
def test_rows_are_the_one_color_fills_rows(extra, monkeypatch):
    """Every row of a one-color fill, and no other, in a shape of two pieces (each piece's rows
    start half a row in from its own edge) and in a square with a hole; with each of the rows
    settings and Reverse. The rows are read where tatami() lays them out (both shapes start at the
    origin, so the blend's move to the origin changes nothing)."""
    seen = []
    original = stitches._rows

    def spy(poly, angle, spacing, extend, ys=None):
        rows = original(poly, angle, spacing, extend, ys)
        if ys is None:  # a one-color fill: tatami's own heights, half a row in, then a spacing apart
            ys, y = [], poly.bounds[1] + spacing / 2
            while y < poly.bounds[3]:
                ys.append(y)
                y += spacing
        seen.extend(round(y, 9) for y, segs in zip(ys, rows) if segs)
        return rows

    monkeypatch.setattr(stitches, "_rows", spy)
    extra = dict(extra)
    carve = extra.pop("carve", False)
    for obj in (_blend(BOWTIE, angle_deg=90, **extra), _blend(holes=[HOLE], **extra)):
        if carve:
            obj["geometry"]["carve"] = [_nodes([(3, 10), (27, 20)])]
        seen.clear()
        forget_stitches()  # nothing from a cache: every row is laid out here
        parts = generate_parts(obj)
        together = sorted(seen)
        seen.clear()
        forget_stitches()
        generate(_plain(obj))
        assert together == sorted(seen) and len(together) >= 15, extra
        assert len(parts) == 1 + len(obj["params"]["blend"])


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
        # Together, exactly a one-color fill's rows (or, too thin for one, a row across the middle).
        plain = blend.plain_rows(-7.0, -7.0 + size, spacing) or [-7.0 + size / 2]
        assert sorted(y for ys in rows for y in ys) == plain
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


def test_a_color_keeps_its_turn_for_two_rows():
    """Where a color's rows are far apart (the thin end of its fade), a row more than 4 mm from its
    color's last one (or its color's first) is never sewn alone: the next row is its color too.
    The other color is not starved: all the one-color fill's rows are still sewn."""
    held = 0
    for spacing in (1.0, 1.5, 2.5, 3.0):
        for colors in (2, 3):
            params = FillParams.from_dict({"pattern": "blend", "spacing_mm": spacing, "blend": [dict(BLUE)] * (colors - 1)})
            ys = blend.plain_rows(0.0, 40.0, spacing)
            owners = blend.assign(ys, params, colors, 0.0, 40.0)
            last = {}
            for i, (y, c) in enumerate(zip(ys, owners)):
                if c not in last or y - last[c] > blend.LONE_MM + 1e-9:
                    assert i + 1 < len(ys) and owners[i + 1] == c, (spacing, colors, i, owners)
                    held += c != owners[i - 1] if i else 1
                last[c] = y
            assert set(owners) == set(range(colors)), (spacing, colors, owners)
    assert held >= 10


def test_every_color_is_sewn_when_there_is_room():
    """With at least two rows per color, every color is sewn (at least a pair), for any Balance,
    2 to 4 colors, either way round; each run of a color starts where that color has weight, or
    at most 4 rows from it (a color whose weight lies only in the last rows, squeezed in among
    the others); and below the 4 mm a lone row would need, no color is ever a lone row."""
    for colors in (2, 3, 4):
        for spacing in (0.4, 1.0, 1.5, 3.0, 5.0):
            for b10 in range(-10, 11, 2):
                for flip in (False, True):
                    params = FillParams.from_dict({"pattern": "blend", "spacing_mm": spacing, "blend_balance": b10 / 10,
                                                   "blend": [dict(BLUE)] * (colors - 1), "blend_flip": flip})
                    gamma = 2.0 ** (-b10 / 10)
                    for n in range(2 * colors, 41):
                        hi = n * spacing
                        ys = blend.plain_rows(0.0, hi, spacing)
                        owners = blend.assign(ys, params, colors, 0.0, hi)
                        case = (colors, spacing, b10 / 10, flip, n, owners)
                        assert len(ys) == n and all(owners.count(c) >= 2 for c in range(colors)), case
                        w = [blend._whole_weights(((hi - y) if flip else y) / hi, gamma, colors) for y in ys]
                        for i, c in enumerate(owners):
                            if i == 0 or owners[i - 1] != c:
                                assert min(abs(j - i) for j in range(n) if w[j][c] > 0) <= 4, (case, i)
                                if spacing <= blend.LONE_MM:
                                    prev = [j for j in range(i) if owners[j] == c]
                                    if not prev or ys[i] - ys[prev[-1]] > blend.LONE_MM + 1e-9:
                                        assert i + 1 < n and owners[i + 1] == c, (case, i)
    params = FillParams.from_dict({"pattern": "blend", "spacing_mm": 1.0, "blend_balance": 0.8,
                                   "blend": [dict(BLUE)] * 3, "blend_flip": True})
    owners = blend.assign(blend.plain_rows(0.0, 40.0, 1.0), params, 4, 0.0, 40.0)
    assert [owners.count(c) for c in range(4)] == [2, 10, 16, 12] and owners[-3:] in ([0, 0, 1], [1, 0, 0])


def test_too_few_rows_says_so():
    """A shape with too few rows for every color sews the colors it can, and says which one it
    left out and what to do; one with enough rows says nothing."""
    small = _blend(_nodes([(0, 0), (20, 0), (20, 10), (0, 10)]), spacing_mm=3.0)
    parts = generate_parts(small)
    assert [slot for _, _, slot in parts] == [0]
    assert blend.too_few([1]) in parts[0][1]
    assert blend.too_few([1]) == ("This shape has too few rows to blend all its colors, so the second color is "
                                  "not sewn. Make the shape bigger or lower the spacing (a smaller number) to "
                                  "fit more rows.")
    assert "the second color and the third color" in blend.too_few([1, 2])
    assert not any(w.startswith("This shape has too few rows") for w in generate_parts(_blend(spacing_mm=3.0))[0][1])


def test_ties_go_to_the_lower_thread_slot():
    """Equal tallies (equal weights, from the first row) give the row to the color in the lower
    thread slot, so the same design sews the same on every computer."""
    params = FillParams.from_dict({"pattern": "blend", "spacing_mm": 0.4, "blend": [dict(BLUE)]})
    assert blend.assign([5.0, 5.2, 5.4, 5.6], params, 2, 0.0, 10.0)[0] == 0  # weights 1/2 and 1/2
    flipped = FillParams.from_dict({"pattern": "blend", "spacing_mm": 0.4, "blend": [dict(BLUE)], "blend_flip": True})
    assert blend.assign([5.0, 5.2, 5.4, 5.6], flipped, 2, 0.0, 10.0)[0] == 0
    assert blend._whole_weights(0.5, 1.0, 2) == [500000, 500000]
    assert all(sum(blend._whole_weights(t / 97, g, n)) == 1_000_000 for t in range(98) for g in (0.5, 1, 2) for n in (2, 3, 4))


def test_swap_reverses():
    """Swapping the colors (as the panel does: the threads in the other order, the balance
    negated) mirrors the blend: at balance 0 each thread's rows, band by band, are the mirror image
    of where they were (rows are given out lowest first, so row by row they can differ by a few);
    together they are still every row of the fill. With a balance each color keeps the share of the
    shape it had."""
    ab, ba = _rows_by_part(_blend()), _rows_by_part({**_blend(others=(RED,)), "thread": dict(BLUE)})
    for ours, theirs in ((ab[0], ba[1]), (ab[1], ba[0])):
        mirrored = sorted(round(SIDE - y, 4) for y in ours)
        assert _bands(mirrored, bands=10) == _bands(theirs, bands=10)
        assert len(set(mirrored) ^ set(theirs)) <= 10  # rows off their mirror image (of 100)
        assert abs(len(ours) - len(theirs)) <= 1
    assert sorted(ba[0] + ba[1]) == sorted(ab[0] + ab[1])
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
