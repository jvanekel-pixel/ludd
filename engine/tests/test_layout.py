"""Layouts: placing, transforming, merging and editing stitch files without touching them."""

import math
import os
from pathlib import Path

import pyembroidery as pe
import pytest

from threadline_engine import design, layout
from threadline_engine.layout import LayoutError

M = pe.COMMAND_MASK
S, J, T, P, C = pe.STITCH, pe.JUMP, pe.TRIM, pe.STOP, pe.COLOR_CHANGE

RED = pe.EmbThread("#ff0000", "Red", "1", brand="Test")
BLUE = pe.EmbThread("#0000ff", "Blue", "2", brand="Test")


def write_square(path: Path, size=200, colors=(RED, BLUE), offset=(0, 0)) -> str:
    """Two color blocks: top edge in color 1, then (color change) a jump and the bottom edge in color 2."""
    p = pe.EmbPattern()
    for c in colors:
        p.add_thread(c)
    ox, oy = offset
    for x in range(0, size + 1, 25):
        p.stitch_abs(ox + x, oy)
    p.color_change()
    p.move_abs(ox, oy + size)
    for x in range(0, size + 1, 25):
        p.stitch_abs(ox + x, oy + size)
    p.end()
    pe.write(p, str(path), {"version": 6})
    return str(path)


@pytest.fixture
def sq(tmp_path):
    return write_square(tmp_path / "sq.pes")


def lay(*items, **extra):
    return {"items": [dict(id=str(i), **it) for i, it in enumerate(items)], **extra}


def stitches(summary, item=None):
    r = summary["records"]
    return [
        (round(x, 2), round(y, 2))
        for x, y, k, it in zip(r["x"], r["y"], r["kind"], r["item"])
        if k == design.STITCH and (item is None or it == item)
    ]


def test_single_item_matches_the_file(sq):
    s = layout.render_summary(lay({"path": sq}))
    d = design.open_design(sq)
    assert stitches(s) == stitches({"records": {**d["records"], "item": [0] * len(d["records"]["x"])}})
    assert s["info"]["colors"] == 2
    assert s["items"][0]["bounds_mm"] == [0, 0, 20, 20]
    assert [b["sources"] for b in s["blocks"]] == [[{"item": 0, "block": 0}], [{"item": 0, "block": 1}]]


def test_records_point_back_to_source(sq):
    s = layout.render_summary(lay({"path": sq}))
    src = design.load(sq).stitches
    r = s["records"]
    for x, y, k, it, si in zip(r["x"], r["y"], r["kind"], r["item"], r["src"]):
        if k == design.STITCH:
            assert it == 0 and si >= 0
            assert (src[si][0] / 10, src[si][1] / 10) == (x, y)


def test_move_rotate_mirror_scale(sq):
    moved = layout.render_summary(lay({"path": sq, "transform": {"x": 5, "y": -3}}))
    assert moved["items"][0]["bounds_mm"] == [5, -3, 25, 17]

    rot = layout.render_summary(lay({"path": sq, "transform": {"rotate": 90}}))
    b = [round(v, 6) for v in rot["items"][0]["bounds_mm"]]
    assert b == [0, 0, 20, 20]  # a square about its centre stays put
    # The first stitch (top-left corner) goes to the top-right under a clockwise quarter turn.
    assert stitches(rot)[0] == (20.0, 0.0)

    flip = layout.render_summary(lay({"path": sq, "transform": {"flip_x": True}}))
    assert stitches(flip)[0] == (20.0, 0.0)

    big = layout.render_summary(lay({"path": sq, "transform": {"scale_x": 1.5, "scale_y": 1.5}}))
    assert big["items"][0]["bounds_mm"] == [-5, -5, 25, 25]  # grows about the centre
    assert any(w["code"].startswith("scale_") for w in big["warnings"])
    assert not layout.render_summary(lay({"path": sq, "transform": {"scale_x": 1.2, "scale_y": 1.2}}))["warnings"]

    with pytest.raises(LayoutError):
        layout.render_summary(lay({"path": sq, "transform": {"scale_x": 0}}))


def test_two_items_merge_with_color_change(sq, tmp_path):
    other = write_square(tmp_path / "b.pes", offset=(500, 0))
    s = layout.render_summary(lay({"path": sq}, {"path": other}))
    assert s["info"]["colors"] == 4
    assert s["info"]["color_changes"] == 3
    assert len(s["items"]) == 2
    assert s["name"] == "sq + 1 more"
    assert len(stitches(s, 0)) == len(stitches(s, 1)) == 18


