"""Blackwork fill (digitize/fills/blackwork.py): a lattice of lines (fills/lattice.py), every one
sewn twice, out and back."""

import json
import math
import time
from collections import Counter

import pytest
import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

import invariants
from snapshot_util import SNAPSHOT_DIR, check, digest_recs_steady
from steady_util import forget_stitches, nudge_trig
from threadline_engine import layout
from threadline_engine.digitize import fills, paths
from threadline_engine.digitize import stitches as dz
from threadline_engine.digitize.fills import blackwork, lattice, motif, spiral
from threadline_engine.digitize.stitches import JUMP, STITCH, TRIM, DigitizeError, FillParams, fill_parts, generate

LATTICES = ("diamonds", "grid", "honeycomb", "crossed")
THREAD = {"color": "#1f3a93", "name": "Navy", "catalog": "", "brand": ""}


def _nodes(points):
    return [[x, y, "c"] for x, y in points]


def _round(r, n=48, middle=(20.0, 20.0)):
    return _nodes((middle[0] + r * math.cos(2 * math.pi * i / n), middle[1] + r * math.sin(2 * math.pi * i / n))
                  for i in range(n))


SQUARE = _nodes([(0, 0), (40, 0), (40, 40), (0, 40)])
HOLE = _nodes([(13, 13), (27, 13), (27, 27), (13, 27)])
CIRCLE = _round(20)
STAR = _nodes((20 + r * math.cos(-math.pi / 2 + math.pi * k / 5), 20 + r * math.sin(-math.pi / 2 + math.pi * k / 5))
              for k, r in enumerate([20, 9] * 5))
L_SHAPE = _nodes([(0, 0), (40, 0), (40, 16), (16, 16), (16, 40), (0, 40)])
# The Shapes menu's heart (design/shapes.ts), 40 mm wide.
_HEART_SIDE = [(4.38, -15.6), (10.76, -18), (17.34, -15.6), (19.92, -8.4), (14.74, 3.8)]
HEART = [[20, 7.6, "c"], *([x + 20, y + 18, "s"] for x, y in _HEART_SIDE), [20, 36, "c"],
         *([20 - x, y + 18, "s"] for x, y in reversed(_HEART_SIDE))]
SIMPLE = {"square": (SQUARE, []), "circle": (CIRCLE, []), "donut": (SQUARE, [HOLE]), "heart": (HEART, [])}
SHAPES = {**SIMPLE, "star": (STAR, []), "l_shape": (L_SHAPE, [])}


def _fill(kind="diamonds", outline=SQUARE, holes=(), **params):
    return {"kind": "fill", "geometry": {"outline": outline, "holes": list(holes)},
            "params": {"pattern": "blackwork", "blackwork_lattice": kind, "underlay": [], **params}}


def _bare(kind="diamonds", outline=SQUARE, holes=(), **params):
    return generate(_fill(kind, outline, holes, tie_in=False, tie_off=False, **params))[0]


def _shape_of(obj):
    g = obj["geometry"]
    return unary_union(fill_parts(g["outline"], g.get("holes") or []))


def _clipped(kind, outline=SQUARE, holes=(), cell=5.0):
    """The lattice's segments inside the shape, in the shape's own frame."""
    local, _ = motif.own_frame(fill_parts(outline, list(holes))[0])
    return local, lattice.clip_segments(lattice.tile_segments(kind, cell, local.bounds), local)


def _pieces(kind, outline=SQUARE, holes=(), stitch=2.5):
    """The lattice's double runs, one for each piece that hangs together."""
    return lattice.double_run_paths(_clipped(kind, outline, holes)[1], stitch, spiral.FAR)


def _needles(recs):
    return [(x, y) for x, y, k in recs if k == STITCH]


def _key(p):
    return round(p[0], 4), round(p[1], 4)


def _threads(recs):
    return [(a[:2], b[:2]) for a, b in zip(recs, recs[1:]) if a[2] == b[2] == STITCH]


# ---------------------------------------------------------------- registered, and its settings


def test_blackwork_is_an_open_fill_with_no_automatic_underlay():
    spec = fills.get("blackwork")
    assert spec.kind == "open" and not spec.covers
    assert list(fills.REGISTRY)[-1] == "blackwork"
    for level in (None, "light", "normal", "heavy"):
        auto = {"underlay": "auto", **({"underlay_level": level} if level else {})}
        assert FillParams.from_dict({"pattern": "blackwork", **auto}).underlay == ()
    p = FillParams.from_dict({"pattern": "blackwork"})
    assert p.value("blackwork_mm") == 5 and p.blackwork_lattice == "diamonds"
    assert spec.step_mm2(p) == pytest.approx(5 * 3.5 / 4)
    assert lattice.LATTICES == LATTICES


