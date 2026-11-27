"""Phase 7 integration: what only shows when the tracks meet (docs/phases/PHASE-07-lines-sequencing-
drawing.md, section 8)."""

import json
import math
import zipfile

import pyembroidery as pe
import pytest
from shapely.geometry import LineString

from threadline_engine import layout, project
from threadline_engine.digitize.paths import flatten
from threadline_engine.digitize.smallobjects import buttonhole
from threadline_engine.digitize.stitches import STITCH, generate
from threadline_engine.jumps import _reversed_path, optimize_jumps, reverses_exactly, set_end

RED = {"color": "#cc2222", "name": "Red", "catalog": "", "brand": ""}


def _circle(cx, cy, r, n=24):
    return [[cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n), "s"] for k in range(n)]


def test_a_mirrored_line_with_the_other_side_sews_the_mirror_image():
    """What the app's mirror command relies on: mirrored points with the side swapped sew the exact
    mirror image, teeth and all (the order of the points stays)."""
    for side, other in (("left", "right"), ("right", "left")):
        line = {"kind": "run", "geometry": {"nodes": _circle(0, 0, 15), "closed": True},
                "params": {"style": "motif", "motif": "blanket", "motif_side": side}, "thread": RED}
        mirrored = {**line, "geometry": {**line["geometry"], "nodes": [[-x, y, k] for x, y, k in line["geometry"]["nodes"]]},
                    "params": {**line["params"], "motif_side": other}}
        a = [r for r in generate(line)[0] if r[2] == STITCH]
        b = [r for r in generate(mirrored)[0] if r[2] == STITCH]
        assert len(a) == len(b)
        assert max(math.dist((-x, y), (u, v)) for (x, y, _), (u, v, _) in zip(a, b)) < 0.02


def test_a_gap_meant_as_a_slit_is_not_called_a_mistake():
    """A buttonhole's two lips with the smallest cut gap sit close enough for the gap check; its
    advice must not tell you to close the slit."""
    made = buttonhole(16, 5, "bar", 0.6, 0, [0, 0])
    items = [{**o, "id": f"o{n}", "thread": RED, "transform": {}, "threads": [], "ops": [], "group": "g"}
             for n, o in enumerate(made["objects"])]
    gaps = [c for c in layout.check({"items": items})["checks"] if c["code"].startswith("gap_")]
    assert gaps, "the lips are closer than the gap check's limit"
    assert all("buttonhole" in c["fix"] and "on purpose" in c["fix"] for c in gaps)


# ---------------------------------------------------------------- turning lines round (jumps.py)

BENDS = {
    # curve points, a corner, and a straight stretch in the middle
    "curves_and_a_corner": [[0, 0, "c"], [10, 4, "s"], [20, -3, "s"], [30, 0, "c"], [38, 8, "s"], [45, 0, "s"]],
    "straight_then_curves": [[0, 0, "c"], [10, 0, "l"], [20, 8, "c"], [28, 0, "s"], [36, 8, "c"]],
    "curves_then_straight": [[0, 0, "s"], [10, 6, "s"], [20, 0, "c"], [30, 0, "l"]],
}


def _curve(nodes, closed):
    return LineString(flatten(nodes, closed)[0])


@pytest.mark.parametrize("name", sorted(BENDS))
@pytest.mark.parametrize("closed", [False, True])
def test_turning_a_line_round_draws_the_same_curve(name, closed):
    nodes = BENDS[name]
    assert reverses_exactly(nodes, closed)
    turned = _reversed_path(nodes, closed)
    assert [(x, y) for x, y, _ in turned] == [(x, y) for x, y, _ in reversed(nodes)]
    assert _curve(turned, closed).hausdorff_distance(_curve(nodes, closed)) < 1e-6
    assert _curve(_reversed_path(turned, closed), closed).hausdorff_distance(_curve(nodes, closed)) < 1e-6


def test_a_curve_point_before_a_straight_stretch_cannot_turn_exactly():
    nodes = [[0, 0, "c"], [10, 5, "s"], [20, 0, "l"]]
    assert not reverses_exactly(nodes)
    turned = _reversed_path(nodes)
    # The straight stretch stays straight.
    assert [k for *_, k in turned] == ["c", "l", "c"]


def _line(nodes, **params):
    return {"id": "a", "kind": "run", "geometry": {"nodes": nodes}, "params": params, "thread": RED,
            "transform": {}, "threads": [], "ops": []}


def _teeth_side(obj):
    """Which side of the horizontal line y = 0 the motif's teeth are on."""
    ys = [y for _, y, k in generate(obj)[0] if k == STITCH]
    return "up" if min(ys) < -0.5 else "down" if max(ys) > 0.5 else "none"


def test_dragging_an_end_to_turn_a_line_keeps_its_teeth():
    line = _line([[0, 0, "c"], [30, 0, "l"]], style="motif", motif="blanket", motif_side="left")
    turned = set_end(line, "start", [30, 0])
    assert turned["geometry"]["nodes"][0][:2] == [30, 0] and turned["params"]["motif_side"] == "right"
    assert _teeth_side(turned) == _teeth_side(line) == "up"


