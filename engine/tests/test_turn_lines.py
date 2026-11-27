"""Turning a line round must never change what is sewn (Phase 7 audit, finding 3): a line whose
curve would change, or a motif line whose pattern would come out differently, keeps its direction."""

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
