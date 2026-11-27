"""Golden round trips for the craft line styles, a motif to one side, blackwork and the lock-stitch
shapes: each saved as PES (the owner's Brother) and JEF reopens with the same stitches and colors,
the same size, and every jump and trim (French knots have both)."""

import pytest

from threadline_engine import design, layout


def c(x, y, kind="c"):
    return [x, y, kind]


RED = {"color": "#cc2222", "name": "Red", "catalog": "", "brand": ""}
S_CURVE = [c(0, 0, "s"), c(15, 8, "s"), c(30, -8, "s"), c(45, 0, "s")]
SQUARE = [c(0, 0), c(30, 0), c(30, 30), c(0, 30)]
DOTS = [c(0, 0), c(5, 4), c(11, 1), c(19, 3), c(21.5, 2)]


def line(nodes=S_CURVE, closed=False, **params):
    return {"id": "r", "kind": "run", "geometry": {"nodes": nodes, "closed": closed}, "thread": RED, "params": params}


def fill(**params):
    return {"id": "f", "kind": "fill", "geometry": {"outline": SQUARE}, "thread": RED, "params": params}


CASES = {
    "backstitch": line(style="backstitch"),
    "stem": line(style="stem"),
    "candlewick": line(style="candlewick"),
    "redwork": line(SQUARE, closed=True, style="redwork"),
    "knots": line(DOTS, style="knots"),
    "motif_left": line(style="motif", motif="blanket", motif_side="left"),
    "blackwork_diamonds": fill(pattern="blackwork"),
    "blackwork_grid": fill(pattern="blackwork", blackwork_lattice="grid"),
    "blackwork_honeycomb": fill(pattern="blackwork", blackwork_lattice="honeycomb"),
    "blackwork_crossed": fill(pattern="blackwork", blackwork_lattice="crossed", blackwork_mm=6),
    "triangle_line": line(tie_style="triangle"),
    "backtack_satin": {"id": "s", "kind": "satin", "thread": RED, "params": {"tie_style": "backtack"},
                       "geometry": {"nodes": S_CURVE, "width_mm": 4}},
    "triangle_fill": fill(tie_style="triangle"),
}


@pytest.mark.parametrize("ext", ["pes", "jef"])
@pytest.mark.parametrize("name", sorted(CASES))
def test_round_trip(name, ext, tmp_path):
    lay = {"items": [CASES[name]]}
    sewn = layout.render_summary(lay)
    out = tmp_path / f"{name}.{ext}"
    layout.export(lay, str(out))
    back = design.open_design(str(out))
    for key in ("stitches", "colors"):
        assert back["info"][key] == sewn["info"][key], key
    for key in ("jumps", "trims"):  # the writers add their own moves at the start; none are lost
        assert back["info"][key] >= sewn["info"][key], key
    assert back["info"]["width_mm"] == pytest.approx(sewn["info"]["width_mm"], abs=0.2)
    assert back["info"]["height_mm"] == pytest.approx(sewn["info"]["height_mm"], abs=0.2)
