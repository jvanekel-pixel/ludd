"""Lock stitches in three shapes (digitize/ties.py): standard (the ties LUDD has always sewn),
triangle and back-tack."""

import json
import math

import pytest
from shapely.geometry import LineString, Point as ShapelyPoint, box

import invariants
from snapshot_util import SNAPSHOT_DIR, check, digest_recs_steady
from steady_util import forget_stitches, nudge_trig
from threadline_engine import layout
from threadline_engine.digitize import stitches as dz
from threadline_engine.digitize import ties
from threadline_engine.digitize.applique import STOP
from threadline_engine.digitize.stitches import JUMP, STITCH, TRIM, DigitizeError, fill_parts, generate

STYLES = ("standard", "triangle", "backtack")


def c(x, y):
    return [x, y, "c"]


LINE = {"kind": "run", "geometry": {"nodes": [c(0, 0), c(10, 0)]}, "params": {}}
SATIN = {"kind": "satin", "geometry": {"nodes": [c(0, 0), c(20, 0)], "width_mm": 4}, "params": {}}
FILL = {"kind": "fill", "geometry": {"outline": [c(0, 0), c(15, 0), c(15, 10), c(0, 10)]}, "params": {}}
APPLIQUE = {"kind": "applique", "geometry": {"outline": [c(0, 0), c(20, 0), c(20, 20), c(0, 20)]}, "params": {}}


def _with(obj, **params):
    return {**obj, "params": {**obj["params"], **params}}


def _points(recs):
    return [(round(x, 6), round(y, 6)) for x, y, k in recs if k == STITCH]


# Records ending in a trim and a jump, as a fill of several pieces or a French knot can.
TRAILING = [(0.0, 0.0, STITCH), (2.0, 0.0, STITCH), (4.0, 1.0, STITCH), (4.0, 1.0, TRIM), (10.0, 0.0, JUMP)]
SAMPLES = [TRAILING, TRAILING[:3], [(1.0, 1.0, JUMP), (0.0, 0.0, STITCH), (0.2, 0.1, STITCH), (5.0, 0.0, STITCH)],
           [(0.0, 0.0, STITCH)], []]


def test_standard_equals_the_old_ties():
    for recs in SAMPLES:
        assert ties.tie_in(list(recs), "standard") == dz.tie_in(list(recs))
        assert ties.tie_off(list(recs), "standard") == dz.tie_off(list(recs))
    for obj in (LINE, SATIN, FILL):
        assert generate(_with(obj, tie_style="standard")) == generate(obj)
        assert generate(_with(obj, tie_style="")) == generate(obj) == generate(_with(obj, tie_style=None))


def test_triangle_returns_to_the_start():
    pts = _points(generate(_with(LINE, tie_style="triangle"))[0])
    assert pts[:5] == [(0, 0), (0.6, 0), (0.3, 0.52), (0, 0), (2.5, 0)]
    # At the end it is mirrored: the lock goes back toward the stitch before.
    assert pts[-4:] == [(10, 0), (9.4, 0), (9.7, -0.52), (10, 0)]
    for a, b in zip(pts[:4], pts[1:4]):
        assert math.dist(a, b) >= dz.MIN_STITCH_MM


def test_backtack_goes_back_and_forth_twice():
    pts = _points(generate(_with(LINE, tie_style="backtack"))[0])
    assert pts[:6] == [(0, 0), (1, 0), (0, 0), (1, 0), (0, 0), (2.5, 0)]
    assert pts[-5:] == [(10, 0), (9, 0), (10, 0), (9, 0), (10, 0)]
    # On a short first stitch it reaches 80% of it, never less than a stitch.
    for length, reach in [(0.8, 0.64), (0.35, 0.3)]:
        got = _points(ties.tie_in([(0.0, 0.0, STITCH), (length, 0.0, STITCH)], "backtack"))
        assert got == [(0, 0), (reach, 0), (0, 0), (reach, 0), (0, 0), (length, 0)]


@pytest.mark.parametrize("style", STYLES)
def test_lock_goes_before_a_trailing_trim(style):
    out = ties.tie_off(list(TRAILING), style)
    assert out[-2:] == TRAILING[-2:]  # the trim and the jump stay last
    lock = out[2:-2]
    assert lock[0] == TRAILING[2] and all(r[2] == STITCH for r in lock)
    assert lock[-1][:2] == pytest.approx((4.0, 1.0))
    assert all(math.dist(a[:2], b[:2]) >= dz.MIN_STITCH_MM - 1e-9 for a, b in zip(lock, lock[1:]))