def test_merge_same_colors_and_color_sort(sq, tmp_path):
    other = write_square(tmp_path / "b.pes", offset=(500, 0))
    plain = layout.render_summary(lay({"path": sq}, {"path": other}))
    assert [t["name"] for t in plain["threads"]] == ["Red", "Blue", "Red", "Blue"]

    merged = layout.render_summary(lay({"path": sq}, {"path": other}, merge_colors=True))
    assert merged["info"]["colors"] == 4  # blue then red: nothing adjacent to merge

    sorted_ = layout.render_summary(lay({"path": sq}, {"path": other}, color_sort=True))
    assert [t["name"] for t in sorted_["threads"]] == ["Red", "Blue"]
    assert sorted_["info"]["color_changes"] == 1
    # The joined halves are cut between, so no thread drags across.
    assert sorted_["info"]["trims"] >= 2
    assert sorted(len(b["sources"]) for b in sorted_["blocks"]) == [2, 2]
    # Nothing overlaps, so every colour could be gathered: no note.
    assert not any(w["code"] == "color_sort" for w in sorted_["warnings"])

    # Adjacent same color: item 2 starts with blue after item 1 ends with blue.
    flipped = write_square(tmp_path / "c.pes", colors=(BLUE, RED), offset=(500, 0))
    m = layout.render_summary(lay({"path": sq}, {"path": flipped}, merge_colors=True))
    assert [t["name"] for t in m["threads"]] == ["Red", "Blue", "Red"]


def test_recolor_by_source_block(sq):
    navy = {"color": "#000080", "name": "Navy", "catalog": "9", "brand": "X"}
    s = layout.render_summary(lay({"path": sq, "threads": [None, navy]}))
    assert [t["name"] for t in s["threads"]] == ["Red", "Navy"]
    assert [b["original"]["name"] for b in s["blocks"]] == ["Red", "Blue"]


def test_delete_color_block(sq):
    s = layout.render_summary(lay({"path": sq, "ops": [{"op": "delete_block", "block": 0}]}))
    assert s["info"]["colors"] == 1
    assert [t["name"] for t in s["threads"]] == ["Blue"]
    assert all(y == 20 for _, y in stitches(s))


def test_insert_stop_and_trim(sq):
    s0 = layout.render_summary(lay({"path": sq}))
    r = s0["records"]
    at = next(si for k, si in zip(r["kind"], r["src"]) if k == design.STITCH and si >= 3)
    s = layout.render_summary(lay({"path": sq, "ops": [
        {"op": "insert", "after": at, "command": "stop"},
        {"op": "insert", "after": at, "command": "trim"},
    ]}))
    assert s["info"]["stops"] == 1
    assert s["info"]["trims"] == s0["info"]["trims"] + 1
    assert stitches(s) == stitches(s0)  # nothing moved
    with pytest.raises(LayoutError):
        layout.render_summary(lay({"path": sq, "ops": [{"op": "insert", "after": at, "command": "explode"}]}))


def test_jumps_to_trims(tmp_path):
    p = pe.EmbPattern()
    p.add_thread(RED)
    for x in range(0, 101, 20):
        p.stitch_abs(x, 0)
    p.move_abs(400, 0)  # 30 mm jump, no trim
    for x in range(400, 501, 20):
        p.stitch_abs(x, 0)
    p.move_abs(510, 0)  # 1.5 mm from the last stitch to the next: too short to trim
    p.stitch_abs(515, 0)
    p.end()
    f = tmp_path / "j.exp"  # EXP keeps a plain jump plain (PES marks every jump after the first as a trim)
    pe.write(p, str(f))
    before = layout.render_summary(lay({"path": str(f)}))["info"]["trims"]
    s = layout.render_summary(lay({"path": str(f), "ops": [{"op": "jumps_to_trims", "min_mm": 3}]}))
    assert s["info"]["trims"] == before + 1
    # The layout-wide setting does the same (and covers designs added later).
    assert layout.render_summary(lay({"path": str(f)}, jumps_to_trims=3))["info"]["trims"] == before + 1


def test_basting_box(sq):
    s = layout.render_summary(lay({"path": sq}, basting={"enabled": True, "margin_mm": 5}))
    assert s["threads"][0]["name"] == "Basting"
    assert s["info"]["colors"] == 3
    assert s["info"]["bounds_mm"] == [-5, -5, 25, 25]
    # Basting stitches are no longer than 4 mm.
    r = s["records"]
    pts = [(x, y) for x, y, k, it in zip(r["x"], r["y"], r["kind"], r["item"]) if k == design.STITCH and it == -1]
    assert max(math.dist(a, b) for a, b in zip(pts, pts[1:])) <= 4.0 + 1e-6


