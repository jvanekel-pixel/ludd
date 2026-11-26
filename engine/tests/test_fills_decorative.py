"""The decorative fills: motif, maze, ripple and mesh (digitize/fills)."""

import json
import math

import pytest
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

import invariants
from snapshot_util import SNAPSHOT_DIR, check, digest_recs_steady
from steady_util import forget_stitches, nudge_trig
from test_fill_spiral import _most_threads_along_an_edge
from threadline_engine import layout
from threadline_engine.digitize import fills, lines, patterns
from threadline_engine.digitize import stitches as dz
from threadline_engine.digitize.fills import maze, mesh, motif, ripple, spiral
from threadline_engine.digitize.stitches import (JUMP, STITCH, TRIM, DigitizeError, FillParams, fill_parts,
                                                 generate)

PATTERNS = ("motif", "maze", "ripple", "mesh")
BRANCHED = "This shape is too branched for one maze; Contour may suit it better."
THREAD = {"color": "#2a7f3f", "name": "Green", "catalog": "", "brand": ""}


def _nodes(points):
    return [[x, y, "c"] for x, y in points]


def _smooth(points):
    return [[x, y, "s"] for x, y in points]


def _round(r, n=96, middle=(20.0, 20.0)):
    return _nodes((middle[0] + r * math.cos(2 * math.pi * i / n), middle[1] + r * math.sin(2 * math.pi * i / n))
                  for i in range(n))


SQUARE = _nodes([(0, 0), (40, 0), (40, 40), (0, 40)])
HOLE = _nodes([(14, 14), (26, 14), (26, 26), (14, 26)])
CIRCLE = _round(20)
STAR = _nodes((20 + r * math.cos(-math.pi / 2 + math.pi * k / 5), 20 + r * math.sin(-math.pi / 2 + math.pi * k / 5))
              for k, r in enumerate([20, 9] * 5))
TRIANGLE = _nodes([(20, 0), (40, 35), (0, 35)])
L_SHAPE = _nodes([(0, 0), (40, 0), (40, 16), (16, 16), (16, 40), (0, 40)])
# The ready-made heart from the Shapes menu (design/shapes.ts), moved to sit at the top left.
_HEART_SIDE = [(6.58, -23.4), (16.14, -27), (26, -23.4), (29.89, -12.6), (22.12, 5.7)]
HEART = [[30, 11.4, "c"], *([x + 30, y + 27, "s"] for x, y in _HEART_SIDE), [30, 54, "c"],
         *([30 - x, y + 27, "s"] for x, y in reversed(_HEART_SIDE))]
SHAPES = {"square": (SQUARE, []), "circle": (CIRCLE, []), "star": (STAR, []), "triangle": (TRIANGLE, []),
          "l_shape": (L_SHAPE, []), "heart": (HEART, []), "donut": (SQUARE, [HOLE])}


def _beads(n, neck, size=10.0, gap=3.0):
    """`n` squares in a row, joined by necks `neck` mm wide."""
    parts = [box(i * (size + gap), 0, i * (size + gap) + size, size) for i in range(n)]
    parts += [box(i * (size + gap) + size - 0.5, (size - neck) / 2, (i + 1) * (size + gap) + 0.5, (size + neck) / 2)
              for i in range(n - 1)]
    return _nodes(list(unary_union(parts).simplify(0).exterior.coords)[:-1])


def _fill(pattern, outline=SQUARE, holes=(), **params):
    """A fill with no underlay (what Auto gives these patterns) and any other settings."""
    return {"kind": "fill", "geometry": {"outline": outline, "holes": list(holes)},
            "params": {"pattern": pattern, "underlay": [], **params}}


def _shape_of(obj):
    g = obj["geometry"]
    return unary_union(fill_parts(g["outline"], g.get("holes") or []))


def _recs(pattern, outline=SQUARE, holes=(), **params):
    return generate(_fill(pattern, outline, holes, **params))[0]


def _paths(pattern, outline=SQUARE, holes=(), **params):
    """The pattern's own paths over the shape's biggest piece, as lists of points."""
    obj = _fill(pattern, outline, holes, **params)
    poly = fill_parts(outline, list(holes))[0]
    start = tuple(poly.exterior.coords[0])
    return fills.get(pattern).paths(poly, FillParams.from_dict(obj["params"]), start)[0]


def _needles(recs):
    return [(r[0], r[1]) for r in recs if r[2] == STITCH]


def _threads(recs):
    """The thread between two needle drops in a row, as (from, to)."""
    return [(a[:2], b[:2]) for a, b in zip(recs, recs[1:]) if a[2] == b[2] == STITCH]


def _stays_inside(obj, **kwargs):
    invariants.assert_sane(generate(obj)[0], inside=_shape_of(obj), tolerance_mm=0.3, **kwargs)


def _crossings(recs):
    """How many times the thread crosses itself at an angle (travel included). Thread laid along
    thread, and stitches meeting end to end, aren't crossings."""
    threads = [LineString(t) for t in _threads(recs) if math.dist(*t) > 0]
    tree = STRtree(threads)
    found = 0
    for i, a in enumerate(threads):
        for j in tree.query(a):
            if j <= i + 1:
                continue
            b = threads[j]
            meet = a.intersection(b)
            if meet.geom_type != "Point" or min(meet.distance(Point(p)) for p in [*a.coords, *b.coords]) < 1e-6:
                continue
            ways = [math.atan2(q[1] - p[1], q[0] - p[0]) for p, q in (a.coords, b.coords)]
            found += abs(math.remainder(ways[0] - ways[1], math.pi)) > math.radians(10)
    return found


