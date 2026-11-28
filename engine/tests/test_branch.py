"""Branching (P7-B1, P7-B2): shapes in one thread sewn as one path, with one start and one end.

`showing()` is the measure of connecting thread that shows (the audit can rerun it): every joining
stitch and move the planner adds, sampled every 0.1 mm, that lies within 0.25 mm of stitching sewn
earlier and has no later stitching within 0.25 mm. `test_thread_that_shows_on_random_branches`
prints it for 120 seeded random branches (run with -s)."""

import json
import math
import random
import statistics
import time

import pyembroidery as pe
import pytest
import shapely
from shapely.geometry import LineString, Point, Polygon

from invariants import assert_sane
from snapshot_util import SNAPSHOT_DIR, check, digest_pattern_steady
from steady_util import forget_stitches, nudge_trig
from threadline_engine import layout as L
from threadline_engine import project
from threadline_engine.digitize import stitches as dz
from threadline_engine.layout import branch
from threadline_engine.methods import dispatcher

I = {"x": 0, "y": 0, "rotate": 0, "scale_x": 1, "scale_y": 1, "flip_x": False, "flip_y": False}
RED = {"color": "#cc2222", "name": "Red", "catalog": "", "brand": ""}
BLUE = {"color": "#2222cc", "name": "Blue", "catalog": "", "brand": ""}
M = pe.COMMAND_MASK


def obj(i, kind, geometry, thread=RED, params=None, br="b1", **extra):
    it = {"id": i, "kind": kind, "geometry": geometry, "params": params or {}, "thread": thread, "transform": I,
          "threads": [], "ops": [], **extra}
    if br:
        it["branch"] = br
    return it


def sq(x, y, w, h=None):
    h = w if h is None else h
    return [[x, y, "c"], [x + w, y, "c"], [x + w, y + h, "c"], [x, y + h, "c"]]


def circle(cx, cy, r, n=24):
    return [[cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n), "c"] for k in range(n)]


def fill(i, x, y, w, h=None, **kw):
    return obj(i, "fill", {"outline": sq(x, y, w, h)}, **kw)


def lay(*items, **extra):
    return {"version": 1, "items": list(items), **extra}


def recs_of(r):
    """The rendered pattern as (x mm, y mm, command, item) records."""
    return [(x / 10, y / 10, k & M, it) for (x, y, k), it in zip(r.pattern.stitches, r.item_of)]


def between_first_and_last(recs, members):
    """The records from the first stitch of `members` (item indices) to the last."""
    on = [n for n, (_, _, k, it) in enumerate(recs) if k == pe.STITCH and it in members]
    return recs[on[0]:on[-1] + 1]


def cuts_in(recs):
    return sum(1 for r in recs if r[2] in (pe.JUMP, pe.TRIM, pe.COLOR_CHANGE))


@pytest.fixture(autouse=True)
def _fresh():
    branch.forget()
    yield
    branch.forget()


# ---------------------------------------------------------------- done-when 3


THREE_TOUCHING = {
    "edges": [fill("a", 0, 0, 10), fill("b", 10, 0, 10), fill("c", 20, 0, 10)],
    "overlap": [fill("a", 0, 0, 12), fill("b", 9, 2, 12), fill("c", 18, 0, 12)],
    "corners": [fill("a", 0, 0, 10), fill("b", 10, 10, 10), fill("c", 20, 20, 10)],
}


@pytest.mark.parametrize("case", sorted(THREE_TOUCHING))
def test_three_touching_squares_sew_as_one_path(case):
    layout = lay(*THREE_TOUCHING[case])
    r = L.render(layout)
    assert len(r.blocks) == 1
    recs = recs_of(r)
    span = between_first_and_last(recs, {0, 1, 2})
    assert cuts_in(span) == 0, [x for x in span if x[2] != pe.STITCH]
    assert_sane([(x, y, k) for x, y, k, _ in recs if k != pe.END])
    assert [b["items"] for b in r.branches] == [["a", "b", "c"]] and r.branches[0]["cuts"] == 0