def test_export_layout_and_never_overwrite_sources(sq, tmp_path):
    out = tmp_path / "out.pes"
    rep = layout.export(lay({"path": sq, "transform": {"x": 10}}), str(out), {"machine": "brother-pe550d"})
    assert rep["path"] == str(out.resolve())
    back = design.open_design(str(out))
    assert back["info"]["stitches"] == 18
    with pytest.raises(LayoutError, match="original"):
        layout.export(lay({"path": sq}), sq)


def test_preview_export_with_cut_stops(sq, tmp_path):
    def stops(f, on=True):
        return layout.preview_export(lay({"path": f}), {"machine": "brother-pe550d", "cut_stops": {"enabled": on}}, "pes")["stops_added"]

    # The move in sq comes after a colour change, where the machine cuts anyway: no stop needed.
    assert stops(sq) == 0
    # A long move inside one colour gets exactly one stop, and none when cut stops are off.
    p = pe.EmbPattern()
    p.add_thread(RED)
    for y in (0, 200):
        p.move_abs(0, y)
        for x in range(0, 201, 25):
            p.stitch_abs(x, y)
    p.end()
    one = str(tmp_path / "one.pes")
    pe.write(p, one, {"version": 6})
    assert stops(one) == 1 and stops(one, on=False) == 0


def test_errors(tmp_path):
    with pytest.raises(LayoutError, match="no designs"):
        layout.render_summary({"items": []})
    with pytest.raises(LayoutError, match="not found"):
        layout.render_summary(lay({"path": str(tmp_path / "missing.pes")}))


def test_cache_reloads_changed_files(tmp_path):
    f = tmp_path / "x.pes"
    write_square(f)
    assert layout.render_summary(lay({"path": str(f)}))["info"]["stitches"] == 18
    write_square(f, size=100)
    import os
    os.utime(f, (os.stat(f).st_atime, os.stat(f).st_mtime + 5))
    assert layout.render_summary(lay({"path": str(f)}))["info"]["stitches"] == 10


# ---------------------------------------------------------------- digitized objects


def obj(kind, geometry, thread=None, **extra):
    return {"kind": kind, "geometry": geometry, "params": {}, "thread": thread or {"color": "#ff0000", "name": "Red"}, **extra}


SATIN = {"rail_a": [[0, 0, "c"], [30, 0, "c"]], "rail_b": [[0, 4, "c"], [30, 4, "c"]]}
SQUARE_FILL = {"outline": [[0, 0, "c"], [20, 0, "c"], [20, 20, "c"], [0, 20, "c"]]}


def test_objects_render_next_to_files(sq):
    s = layout.render_summary(lay({"path": sq}, obj("satin", SATIN)))
    assert [i["kind"] for i in s["items"]] == ["file", "satin"]
    assert s["items"][1]["name"] == "Satin 2"
    assert s["info"]["colors"] == 3
    b = s["items"][1]["bounds_mm"]
    assert b[1] == pytest.approx(-0.1) and b[3] == pytest.approx(4.1)  # pull compensation widens the sides
    assert s["blocks"][2]["sources"] == [{"item": 1, "block": 0}]


def test_scaling_an_object_keeps_density():
    base = layout.render_summary(lay(obj("fill", SQUARE_FILL)))
    big = layout.render_summary(lay(obj("fill", SQUARE_FILL, transform={"scale_x": 2, "scale_y": 2})))
    # Twice the size: the fill rows quadruple (density kept); outline underlay and ties only double.
    ratio = big["info"]["stitches"] / base["info"]["stitches"]
    assert 3.0 < ratio < 4.5
    assert not [w for w in big["warnings"] if w["code"].startswith("scale_")]


def test_same_thread_objects_join_without_color_change():
    red = {"color": "#ff0000", "name": "Red"}
    near = obj("run", {"nodes": [[0, 0, "c"], [10, 0, "c"]]}, red)
    close = obj("run", {"nodes": [[11, 0, "c"], [20, 0, "c"]]}, red)
    far = obj("run", {"nodes": [[60, 0, "c"], [70, 0, "c"]]}, red)
    s = layout.render_summary(lay(near, close, far))
    assert s["info"]["colors"] == 1 and s["info"]["color_changes"] == 0
    assert s["info"]["trims"] == 1  # only the long move is trimmed
    blue = obj("run", {"nodes": [[0, 5, "c"], [10, 5, "c"]]}, {"color": "#0000ff", "name": "Blue"})
    assert layout.render_summary(lay(near, blue, far))["info"]["colors"] == 3


def test_object_errors_name_the_object():
    with pytest.raises(LayoutError, match="Satin 1"):
        layout.render_summary(lay(obj("satin", {"rail_a": [[0, 0, "c"], [5, 0, "c"]], "rail_b": [[0, 2, "c"]]})))
    with pytest.raises(LayoutError, match="no points"):
        layout.render_summary(lay(obj("fill", {"outline": []})))