def _rows_of(outline, **params):
    """A motif fill's rows over an outline that starts at (0, 0), top to bottom at angle 0: each
    row's pieces, as the needle points along them."""
    params = FillParams.from_dict(_fill("motif", outline, **params)["params"])
    return motif._rows(fill_parts(outline)[0], params, min(params.stitch_mm, 7.0))


# ---------------------------------------------------------------- all four


def test_the_four_fills_are_open_with_no_automatic_underlay():
    for name in PATTERNS:
        assert fills.get(name).kind == "open" and not fills.get(name).covers
        for level in (None, "light", "normal", "heavy"):
            auto = {"underlay": "auto", **({"underlay_level": level} if level else {})}
            assert FillParams.from_dict({"pattern": name, **auto}).underlay == ()


@pytest.mark.parametrize("params,says", [
    ({"pattern": "motif", "motif_mm": 1}, "^Repeat must be between 1.5 and 20 mm$"),
    ({"pattern": "motif", "motif_width_mm": 11}, "^Height must be between 0.5 and 10 mm$"),
    ({"pattern": "motif", "motif_gap_mm": -1}, "^Row gap must be between 0 and 10 mm$"),
    ({"pattern": "motif", "motif_stagger": 2}, "^Shift alternate rows must be between 0 and 1$"),
    ({"pattern": "maze", "maze_mm": 0.5}, "^Path spacing must be between 0.8 and 6 mm$"),
    ({"pattern": "ripple", "ripple_mm": 9}, "^Ring spacing must be between 0.6 and 8 mm$"),
    ({"pattern": "mesh", "mesh_mm": 0.5}, "^Cell size must be between 1 and 10 mm$"),
    ({"pattern": "mesh", "mesh_cross_deg": 100}, "^Crossing angle must be between 45 and 90°$"),
])
def test_their_settings_are_range_checked(params, says):
    with pytest.raises(DigitizeError, match=says):
        FillParams.from_dict(params)


CASES = [(p, n) for p in PATTERNS for n in SHAPES]


@pytest.mark.parametrize("pattern,name", CASES, ids=[f"{p}-{n}" for p, n in CASES])
def test_each_fill_stays_inside_with_no_long_stitch(pattern, name):
    obj = _fill(pattern, *SHAPES[name], underlay="auto")
    _stays_inside(obj)


@pytest.mark.parametrize("pattern", PATTERNS)
@pytest.mark.parametrize("name", ["square", "circle", "star", "donut", "heart"])
def test_each_fill_is_the_same_every_time(pattern, name):
    invariants.assert_deterministic(lambda: generate(_fill(pattern, *SHAPES[name]))[0])


MOVES = [(10, -7.5), (0.1234, 33.333), (-250.7, 1000.9)]


@pytest.mark.parametrize("pattern", PATTERNS)
@pytest.mark.parametrize("name", ["square", "star", "donut", "heart", "l_shape"])
def test_each_fill_moves_with_its_shape(pattern, name):
    obj = _fill(pattern, *SHAPES[name], **({"ripple_center": [12.5, 17.25]} if pattern == "ripple" else {}))
    for dx, dy in MOVES:
        invariants.assert_moves_with_shape(obj, dx, dy)


@pytest.mark.parametrize("pattern", PATTERNS)
def test_a_shape_far_from_the_middle_of_the_hoop_sews_the_same(pattern):
    obj = _fill(pattern, STAR)
    invariants.assert_moves_with_shape(obj, -20, -20)  # round the origin, where signs change


def test_of_equally_far_points_simplifying_keeps_the_first():
    """Distances that differ by less than a millionth of a mm, as a last digit makes them on
    another computer, count as the same; a point no farther than the tolerance can go."""
    assert motif.kept_points([(0, 0), (1, 1), (2, 1 + 1e-10), (3, 0)], 0.5) == [0, 1, 3]
    assert motif.kept_points([(0, 0), (1, 0.5 + 1e-10), (2, 0)], 0.5) == [0, 2]
    assert motif.kept_points([(0, 0), (1, 0.51), (2, 0)], 0.5) == [0, 1, 2]


def test_line_ends_by_a_corner_go_to_the_corner():
    """Mesh lines at 45 degrees run through the corners of a square. Cut on the grown outline,
    their ends are as near one side as the other; left there, a last digit would choose the way
    the next join goes."""
    rings = motif.edge_rings(box(0, 0, 10, 10))
    ends = [[(-0.0071, -0.0071), (5.0, 3.0), (10.0071, 10.0071)], [(3.0, -0.01), (10.01, 7.0)]]
    got = motif.onto_edges(ends, rings)
    assert [[(round(x, 9), round(y, 9)) for x, y in s] for s in got] == [[(0, 0), (5, 3), (10, 10)], [(3, 0), (10, 7)]]