@pytest.mark.parametrize("case", sorted(THREE_TOUCHING))
def test_the_branch_command_sews_one_path_into_the_pes_file(case, tmp_path):
    """The whole way the user goes: Branch (layout.branch_plan, its order applied and the branch
    ids set, as the app commits it), render, export to PES and read the file back."""
    shapes = [{k: v for k, v in it.items() if k != "branch"} for it in THREE_TOUCHING[case]]
    blue = obj("x", "fill", {"outline": sq(60, 0, 10)}, thread=BLUE, br=None)
    # Listed with another shape between them, which doesn't overlap them: the command moves it.
    layout = lay(shapes[0], blue, shapes[1], shapes[2])

    def call(method, **params):
        out = dispatcher.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}))
        assert "error" not in out, out
        return out["result"]

    plan = call("layout.branch_plan", layout=layout, ids=["a", "b", "c"])
    assert plan["ok"] and plan["order"] == ["a", "b", "c", "x"], plan
    by_id = {it["id"]: it for it in layout["items"]}
    branched = lay(*[{**by_id[i], **({"branch": "n1"} if i != "x" else {})} for i in plan["order"]])
    summary = call("layout.render", layout=branched)
    assert summary["branches"][0]["items"] == ["a", "b", "c"]
    dest = tmp_path / "three.pes"
    call("layout.export", layout=branched, dest=str(dest))
    back = pe.read(str(dest))
    first_color = []
    for x, y, k in back.stitches:
        if k & M in (pe.COLOR_CHANGE, pe.STOP, pe.END) and any(c == pe.STITCH for *_, c in first_color):
            break
        first_color.append((x / 10, y / 10, k & M))
    sewn = [n for n, r in enumerate(first_color) if r[2] == pe.STITCH]
    span = first_color[sewn[0]:sewn[-1] + 1]
    assert not [r for r in span if r[2] != pe.STITCH], "a jump or trim inside the branch in the PES file"
    pts = [(x, y) for x, y, k in span]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    width = max(xs) - min(xs)
    assert width > 28  # all three shapes are in that one run (each is 10 or 12 mm wide)


# ---------------------------------------------------------------- the measure of thread that shows


def _segments(recs):
    """Each stitched segment: (index of its end record, start, end, connecting?)."""
    out = []
    prev = None  # (index, x, y, item)
    cut = False
    for n, (x, y, k, it) in enumerate(recs):
        if k == pe.TRIM or k == pe.COLOR_CHANGE:
            cut = True
        if k != pe.STITCH:
            continue
        if prev is not None and not cut:
            joining = prev[3] < 0 or it < 0 or prev[3] != it
            if math.dist(prev[1:3], (x, y)) > 1e-9:
                out.append((n, prev[1:3], (x, y), joining))
        prev, cut = (n, x, y, it), False
    return out