def test_object_warnings_surface(sq):
    wide = {"rail_a": [[0, 0, "c"], [30, 0, "c"]], "rail_b": [[0, 14, "c"], [30, 14, "c"]]}
    s = layout.render_summary(lay(obj("satin", wide, name="Big satin")))
    assert any("Big satin" in w["message"] and "wide" in w["message"] for w in s["warnings"])


def test_object_recolor_and_export(tmp_path):
    l = lay(obj("fill", SQUARE_FILL, threads=[{"color": "#00ff00", "name": "Green", "catalog": "", "brand": ""}]))
    s = layout.render_summary(l)
    assert s["threads"][0]["name"] == "Green" and s["blocks"][0]["original"]["name"] == "Red"
    out = tmp_path / "drawn.pes"
    layout.export(l, str(out))
    assert design.open_design(str(out))["info"]["stitches"] == s["info"]["stitches"]


def test_object_cache_returns_same_stitches():
    l = lay(obj("fill", SQUARE_FILL))
    a = layout.render_summary(l)["records"]
    b = layout.render_summary(l)["records"]
    assert a["x"] == b["x"] and a["kind"] == b["kind"]


def test_stitch_editing_deletes_and_moves_single_stitches(sq):
    base = layout.render(lay({"path": sq}))
    recs = [r for b in base.blocks for r in b.recs if r[2] == pe.STITCH]
    victim, mover = recs[3], recs[6]
    edited = layout.render(lay({"path": sq, "ops": [
        {"op": "delete_stitches", "indices": [victim[4]]},
        {"op": "move_stitch", "index": mover[4], "dx_mm": 1.5, "dy_mm": -2.0},
    ]}))
    after = {r[4]: r for b in edited.blocks for r in b.recs if r[2] == pe.STITCH}
    assert victim[4] not in after
    assert after[mover[4]][0] == pytest.approx(mover[0] + 15)
    assert after[mover[4]][1] == pytest.approx(mover[1] - 20)
    assert len(after) == len(recs) - 1



def test_a_moved_stitch_turns_and_resizes_with_the_design(sq):
    """A stitch-edit move is kept in the design's own frame: turning the design 90 degrees and
    doubling it turns and doubles the move too (it used to stay a fixed shift on the hoop)."""
    turned = {"x": 0, "y": 0, "rotate": 90, "scale_x": 2, "scale_y": 2, "flip_x": False, "flip_y": False}
    base = layout.render(lay({"path": sq, "transform": turned}))
    recs = {r[4]: r for b in base.blocks for r in b.recs if r[2] == pe.STITCH}
    i = sorted(recs)[6]
    moved = layout.render(lay({"path": sq, "transform": turned,
                               "ops": [{"op": "move_stitch", "index": i, "dx_mm": 1.0, "dy_mm": 0.0, "local": True}]}))
    after = {r[4]: r for b in moved.blocks for r in b.recs if r[2] == pe.STITCH}
    # 1 mm right in the design's frame: 2 mm down on the hoop after turning 90 degrees and doubling.
    assert after[i][0] == pytest.approx(recs[i][0], abs=0.01)
    assert after[i][1] == pytest.approx(recs[i][1] + 20, abs=0.01)


def _three_colour_pes(tmp_path):
    p = pe.EmbPattern()
    for n, c in (("Red", "#ff0000"), ("Blue", "#0000ff"), ("Green", "#00ff00")):
        p.add_thread(pe.EmbThread(c, n, "1", brand="T"))
    for blk in range(3):
        if blk:
            p.color_change()
        p.move_abs(0, blk * 100)
        for x in range(0, 201, 25):
            p.stitch_abs(x, blk * 100)
    p.end()
    f = tmp_path / "three.pes"
    pe.write(p, str(f), {"version": 6})
    return str(f)


def test_qa_c4_a_colour_with_every_stitch_deleted_disappears(tmp_path):
    f = _three_colour_pes(tmp_path)
    base = layout.render(lay({"path": f}))
    by_block = [[r[4] for r in b.recs if r[2] == pe.STITCH] for b in base.blocks]
    for gone, left in ((0, ["#0000ff", "#00ff00"]), (1, ["#ff0000", "#00ff00"])):
        l = lay({"path": f, "ops": [{"op": "delete_stitches", "indices": by_block[gone]}]})
        s = layout.render_summary(l)
        assert s["info"]["colors"] == 2 and s["info"]["color_changes"] == 1
        out = tmp_path / f"cut{gone}.pes"
        layout.export(l, str(out), {"machine": "brother-pe550d"})
        back = pe.read(str(out))
        assert [t.hex_color() for t in back.threadlist] == left  # the thread table matches the stitches
    with pytest.raises(layout.LayoutError, match="no stitches"):
        layout.render(lay({"path": f, "ops": [{"op": "delete_stitches", "indices": [i for b in by_block for i in b]}]}))