def _resized(pattern, scale, **params):
    """A 20 mm square made `scale` times bigger with the handles, as the app draws it, its top
    left corner kept at (0, 0): its records in mm."""
    shift = 10 * (scale - 1)  # the handles scale about the middle
    item = {**_fill(pattern, _nodes([(0, 0), (20, 0), (20, 20), (0, 20)]), tie_in=False, tie_off=False, **params),
            "id": "a", "thread": THREAD, "transform": {"x": shift, "y": shift, "scale_x": scale, "scale_y": scale}}
    forget_stitches()
    block = layout.render({"items": [item]}).blocks[0]
    return [(x / 10, y / 10, k) for x, y, k, *_ in block.recs]


# ---------------------------------------------------------------- motif fill


def _motif_rows(**params):
    """The rows of a motif fill of the 40 mm square at angle 0, top first, each in one piece."""
    rows = _rows_of(SQUARE, **{"angle_deg": 0, **params})
    assert all(len(row) <= 1 for row in rows)
    return [row[0] for row in rows if row]


def _peaks(path, top):
    """x of each point at height `top` (the zigzag's tips)."""
    return sorted({round(x, 3) for x, y in path if abs(y - top) < 0.001})


@pytest.mark.parametrize("gap,stagger", [(0.5, 0.5), (2.0, 0.25), (1.0, 0.0), (0.0, 1.0)])
def test_motif_rows_are_evenly_spaced_and_staggered(gap, stagger):
    rows = _motif_rows(motif="zigzag", motif_mm=5, motif_width_mm=4, motif_gap_mm=gap, motif_stagger=stagger)
    full = [r for r in rows if max(y for _, y in r) - min(y for _, y in r) > 3.99]
    assert len(full) >= 4
    middles = [(min(y for _, y in r) + max(y for _, y in r)) / 2 for r in full]
    assert [b - a for a, b in zip(middles, middles[1:])] == pytest.approx([4 + gap] * (len(full) - 1), abs=0.01)
    phases = [_peaks(r, max(y for _, y in r))[1] % 5 for r in full]
    for a, b in zip(phases, phases[1:]):
        off = [(b - a - sign * stagger * 5) % 5 for sign in (1, -1)]  # shifted one way or back
        assert min(min(d, 5 - d) for d in off) < 0.01, phases
    for r in full:  # whole repeats, 5 mm apart
        peaks = _peaks(r, max(y for _, y in r))
        assert [b - a for a, b in zip(peaks, peaks[1:])] == pytest.approx([5] * (len(peaks) - 1), abs=0.01)


def test_motif_rows_are_sewn_back_and_forth():
    # Nine rows 4.5 mm apart, centered: row k is the stitching within 2 mm of y = 2 + 4.5k.
    pts = _needles(_recs("motif", angle_deg=0, motif="wave", motif_stagger=0, tie_in=False, tie_off=False))
    visits = []  # (row, the x where the stitching entered it, the x where it left)
    for x, y in pts:
        k = round((y - 2) / 4.5)
        if not 0.01 < x < 39.99:  # joins run along the sides
            continue
        if visits and visits[-1][0] == k:
            visits[-1][2] = x
        else:
            visits.append([k, x, x])
    assert [k for k, _, _ in visits] == list(range(9)) or [k for k, _, _ in visits] == list(range(8, -1, -1))
    ways = [1 if end > start else -1 for _, start, end in visits]
    assert all(a == -b for a, b in zip(ways, ways[1:]))


@pytest.mark.parametrize("name", ["square", "circle", "star", "donut", "l_shape", "heart"])
@pytest.mark.parametrize("pattern", ["motif", "ripple", "mesh"])
def test_joining_thread_does_not_pile_up_along_the_edges(pattern, name):
    obj = _fill(pattern, *SHAPES[name], tie_in=False, tie_off=False)
    assert _most_threads_along_an_edge(generate(obj)[0], _shape_of(obj)) <= 6


@pytest.mark.parametrize("name", ["square", "star", "donut"])
def test_no_thread_cuts_across_a_motif_fill(name):
    """Every join between pieces keeps to an edge: none shows across the pattern."""
    shape = _shape_of(_fill("motif", *SHAPES[name]))
    local, origin = motif.own_frame(fill_parts(*SHAPES[name])[0])
    rows = motif._rows(local, FillParams.from_dict({"pattern": "motif", "angle_deg": 30}), 3.5)
    laid = [LineString(motif.place(p, origin)) for row in rows for p in row]
    motif_lines = unary_union(laid).buffer(0.05)
    inner = shape.buffer(-1.0)
    off = 0.0
    for a, b in _threads(_recs("motif", *SHAPES[name], angle_deg=30, tie_in=False, tie_off=False)):
        piece = LineString([a, b]).difference(motif_lines).intersection(inner)
        off += piece.length
    assert off < 1.0


@pytest.mark.parametrize("width,middle", [(40, 20), (43, 21.5), (37.5, 18.75)])
def test_whole_repeats_are_centered_on_the_shape(width, middle):
    outline = _nodes([(0, 0), (width, 0), (width, 20), (0, 20)])
    paths = [p for row in _rows_of(outline, angle_deg=0, motif="zigzag", motif_mm=5, motif_stagger=0) for p in row]
    whole = [p for p in paths if min(y for _, y in p) > 0.05 and max(y for _, y in p) < 19.95]  # not cut
    assert len(whole) >= 3
    for path in whole:
        top = max(y for _, y in path)
        peaks = _peaks(path, top)
        mirrored = sorted(round(2 * middle - x, 3) for x in peaks)
        assert peaks == pytest.approx(mirrored, abs=0.01)
        assert min(x for x, _ in path) == pytest.approx(0, abs=0.02)
        assert max(x for x, _ in path) == pytest.approx(width, abs=0.02)