def test_cell_size_checked():
    for cell in (2.9, 12.1):
        with pytest.raises(DigitizeError, match="^Cell size must be between 3 and 12 mm$"):
            FillParams.from_dict({"pattern": "blackwork", "blackwork_mm": cell})
    for cell in (3, 12):
        assert generate(_fill(blackwork_mm=cell))[0]
    with pytest.raises(DigitizeError, match="^Unknown blackwork lattice: weave$"):
        FillParams.from_dict({"pattern": "blackwork", "blackwork_lattice": "weave"})
    plain = {**_fill(), "params": {"pattern": "blackwork"}}  # diamonds unless another lattice is chosen
    assert generate(plain) == generate({**plain, "params": {"pattern": "blackwork", "blackwork_lattice": "diamonds"}})
    assert generate(plain) != generate({**plain, "params": {"pattern": "blackwork", "blackwork_lattice": "grid"}})


# ---------------------------------------------------------------- the lattice


def _graph(segments):
    """Whether the segments (as pairs of points) hang together in one piece."""
    parent = {}

    def root(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in segments:
        parent[root(_key(a))] = root(_key(b))
    return len({root(a) for a in list(parent)})


@pytest.mark.parametrize("kind", LATTICES)
def test_each_lattice_is_one_piece_made_of_cells_the_size_asked(kind):
    segments = lattice.tile_segments(kind, 5.0, (0.0, 0.0, 40.0, 40.0))
    assert _graph(segments) == 1
    lengths = sorted({round(math.dist(a, b), 4) for a, b in segments})
    if kind in ("grid", "diamonds"):
        assert lengths == [5.0]
    elif kind == "honeycomb":
        assert lengths == [round(5 / math.sqrt(3), 4)]  # hexagons 5 mm across the flats
        upright = sorted({round(a[0], 4) for a, b in segments if abs(a[0] - b[0]) < 1e-9})
        assert [q - p for p, q in zip(upright, upright[1:])] == pytest.approx([2.5] * (len(upright) - 1))
    else:
        assert lengths == pytest.approx([5 / math.sqrt(2), 5.0], abs=1e-3)
    angles = {round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))) % 180 for a, b in segments}
    assert angles == {"grid": {0, 90}, "diamonds": {45, 135}, "honeycomb": {30, 90, 150},
                      "crossed": {0, 45, 90, 135}}[kind]
    # Where lines cross they share an end: none runs across another.
    lines = [LineString(s) for s in segments]
    assert not any(a.crosses(b) for i, a in enumerate(lines) for b in lines[i + 1 : i + 40])


def test_lattice_lines_are_the_cell_size_apart():
    for kind, way in (("grid", 0.0), ("diamonds", 45.0)):
        a = math.radians(way)
        normal = (-math.sin(a), math.cos(a))
        offsets = sorted({round((p[0] + q[0]) / 2 * normal[0] + (p[1] + q[1]) / 2 * normal[1], 3)
                          for p, q in lattice.tile_segments(kind, 5.0, (0.0, 0.0, 40.0, 40.0))
                          if abs(math.remainder(math.atan2(q[1] - p[1], q[0] - p[0]) - a, math.pi)) < 0.01})
        assert [b - a for a, b in zip(offsets, offsets[1:])] == pytest.approx([5] * (len(offsets) - 1), abs=0.002)


def test_clip_drops_pieces_under_0_8_mm():
    area = box(0, 0, 10, 10)
    got = lattice.clip_segments([((-5, 2), (0.7, 2)), ((-5, 4), (0.9, 4)), ((2, 2), (8, 2)), ((12, 0), (15, 0)),
                                 ((-1, 6), (11, 6))], area)
    assert sorted((round(a[0], 2), round(b[0], 2), round(a[1], 2)) for a, b in got) == [
        (-0.01, 0.9, 4.0), (-0.01, 10.01, 6.0), (2.0, 8.0, 2.0)]