def test_qa_c12_keep_existing_never_overwrites(sq, tmp_path):
    out = tmp_path / "Emma.pes"
    out.write_bytes(b"precious")
    r = layout.export(lay({"path": sq}), str(out), {"machine": "brother-pe550d"}, keep_existing=True)
    assert out.read_bytes() == b"precious"
    assert r["path"].endswith("Emma (1).pes")


# ---------------------------------------------------------------- phase 4 (QA medium and low findings)

from test_lettering import font_path  # noqa: E402,F401  (a tiny font built in the test)


def _row_file(tmp_path, n=9, name="row.pes"):
    p = pe.EmbPattern()
    p.add_thread(RED)
    for x in range(0, 25 * n, 25):
        p.stitch_abs(x, 0)
    p.end()
    f = tmp_path / name
    pe.write(p, str(f), {"version": 6})
    return str(f)


def _stops(r):
    return sum(1 for *_, c in r.pattern.stitches if c & M == P)


def test_qa4_an_inserted_stop_stays_when_its_stitch_is_deleted(tmp_path):
    f = _row_file(tmp_path)
    ins = {"op": "insert", "after": 5, "command": "stop"}
    assert _stops(layout.render(lay({"path": f, "ops": [ins]}))) == 1
    r = layout.render(lay({"path": f, "ops": [ins, {"op": "delete_stitches", "indices": [5]}]}))
    assert _stops(r) == 1
    # It sits after the last stitch kept before it (stitch 4, at 10 mm).
    i = next(k for k, (*_, c) in enumerate(r.pattern.stitches) if c & M == P)
    assert r.pattern.stitches[i][:2] == r.pattern.stitches[i - 1][:2] == [100, 0]


def test_qa4_damaged_stitch_edits_are_skipped_not_fatal(tmp_path):
    f = _row_file(tmp_path)
    clean = layout.render_summary(lay({"path": f}))
    bad_ops = [
        {"op": "move_stitch", "dx_mm": 1, "dy_mm": 0},
        {"op": "move_stitch", "index": 5, "dx_mm": None, "dy_mm": 0},
        {"op": "move_stitch", "index": 5, "dx_mm": "abc", "dy_mm": 0},
        {"op": "move_stitch", "index": 5, "dx_mm": float("nan"), "dy_mm": 0},
        {"op": "delete_stitches", "indices": [None, "x", -1, 2.5]},
        {"op": "delete_block", "block": None},
        {"op": "insert", "after": None, "command": "stop"},
        {"op": "jumps_to_trims", "min_mm": "x"},
    ]
    s = layout.render_summary(lay({"path": f, "ops": bad_ops}))
    assert stitches(s) == stitches(clean)