@pytest.mark.parametrize("name", ["square", "circle", "star", "l_shape", "donut"])
@pytest.mark.parametrize("angle,motif_name", [(0, "wave"), (45, "leaf"), (120, "blanket"), (30, "scallop")])
def test_motif_fill_keeps_whole_repeats_inside(name, angle, motif_name):
    obj = _fill("motif", *SHAPES[name], motif=motif_name, angle_deg=angle)
    _stays_inside(obj)
    # And it covers the shape from side to side: no part of it more than a row away from stitching.
    shape = _shape_of(obj)
    assert invariants.coverage(generate(obj)[0], shape.buffer(-1), 3.0) > 0.97


def test_motif_fill_follows_the_angle():
    rows = [p for row in _rows_of(SQUARE, motif="wave", angle_deg=30, motif_stagger=0) for p in row]
    long = [p for p in rows if math.dist(p[0], p[-1]) > 25]
    assert len(long) >= 5
    for path in long:
        (x0, y0), (x1, y1) = path[0], path[-1]
        degrees = math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180
        assert degrees == pytest.approx(30, abs=10)  # a wave's ends can be its height apart


def test_motif_pieces_under_half_a_repeat_are_left_out():
    # A U with 2 mm arms: what a row lays across an arm is under half of a 5 mm repeat.
    u_shape = _nodes([(0, 0), (2, 0), (2, 14), (18, 14), (18, 0), (20, 0), (20, 20), (0, 20)])
    recs = _recs("motif", u_shape, motif="wave", angle_deg=0, motif_mm=5, tie_in=False, tie_off=False)
    assert recs and min(y for _, y in _needles(recs)) > 11.9
    # With arms wide enough for half a repeat, they're sewn.
    wide = _nodes([(0, 0), (4, 0), (4, 14), (16, 14), (16, 0), (20, 0), (20, 20), (0, 20)])
    assert min(y for _, y in _needles(_recs("motif", wide, motif="wave", angle_deg=0, motif_mm=5))) < 1


def test_motif_fill_with_a_user_unit():
    # A bump one third as tall as it is long, drawn above its line (v < 0).
    unit = [[0, 0], [0.5, -0.33], [1, 0]]
    own = {"motif": "user:bump", "motif_unit": unit, "motif_mm": 6, "motif_width_mm": 2, "motif_stagger": 0}
    rows = _motif_rows(**own)
    full = [r for r in rows if max(y for _, y in r) - min(y for _, y in r) > 1.99]
    assert len(full) >= 10
    for r in full:
        top = min(y for _, y in r)  # the bumps point up
        assert max(y for _, y in r) - top == pytest.approx(2, abs=0.01)  # Height is how tall it sews
        tips = _peaks(r, top)
        assert [b - a for a, b in zip(tips, tips[1:])] == pytest.approx([6] * (len(tips) - 1), abs=0.01)
    # The carried unit is sewn, whatever the name says.
    assert _recs("motif", angle_deg=0, **own) == _recs("motif", angle_deg=0, **{**own, "motif": "wave"})
    assert _recs("motif", angle_deg=0, **own) != _recs("motif", angle_deg=0, motif="wave", motif_mm=6,
                                                        motif_width_mm=2, motif_stagger=0)
    _stays_inside(_fill("motif", STAR, **own, angle_deg=65))


def test_motif_fill_needs_a_known_motif():
    with pytest.raises(DigitizeError, match="^Unknown motif: user:gone$"):
        generate(_fill("motif", motif="user:gone"))
    with pytest.raises(DigitizeError, match="^Unknown motif: plaid$"):
        generate(_fill("motif", motif="plaid"))


def test_a_motif_that_would_need_too_many_stitches_is_refused():
    jagged = [[i / 199, (i % 2) - 0.5] for i in range(200)]
    jagged[0], jagged[-1] = [0, 0], [1, 0]
    huge = _nodes([(0, 0), (300, 0), (300, 300), (0, 300)])
    with pytest.raises(DigitizeError, match="far more than any design"):
        generate(_fill("motif", huge, motif="user:jagged", motif_unit=jagged, motif_mm=1.5, motif_width_mm=10,
                       motif_gap_mm=0))
    # One that loops far past its ends makes each row lay far more repeats than the shape holds.
    looping = [[0, 0], [900, -0.5], [-900, 0.5]] + [[(i % 2) * 0.5, 0.1] for i in range(100)] + [[1, 0]]
    with pytest.raises(DigitizeError, match="far more than any design"):
        generate(_fill("motif", motif="user:looping", motif_unit=looping, motif_mm=1.5))


def test_a_shape_too_small_for_a_motif_says_so():
    with pytest.raises(DigitizeError, match="too small for a motif fill"):
        generate(_fill("motif", _nodes([(0, 0), (1.5, 0), (1.5, 20), (0, 20)]), angle_deg=0, motif_mm=5))