@pytest.mark.parametrize("kind", LATTICES)
@pytest.mark.parametrize("name", sorted(SHAPES))
def test_every_segment_sewn_twice(kind, name):
    paths = _pieces(kind, *SHAPES[name])
    seen = Counter()
    for path in paths:
        assert math.dist(path[0], path[-1]) < 1e-9  # each ends where it began
        seen.update((_key(a), _key(b)) for a, b in zip(path, path[1:]))
    both = Counter(frozenset(k) for k in seen.elements())
    assert set(both.values()) == {2}, sorted(both.values())
    assert all(seen[(b, a)] == 1 for a, b in seen)  # once each way
    assert max(math.dist(a, b) for path in paths for a, b in zip(path, path[1:])) <= 2.5 + 1e-6
    # A needle point at every crossing and end, and every stretch of the lattice is sewn.
    needles = {_key(p) for path in paths for p in path}
    segments = _clipped(kind, *SHAPES[name])[1]
    assert all(_key(a) in needles and _key(b) in needles for a, b in segments)
    walked = sum(math.dist(a, b) for path in paths for a, b in zip(path, path[1:]))
    assert walked == pytest.approx(2 * sum(math.dist(a, b) for a, b in segments), rel=1e-6)


@pytest.mark.parametrize("kind", LATTICES)
def test_the_fill_sews_the_lattice_twice(kind):
    """Through generate(), as the design sews: the same stretch twice, once each way."""
    threads = Counter(frozenset((_key(a), _key(b))) for a, b in _threads(_bare(kind, stitch_mm=2.5)))
    assert set(threads.values()) == {2}


def test_double_run_has_a_needle_point_at_every_crossing_and_end():
    # Two lines that cross, one ending part way along another, and one apart.
    segments = [((0, 0), (10, 0)), ((5, -5), (5, 5)), ((8, 0), (8, 6)), ((20, 20), (24, 20))]
    paths = lattice.double_run_paths(segments, 2.0, (0.0, -1.0))
    assert len(paths) == 2 and paths[0][0] == (0, 0)  # the piece nearest the start first, from there
    points = {_key(p) for p in paths[0]}
    assert {_key(p) for p in [(0, 0), (5, 0), (8, 0), (10, 0), (5, -5), (5, 5), (8, 6)]} <= points
    walked = Counter(frozenset((_key(a), _key(b))) for p in paths for a, b in zip(p, p[1:]))
    assert set(walked.values()) == {2}
    assert sum(math.dist(*sorted(k)) for k in walked.elements()) == pytest.approx(2 * (10 + 10 + 6 + 4))
    # The same segments in another order, or turned round, are walked the same way.
    shuffled = [(b, a) for a, b in reversed(segments)]
    assert lattice.double_run_paths(shuffled, 2.0, (0.0, -1.0)) == paths


@pytest.mark.parametrize("kind", LATTICES)
@pytest.mark.parametrize("name", sorted(SIMPLE))
def test_one_piece_has_no_jumps(kind, name):
    outline, holes = SIMPLE[name]
    assert len(_pieces(kind, outline, holes)) == 1
    recs = generate(_fill(kind, outline, holes, underlay="auto"))[0]
    assert invariants.count(recs, JUMP) == 0 and invariants.count(recs, TRIM) == 0


@pytest.mark.parametrize("kind", LATTICES)
@pytest.mark.parametrize("name", sorted(SHAPES))
def test_lines_stay_inside_the_shape(kind, name):
    obj = _fill(kind, *SHAPES[name])
    shape = _shape_of(obj)
    # The lattice's own lines lie inside (cut at the shape grown by a hair)...
    local, lines = _clipped(kind, *SHAPES[name])
    assert lines and all(local.buffer(0.02).covers(LineString(s)) for s in lines)
    # ...and what joins pieces apart goes no further out than any open fill's travel.
    apart = len(_pieces(kind, *SHAPES[name])) > 1
    invariants.assert_sane(generate(obj)[0], inside=shape, tolerance_mm=0.3 if apart else 0.05)


# Joins between a lattice's separate pieces follow the edge, never straight across open cells
# (Phase 7 audit, finding 5: 37 mm of thread across a 40 mm star).
def _ring(cx, cy, r, n=48):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def _star(R, r, mid):
    return [(mid + rr * math.cos(-math.pi / 2 + math.pi * k / 5), mid + rr * math.sin(-math.pi / 2 + math.pi * k / 5))
            for k, rr in enumerate([R, r] * 5)]