def test_qa4_index_minus_one_does_not_delete_a_drawn_shape():
    sq_ = [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"], [0, 10, "c"]]
    obj = {"kind": "fill", "geometry": {"outline": sq_}, "params": {}}
    n = layout.render_summary(lay(obj))["info"]["stitches"]
    assert layout.render_summary(lay({**obj, "ops": [{"op": "delete_stitches", "indices": [-1]}]}))["info"]["stitches"] == n


def test_qa4_one_op_moves_many_stitches(tmp_path):
    f = _row_file(tmp_path)
    one = [{"op": "move_stitches", "indices": [3, 4, 5], "dx_mm": 1.5, "dy_mm": -2, "local": True}]
    each = [{"op": "move_stitch", "index": i, "dx_mm": 1.5, "dy_mm": -2, "local": True} for i in (3, 4, 5)]
    for tr in ({}, {"rotate": 90}):
        a = layout.render_summary(lay({"path": f, "ops": one, "transform": tr}))
        b = layout.render_summary(lay({"path": f, "ops": each, "transform": tr}))
        assert stitches(a) == stitches(b) != stitches(layout.render_summary(lay({"path": f, "transform": tr})))


def test_qa4_trim_jumps_leaves_already_trimmed_jumps_alone(tmp_path):
    p = pe.EmbPattern()
    p.add_thread(RED)
    for x in range(0, 101, 20):
        p.stitch_abs(x, 0)
    p.trim()
    p.move_abs(400, 0)
    for x in range(400, 501, 20):
        p.stitch_abs(x, 0)
    p.end()
    f = tmp_path / "t.pes"
    pe.write(p, str(f), {"version": 6})
    before = layout.render_summary(lay({"path": str(f)}))["info"]
    after = layout.render_summary(lay({"path": str(f), "ops": [{"op": "jumps_to_trims", "min_mm": 3}]}))["info"]
    assert after["trims"] == before["trims"] and after["jumps"] == before["jumps"]


def _fill(i, x0, y0, x1, y1, color):
    return {"id": i, "kind": "fill", "geometry": {"outline": [[x0, y0, "c"], [x1, y0, "c"], [x1, y1, "c"], [x0, y1, "c"]]},
            "params": {}, "thread": {"color": color, "name": color}}


def test_qa4_sort_colors_never_puts_a_shape_under_one_meant_to_be_below():
    """A blue patch, a red heart on it and a small blue eye on the heart: gathering the blues would
    sew the eye before the heart, hiding it. The eye keeps its place; a note says why."""
    items = [_fill("patch", 0, 0, 40, 40, "#0000ff"), _fill("heart", 10, 10, 30, 30, "#ff0000"),
             _fill("eye", 15, 15, 25, 25, "#0000ff")]
    r = layout.render({"items": items, "color_sort": True})
    order = [sorted({x[3] for x in b.recs if x[2] == S and x[3] >= 0}) for b in r.blocks]
    assert order == [[0], [1], [2]]
    assert any(w["code"] == "color_sort" for w in r.warnings)
    # Shapes that don't overlap are still gathered.
    apart = [_fill("a", 0, 0, 10, 10, "#0000ff"), _fill("b", 20, 0, 30, 10, "#ff0000"), _fill("c", 40, 0, 50, 10, "#0000ff")]
    r = layout.render({"items": apart, "color_sort": True})
    assert [b.thread["color"] for b in r.blocks] == ["#0000ff", "#ff0000"]
    assert not any(w["code"] == "color_sort" for w in r.warnings)


def test_qa4_basting_box_comes_in_to_fit_the_hoop():
    d = _fill("a", 0, 0, 90, 60, "#ff0000")
    plain = layout.render_summary({"items": [d], "basting": {"enabled": True, "margin_mm": 5}})["info"]
    assert plain["width_mm"] > 100  # the old way: the box makes it too big for a 100 mm hoop
    fit = layout.render_summary({"items": [d], "basting": {"enabled": True, "margin_mm": 5, "fit_mm": [100, 100]}})
    assert fit["info"]["width_mm"] <= 100
    assert not fit["warnings"]
    # Too tight for even a 2 mm box: it stays 2 mm away and says so.
    big = _fill("a", 0, 0, 98, 60, "#ff0000")
    s = layout.render_summary({"items": [big], "basting": {"enabled": True, "margin_mm": 5, "fit_mm": [100, 100]}})
    assert s["info"]["width_mm"] == pytest.approx(98.1 + 4, abs=0.2)
    assert any(w["code"] == "basting_fit" for w in s["warnings"])


def test_qa4_a_stop_in_a_drawn_shape_is_dropped_with_a_note_once_the_shape_changes():
    obj = _fill("a", 0, 0, 20, 20, "#ff0000")
    r = layout.render({"items": [obj]})
    count = 1 + max(s for s, it in zip(r.src_of, r.item_of) if it == 0)
    ins = {"op": "insert", "after": 10, "command": "stop", "n": count}
    assert _stops(layout.render({"items": [{**obj, "ops": [ins]}]})) == 1
    bigger = _fill("a", 0, 0, 30, 20, "#ff0000")
    r = layout.render({"items": [{**bigger, "ops": [ins]}]})
    assert _stops(r) == 0
    assert any("shape changed" in w["message"] for w in r.warnings)


def test_qa4_split_export_never_replaces_earlier_files(tmp_path):
    d = {"items": [_fill("a", 0, 0, 150, 60, "#ff0000")]}
    first = layout.export_split(d, str(tmp_path / "big.pes"), {"width_mm": 100, "height_mm": 100})
    Path(first["paths"][0]).write_bytes(b"keep me")
    again = layout.export_split(d, str(tmp_path / "big.pes"), {"width_mm": 100, "height_mm": 100})
    assert Path(first["paths"][0]).read_bytes() == b"keep me"
    assert all(Path(p).name.startswith("big (1) ") for p in again["paths"])


def test_qa4_fabric_reaches_lettering_and_the_text_cache_key_covers_size_and_shape(font_path):
    text = {"kind": "text", "text": "IO", "font": {"path": font_path, "index": 0}, "size_mm": 15, "style": "fill"}
    woven = layout.render_summary({"items": [dict(text, id="t")], "fabric": "woven"})["info"]["stitches"]
    towel = layout.render_summary({"items": [dict(text, id="t")], "fabric": "towel"})["info"]["stitches"]
    assert woven != towel
    # Size and shape are part of the text cache key: changing them changes the stitches.
    small = layout.render_summary({"items": [dict(text, id="t", size_mm=8)]})["info"]
    big = layout.render_summary({"items": [dict(text, id="t", size_mm=16)]})["info"]
    assert big["width_mm"] > small["width_mm"] * 1.5
    arch = layout.render_summary({"items": [dict(text, id="t", shape={"type": "arch", "radius_mm": 30})]})["info"]
    straight = layout.render_summary({"items": [dict(text, id="t")]})["info"]
    assert (arch["width_mm"], arch["height_mm"]) != (straight["width_mm"], straight["height_mm"])


def test_qa4_a_stop_can_be_inserted_in_lettering(font_path):
    text = {"id": "t", "kind": "text", "text": "IO", "font": {"path": font_path, "index": 0}, "size_mm": 10, "style": "satin"}
    r = layout.render({"items": [text]})
    src = [s for s, it, (*_, c) in zip(r.src_of, r.item_of, r.pattern.stitches) if it == 0 and c & M == S]
    assert src == sorted(src) and src[0] >= 0  # lettering's records are numbered in sewing order
    r = layout.render({"items": [{**text, "ops": [{"op": "insert", "after": src[len(src) // 2], "command": "stop"}]}]})
    assert _stops(r) == 1


def test_qa4_gap_check_still_runs_with_many_shapes():
    items = [_fill("L", 0, 0, 20, 20, "#ff0000"), {**_fill("R", 20.3, 0, 40, 20, "#ff0000"), "params": {"angle_deg": -45}}]
    items += [_fill(f"s{i}", 60 + (i % 10) * 12, (i // 10) * 12, 68 + (i % 10) * 12, 8 + (i // 10) * 12, "#0000ff") for i in range(100)]
    assert "gap_0_1" in [c["code"] for c in layout.check({"items": items})["checks"]]


def test_qa4_thick_spots_in_a_bought_design_are_a_note_but_in_drawn_shapes_a_warning(tmp_path):
    p = pe.EmbPattern()
    p.add_thread(RED)
    for layer in range(4):  # four dense layers on top of each other, 10 x 10 mm
        for row in range(0, 101, 3):
            xs = range(0, 101, 20) if row % 2 == 0 else range(100, -1, -20)
            for x in xs:
                p.stitch_abs(x, row)
    p.end()
    f = tmp_path / "thick.pes"
    pe.write(p, str(f), {"version": 6})
    checks = {c["code"]: c["level"] for c in layout.check(lay({"path": str(f)}))["checks"]}
    assert checks.get("dense") == "info"
    stacked = [_fill(f"f{i}", 0, 0, 20, 20, "#ff0000") for i in range(4)]
    checks = {c["code"]: c["level"] for c in layout.check({"items": stacked})["checks"]}
    assert checks.get("dense") == "warning"


def test_qa4_fabric_presets_keep_spacing_in_range_and_suggest_knockdown():
    from threadline_engine import fabrics

    assert fabrics.apply({"kind": "fill", "params": {"spacing_mm": 4.0}}, "woven")["params"]["spacing_mm"] == 4.0
    assert fabrics.apply({"kind": "satin", "params": {"spacing_mm": 0.16}}, "woven")["params"]["spacing_mm"] == 0.16
    assert "knockdown" in fabrics.advice("towel").lower() and "knockdown" in fabrics.advice("fleece").lower()
    assert "knockdown" not in fabrics.advice("woven").lower()


# The cuts that cut-stops depend on (QA tests: they could vanish with no test failing).

PE550D = {"machine": "brother-pe550d", "hoop": "4x4", "cut_stops": {"enabled": True, "min_jump_mm": 3}}


def test_qa4_cut_stops_from_colours_joined_by_sorting(sq, tmp_path):
    other = write_square(tmp_path / "b.pes", offset=(500, 0))
    r = layout.preview_export(lay({"path": sq}, {"path": other}, color_sort=True), PE550D, "pes")
    assert r["stops_added"] >= 2  # each joined pair of same-colour halves is cut


def test_qa4_cut_stops_between_letters(font_path):
    text = {"id": "t", "kind": "text", "text": "I I I", "font": {"path": font_path, "index": 0}, "size_mm": 10, "style": "satin"}
    r = layout.preview_export({"items": [text]}, PE550D, "pes")
    assert r["stops_added"] == 2


def test_qa4_cut_stops_when_fewer_jumps_cant_hide_the_move():
    items = [_fill("a", 0, 0, 6, 6, "#ff0000"), _fill("b", 30, 0, 36, 6, "#ff0000")]
    r = layout.preview_export({"items": items, "travel_under": True}, PE550D, "pes")
    assert r["stops_added"] == 1


def test_qa4_jef_export_for_janome_sews_long_stitches_and_keeps_short_trims(tmp_path):
    p = pe.EmbPattern()
    p.add_thread(RED)
    p.stitch_abs(0, 0)
    p.stitch_abs(200, 0)  # 20 mm
    p.stitch_abs(210, 0)
    p.trim()
    p.move_abs(220, 0)  # a 1 mm move with a trim
    p.stitch_abs(230, 0)
    p.stitch_abs(240, 0)
    p.end()
    src = tmp_path / "s.pes"
    pe.write(p, str(src), {"version": 6})
    out = tmp_path / "s.jef"
    layout.export(lay({"path": str(src)}), str(out), {"machine": "janome-generic"})
    back = pe.read(str(out), {"trims": True})
    recs = [(x, y, c & M) for x, y, c in back.stitches]
    sewn = [(x, y) for x, y, k in recs if k == S]
    assert max(math.dist(a, b) for a, b in zip(sewn, sewn[1:])) <= 127
    assert sum(1 for *_, k in recs if k == T) >= 1
    first_jump = next((i for i, (*_, k) in enumerate(recs) if k == J and i > 1), None)
    assert first_jump is None or recs[first_jump - 1][2] == T  # no needle-up jump inside the long stitch


def test_qa4_machine_stitch_limit_is_an_error(isolated_data_dir, sq):
    import json

    d = isolated_data_dir / "machines"
    d.mkdir(parents=True, exist_ok=True)
    (d / "tiny.json").write_text(json.dumps({"id": "tiny", "name": "Tiny", "formats": ["pes"], "cuts": "trim",
                                             "hoops": [{"id": "h", "width_mm": 100, "height_mm": 100}], "max_stitches": 5}), encoding="utf-8")
    r = layout.preview_export(lay({"path": sq}), {"machine": "tiny"}, "pes")
    assert any(w["code"] == "max_stitches" and w["level"] == "error" for w in r["warnings"])


def test_qa4_source_cache_notices_a_changed_file_and_stays_small(tmp_path, monkeypatch):
    f = _row_file(tmp_path, n=5)
    assert layout.render_summary(lay({"path": f}))["info"]["stitches"] == 5
    st = os.stat(f)
    _row_file(tmp_path, n=8)  # rewritten with the same time stamp: the size gives it away
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert layout.render_summary(lay({"path": f}))["info"]["stitches"] == 8
    monkeypatch.setattr(layout.files, "_CACHE_MAX", 3)
    for i in range(6):
        layout.render(lay({"path": _row_file(tmp_path, name=f"r{i}.pes")}))
    assert len(layout._cache) <= 3


def _rows(path, colors):
    """One row of stitches per colour, row k at y = 10 k mm."""
    p = pe.EmbPattern()
    for k, col in enumerate(colors):
        p.add_thread(pe.EmbThread(col, col))
        if k:
            p.color_change()
            p.move_abs(0, 100 * k)
        for x in range(0, 201, 25):
            p.stitch_abs(x, 100 * k)
    p.end()
    pe.write(p, str(path), {"version": 6})


def test_qa2_p3_edits_stay_on_their_stitches_when_the_file_is_re_saved_elsewhere(tmp_path):
    """Decision 5: recolours, deleted colours and deleted stitches refer to the file's colour and
    stitch numbers; re-saving the placed file elsewhere put them on other stitches, silently."""
    from threadline_engine import project

    f = tmp_path / "rows.pes"
    _rows(f, ["#ff0000", "#0000ff"])
    edited = {"path": str(f), "threads": [None, {"color": "#00ff00", "name": "Green"}],
              "ops": [{"op": "delete_stitches", "indices": [3, 4, 5]}, {"op": "delete_block", "block": 0}]}
    before = layout.render_summary(lay(edited))
    assert [t["name"] for t in before["threads"]] == ["Green"]
    _rows(f, ["#ffff00", "#ff0000", "#0000ff"])  # re-saved in another program, one colour added
    os.utime(f, (os.path.getatime(f), os.path.getmtime(f) + 5))
    after = layout.render_summary(lay(edited))
    assert after["threads"] == before["threads"] and stitches(after) == stitches(before)
    # Saving embeds those same bytes, and the project reopens and sews the same.
    proj = {"layout": lay(edited)}
    saved = project.save(str(tmp_path / "p"), proj)
    reopened = project.open_project(saved["path"])
    assert stitches(layout.render_summary(reopened["layout"])) == stitches(before)
    # Without edits the item follows the file on disk, as before.
    assert len(layout.render_summary(lay({"path": str(f)}))["blocks"]) == 3
