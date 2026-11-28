"""Turning a line round must never change what is sewn (Phase 7 audit, finding 3): a line whose
curve would change, or a motif line whose pattern would come out differently, keeps its direction."""

import math
import random

import pytest
from shapely.geometry import MultiPoint
from steady_util import forget_stitches, nudge_trig

from threadline_engine import jumps
from threadline_engine.digitize import lines
from threadline_engine.digitize import stitches as dz
from threadline_engine.digitize.lines import builtin
from threadline_engine.methods.shapes import shape_set_end

THREAD = {"color": "#1f3a93", "name": "Navy", "catalog": "", "brand": ""}
SAW = [[0, 0], [0.8, -1], [1, 0]]  # a motif of your own, lopsided both ways
#: Every motif and side that sews the same from either end; every other one doesn't.
SAME_TURNED = {("blanket", "left"), ("blanket", "right"), ("scallop", "left"), ("scallop", "right"),
               ("zigzag", "left"), ("zigzag", "right"), ("wave", "center")}
CASES = [(m, s) for m in ["blanket", "leaf", "scallop", "wave", "zigzag", "saw"] for s in ("center", "left", "right")]


def line(nodes, ident="a", **params):
    return {"id": ident, "kind": "run", "geometry": {"nodes": nodes}, "params": params, "thread": THREAD}


def motif(name, side, length=40.0, **extra):
    params = {"style": "motif", "motif_side": side}
    params.update({"motif": "saw", "motif_unit": SAW} if name == "saw" else {"motif": name})
    return {**line([[0, 0, "c"], [length, 0, "l"]], "m", **params), **extra}


def needles(it):
    return MultiPoint([(x, y) for x, y, k in dz.generate(jumps._placed(it))[0] if k == dz.STITCH])


def test_the_motif_table_names_every_built_in_motif():
    assert {m for m, _ in CASES} == {*lines.MOTIF_UNITS, "saw"}


@pytest.mark.parametrize("name,side", CASES)
def test_a_motif_line_turns_only_when_it_sews_the_same(name, side):
    for it in (motif(name, side), motif(name, side, 23.7),
               motif(name, side, transform={"x": 3, "y": -2, "rotate": 30, "scale_x": 1.4, "scale_y": 0.8,
                                             "flip_x": False, "flip_y": False})):
        assert jumps.can_turn(it) is ((name, side) in SAME_TURNED)
        apart = needles(it).hausdorff_distance(needles(jumps.turned_round(it)))
        assert (apart <= 0.05) is ((name, side) in SAME_TURNED)  # measured on its needle points


def test_the_check_answers_the_same_with_the_maths_one_last_digit_off(monkeypatch):
    forget_stitches()
    try:
        for seed in range(4):
            nudge_trig(monkeypatch, seed, dz, jumps, lines, builtin, rotations=True)
            forget_stitches()
            for name, side in CASES:
                assert jumps.can_turn(motif(name, side, 23.7)) is ((name, side) in SAME_TURNED), (seed, name, side)
            monkeypatch.undo()
    finally:
        monkeypatch.undo()
        forget_stitches()


def test_optimize_jumps_keeps_a_lopsided_motif_line_and_turns_one_that_sews_the_same():
    first = line([[30, 0, "c"], [40, 0, "l"]], "first")
    for side, turned in (("center", False), ("left", True)):
        blanket = motif("blanket", side, 38.0)
        result = jumps.optimize_jumps({"items": [first, blanket]})
        assert ("m" in result["changes"]) is turned, side
        if turned:  # it starts by the first line now, with the same teeth on the same side
            after = {**blanket, **result["changes"]["m"]}
            assert after["geometry"]["nodes"][0][0] == 38.0 and after["params"]["motif_side"] == "right"
            assert needles(blanket).hausdorff_distance(needles(after)) <= 0.05
            assert result["after_mm"] < result["before_mm"]


@pytest.mark.parametrize("obj,which,why", [
    # a straight stretch leaving a curve point: turned round, the point can't stay a curve
    (line([[0, 0, "c"], [10, 5, "s"], [20, 0, "l"]]), "start", "curve"),
    (motif("blanket", "center"), "start", "pattern"),
    (motif("leaf", "left"), "end", "pattern"),
])
def test_dragging_an_end_dot_to_the_other_end_refuses_to_change_what_is_sewn(obj, which, why):
    at = [20, 0] if obj["id"] == "a" else [40, 0]
    at = at if which == "start" else [0, 0]
    with pytest.raises(jumps.EndsError) as said:
        shape_set_end(obj, which, at)  # the engine method the app calls: its words reach the user
    assert str(said.value) == jumps.NOT_TURNED[why] and said.value.rpc_code == -32000