@pytest.mark.parametrize("style", ["triangle", "backtack"])
@pytest.mark.parametrize("obj", [LINE, SATIN, FILL], ids=["run", "satin", "fill"])
def test_only_the_locks_change(obj, style):
    plain = generate(_with(obj, tie_in=False, tie_off=False))[0]
    tied = generate(_with(obj, tie_style=style))[0]
    assert tied != generate(obj)[0]
    extra = 3 if style == "triangle" else 4
    assert len(tied) == len(plain) + 2 * extra
    assert tied[0] == plain[0] and tied[1 + extra : -extra - 1] == plain[1:-1] and tied[-1] == plain[-1]
    # With a lock box unticked, only the other end is locked.
    assert generate(_with(obj, tie_style=style, tie_off=False))[0] == tied[: -extra]
    assert generate(_with(obj, tie_style=style, tie_in=False, tie_off=False))[0] == plain


def test_unknown_tie_style_is_refused():
    for obj in (LINE, SATIN, FILL):
        with pytest.raises(DigitizeError, match="^Unknown lock stitch style: zigzag$"):
            generate(_with(obj, tie_style="zigzag"))
    with pytest.raises(layout.LayoutError, match="Unknown lock stitch style: zigzag"):
        layout.render({"items": [{**_with(LINE, tie_style="zigzag"), "id": "a"}]})


def test_appliques_keep_the_standard_locks():
    for style in ("triangle", "backtack", "zigzag"):
        assert generate(_with(APPLIQUE, tie_style=style)) == generate(APPLIQUE)
    assert any(r[2] == STOP for r in generate(APPLIQUE)[0])


def test_lettering_keeps_the_standard_locks():
    from threadline_engine import lettering

    outline = [f for f in lettering.list_fonts() if f.get("kind") == "outline" and not f.get("symbol")]
    if not outline:
        pytest.skip("no installed font to try lettering with")
    text = {"id": "t", "kind": "text", "text": "Ao", "font": outline[0], "size_mm": 15, "style": "satin"}
    plain = layout.render({"items": [text]}).pattern.stitches
    shaped = {**text, "tie_style": "backtack", "params": {"tie_style": "backtack"}}
    assert layout.render({"items": [shaped]}).pattern.stitches == plain


def test_the_pieces_joined_inside_one_fill_keep_the_standard_locks():
    # An outline that crosses itself gives two pieces, locked off and on again where they join.
    bowtie = {"kind": "fill", "geometry": {"outline": [c(0, 0), c(20, 20), c(20, 0), c(0, 20)]}, "params": {}}
    assert len(fill_parts(bowtie["geometry"]["outline"])) == 2
    plain = generate(bowtie)[0]
    shaped = generate(_with(bowtie, tie_style="backtack"))[0]
    inner = lambda recs, extra: recs[1 + extra : -extra - 1]  # noqa: E731
    assert inner(shaped, 4) == inner(plain, 2)


@pytest.mark.parametrize("style", ["triangle", "backtack"])
def test_a_design_resized_with_the_handles_keeps_the_locks_in_mm(style):
    item = {**_with(LINE, tie_style=style, stitch_mm=2.5), "id": "a", "transform": {"scale_x": 3, "scale_y": 3}}
    pts = [(x / 10, y / 10) for x, y, k, *_ in layout.render({"items": [item]}).blocks[0].recs if k == STITCH]
    assert math.dist(pts[0], pts[1]) == pytest.approx(0.6 if style == "triangle" else 1.0, abs=1e-6)


# ---------------------------------------------------------------- snapshots and invariants


def _case(obj, style, nodes_at=(7, 11)):
    dx, dy = nodes_at
    g = dict(obj["geometry"])
    for key in ("nodes", "outline"):
        if g.get(key):
            g[key] = [[x + dx, y + dy, k] for x, y, k in g[key]]
    return {**obj, "geometry": g, "params": {**obj["params"], "tie_style": style}}