def showing(layout):
    """For each branch: {"shows_mm", "deep_mm", "cuts", "hidden_mm"}. Connecting thread is every
    stitch segment between two members, or to or from a stitch that belongs to no item, inside the
    branch's span; "shows" counts its 0.1 mm samples lying within 0.25 mm of stitching sewn earlier
    with no later (non-connecting) stitching within 0.25 mm; "deep" the part of that more than
    0.5 mm inside the members' outlines."""
    r = L.render(layout)
    recs = recs_of(r)
    segs = _segments(recs)
    own = [s for s in segs if not s[3]]
    tree = shapely.STRtree([LineString([a, b]) for _, a, b, _ in own])
    ends = [n for n, *_ in own]
    out = []
    items = layout["items"]
    for info in r.branches:
        idx = {i for i, it in enumerate(items) if str(it.get("id")) in info["items"]}
        on = [n for n, (_, _, k, it) in enumerate(recs) if k == pe.STITCH and it in idx]
        lo, hi = on[0], on[-1]
        shapes = [m.shape for i in sorted(idx) if (m := branch._member(i, items[i])) is not None
                  and m.shape.geom_type != "LineString"]
        inside = shapely.union_all(shapes).buffer(-0.5) if shapes else Polygon()
        shows = deep = 0.0
        for n, a, b, joining in segs:
            if not joining or not lo < n <= hi:
                continue
            length = math.dist(a, b)
            steps = max(1, math.ceil(length / 0.1))
            for s in range(steps):
                t = (s + 0.5) / steps
                p = Point(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                near = [ends[k] for k in tree.query(p, predicate="dwithin", distance=0.25)]
                if any(e < n for e in near) and not any(e > n for e in near):
                    shows += length / steps
                    if inside.covers(p):
                        deep += length / steps
        out.append({"shows_mm": round(shows, 2), "deep_mm": round(deep, 2), "cuts": info["cuts"],
                    "hidden_mm": info["hidden_mm"]})
    return out


def test_thread_that_shows_on_three_touching_shapes():
    for case in sorted(THREE_TOUCHING):
        (m,) = showing(lay(*THREE_TOUCHING[case]))
        print(case, m)
        assert m["cuts"] == 0
        assert m["shows_mm"] <= 1.5, (case, m)
        assert m["deep_mm"] <= 0.5, (case, m)


def test_the_measure_sees_thread_left_on_finished_stitching(monkeypatch):
    """The measure itself: a join sewn straight back across the shape just finished shows."""
    layout = lay(fill("a", 0, 0, 10, params={"end_mm": [0, 5]}), fill("b", 10, 0, 10))
    real = branch._entered
    monkeypatch.setattr(branch, "_entered", lambda m, prev, nxt: (m.item, None) if m.idx == 0 else real(m, prev, nxt))
    monkeypatch.setattr(branch, "_join", lambda a, b, zone: ("on", [a, b]))
    (m,) = showing(layout)
    assert m["shows_mm"] > 8 and m["deep_mm"] > 7, m


def _random_member(rng, i, x, y):
    kind = rng.choice(("square", "circle", "line", "ribbon"))
    size = rng.uniform(6, 16)
    if kind == "square":
        return obj(f"m{i}", "fill", {"outline": sq(x, y - size / 2, size)}), size
    if kind == "circle":
        return obj(f"m{i}", "fill", {"outline": circle(x + size / 2, y, size / 2)}), size
    a = rng.uniform(-0.6, 0.6)
    nodes = [[x, y, "c"], [x + size * math.cos(a), y + size * math.sin(a), "c"]]
    if rng.random() < 0.5:
        nodes = nodes[::-1]
    if kind == "line":
        return obj(f"m{i}", "run", {"nodes": nodes}), size * math.cos(a)
    return obj(f"m{i}", "satin", {"nodes": nodes, "width_mm": rng.uniform(2, 4)}), size * math.cos(a)


def random_branches(seed=7, count=120):
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        items, x = [], 0.0
        for i in range(rng.randint(3, 6)):
            it, w = _random_member(rng, i, x, rng.uniform(-3, 3))
            items.append(it)
            x += w + rng.choice((0.0, 0.0, -2.0, -4.0, 2.0, 6.0))  # touching, overlapping, apart
        rng.shuffle(items)
        out.append(lay(*items))
    return out


def test_thread_that_shows_on_random_branches():
    found = [m for layout in random_branches() for m in showing(layout)]
    shows = [m["shows_mm"] for m in found]
    print(f"\n{len(found)} branches: shows total {sum(shows):.1f} mm, median {statistics.median(shows):.2f}, "
          f"worst {max(shows):.2f}; more than 0.5 mm inside {sum(m['deep_mm'] for m in found):.1f} mm, "
          f"worst {max(m['deep_mm'] for m in found):.2f}; cuts {sum(m['cuts'] for m in found)}; "
          f"hidden travel {sum(m['hidden_mm'] for m in found):.1f} mm")
    assert len(found) >= 100
    assert statistics.median(shows) <= 1.0


# ---------------------------------------------------------------- the order


def _sewn_ids(r):
    return r.branches[0]["items"]


def test_order_is_the_shortest():
    xs = [26, 0, 39, 13]  # four squares 3 mm apart, listed out of order
    r = L.render(lay(*[fill(f"s{x}", x, 0, 10) for x in xs]))
    assert _sewn_ids(r) in (["s0", "s13", "s26", "s39"], ["s39", "s26", "s13", "s0"])


def test_overlapping_members_keep_their_layering():
    xs = [16, 0, 24, 8]  # four squares overlapping their neighbours, listed out of order
    items = [fill(f"s{x}", x, 0, 10) for x in xs]
    r = L.render(lay(*items))
    sewn = _sewn_ids(r)
    for p, q in ((0, 8), (8, 16), (16, 24)):
        a, b = f"s{p}", f"s{q}"
        listed = [it["id"] for it in items]
        assert (sewn.index(a) < sewn.index(b)) == (listed.index(a) < listed.index(b)), (a, b, sewn)


def test_branch_start_and_end_are_honored():
    items = [fill("a", 0, 0, 10), fill("b", 13, 0, 10), fill("c", 26, 0, 10)]
    layout = lay(*items, branches={"b1": {"start_mm": [36, 5], "end_mm": [0, 5]}})
    r = L.render(layout)
    pts = [(x, y) for x, y, k, it in recs_of(r) if k == pe.STITCH]
    assert _sewn_ids(r) == ["c", "b", "a"]
    assert math.dist(pts[0], (36, 5)) <= 1.5 and math.dist(pts[-1], (0, 5)) <= 1.5, (pts[0], pts[-1])


def test_open_lines_are_turned_to_shorten_moves():
    items = [obj("a", "run", {"nodes": [[20, 0, "c"], [0, 0, "c"]]}),
             obj("b", "run", {"nodes": [[40, 0, "c"], [20.6, 0, "c"]]})]
    for dots in ({}, {"branches": {"b1": {"start_mm": [0, 0], "end_mm": [40, 0]}}}):
        r = L.render(lay(*items, **dots))
        recs = recs_of(r)
        pts = [(x, y) for x, y, k, it in recs if k == pe.STITCH]
        assert math.dist(pts[0], (0, 0)) <= 1.5 and math.dist(pts[-1], (40, 0)) <= 1.5, (pts[0], pts[-1])
        assert cuts_in(between_first_and_last(recs, {0, 1})) == 0


def test_a_resized_member_is_planned_at_the_size_that_sews():
    # Drawn 3 mm from the first square, B touches it once resized to twice its width.
    b = fill("b", 13, 0, 6, 10)
    b["transform"] = {**I, "scale_x": 2}
    r = L.render(lay(fill("a", 0, 0, 10), b))
    recs = recs_of(r)
    assert cuts_in(between_first_and_last(recs, {0, 1})) == 0
    first_b = next((x, y) for x, y, k, it in recs if k == pe.STITCH and it == 1)
    assert first_b[0] < 11.0, first_b


# ---------------------------------------------------------------- joins


def test_join_runs_under_a_later_shape():
    blue = obj("x", "fill", {"outline": sq(-2, -2, 34, 14)}, thread=BLUE, br=None)
    layout = lay(fill("a", 0, 0, 10), fill("b", 20, 0, 10), blue)
    r = L.render(layout)
    recs = recs_of(r)
    span = between_first_and_last(recs, {0, 1})
    assert cuts_in(span) == 0
    join = [(x, y) for x, y, k, it in span if it == -1]
    assert join and all(k == pe.STITCH for x, y, k, it in span if it == -1)
    assert sum(1 for p in join if 10.5 < p[0] < 19.5) >= 3  # it crosses the gap
    cover = L._cover(next(b for b in r.blocks if b.thread["color"] == BLUE["color"]))
    for p in join:
        assert cover.distance(Point(p)) <= branch.REACH_MM + 1e-6, p
    assert r.branches[0]["hidden_mm"] > 9


def test_no_hidden_way_is_a_cut_with_a_note():
    r = L.render(lay(fill("a", 0, 0, 10), fill("b", 20, 0, 10)))
    span = between_first_and_last(recs_of(r), {0, 1})
    assert sum(1 for x in span if x[2] == pe.TRIM) == 1 and sum(1 for x in span if x[2] == pe.JUMP) == 1
    notes = [w for w in r.warnings if w["code"].startswith("branch_")]
    assert len(notes) == 1 and "Fill 1" in notes[0]["message"] and "Fill 2" in notes[0]["message"]
    assert "cut" in notes[0]["message"] and r.branches[0]["cuts"] == 1


def test_a_short_gap_jumps_and_says_so():
    r = L.render(lay(fill("a", 0, 0, 10), fill("b", 12.5, 0, 10)))
    span = between_first_and_last(recs_of(r), {0, 1})
    assert sum(1 for x in span if x[2] == pe.TRIM) == 0 and sum(1 for x in span if x[2] == pe.JUMP) == 1
    (note,) = [w for w in r.warnings if w["code"].startswith("branch_")]
    assert "jumps" in note["message"] and r.branches[0]["cuts"] == 0


def _stitch_count(item, idx=0):
    blocks = L._object_blocks(item, idx)[0]
    return sum(1 for b in blocks for r in b.recs if r[2] == pe.STITCH)


def _sewn_count(r, idx):
    return sum(1 for x, y, k, it in recs_of(r) if k == pe.STITCH and it == idx)


def test_inner_locks_are_left_out_where_the_thread_runs_on():
    layout = lay(*THREE_TOUCHING["edges"])
    r = L.render(layout)
    prepared = branch.prepared_items(layout)
    full = [_stitch_count(prepared[i], i) for i in range(3)]
    # Each lock is two stitches: the ends keep their outer lock, the middle one has none.
    assert [_sewn_count(r, i) for i in range(3)] == [full[0] - 2, full[1] - 4, full[2] - 2]


def test_locks_stay_round_a_cut():
    layout = lay(fill("a", 0, 0, 10), fill("b", 20, 0, 10))
    r = L.render(layout)
    prepared = branch.prepared_items(layout)
    assert [_sewn_count(r, i) for i in range(2)] == [_stitch_count(prepared[i], i) for i in range(2)]


# ---------------------------------------------------------------- who is in a branch


def test_other_threads_and_appliques_are_left_out_with_a_note():
    blend = fill("e", 50, 0, 10, params={"pattern": "blend", "blend": [dict(BLUE)]})
    items = [fill("a", 0, 0, 10), fill("b", 10, 0, 10), fill("c", 20, 0, 10, thread=BLUE),
             obj("d", "applique", {"outline": sq(30, 0, 10)}), blend]
    r = L.render(lay(*items))
    codes = sorted(w["code"] for w in r.warnings if w["code"].startswith("branch_"))
    assert codes == ["branch_applique_3", "branch_blend_4", "branch_thread_2"]
    for w in r.warnings:
        if w["code"].startswith("branch_"):
            assert "Alt+Shift+U" in w["message"]
    assert [b["items"] for b in r.branches] == [["a", "b"]]


def test_a_member_sewn_apart_starts_a_path_of_its_own():
    items = [fill("a", 0, 0, 10), fill("b", 10, 0, 10), fill("x", 40, 0, 5, thread=BLUE, br=None),
             fill("c", 20, 0, 10)]
    r = L.render(lay(*items))
    (note,) = [w for w in r.warnings if w["code"].startswith("branch_")]
    assert note["code"] == "branch_apart_3" and "Fill 4" in note["message"] and "Fill 1" in note["message"]
    assert [b["items"] for b in r.branches] == [["a", "b"]]


def test_a_branch_of_one_is_ignored():
    alone = lay(fill("a", 0, 0, 10), fill("b", 20, 0, 10, br="b2"))
    plain = lay(fill("a", 0, 0, 10, br=None), fill("b", 20, 0, 10, br=None))
    r, p = L.render(alone), L.render(plain)
    assert r.pattern.stitches == p.pattern.stitches and r.branches == []
    assert not [w for w in r.warnings if w["code"].startswith("branch_")]
    assert "branches" not in L.render_summary(alone)


def test_no_branch_means_the_same_items_object():
    layout = lay(fill("a", 0, 0, 10, br=None), fill("b", 20, 0, 10, br=None))
    assert branch.prepared_items(layout) is layout["items"]


def test_copies_of_a_member_join_its_branch():
    a = fill("a", 0, 0, 10)
    copy = {**a, "id": "a2", "transform": {**I, "x": 10}}
    r = L.render(lay(a, copy, fill("c", 20, 0, 10)))
    assert r.branches[0]["items"] == ["a", "a2", "c"] and r.branches[0]["cuts"] == 0


# ---------------------------------------------------------------- with the layout's other passes


def test_other_passes_leave_the_branch_whole():
    blue = fill("x", 40, 0, 10, thread=BLUE, br=None)
    red_after = fill("z", 60, 0, 10, br=None)
    base = [*THREE_TOUCHING["overlap"], blue, red_after]
    for settings in ({"remove_overlap": {"enabled": True}}, {"travel_under": True}, {"color_sort": True},
                     {"merge_colors": True}, {"color_sort": True, "travel_under": True}):
        r = L.render(lay(*base, **settings))
        recs = recs_of(r)
        span = between_first_and_last(recs, {0, 1, 2})
        assert cuts_in(span) == 0, settings
        assert {it for *_, it in span} <= {0, 1, 2, -1}, settings  # nothing else sewn inside it
        assert r.branches and r.branches[0]["items"] == ["a", "b", "c"], settings


def test_remove_overlap_cuts_the_lower_member_and_the_path_follows():
    shapes = [fill("a", 0, 0, 20), fill("b", 8, 2, 20), fill("c", 26, 0, 12)]
    on = L.render(lay(*shapes, remove_overlap={"enabled": True, "keep_mm": 1}))
    off = L.render(lay(*shapes))
    assert _sewn_count(on, 0) < _sewn_count(off, 0)  # the first square leaves out what B hides
    assert on.branches[0]["cuts"] == 0


# ---------------------------------------------------------------- caching and speed


def test_plan_is_cached(monkeypatch):
    layout = lay(*THREE_TOUCHING["edges"], fill("x", 0, 20, 30, 10, thread=BLUE, br=None))
    L.render(layout)
    made = []
    real = dz.generate_parts
    monkeypatch.setattr(dz, "generate_parts", lambda o: made.append(1) or real(o))
    planned = []
    real_plan = branch._plan
    monkeypatch.setattr(branch, "_plan", lambda *a: planned.append(1) or real_plan(*a))
    L.render(layout)
    assert made == [] and planned == []
    # A dot moved is a new plan.
    L.render({**layout, "branches": {"b1": {"start_mm": [30, 5]}}})
    assert planned == [1]


def test_twenty_members_close_only_the_covers_near_each_join(monkeypatch):
    rng = random.Random(3)
    cells = [(c, r) for r in range(4) for c in range(5)]
    rng.shuffle(cells)
    items = [fill(f"s{k}", c * 9.0, r * 9.0, 8) for k, (c, r) in enumerate(cells)]
    layout = lay(*items)
    L.render({**layout, "items": [{**it, "branch": None} for it in items]})  # the stitches, made once
    closed = []  # how many shapes each closing in branch.py merges (the costly step of planning)

    class Counted:
        def __getattr__(self, name):
            return getattr(shapely, name)

        def union_all(self, geoms, *args, **kwargs):
            closed.append(len(geoms))
            return shapely.union_all(geoms, *args, **kwargs)

    monkeypatch.setattr(branch, "shapely", Counted())
    t0 = time.perf_counter()
    r = L.render(layout)
    seconds = time.perf_counter() - t0
    assert len(r.branches[0]["items"]) == 20
    # The same on every computer. These 8 mm squares lie 1 mm apart, too far for the closing to
    # merge any two, so a join's zone needs only the covers within branch.NEAR_MM of its two ends
    # (the squares around them, at most 6 here): 37 shapes over the 18 joins that close anything.
    # The ceiling of 60 leaves room for small moves of the members' start and end points, and is
    # far below the 189 (19 + 18 + ... + 2) of closing every later cover for every join, which
    # took most of the planning time.
    assert sum(closed) <= 60, (sum(closed), closed)
    assert seconds < 20.0, seconds  # only a guard against a blow-up; the count above is the real check


# ---------------------------------------------------------------- the Branch command


def test_branch_plan_refuses_in_plain_words():
    a, b = fill("a", 0, 0, 10, br=None), fill("b", 10, 0, 10, br=None)
    text = {"id": "t", "kind": "text", "text": "Hi", "font": "block", "height_mm": 10, "transform": I}
    app = obj("d", "applique", {"outline": sq(30, 0, 10)}, br=None)
    blue = fill("c", 20, 0, 10, thread=BLUE, br=None)
    cases = {
        "one": (lay(a, b), ["a"], "Select two or more drawn shapes"),
        "text": (lay(a, b, text), ["a", "b", "t"], "is lettering"),
        "applique": (lay(a, b, app), ["a", "d"], "is an applique"),
        "threads": (lay(a, b, blue), ["a", "c"], "more than one thread"),
    }
    for name, (layout, ids, words) in cases.items():
        out = branch.branch_plan(layout, ids)
        assert out["ok"] is False and words in out["reason"] and out["order"] == [], (name, out)
    out = branch.branch_plan(lay(a, b, app), ["a", "d"])
    assert "Applique 3 is an applique" in out["reason"]


def test_branch_plan_names_the_blocker():
    leaf = fill("x", 12, 2, 6, thread=BLUE, br=None, name="Leaf 3")
    items = [fill("a", 0, 0, 10, br=None), leaf, fill("b", 10, 0, 10, br=None, name="Leaf 2")]
    out = branch.branch_plan(lay(*items), ["a", "b"])
    assert out == {"ok": False, "reason": "Leaf 3 is sewn between these shapes and overlaps Leaf 2: move it first.",
                   "order": []}
    # Something between them that overlaps neither goes after them.
    items[1] = fill("x", 40, 0, 6, thread=BLUE, br=None)
    assert branch.branch_plan(lay(*items), ["b", "a"]) == {"ok": True, "reason": "", "order": ["a", "b", "x"]}


def test_render_summary_lists_branches():
    s = L.render_summary(lay(*THREE_TOUCHING["edges"]))
    (b,) = s["branches"]
    assert set(b) == {"id", "items", "start", "end", "hidden_mm", "cuts"}
    assert b["id"] == "b1" and b["items"] == ["a", "b", "c"] and b["cuts"] == 0
    pts = [(x, y) for x, y, k in zip(s["records"]["x"], s["records"]["y"], s["records"]["kind"]) if k == 0]
    # (the summary's records are rounded to 0.01 mm)
    assert b["start"] == pytest.approx(list(pts[0]), abs=0.006) and b["end"] == pytest.approx(list(pts[-1]), abs=0.006)


def test_project_names_the_feature():
    assert "branches" in project._features(lay(*THREE_TOUCHING["edges"]))
    assert "branches" not in project._features(lay(fill("a", 0, 0, 10, br=None)))


# ---------------------------------------------------------------- snapshots


# Each starts at a green dot: a fill left to start where it likes starts at a corner, and a plain
# fill's cross-hatch underlay then has two mirror-image ways to go from it, chosen by a sine's
# last digit (the fill's own choice, branch or not: a lone 10 mm square fill differs under some of
# the last-digit test's noise), so the suite would test that instead of the branch.
DOT = {"branches": {"b1": {"start_mm": [0, 3.1]}}}
SNAPSHOT_CASES = {
    "three_squares": lay(*THREE_TOUCHING["edges"], **DOT),
    "under_a_later_fill": lay(fill("a", 0, 0, 10), fill("b", 20, 0, 10),
                              obj("x", "fill", {"outline": sq(-2, -2, 34, 14)}, thread=BLUE, br=None,
                                  params={"start_mm": [-2, 1.3]}), **DOT),
    "lines_and_fill": lay(obj("l", "run", {"nodes": [[-12, 5, "c"], [0, 5, "c"]]}), fill("a", 0, 0, 10),
                          obj("r", "satin", {"nodes": [[24, 2, "c"], [10, 5, "c"]], "width_mm": 3}),
                          obj("c", "run", {"nodes": circle(30, 5, 6), "closed": True})),
    "with_a_gap": lay(fill("a", 0, 0, 10), fill("b", 18, 0, 10), obj("c", "fill", {"outline": circle(33, 5, 5)}), **DOT),
}


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshots(name):
    r = L.render(SNAPSHOT_CASES[name])
    for blk in r.blocks:
        assert_sane([(x / 10, y / 10, k) for x, y, k, *_ in blk.recs])
    check("branch", name, digest_pattern_steady(r.pattern))


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_snapshots_do_not_hang_on_the_last_digit_of_a_sine(seed, monkeypatch):
    path = SNAPSHOT_DIR / "branch.json"
    if not path.exists():
        pytest.skip("snapshots not recorded yet")
    recorded = json.loads(path.read_text(encoding="utf-8"))
    forget_stitches()
    branch.forget()
    try:
        nudge_trig(monkeypatch, seed, dz, branch, rotations=True)
        for name in sorted(SNAPSHOT_CASES):
            assert digest_pattern_steady(L.render(SNAPSHOT_CASES[name]).pattern) == recorded[name], name
    finally:
        monkeypatch.undo()
        forget_stitches()
        branch.forget()