def test_motif_settings_stay_in_mm_when_resized():
    """Twice the shape means twice the rows and repeats, each still Height tall, Row gap apart and
    Repeat long."""
    recs = _resized("motif", 2, motif="zigzag", angle_deg=0, motif_mm=5, motif_width_mm=4, motif_gap_mm=1,
                    motif_stagger=0)
    inside = [(x, y) for x, y, k in recs if k == STITCH and 1 < x < 39]
    # Eight rows 5 mm apart (4 mm tall, 1 mm between), from 0.5 to 39.5 in a 40 mm square: each
    # needle point is at a row's top, middle or bottom.
    assert all(min(abs((y - 0.5) % 5 - d) for d in (0, 2, 4, 5)) < 0.02 for _, y in inside)
    assert sorted({round(y, 2) for _, y in inside if abs((y - 0.5) % 5 - 4) < 0.02}) == [4.5 + 5 * k for k in range(8)]
    tips = sorted({round(x, 2) for x, y in inside if abs(y - 4.5) < 0.02})
    assert [b - a for a, b in zip(tips, tips[1:])] == pytest.approx([5] * (len(tips) - 1), abs=0.02)
    assert len(tips) == 8


# ---------------------------------------------------------------- maze


def _maze_line(recs):
    return LineString(_needles(recs))


SIMPLE_MAZES = [("square", 2), ("square", 0.8), ("square", 1.2), ("square", 3), ("square", 6), ("circle", 2),
                ("circle", 0.8), ("star", 2), ("star", 1.2), ("triangle", 2), ("l_shape", 2), ("heart", 2),
                ("heart", 1.4)]


@pytest.mark.parametrize("name,spacing", SIMPLE_MAZES)
def test_maze_is_one_path_that_never_crosses(name, spacing):
    obj = _fill("maze", *SHAPES[name], maze_mm=spacing, tie_in=False, tie_off=False)
    recs, warnings = generate(obj)
    invariants.assert_sane(recs, inside=_shape_of(obj), tolerance_mm=0.3, max_jumps=0, max_trims=0)
    assert _maze_line(recs).is_simple
    assert warnings == []


@pytest.mark.parametrize("name,spacing", SIMPLE_MAZES)
def test_maze_starts_and_ends_at_the_edge(name, spacing):
    obj = _fill("maze", *SHAPES[name], maze_mm=spacing, tie_in=False, tie_off=False)
    pts = _needles(generate(obj)[0])
    edge = _shape_of(obj).exterior
    for end in (pts[0], pts[-1]):
        assert edge.distance(Point(end)) <= spacing


@pytest.mark.parametrize("spacing", [2, 3, 1.5])
@pytest.mark.parametrize("degrees", [7, 83, 97, 187])
def test_maze_spacing(spacing, degrees):
    """Neighboring turns are Path spacing apart, along a ray from the middle (the seam is at the
    top of a square)."""
    recs = _recs("maze", maze_mm=spacing, tie_in=False, tie_off=False)
    middle = (20.0, 20.0)
    a = math.radians(degrees)
    ray = LineString([middle, (middle[0] + 30 * math.cos(a), middle[1] + 30 * math.sin(a))])
    hits = []
    for seg in _threads(recs):
        cross = ray.intersection(LineString(seg))
        if not cross.is_empty:
            hits += [math.dist(middle, (p.x, p.y)) for p in getattr(cross, "geoms", [cross]) if p.geom_type == "Point"]
    hits.sort()
    rings = [h for i, h in enumerate(hits) if i == 0 or h - hits[i - 1] > 0.05]
    assert len(rings) >= int(20 / spacing) - 1, rings
    gaps = [b - a for a, b in zip(rings, rings[1:])]
    assert all(abs(gap - spacing) <= 0.3 for gap in gaps), gaps


@pytest.mark.parametrize("name,least", [("square", 0.97), ("circle", 0.97), ("heart", 0.93), ("star", 0.85)])
def test_maze_fills_the_shape(name, least):
    obj = _fill("maze", *SHAPES[name], maze_mm=2)
    assert invariants.coverage(generate(obj)[0], _shape_of(obj), 1.3) >= least


@pytest.mark.parametrize("neck", [1.0, 3.0])  # gone at the first ring, or further in
def test_branched_shape_warns(neck):
    warnings = generate(_fill("maze", _beads(5, neck), maze_mm=2))[1]
    assert warnings == [BRANCHED]
    assert generate(_fill("maze", _beads(4, neck), maze_mm=2))[1] == []  # four pieces: fine


def test_a_shape_with_a_hole_is_branched():
    obj = _fill("maze", SQUARE, [HOLE], maze_mm=2, tie_in=False, tie_off=False)
    recs, warnings = generate(obj)
    assert warnings == [BRANCHED]
    invariants.assert_sane(recs, inside=_shape_of(obj), tolerance_mm=0.3, max_jumps=0, max_trims=0)
    poly = fill_parts(SQUARE, [HOLE])[0]
    paths = fills.get("maze").paths(poly, FillParams.from_dict(obj["params"]), (0.0, 0.0))[0]
    assert len(paths) > 1  # several mazes
    # ...and nothing crosses: not a maze itself, nor the travel from one to the next.
    assert _crossings(recs) == 0


