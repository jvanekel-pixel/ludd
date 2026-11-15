"""Fewer jumps and trims: moves hidden under later stitching, and the shortest sewing order."""

import pyembroidery as pe

from threadline_engine import layout as L

RED = {"color": "#cc2222", "name": "Red", "catalog": "", "brand": ""}
BLUE = {"color": "#2222cc", "name": "Blue", "catalog": "", "brand": ""}
IDENT = {"x": 0, "y": 0, "rotate": 0, "scale_x": 1, "scale_y": 1, "flip_x": False, "flip_y": False}


def square(i, x, y, w, thread):
    nodes = [[x, y, "c"], [x + w, y, "c"], [x + w, y + w, "c"], [x, y + w, "c"]]
    return {"id": i, "kind": "fill", "geometry": {"outline": nodes}, "params": {"underlay": []}, "thread": thread,
            "transform": IDENT, "threads": [], "ops": []}


def commands(r, kinds):
    return sum(1 for x, y, c in r.pattern.stitches if c & L.M in kinds)


def two_red_spots_under_a_blue_patch(travel):
    return {"version": 1, "travel_under": travel, "items": [
        square("a", 0, 0, 6, RED), square("b", 30, 0, 6, RED),
        square("c", -2, -2, 40, BLUE),  # sewn later, over the way from a to b
    ]}


def test_moves_under_later_stitching_become_hidden_travel():
    off = L.render(two_red_spots_under_a_blue_patch(False))
    on = L.render(two_red_spots_under_a_blue_patch(True))
    assert commands(off, {pe.TRIM}) >= 1
    assert commands(on, {pe.TRIM, pe.JUMP}) < commands(off, {pe.TRIM, pe.JUMP})
    # The travel stitches are short.
    pts = [(r[0], r[1]) for r in on.blocks[0].recs if r[2] == pe.STITCH]  # the red block
    assert max(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in zip(pts, pts[1:])) / 10 < 8


def test_moves_over_bare_fabric_still_jump_and_trim():
    lay = {"version": 1, "travel_under": True, "items": [square("a", 0, 0, 6, RED), square("b", 30, 0, 6, RED)]}
    assert commands(L.render(lay), {pe.TRIM}) >= 1


def test_shortest_order_reorders_separate_same_thread_shapes():
    lay = {"version": 1, "items": [square("a", 0, 0, 5, RED), square("b", 60, 0, 5, RED), square("c", 20, 0, 5, RED),
                                   square("d", 40, 0, 5, RED)]}
    r = L.optimize_order(lay)
    assert r["order"][0] == "a" and set(r["order"]) == {"a", "b", "c", "d"}
    assert r["order"] == ["a", "c", "d", "b"]
    assert r["saved_mm"] > 0


def test_shortest_order_keeps_overlapping_shapes_in_place():
    lay = {"version": 1, "items": [square("a", 0, 0, 30, RED), square("b", 50, 0, 5, RED), square("c", 10, 10, 5, RED)]}
    assert L.optimize_order(lay)["order"] == ["a", "b", "c"]


def test_qa_c2_thin_running_stitches_never_crash_the_render():
    """QA C2: a running stitch's cover used to come out invalid and crash GEOS."""
    Y = {"color": "#f1c40f", "name": "y", "catalog": "", "brand": ""}

    def run(i, nodes, tr=None):
        return {"id": i, "kind": "run", "thread": Y, "threads": [], "ops": [], "transform": tr or {},
                "geometry": {"nodes": [[x, y, "s"] for x, y in nodes], "closed": False}, "params": {"style": "single", "stitch_mm": 7.06}}

    tr = {"x": -21.53, "y": -6.47, "rotate": 363.7, "scale_x": 0.6286, "scale_y": 0.6286, "flip_x": True, "flip_y": False}
    bad = run("b", [(1.912, 1.553), (-1.575, 6.743), (-8.657, 17.875), (-18.096, 24.422), (-6.892, 23.839)], tr)
    L.render({"items": [run("a", [(0, 0), (3, 0)]), bad], "travel_under": True})