def _box(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


FOUR_HOLES = [_box(4, 4, 14, 14), _box(22, 4, 14, 14), _box(4, 22, 14, 14), _box(22, 22, 14, 14)]
JOINED_SHAPES = {  # outline, holes
    "audit's star": (_star(20, 9, 20), []),
    "thin star": (_star(30, 6, 30), []),
    "square with a big hole": (_box(0, 0, 40, 40), [_box(4, 4, 32, 32)]),
    "four holes": (_box(0, 0, 40, 40), FOUR_HOLES),
    "off-center donut": (_ring(20, 20, 20), [_ring(26, 20, 12)]),
    "letter B": (_box(0, 0, 24, 40), [_box(6, 6, 12, 11), _box(6, 23, 12, 11)]),
}


@pytest.mark.parametrize("cell", [3, 5, 8])
@pytest.mark.parametrize("kind", LATTICES)
@pytest.mark.parametrize("name", list(JOINED_SHAPES))
def test_no_joining_thread_crosses_an_open_cell(name, kind, cell):
    outline, holes = JOINED_SHAPES[name]
    obj = _fill(kind, _nodes(outline), [_nodes(h) for h in holes], blackwork_mm=cell, underlay="auto")
    recs = generate(obj)[0]
    shape = _shape_of(obj)
    lines = []
    for part in fill_parts(obj["geometry"]["outline"], obj["geometry"]["holes"]):
        local, (ox, oy) = motif.own_frame(part)
        lines += [LineString([(a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy)])
                  for a, b in lattice.clip_segments(lattice.tile_segments(kind, cell, local.bounds), local)]
    lines = unary_union(lines)
    shapely.prepare(lines)
    samples = []
    for a, b in _threads(recs):
        n = max(1, math.ceil(math.dist(a, b) / 0.25))
        samples += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n + 1)]
    points = shapely.points(samples)
    inside = points[shapely.distance(shape.boundary, points) > 0.6]  # away from every edge: on a line
    worst = float(shapely.distance(lines, inside).max()) if len(inside) else 0.0
    assert worst <= 0.25, f"{worst:.2f} mm from every line and edge"
    if not holes:  # the edge reaches every piece of a shape without holes: no jumps at all
        assert invariants.count(recs, JUMP) == 0 and invariants.count(recs, TRIM) == 0


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_joins_do_not_hang_on_the_last_digit(seed, monkeypatch):
    """Both ways round an edge can tie on a symmetric shape with holes: the choice, like the
    joins' checks, must come out the same on every computer."""
    cases = [(k, name) for k in ("diamonds", "grid") for name in ("square with a big hole", "four holes", "letter B")]
    want = {c: _bare(c[0], _nodes(JOINED_SHAPES[c[1]][0]), [_nodes(h) for h in JOINED_SHAPES[c[1]][1]], blackwork_mm=5)
            for c in cases}
    forget_stitches()
    try:
        nudge_trig(monkeypatch, seed, dz, paths, lattice, motif, blackwork)
        for (kind, name), recs in want.items():
            outline, holes = JOINED_SHAPES[name]
            got = _bare(kind, _nodes(outline), [_nodes(h) for h in holes], blackwork_mm=5)
            assert [r[2] for r in got] == [r[2] for r in recs], (kind, name)
            assert max(math.dist(a[:2], b[:2]) for a, b in zip(got, recs)) < 0.001, (kind, name)
    finally:
        monkeypatch.undo()
        forget_stitches()


@pytest.mark.parametrize("kind", LATTICES)
def test_the_whole_shape_is_covered(kind):
    obj = _fill(kind, SQUARE, [HOLE], blackwork_mm=5)
    assert invariants.coverage(generate(obj)[0], _shape_of(obj), 3.0) > 0.99


@pytest.mark.parametrize("kind", LATTICES)
@pytest.mark.parametrize("name", ["square", "donut", "star", "heart"])
def test_each_lattice_moves_with_its_shape(kind, name):
    obj = _fill(kind, *SHAPES[name])
    for dx, dy in [(10, -7.5), (0.1234, 33.333), (-250.7, 1000.9), (-20, -20)]:
        invariants.assert_moves_with_shape(obj, dx, dy)
    invariants.assert_deterministic(lambda: generate(obj)[0])


@pytest.mark.parametrize("dot", [(40, 40), (0, 21), (23, 0)])
def test_blackwork_starts_by_the_green_dot(dot):
    first = _needles(_bare("grid", start_mm=list(dot)))[0]
    assert math.dist(first, dot) <= 2.5


def test_the_edge_run_can_be_asked_for():
    edged = generate(_fill(underlay=["edge"]))[0]
    assert len(edged) > len(generate(_fill())[0])


def test_cell_size_stays_in_mm_when_resized():
    """A 20 mm square made twice as big with the handles still has 5 mm cells."""
    item = {**_fill("grid", _nodes([(0, 0), (20, 0), (20, 20), (0, 20)]), tie_in=False, tie_off=False,
                    blackwork_mm=5), "id": "a", "thread": THREAD, "transform": {"x": 10, "y": 10, "scale_x": 2, "scale_y": 2}}
    forget_stitches()
    recs = [(x / 10, y / 10, k) for x, y, k, *_ in layout.render({"items": [item]}).blocks[0].recs]
    level = sorted({round((a[1] + b[1]) / 2, 2) for a, b in _threads(recs) if abs(a[1] - b[1]) < 1e-6})
    assert level == pytest.approx([5 * k for k in range(9)], abs=0.011)