def test_a_neck_further_in_still_makes_one_path():
    """Two lobes joined by a neck that only the inner rings pinch off: each lobe gets its own
    maze, reached from the ring around them, without a jump or a crossing."""
    obj = _fill("maze", _beads(3, 3.0), maze_mm=2, tie_in=False, tie_off=False)
    recs, warnings = generate(obj)
    assert warnings == []
    invariants.assert_sane(recs, inside=_shape_of(obj), tolerance_mm=0.3, max_jumps=0, max_trims=0)
    assert _maze_line(recs).is_simple
    for k in range(3):  # every lobe is sewn, in to its middle
        assert any(math.dist(p, (13 * k + 5, 5)) < 2.1 for p in _needles(recs)), k


@pytest.mark.parametrize("beads", [2, 4])
def test_pieces_apart_from_the_first_ring_are_joined_inside_the_shape(beads):
    obj = _fill("maze", _beads(beads, 1.0), maze_mm=2, tie_in=False, tie_off=False)
    recs, warnings = generate(obj)
    assert warnings == []
    invariants.assert_sane(recs, inside=_shape_of(obj), tolerance_mm=0.3, max_jumps=0, max_trims=0)
    assert _crossings(recs) == 0


def test_the_branched_warning_is_said_once():
    bowtie = _nodes([(0, 0), (40, 40), (40, 0), (0, 40)])  # two pieces, each fine on its own
    assert generate(_fill("maze", bowtie, maze_mm=2))[1] == []
    # A hole right across a long shape cuts it in two, and each half has a hole of its own.
    long_shape = _nodes([(0, 0), (60, 0), (60, 20), (0, 20)])
    holes = [_nodes([(29, -2), (31, -2), (31, 22), (29, 22)]), _nodes([(10, 6), (18, 6), (18, 14), (10, 14)]),
             _nodes([(42, 6), (50, 6), (50, 14), (42, 14)])]
    assert len(fill_parts(long_shape, holes)) == 2
    assert generate(_fill("maze", long_shape, holes, maze_mm=2))[1] == [BRANCHED]


@pytest.mark.parametrize("dot", [(40, 20), (0, 33), (11, 40)])
def test_maze_starts_by_the_green_dot(dot):
    first = _needles(_recs("maze", maze_mm=2, start_mm=list(dot)))[0]
    assert math.dist(first, dot) <= 4
    obj = _fill("maze", maze_mm=2, start_mm=list(dot), tie_in=False, tie_off=False)
    assert _maze_line(generate(obj)[0]).is_simple


def test_a_shape_too_small_for_a_maze_says_so():
    with pytest.raises(DigitizeError, match="too small for a maze fill"):
        generate(_fill("maze", _nodes([(0, 0), (40, 0), (40, 1.5), (0, 1.5)]), maze_mm=2))


def test_maze_spacing_stays_in_mm_when_resized():
    recs = _resized("maze", 2, maze_mm=2)  # a 40 mm square now
    ray = LineString([(20, 20), (41, 22.3)])
    hits = sorted(math.dist((20, 20), (p.x, p.y)) for seg in _threads(recs)
                  for p in [ray.intersection(LineString(seg))] if p.geom_type == "Point")
    rings = [h for i, h in enumerate(hits) if i == 0 or h - hits[i - 1] > 0.05]
    assert len(rings) >= 9 and all(abs(b - a - 2) <= 0.3 for a, b in zip(rings, rings[1:])), rings


# ---------------------------------------------------------------- ripple


def _off_ring(p, center, spacing):
    """How far a point is from the nearest ring."""
    d = math.dist(p, center)
    return abs(d - spacing * round(d / spacing))


def _inner_needles(recs, shape, margin=1.0):
    inner = shape.buffer(-margin)
    return [p for p in _needles(recs) if inner.contains(Point(p))]


@pytest.mark.parametrize("spacing", [2, 3, 0.8])
def test_ripple_rings_are_circles_about_the_center(spacing):
    obj = _fill("ripple", ripple_mm=spacing, tie_in=False, tie_off=False)
    recs = generate(obj)[0]
    inside = _inner_needles(recs, _shape_of(obj))
    assert len(inside) > 100
    assert max(_off_ring(p, (20, 20), spacing) for p in inside) <= 0.15
    # Every ring out to the corners is there.
    rings = {round(math.dist(p, (20, 20)) / spacing) for p in _needles(recs)}
    assert set(range(1, int(26 / spacing) + 1)) <= rings


def test_ripple_chords_stay_close_to_their_circles():
    recs = _recs("ripple", ripple_mm=2, tie_in=False, tie_off=False)
    shape = _shape_of(_fill("ripple"))
    inner = shape.buffer(-1.2)
    for a, b in _threads(recs):
        ra, rb = math.dist(a, (20, 20)), math.dist(b, (20, 20))
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if abs(ra - rb) < 0.5 and inner.contains(Point(mid)):
            assert (ra + rb) / 2 - math.dist(mid, (20, 20)) <= 0.101


def test_ripple_center_can_be_set():
    obj = _fill("ripple", ripple_mm=2, ripple_center=[10, 12], tie_in=False, tie_off=False)
    inside = _inner_needles(generate(obj)[0], _shape_of(obj))
    assert len(inside) > 150
    assert max(_off_ring(p, (10, 12), 2) for p in inside) <= 0.15


