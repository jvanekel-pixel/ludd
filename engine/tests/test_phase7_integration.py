"""Phase 7 integration: what only shows when the tracks meet (docs/phases/PHASE-07-lines-sequencing-
drawing.md, section 8)."""

import math

from threadline_engine import layout
from threadline_engine.digitize.smallobjects import buttonhole
from threadline_engine.digitize.stitches import STITCH, generate

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