def test_qa_c6_sorted_colors_never_leave_travel_on_top():
    """QA C6: with Sort colors on, the move between the red squares is no longer under later
    stitching (the blue is sewn first), so it must be a trim and jump, not bare travel."""
    lay = {"version": 1, "travel_under": True, "color_sort": True, "items": [
        square("x", -30, -30, 5, BLUE), square("a", 0, 0, 6, RED), square("b", 30, 0, 6, RED), square("c", -2, -2, 40, BLUE)]}
    r = L.render(lay)
    reds = [i for i, b in enumerate(r.blocks) if b.thread["color"] == RED["color"]]
    assert len(reds) == 1
    red = r.blocks[reds[0]]
    gap = [p for p in red.recs if p[2] == pe.STITCH and 8 < p[0] / 10 < 28]
    if gap:
        # Travel is only there if the blue patch is still sewn after it (here Sort colors keeps the
        # patch after the reds, because moving it ahead would put it under them).
        later = [b for b in r.blocks[reds[0] + 1:] if b.thread["color"] == BLUE["color"]]
        assert later and any(L._cover(b) is not None and L._cover(b).contains(L.LineString([(p[0] / 10, p[1] / 10) for p in gap]))
                             for b in later)
    else:
        assert any(p[2] in (pe.TRIM, pe.JUMP) for p in red.recs)


def test_qa_c3_nothing_to_join_costs_nothing():
    """QA C3: one big fill (nothing to join) renders as fast with the option on as off."""
    import time

    lay = {"version": 1, "items": [square("a", 0, 0, 80, RED)]}
    L.render({**lay, "travel_under": False})
    t = time.perf_counter()
    L.render({**lay, "travel_under": False})
    off = time.perf_counter() - t
    t = time.perf_counter()
    L.render({**lay, "travel_under": True})
    on = time.perf_counter() - t
    assert on < off + 0.2


# ---------------------------------------------------------------- phase 4 (QA medium and low findings)

def test_qa4_shortest_order_is_the_same_with_fewer_jumps_on():
    reds = [square("a", 0, 0, 5, RED), square("b", 60, 0, 5, RED), square("c", 20, 0, 5, RED), square("d", 40, 0, 5, RED)]
    cover = square("cover", -5, -5, 80, BLUE)
    off = L.optimize_order({"items": reds + [cover], "travel_under": False})
    on = L.optimize_order({"items": reds + [cover], "travel_under": True})
    assert on["order"] == off["order"] == ["a", "c", "d", "b", "cover"]
    assert on["saved_mm"] == off["saved_mm"] > 0


def test_qa4_hidden_travel_belongs_to_no_shape():
    r = L.render(two_red_spots_under_a_blue_patch(True))
    travel = [i for i, ((*_, c), s) in enumerate(zip(r.pattern.stitches, r.src_of)) if c & L.M == pe.STITCH and s < 0]
    assert travel and all(r.item_of[i] == -1 for i in travel)


def test_qa4_shortest_order_mixes_fills_and_lines_and_only_pins_overlapping_shapes():
    def line(i, x):
        return {"id": i, "kind": "run", "geometry": {"nodes": [[x, 2, "c"], [x + 5, 2, "c"]]}, "params": {}, "thread": RED,
                "transform": IDENT, "threads": [], "ops": []}

    mixed = L.optimize_order({"items": [square("a", 0, 0, 5, RED), line("b", 60), square("c", 20, 0, 5, RED), line("d", 40)]})
    assert mixed["order"] == ["a", "c", "d", "b"] and mixed["saved_mm"] > 0
    # e and f overlap: they keep their order, but the rest is still reordered.
    r = L.optimize_order({"items": [square("a", 0, 0, 5, RED), square("b", 60, 0, 5, RED), square("c", 20, 0, 5, RED),
                                    square("d", 40, 0, 5, RED), square("e", 100, 0, 10, RED), square("f", 105, 0, 10, RED)]})
    assert r["saved_mm"] > 0
    assert r["order"].index("e") < r["order"].index("f")
    assert r["order"][:4] == ["a", "c", "d", "b"]


def test_qa4_travel_is_hidden_only_under_close_rows():
    """Rows 0.4 mm apart hide the travel; rows 1.4 mm apart leave bare strips, so it's a trim and jump."""
    def lay(spacing):
        cover = square("c", 0, -3, 38, BLUE)
        cover["geometry"]["outline"] = [[0, -3, "c"], [38, -3, "c"], [38, 9, "c"], [0, 9, "c"]]
        cover["params"] = {"underlay": [], "spacing_mm": spacing}
        a = {"id": "a", "kind": "run", "geometry": {"nodes": [[2, 3, "c"], [4, 3, "c"]]}, "params": {}, "thread": RED,
             "transform": IDENT, "threads": [], "ops": []}
        b = dict(a, id="b", geometry={"nodes": [[34, 3, "c"], [36, 3, "c"]]})
        return {"items": [a, b, cover], "travel_under": True}

    assert commands(L.render(lay(0.4)), {pe.TRIM}) == 0
    assert commands(L.render(lay(1.4)), {pe.TRIM}) >= 1
