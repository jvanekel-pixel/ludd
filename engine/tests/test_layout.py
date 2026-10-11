"""Layouts: placing, transforming, merging and editing stitch files without touching them."""

import math
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
    assert any(w["code"] == "color_sort" for w in sorted_["warnings"])

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
    f = tmp_path / "j.pes"
    pe.write(p, str(f), {"version": 6})
    before = layout.render_summary(lay({"path": str(f)}))["info"]["trims"]
    s = layout.render_summary(lay({"path": str(f), "ops": [{"op": "jumps_to_trims", "min_mm": 3}]}))
    assert s["info"]["trims"] == before + 1


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


def test_preview_export_with_cut_stops(sq):
    r = layout.preview_export(lay({"path": sq}), {"machine": "brother-pe550d", "cut_stops": {"enabled": True}}, "pes")
    assert "stops_added" in r and "info" in r


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