def test_ripple_starts_where_spiral_would():
    poly = fill_parts(L_SHAPE)[0]
    middle = spiral._middle(poly)
    obj = _fill("ripple", L_SHAPE, ripple_mm=2, tie_in=False, tie_off=False)
    recs = generate(obj)[0]
    inside = _inner_needles(recs, _shape_of(obj))
    assert max(_off_ring(p, middle, 2) for p in inside) <= 0.15
    assert math.dist(_needles(recs)[0], middle) == pytest.approx(2, abs=0.01)  # on the first ring


@pytest.mark.parametrize("name", ["square", "circle", "star", "donut", "l_shape"])
def test_ripple_is_sewn_from_the_center_out(name):
    """The whole rings first, from the middle out; then each part of the shape the cut rings reach
    into, outward in turn."""
    obj = _fill("ripple", *SHAPES[name], ripple_mm=2, tie_in=False, tie_off=False)
    recs = generate(obj)[0]
    poly = _shape_of(obj)
    center = spiral._middle(poly)
    whole = [k for k in range(1, 30) if poly.buffer(0.01).covers(Point(center).buffer(2 * k, 64).exterior)]
    seen = [round(math.dist(p, center) / 2) for p in _inner_needles(recs, poly)
            if _off_ring(p, center, 2) <= 0.1]
    first_cut = next((i for i, k in enumerate(seen) if k not in whole), len(seen))
    assert whole and seen[:first_cut] == sorted(seen[:first_cut]) and set(seen[:first_cut]) == set(whole)
    assert math.dist(_needles(recs)[0], center) == pytest.approx(2, abs=0.01)  # begun on the first ring


@pytest.mark.parametrize("name", ["square", "circle", "star", "donut", "l_shape", "heart"])
def test_ripple_joins_keep_to_the_edges(name):
    obj = _fill("ripple", *SHAPES[name], ripple_mm=2, tie_in=False, tie_off=False)
    recs = generate(obj)[0]
    poly = _shape_of(obj)
    center = spiral._middle(poly)
    inner = poly.buffer(-1.2)
    across = 0.0
    for a, b in _threads(recs):
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        step = math.dist(a, b) <= 2.3 and abs(abs(math.dist(a, center) - math.dist(b, center)) - 2) < 0.2
        if not step and _off_ring(mid, center, 2) > 0.3 and inner.contains(Point(mid)):
            across += math.dist(a, b)
    assert across < 1.0
    invariants.assert_sane(recs, inside=poly, tolerance_mm=0.3, max_jumps=0, max_trims=0)


def test_ripple_about_a_point_outside_the_shape():
    obj = _fill("ripple", ripple_mm=2, ripple_center=[-15, 20], tie_in=False, tie_off=False)
    recs = generate(obj)[0]
    inside = _inner_needles(recs, _shape_of(obj))
    assert max(_off_ring(p, (-15, 20), 2) for p in inside) <= 0.15
    invariants.assert_sane(recs, inside=_shape_of(obj), tolerance_mm=0.3, max_jumps=0, max_trims=0)


def test_a_ripple_center_absurdly_far_away_is_refused():
    with pytest.raises(DigitizeError, match="ripple"):
        generate(_fill("ripple", ripple_center=[1e7, 20]))


def test_a_ripple_center_that_moves_with_the_shape():
    obj = _fill("ripple", ripple_center=[3, 7])
    invariants.assert_moves_with_shape(obj, 11.3, -4.9)
    moved = dz.transform_geometry(obj, layout.Transform.from_dict({"x": 11.3, "y": -4.9}), (0, 0))
    assert moved["params"]["ripple_center"] == pytest.approx([14.3, 2.1])


def test_ripple_spacing_stays_in_mm_when_resized():
    recs = _resized("ripple", 2, ripple_mm=2)
    inside = [(x, y) for x, y, k in recs if k == STITCH and 1 < x < 39 and 1 < y < 39]
    assert len(inside) > 200 and max(_off_ring(p, (20, 20), 2) for p in inside) <= 0.15


# ---------------------------------------------------------------- mesh


def _inner_threads(recs, shape, margin=1.0, longer=0.5):
    inner = shape.buffer(-margin)
    return [(a, b) for a, b in _threads(recs)
            if math.dist(a, b) > longer and inner.contains(Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))]