def test_dragging_an_end_dot_still_turns_a_line_that_sews_the_same():
    plain = line([[0, 0, "c"], [10, 5, "s"], [20, 0, "s"]])
    assert shape_set_end(plain, "start", [20, 0])["geometry"]["nodes"][0][:2] == [20, 0]
    blanket = motif("blanket", "left")
    turned = shape_set_end(blanket, "start", [40, 0])
    assert turned["geometry"]["nodes"][0][:2] == [40, 0] and turned["params"]["motif_side"] == "right"
    # dropped by its own end, a line that can't turn is simply left as it is (the app moves its point)
    assert shape_set_end(motif("blanket", "center"), "start", [1, 0]) == motif("blanket", "center")


def test_the_refusals_say_why_and_what_to_do():
    for words in jumps.NOT_TURNED.values():
        assert "keeps its direction" in words and "draw the line again from that end" in words


# ---------------------------------------------------------------- how far the others move

# Candlewicking, French knots and the hand-sewn look are turned (fewer jumps matter more than half
# a millimeter along the line) although their stitches then sit a little differently along it. The
# knowledge base (F-1805) and the manual give these figures: the most a turned line's needle points
# lie from the drawn one's.
TURNED_APART_MM = {
    "candlewick": ({"style": "candlewick"}, 0.5),  # 1.6 mm knots: each knot's star points the other way
    "candlewick, 3 mm knots": ({"style": "candlewick", "knot_mm": 3.0, "knot_gap_mm": 5.0}, 0.93),
    "French knots": ({"style": "knots"}, 0.5),  # points at least a knot apart
    "French knots, 3 mm": ({"style": "knots", "knot_mm": 3.0}, 0.93),
    # points closer than a knot: the other of two such points may be the one left out
    "French knots, crowded": ({"style": "knots"}, 2.1),
    "hand-sewn single": ({"style": "single", "hand_pct": 100}, 0.9),  # 2.5 mm stitches
    "hand-sewn triple": ({"style": "triple", "hand_pct": 100}, 0.9),
    "hand-sewn bean": ({"style": "bean", "hand_pct": 100}, 0.9),
    "hand-sewn single, 12 mm stitches": ({"style": "single", "hand_pct": 100, "stitch_mm": 12}, 3.6),
}


def _open_line(rng, apart: float):
    """A random straight, cornered or curved line whose points lie at least `apart` mm apart."""
    shape = rng.choice(("straight", "corners", "curves"))
    if shape == "straight":
        length, a = rng.uniform(3, 150), rng.uniform(0, 2 * math.pi)
        return [[0, 0, "c"], [length * math.cos(a), length * math.sin(a), "l"]]
    while True:
        pts = [(0.0, 0.0)]
        for _ in range(rng.randint(2, 7)):
            step, a = rng.uniform(max(1.0, apart), 30), rng.uniform(0, 2 * math.pi)
            pts.append((pts[-1][0] + step * math.cos(a), pts[-1][1] + step * math.sin(a)))
        if all(math.dist(p, q) >= apart for i, p in enumerate(pts) for q in pts[i + 1:]):
            return [[round(x, 3), round(y, 3), "c" if shape == "corners" else "s"] for x, y in pts]


def _crowded_line(rng):
    """Points about 0.5 to 1.5 mm apart, closer than a 1.6 mm knot."""
    x, nodes = 0.0, []
    for i in range(rng.randint(3, 12)):
        x += rng.uniform(0.5, 1.5)
        nodes.append([round(x, 3), round((i % 2) * rng.uniform(0, 1), 3), "c"])
    return nodes


@pytest.mark.parametrize("what", sorted(TURNED_APART_MM))
def test_a_turned_line_moves_no_further_than_the_docs_say(what):
    params, most = TURNED_APART_MM[what]
    rng = random.Random(11)
    apart = params.get("knot_mm", 1.6) if params["style"] == "knots" else 1.0
    found = []
    while len(found) < 150:
        nodes = _crowded_line(rng) if "crowded" in what else _open_line(rng, apart)
        it = line(nodes, **params)
        if jumps.can_turn(it):
            found.append(needles(it).hausdorff_distance(needles(jumps.turned_round(it))))
    assert max(found) <= most, max(found)
    assert max(found) >= 0.6 * most, max(found)  # the figure isn't far more than lines really move