def test_too_big_a_blackwork_fill_is_refused_before_it_is_laid_out(monkeypatch):
    # The common guard (by area per stitch) would let this through: about a million stitches.
    huge = _nodes([(0, 0), (900, 0), (900, 900), (0, 900)])
    p = FillParams.from_dict({"pattern": "blackwork", "blackwork_mm": 3, "stitch_mm": 7, "blackwork_lattice": "crossed"})
    assert 900 * 900 / fills.get("blackwork").step_mm2(p) < dz.MAX_STITCHES
    laid = []
    monkeypatch.setattr(blackwork, "tile_segments", lambda *a: laid.append(a))
    start = time.monotonic()
    with pytest.raises(DigitizeError, match=r"^This fill would need about [\d,]+ stitches, far more than any design\. "
                                            r"Make it smaller, or use bigger cells\.$"):
        generate(_fill("crossed", huge, blackwork_mm=3, stitch_mm=7))
    assert not laid and time.monotonic() - start < 5


@pytest.mark.parametrize("kind", LATTICES)
def test_the_estimate_is_near_what_is_sewn(kind):
    for cell, stitch in [(3, 2.0), (5, 3.5), (12, 7)]:
        p = FillParams.from_dict(_fill(kind, blackwork_mm=cell, stitch_mm=stitch)["params"])
        about = blackwork.estimate(fill_parts(SQUARE)[0], p)
        sewn = len(_needles(_bare(kind, blackwork_mm=cell, stitch_mm=stitch)))
        assert 0.7 < about / sewn < 1.6, (cell, stitch, about, sewn)


def test_a_very_big_blackwork_warns_like_repeat_does():
    big = _nodes([(0, 0), (250, 0), (250, 250), (0, 250)])
    recs, warnings = generate(_fill("crossed", big, blackwork_mm=3, underlay="auto"))
    sewn = sum(1 for r in recs if r[2] == STITCH)
    assert sewn > blackwork.WARN_STITCHES == 60_000
    (said,) = [w for w in warnings if "very long sew-out" in w]
    about = int(said.split("about ")[1].split(" stitches")[0].replace(",", ""))
    assert abs(about - sewn) <= 0.02 * sewn and "Bigger cells or a smaller shape sew faster." in said
    assert not [w for w in generate(_fill("crossed", SQUARE, blackwork_mm=3, underlay="auto"))[1] if "very long" in w]


def test_a_shape_too_small_for_blackwork_says_so():
    # No diagonal line has 0.8 mm of itself inside a strip 0.4 mm wide.
    with pytest.raises(DigitizeError, match="too small for a blackwork fill"):
        generate(_fill("diamonds", _nodes([(0, 0), (30, 0), (30, 0.4), (0, 0.4)]), blackwork_mm=12))


# ---------------------------------------------------------------- snapshots and invariants


def _at(outline, dx=7.0, dy=11.0):
    return [[x + dx, y + dy, k] for x, y, k in outline]


SNAPSHOT_CASES = {
    "diamonds_40": _fill("diamonds", _at(SQUARE), underlay="auto"),
    "grid_donut": _fill("grid", _at(SQUARE), [_at(HOLE)], underlay="auto"),
    "honeycomb_40": _fill("honeycomb", _at(SQUARE), underlay="auto"),
    "crossed_40": _fill("crossed", _at(SQUARE), underlay="auto"),
}


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshots(name):
    check("fills_blackwork", name, digest_recs_steady(generate(SNAPSHOT_CASES[name])[0]))


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_snapshots_do_not_hang_on_the_last_digit_of_a_sine(seed, monkeypatch):
    recorded = json.loads((SNAPSHOT_DIR / "fills_blackwork.json").read_text(encoding="utf-8"))
    forget_stitches()
    try:
        nudge_trig(monkeypatch, seed, dz, blackwork, lattice, motif, spiral, rotations=True)
        for name in sorted(SNAPSHOT_CASES):
            assert digest_recs_steady(generate(SNAPSHOT_CASES[name])[0]) == recorded[name], name
    finally:
        monkeypatch.undo()
        forget_stitches()


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshot_cases_pass_the_invariants(name):
    obj = SNAPSHOT_CASES[name]
    invariants.assert_sane(generate(obj)[0], inside=_shape_of(obj), tolerance_mm=0.05, max_jumps=0, max_trims=0)
    invariants.assert_deterministic(lambda: generate(obj)[0])
    invariants.assert_moves_with_shape(obj, 3.3, -8.1)