def test_optimize_jumps_saves_both_parts_of_a_turned_line():
    """A one-sided motif turned round changes its points and its side: both must be saved, or the
    teeth jump across the line."""
    first = _line([[30, 0, "c"], [40, 0, "l"]])
    motif = {**_line([[0, 0, "c"], [38, 0, "l"]], style="motif", motif="blanket", motif_side="left"), "id": "b"}
    change = optimize_jumps({"items": [first, motif]})["changes"]["b"]
    assert change["geometry"]["nodes"][0][:2] == [38, 0]
    assert change["params"]["motif_side"] == "right"


def test_optimize_jumps_leaves_a_satin_with_both_dots_unturned():
    """A satin with both its start and end set keeps them: it isn't turned round."""
    first = _line([[30, 0, "c"], [40, 0, "l"]])
    ribbon = {"id": "b", "kind": "satin", "geometry": {"nodes": [[0, 0, "c"], [38, 0, "l"]], "width_mm": 2},
              "params": {"start_mm": [0, 0], "end_mm": [30, 0]}, "thread": RED, "transform": {}, "threads": [], "ops": []}
    assert "b" not in optimize_jumps({"items": [first, ribbon]})["changes"]
    bare = {**ribbon, "params": {}}
    assert optimize_jumps({"items": [first, bare]})["changes"]["b"]["geometry"]["nodes"][0][:2] == [38, 0]


def test_optimize_jumps_keeps_a_buttonhole_joined():
    """The bar buttonhole's lips hand over under a bar tack: Optimize jumps mustn't lengthen it."""
    made = buttonhole(16, 5, "bar", 1.0, 0, [0, 0])
    items = [{**o, "id": f"o{n}", "thread": RED, "transform": {}, "threads": [], "ops": [], "group": "g"}
             for n, o in enumerate(made["objects"])]
    lay = {"items": items, "travel_under": True}
    before = _jumps(lay)
    changes = optimize_jumps(lay)["changes"]
    after = _jumps({**lay, "items": [{**it, **changes.get(it["id"], {})} for it in items]})
    assert after[0] <= before[0] and after[1] <= before[1] + 0.05


def _jumps(lay):
    """(how many jumps, their length in mm) in the rendered design."""
    stitches = layout.render(lay).pattern.stitches
    moves = [(a, b) for a, b in zip(stitches, stitches[1:]) if b[2] & pe.COMMAND_MASK == pe.JUMP]
    return len(moves), sum(math.dist(a[:2], b[:2]) for a, b in moves) / 10


# ---------------------------------------------------------------- an applique's start (P7-B3)

SQUARE = [[0, 0, "c"], [20, 0, "c"], [20, 20, "c"], [0, 20, "c"]]


def _applique(**params):
    return {"id": "b", "kind": "applique", "geometry": {"outline": SQUARE}, "params": params, "thread": RED,
            "transform": {}, "threads": [], "ops": []}


def _section_starts(recs):
    """Where each of the applique's three parts starts: the first stitch, then each after a stop."""
    starts, fresh = [], True
    for x, y, k in recs:
        if k == STITCH and fresh:
            starts.append((x, y))
            fresh = False
        if k == pe.STOP:
            fresh = True
    return starts


def test_an_applique_starts_each_part_at_the_point_nearest_its_start():
    recs = generate(_applique(start_mm=[23, 11]))[0]
    for x, y in _section_starts(recs):
        assert math.dist((x, y), (20, 11)) < 2.0, (x, y)  # within the border's half width
    assert len(_section_starts(recs)) == 3
    assert sum(r[2] == STITCH for r in recs) == pytest.approx(sum(r[2] == STITCH for r in generate(_applique())[0]), rel=0.03)


def test_optimize_jumps_moves_an_applique_start():
    run = _line([[40, 30, "c"], [24, 18, "l"]])
    lay = {"items": [run, _applique()]}
    out = optimize_jumps(lay)
    assert "start_mm" in out["changes"]["b"]["params"] and out["after_mm"] < out["before_mm"] - 5
    moved = {**lay, "items": [run, {**_applique(), **out["changes"]["b"]}]}
    first = next((x / 10, y / 10) for (x, y, c), it in zip(layout.render(moved).pattern.stitches, layout.render(moved).item_of)
                 if it == 1 and c & pe.COMMAND_MASK == pe.STITCH)
    assert math.dist(first, (20, 18)) < 2.0


def test_a_saved_file_with_a_branch_of_one_does_not_carry_the_branches_flag(tmp_path):
    """An older LUDD refuses a file with a flag it doesn't know, and a branch of one sews as an
    ordinary shape (Phase 7 audit, finding 4)."""
    def square(ident, x, branch):
        return {"id": ident, "kind": "fill", "geometry": {"outline": [[x, 0, "c"], [x + 10, 0, "c"], [x + 10, 10, "c"], [x, 10, "c"]]},
                "params": {}, "thread": {"color": "#cc2222", "name": "Red"}, "branch": branch}

    for items, flagged in (([square("a", 0, "b1")], False),
                           ([square("a", 0, "b1"), square("c", 20, "b2")], False),
                           ([square("a", 0, "b1"), square("c", 10, "b1")], True)):
        saved = project.save(str(tmp_path / "one"), {"title": "t", "layout": {"version": 1, "items": items}, "images": []})
        with zipfile.ZipFile(saved["path"]) as z:
            manifest = json.loads(z.read("project.json"))
        assert ("branches" in manifest["features"]) is flagged, items
        assert manifest["version"] == (2 if flagged else 1)
        back = project.open_project(saved["path"])["layout"]["items"]
        assert [it["branch"] for it in back] == [it["branch"] for it in items]