# A brick weave: plain tatami's choices can turn on the last digit of a sine, which isn't the same
# on every computer; with any row setting it settles them (Phase 6), and the locks don't care.
SNAPSHOT_CASES = {f"{name}_{style}": _case(obj, style)
                  for name, obj in [("run", LINE), ("satin", SATIN), ("fill", _with(FILL, weave="brick"))]
                  for style in STYLES}


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshots(name):
    check("ties", name, digest_recs_steady(generate(SNAPSHOT_CASES[name])[0]))


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_snapshots_do_not_hang_on_the_last_digit_of_a_sine(seed, monkeypatch):
    recorded = json.loads((SNAPSHOT_DIR / "ties.json").read_text(encoding="utf-8"))
    forget_stitches()
    try:
        nudge_trig(monkeypatch, seed, dz, ties, rotations=True)
        for name in sorted(SNAPSHOT_CASES):
            assert digest_recs_steady(generate(SNAPSHOT_CASES[name])[0]) == recorded[name], name
    finally:
        monkeypatch.undo()
        forget_stitches()


# The audit's shapes and settings: triangle locks landed up to 0.49 mm outside these fills.
FILL_SHAPES = {
    "square": [c(0, 0), c(30, 0), c(30, 30), c(0, 30)],
    "star": [c(20 + r * math.cos(-math.pi / 2 + math.pi * k / 5), 20 + r * math.sin(-math.pi / 2 + math.pi * k / 5))
             for k, r in enumerate([20, 9] * 5)],
    "circle": [c(15 + 15 * math.cos(2 * math.pi * i / 40), 15 + 15 * math.sin(2 * math.pi * i / 40)) for i in range(40)],
    "thin": [c(0, 0), c(30, 0), c(30, 1.2), c(0, 1.2)],
}
FILL_SETTINGS = [{}, {"pattern": "blackwork"}, {"weave": "brick"}, {"angle_deg": 0}, {"angle_deg": 90},
                 {"start_mm": [0, 0], "end_mm": [30, 30]}, {"start_mm": [30, 0], "end_mm": [0, 30]},
                 {"start_mm": [15, 0]}, {"underlay": []}, {"pull_comp_mm": 0}]


@pytest.mark.parametrize("name", list(FILL_SHAPES))
def test_triangle_locks_stay_by_their_fill(name):
    shape = fill_parts(FILL_SHAPES[name], [])[0]
    triangles = 0
    for settings in FILL_SETTINGS:
        try:
            recs = generate({"kind": "fill", "geometry": {"outline": FILL_SHAPES[name]},
                             "params": {"tie_style": "triangle", **settings}})[0]
        except DigitizeError:
            continue  # too thin for this pattern
        sewn = [r[:2] for r in recs if r[2] == STITCH]
        for end in (sewn[:4], sewn[::-1][:4]):  # the lock at each end
            assert max(shape.distance(ShapelyPoint(p)) for p in end) <= 0.105, (settings, end)
            a, far, side = end[0], end[1], end[2]
            ux, uy = far[0] - a[0], far[1] - a[1]
            across = abs(ux * (side[1] - a[1]) - uy * (side[0] - a[0])) / math.hypot(ux, uy)
            triangles += abs(across - ties.TRIANGLE_ACROSS_MM) < 0.01
    assert triangles >= len(FILL_SETTINGS)  # most ends still sew the triangle


def _area(obj):
    g = obj["geometry"]
    if obj["kind"] == "run":
        return LineString([n[:2] for n in g["nodes"]]).buffer(0.01)
    if obj["kind"] == "satin":
        return LineString([n[:2] for n in g["nodes"]]).buffer(g["width_mm"] / 2 + 0.1, cap_style="square")
    return box(7, 11, 22, 21)


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshot_cases_pass_the_invariants(name):
    obj = SNAPSHOT_CASES[name]
    # On a line or satin a triangle lock steps 0.52 mm to one side; on a fill it stays by the
    # outline (the rows themselves reach 0.1 mm past it, for pull compensation).
    reach = 0.105 if obj["kind"] == "fill" else 0.55
    invariants.assert_sane(generate(obj)[0], inside=_area(obj), tolerance_mm=reach, max_jumps=0, max_trims=0)
    invariants.assert_deterministic(lambda: generate(obj)[0])
    if obj["kind"] != "fill":  # a tatami fill's needle grid is the hoop's, with any lock
        invariants.assert_moves_with_shape(obj, 3.3, -8.1)