def _degrees(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180


def _near(degrees, want):
    return min((degrees - want) % 180, (want - degrees) % 180)


@pytest.mark.parametrize("angle,cross", [(45, 90), (10, 60), (0, 45), (155, 75)])
def test_mesh_has_two_directions(angle, cross):
    obj = _fill("mesh", angle_deg=angle, mesh_cross_deg=cross, tie_in=False, tie_off=False)
    found = [_degrees(a, b) for a, b in _inner_threads(generate(obj)[0], _shape_of(obj))]
    first = sum(1 for d in found if _near(d, angle) < 0.5)
    second = sum(1 for d in found if _near(d, angle + cross) < 0.5)
    assert first > 50 and second > 50
    assert first + second == len(found), sorted({round(d) for d in found})


@pytest.mark.parametrize("cell,cross", [(3, 90), (5, 60), (1.5, 90), (7.5, 75)])
def test_mesh_cell_size(cell, cross):
    obj = _fill("mesh", angle_deg=20, mesh_mm=cell, mesh_cross_deg=cross, tie_in=False, tie_off=False)
    inner = _inner_threads(generate(obj)[0], _shape_of(obj))
    for direction in (20, 20 + cross):
        a = math.radians(direction)
        normal = (-math.sin(a), math.cos(a))
        offsets = sorted(round(((p[0] + q[0]) / 2) * normal[0] + ((p[1] + q[1]) / 2) * normal[1], 2)
                         for p, q in inner if _near(_degrees(p, q), direction) < 0.5)
        lines_at = [o for i, o in enumerate(offsets) if i == 0 or o - offsets[i - 1] > 0.05]
        assert len(lines_at) >= 40 / cell - 2
        assert [b - a for a, b in zip(lines_at, lines_at[1:])] == pytest.approx([cell] * (len(lines_at) - 1), abs=0.03)


def test_mesh_sews_each_set_back_and_forth():
    paths = _paths("mesh", angle_deg=0, mesh_mm=3)
    runs = [(a, b) for path in paths for a, b in zip(path, path[1:]) if math.dist(a, b) > 1]
    first_set = []
    for a, b in runs:
        if _near(_degrees(a, b), 0) < 1 and 1 < (a[1] + b[1]) / 2 < 39:
            way = 1 if b[0] > a[0] else -1
            if not first_set or abs(first_set[-1][1] - a[1]) > 1:
                first_set.append((way, a[1]))
    ways = [w for w, _ in first_set]
    assert len(ways) >= 11 and all(a == -b for a, b in zip(ways, ways[1:]))


@pytest.mark.parametrize("name", ["square", "circle", "l_shape", "donut", "star"])
def test_mesh_joins_keep_to_the_edges(name):
    obj = _fill("mesh", *SHAPES[name], angle_deg=30, mesh_cross_deg=70, tie_in=False, tie_off=False)
    recs = generate(obj)[0]
    shape = _shape_of(obj)
    across = sum(math.dist(a, b) for a, b in _inner_threads(recs, shape, longer=0)
                 if _near(_degrees(a, b), 30) > 1 and _near(_degrees(a, b), 100) > 1)
    assert across < 1.0
    invariants.assert_sane(recs, inside=shape, tolerance_mm=0.3)


def test_mesh_cell_stays_in_mm_when_resized():
    recs = _resized("mesh", 2, angle_deg=0, mesh_mm=3)
    ys = sorted({round((a[1] + b[1]) / 2, 1) for a, b in _threads(recs)
                 if _near(_degrees(a, b), 0) < 0.5 and 2 < (a[0] + b[0]) / 2 < 38 and 1 < (a[1] + b[1]) / 2 < 39
                 and math.dist(a, b) > 1})
    assert len(ys) >= 12 and [b - a for a, b in zip(ys, ys[1:])] == pytest.approx([3] * (len(ys) - 1), abs=0.11)


# ---------------------------------------------------------------- snapshots


_BUMP = [[0, 0], [0.2, -0.28], [0.5, -0.4], [0.8, -0.28], [1, 0]]


def _at(outline, dx=7.0, dy=11.0):
    return [[x + dx, y + dy, k] for x, y, k in outline]


SNAPSHOT_CASES = {
    "motif_wave": _fill("motif", _at(SQUARE), angle_deg=30, motif="wave", underlay="auto"),
    "motif_user": _fill("motif", _at(CIRCLE), angle_deg=45, motif="user:bump", motif_unit=_BUMP, motif_mm=6,
                        motif_width_mm=2.5, motif_gap_mm=1, motif_stagger=0.25, underlay="auto"),
    "maze_square": _fill("maze", _at(SQUARE), maze_mm=2, underlay="auto"),
    "maze_star": _fill("maze", _at(STAR), maze_mm=2, underlay="auto"),
    "ripple_square": _fill("ripple", _at(SQUARE), underlay="auto"),
    "mesh_90": _fill("mesh", _at(SQUARE), angle_deg=45, mesh_mm=3, underlay="auto"),
    "mesh_60": _fill("mesh", _at(SQUARE), angle_deg=0, mesh_mm=4, mesh_cross_deg=60, underlay="auto"),
}


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshots(name):
    check("fills_decorative", name, digest_recs_steady(generate(SNAPSHOT_CASES[name])[0]))


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_snapshots_do_not_hang_on_the_last_digit_of_a_sine(seed, monkeypatch):
    """Every snapshot case gives its recorded stitches with the last digit of each sine and cosine
    nudged, as another computer's maths library might give it (snapshot_util)."""
    recorded = json.loads((SNAPSHOT_DIR / "fills_decorative.json").read_text(encoding="utf-8"))
    forget_stitches()
    try:
        nudge_trig(monkeypatch, seed, dz, patterns, spiral, motif, maze, ripple, mesh, rotations=True)
        for name in sorted(SNAPSHOT_CASES):
            assert digest_recs_steady(generate(SNAPSHOT_CASES[name])[0]) == recorded[name], name
    finally:
        monkeypatch.undo()
        forget_stitches()  # nothing worked out with the nudged maths may reach another test


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshot_cases_are_sane(name):
    obj = SNAPSHOT_CASES[name]
    _stays_inside(obj)
    invariants.assert_deterministic(lambda: generate(obj)[0])
    invariants.assert_moves_with_shape(obj, 3.3, -8.1)
