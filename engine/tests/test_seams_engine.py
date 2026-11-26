"""Phase 3 engine seams: the layout package, render hooks, fill and line registries, the methods
package and the project feature tables. None of them may change a stitch."""

import dataclasses
import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pyembroidery as pe
import pytest
from shapely.geometry import Polygon

from invariants import assert_sane
from threadline_engine import layout, project
from threadline_engine.digitize import fills, lines
from threadline_engine.digitize.fills import FillPattern, Param
from threadline_engine.digitize.stitches import STITCH, DigitizeError, FillParams, generate, generate_parts, tatami
from threadline_engine.layout import passes
from threadline_engine.methods import dispatcher

MANIFEST = Path(__file__).parent / "snapshots" / "rpc_methods.json"

A1_NAMES = {
    "model": ["LayoutError", "Transform", "Block", "SCALE_WARN", "_thread_dict", "_thread_key", "_stitch_bounds",
              "_index", "_mm", "_record_count"],
    "files": ["_cache", "_CACHE_MAX", "_load", "_split_blocks", "_apply_ops", "_move_stitches", "_jumps_to_trims",
              "_transform"],
    "objects": ["OBJECT_KINDS", "OBJECT_LABEL", "DEFAULT_THREAD", "_object_cache", "_OBJECT_CACHE_MAX",
                "_generate_cached", "_object_blocks"],
    "text": ["_text_cache", "_letter_ring", "text_letters", "_text_block", "text_to_shapes"],
    "joins": ["_join", "_merge_same", "_join_objects", "COVER_CLOSE_MM", "_cover_cache", "_cover",
              "_join_same_thread_objects", "_footprint_cache", "_footprint", "_blocks_overlap", "_sort_by_thread"],
    "order": ["optimize_order"],
    "extras": ["BASTING_STITCH_MM", "BASTING_MIN_MM", "BASTING_THREAD", "_basting", "KNOCKDOWN_THREAD",
               "KNOCKDOWN_SPACING_MM", "_stitched_area", "_knockdown", "applique_svg", "_xml", "export_applique_svg"],
    "render": ["Rendered", "render", "render_summary", "_names", "check"],
    "export": ["split_plan", "export_split", "preview_export", "export"],
}

RED = pe.EmbThread("#ff0000", "Red", "1", brand="Test")
BLUE = pe.EmbThread("#0000ff", "Blue", "2", brand="Test")


def _square(path: Path) -> str:
    """Two color blocks 20 mm wide: the top edge in red, the bottom edge in blue."""
    p = pe.EmbPattern()
    p.add_thread(RED)
    p.add_thread(BLUE)
    for x in range(0, 201, 25):
        p.stitch_abs(x, 0)
    p.color_change()
    p.move_abs(0, 200)
    for x in range(0, 201, 25):
        p.stitch_abs(x, 200)
    p.end()
    pe.write(p, str(path), {"version": 6})
    return str(path)


def _width(blocks) -> float:
    xs = [r[0] for b in blocks for r in b.recs if r[2] == pe.STITCH]
    return max(xs) - min(xs)


@pytest.fixture
def hooks():
    """Registries restored after the test, whatever it registered."""
    saved = (dict(passes.ITEM_OPS_LOCAL), dict(passes.ITEM_OPS_PLACED), list(passes.AFTER_ITEMS), list(passes.AFTER_ORDER),
             list(passes.BEFORE_ITEMS))
    yield passes
    passes.ITEM_OPS_LOCAL.clear()
    passes.ITEM_OPS_LOCAL.update(saved[0])
    passes.ITEM_OPS_PLACED.clear()
    passes.ITEM_OPS_PLACED.update(saved[1])
    passes.AFTER_ITEMS[:] = saved[2]
    passes.AFTER_ORDER[:] = saved[3]
    passes.BEFORE_ITEMS[:] = saved[4]


# ---------------------------------------------------------------- layout package


def test_layout_package_keeps_every_old_name():
    for module, names in A1_NAMES.items():
        # import_module: `layout.render` and `layout.export` are the functions, as they always were.
        sub = importlib.import_module(f"threadline_engine.layout.{module}")
        for name in names:
            assert hasattr(layout, name), name
            assert getattr(layout, name) is getattr(sub, name), f"{module}.{name}"
    assert callable(layout.render) and callable(layout.export)


def test_layout_caches_are_shared_objects():
    assert layout._text_cache is layout.text._text_cache
    assert layout._object_cache is layout.objects._object_cache
    assert layout._cover_cache is layout.joins._cover_cache
    assert layout._footprint_cache is layout.joins._footprint_cache
    assert layout._cache is layout.files._cache


# ---------------------------------------------------------------- render hooks


def _unused_passes(monkeypatch):
    """A fresh copy of passes.py, which no feature has registered anything on."""
    name = "threadline_engine.layout._unused_passes"
    spec = importlib.util.spec_from_file_location(name, passes.__file__)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)  # dataclasses look their module up
    spec.loader.exec_module(module)
    return module


def test_render_hooks_start_empty(monkeypatch):
    fresh = _unused_passes(monkeypatch)
    assert fresh.ITEM_OPS_LOCAL == {}
    assert fresh.ITEM_OPS_PLACED == {}
    assert fresh.AFTER_ITEMS == []
    assert fresh.AFTER_ORDER == []


def test_before_items_starts_empty(monkeypatch):
    assert _unused_passes(monkeypatch).BEFORE_ITEMS == []


def test_the_repairs_register_on_the_hooks_the_spec_names():
    assert "rebuild" in passes.ITEM_OPS_LOCAL
    assert {"filter_small", "declump", "density_limit"} <= set(passes.ITEM_OPS_PLACED)
    assert "remove_overlap" in [name for name, _ in passes.BEFORE_ITEMS]
    assert "remove_hidden" in [name for name, _ in passes.AFTER_ITEMS]


def test_importing_the_repairs_first_registers_them_once():
    """The repairs import the layout package, which imports them back: either order must work."""
    code = """
import threadline_engine.repair.recognize
from threadline_engine.layout import passes

assert "rebuild" in passes.ITEM_OPS_LOCAL
assert [n for n, _ in passes.BEFORE_ITEMS].count("remove_overlap") == 1
"""
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120,
                          cwd=Path(__file__).resolve().parents[1])
    assert done.returncode == 0, done.stderr


def test_before_items_pass_changes_the_layout_and_can_leave_a_note(tmp_path, hooks):
    def shifted(lay):
        moved = [{**it, "transform": {"x": -7}} for it in lay["items"]]
        note = {"level": "info", "code": "test_moved", "message": "Moved 7 mm left"}
        return {**lay, "items": moved, passes.NOTES_KEY: [*lay.get(passes.NOTES_KEY, []), note]}

    sq = _square(tmp_path / "sq.pes")
    lay = {"items": [{"id": "a", "path": sq}], passes.NOTES_KEY: [{"level": "error", "code": "planted", "message": "x"}]}
    before = layout.render({"items": [{"id": "a", "path": sq}]})
    hooks.register_pass("before_items", "test_shifted", shifted)
    with pytest.raises(ValueError):
        hooks.register_pass("before_items", "test_shifted", shifted)
    kept_copy = json.dumps(lay, sort_keys=True)
    after = layout.render(lay)
    assert min(r[0] for b in after.blocks for r in b.recs) == pytest.approx(min(r[0] for b in before.blocks for r in b.recs) - 70)
    assert [w["code"] for w in after.warnings] == ["test_moved"]  # the pass's note, never one planted in the file
    assert json.dumps(lay, sort_keys=True) == kept_copy  # the caller's layout is left alone


def test_placed_item_op_runs_after_the_transform(tmp_path, hooks):
    seen = []

    def probe(blocks, op, ctx):
        seen.append((_width(blocks), ctx.index, op.get("op")))
        ctx.notes.append("probed")
        return blocks

    hooks.register_item_op("test_probe", probe, stage="placed")
    with pytest.raises(ValueError):
        hooks.register_item_op("test_probe", probe, stage="local")
    sq = _square(tmp_path / "sq.pes")
    item = {"id": "a", "path": sq, "transform": {"scale_x": 2, "scale_y": 2}, "ops": [{"op": "test_probe"}]}
    s = layout.render_summary({"items": [item]})
    assert seen == [(pytest.approx(400), 0, "test_probe")]
    assert any(w["code"] == "item_0_0" and "probed" in w["message"] for w in s["warnings"])
    # Unregistered, the op is ignored as before.
    hooks.ITEM_OPS_PLACED.clear()
    plain = layout.render_summary({"items": [{k: v for k, v in item.items() if k != "ops"}]})
    assert layout.render_summary({"items": [item]})["records"] == plain["records"]


def test_local_item_op_can_take_over_scaling(tmp_path, hooks):
    def unscaled(blocks, op, ctx):
        assert _width(blocks) == pytest.approx(200)  # still in the file's own frame
        ctx.transform = dataclasses.replace(ctx.transform, scale_x=1.0, scale_y=1.0)
        return blocks

    hooks.register_item_op("test_unscaled", unscaled, stage="local")
    sq = _square(tmp_path / "sq.pes")
    item = {"id": "a", "path": sq, "transform": {"scale_x": 2, "scale_y": 2}}
    scaled = layout.render({"items": [item]})
    assert _width(scaled.blocks) == pytest.approx(400)
    took = layout.render({"items": [{**item, "ops": [{"op": "test_unscaled"}]}]})
    assert _width(took.blocks) == pytest.approx(200)


def test_after_items_pass_can_drop_a_block(tmp_path, hooks):
    def no_blue(blocks, lay, warnings):
        return [b for b in blocks if b.thread.get("color", "").lower() != "#0000ff"]

    hooks.register_pass("after_items", "test_no_blue", no_blue)
    sq = _square(tmp_path / "sq.pes")
    s = layout.render_summary({"items": [{"id": "a", "path": sq}]})
    assert s["info"]["colors"] == 1
    assert [t["color"].lower() for t in s["threads"]] == ["#ff0000"]


# ---------------------------------------------------------------- fill patterns


def test_six_fill_patterns_registered_in_order():
    assert list(fills.REGISTRY)[:6] == ["tatami", "gradient", "wave", "contour", "stipple", "cross"]  # new ones after


def test_unknown_fill_pattern_message_unchanged():
    with pytest.raises(DigitizeError, match="^Unknown fill pattern: nope$"):
        FillParams.from_dict({"pattern": "nope"})
    with pytest.raises(DigitizeError, match="^Unknown fill pattern: nope$"):
        fills.get("nope")


def test_registered_pattern_params_are_range_checked():
    fills.register(FillPattern("test_throwaway", "rows", params={"test_size_mm": Param(1, 0.5, 2, "Test size")},
                               rows=lambda p: {}, step_mm2=lambda p: p.spacing_mm * p.stitch_mm))
    try:
        with pytest.raises(ValueError):
            fills.register(FillPattern("test_throwaway", "rows"))
        p = FillParams.from_dict({"pattern": "test_throwaway"})
        assert p.value("test_size_mm") == 1 and p.value("spacing_mm") == 0.4
        assert FillParams.from_dict({"pattern": "test_throwaway", "test_size_mm": 1.5}).extra == {"test_size_mm": 1.5}
        with pytest.raises(DigitizeError, match="^Test size must be between 0.5 and 2 mm$"):
            FillParams.from_dict({"pattern": "test_throwaway", "test_size_mm": 3})
    finally:
        fills.REGISTRY.pop("test_throwaway", None)


# ---------------------------------------------------------------- parts: one per thread (Phase 6)


def test_one_part_objects_are_unchanged():
    from test_digitize import SNAPSHOT_CASES

    for name, obj in SNAPSHOT_CASES.items():
        parts = generate_parts(obj)
        assert [slot for _, _, slot in parts] == [0], name
        assert (parts[0][0], parts[0][1]) == generate(obj), name


def _two_parts(pieces, params):
    """A throwaway pattern: rows across in the shape's thread, then rows down in a second one."""
    return [(tatami(pieces[0], 0, 1.0, 3.5, 0.0), [], 0), (tatami(pieces[0], 90, 1.0, 3.5, 0.0), ["Second part."], 1)]


@pytest.fixture
def throwaway_pattern():
    added = []

    def add(spec):
        fills.register(spec)
        added.append(spec.name)

    yield add
    for name in added:
        fills.REGISTRY.pop(name, None)
    layout._object_cache.clear()


def _thread(color):
    return {"color": color, "name": color, "catalog": "", "brand": ""}


OUTLINE = [[0, 0, "c"], [20, 0, "c"], [20, 20, "c"], [0, 20, "c"]]


def test_threads_k_overrides_slot_k(throwaway_pattern):
    throwaway_pattern(FillPattern("test_two_parts", "rows", parts=_two_parts, rows=lambda p: {},
                                  step_mm2=lambda p: p.spacing_mm * p.stitch_mm))
    item = {"id": "a", "kind": "fill", "geometry": {"outline": OUTLINE}, "thread": _thread("#cc0000"),
            "params": {"pattern": "test_two_parts", "blend": [_thread("#0000cc")]}}
    r = layout.render({"items": [item]})
    assert [b.thread["color"] for b in r.blocks] == ["#cc0000", "#0000cc"]
    assert [b.sources for b in r.blocks] == [[(0, 0)], [(0, 1)]]
    sources = [rec[4] for b in r.blocks for rec in b.recs if rec[4] >= 0]
    assert sources == sorted(set(sources))  # numbered through both parts, none twice
    assert any("Second part." in w["message"] for w in r.warnings)
    green = layout.render({"items": [{**item, "threads": [None, _thread("#00cc00")]}]})
    assert [b.thread["color"] for b in green.blocks] == ["#cc0000", "#00cc00"]
    assert [b.original["color"] for b in green.blocks] == ["#cc0000", "#0000cc"]
    both = layout.render({"items": [{**item, "threads": [_thread("#222222"), _thread("#00cc00")]}]})
    assert [b.thread["color"] for b in both.blocks] == ["#222222", "#00cc00"]
    # As one list of records (generate), the thread change is a trim and a jump.
    recs, warnings = generate(item)
    assert warnings == ["Second part."] and sum(1 for *_, k in recs if k == pe.TRIM) == 1


def test_a_covering_open_pattern_may_have_cross_hatch_and_edge_pad(throwaway_pattern):
    asked = []

    def lines_across(poly, params, pos):
        asked.append(poly.bounds)
        x0, y0, x1, y1 = poly.bounds
        return [[(x0, y), (x1, y)] for y in (y0 + 1, (y0 + y1) / 2, y1 - 1)], []

    throwaway_pattern(FillPattern("test_cover", "open", paths=lines_across, covers=True,
                                  step_mm2=lambda p: 1.0))
    throwaway_pattern(FillPattern("test_open", "open", paths=lines_across, step_mm2=lambda p: 1.0))
    obj = {"kind": "fill", "geometry": {"outline": OUTLINE},
           "params": {"pattern": "test_cover", "pull_comp_mm": 1.0, "underlay": ["tatami"]}}
    covering = generate(obj)[0]
    plain = generate({**obj, "params": {**obj["params"], "pattern": "test_open"}})[0]
    assert asked[0] == pytest.approx((-0.5, -0.5, 20.5, 20.5))  # widened by the pull compensation
    assert asked[1] == pytest.approx((0, 0, 20, 20))
    assert len(covering) > len(plain)  # the cross-hatch


# ---------------------------------------------------------------- line styles


def test_line_styles_and_motifs_registered():
    assert list(lines.REGISTRY) == ["single", "triple", "bean", "motif"]
    assert list(lines.MOTIF_UNITS) == ["wave", "zigzag", "scallop", "blanket", "leaf"]  # LUDD 1.0's four, then Phase 5's
    assert all(callable(s.points) for s in lines.REGISTRY.values())


# ---------------------------------------------------------------- methods


def test_rpc_method_list_matches_the_manifest():
    names = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(names) == 66
    assert sorted(dispatcher._methods) == names


# ---------------------------------------------------------------- tatami's row hooks (Phase 6)


SQUARE_20 = Polygon([(0, 0), (20, 0), (20, 20), (0, 20)])


def _row_heights(recs) -> list[float]:
    return sorted({round(y, 6) for _, y, k in recs if k == STITCH})


def test_row_ys_places_the_rows():
    heights = [1.0, 2.5, 6.0, 6.4, 8.9]
    recs = tatami(SQUARE_20, 0, 0.4, 3.5, 0.0, row_ys=heights)
    assert _row_heights(recs) == heights
    assert_sane(recs, inside=SQUARE_20)
    assert tatami(SQUARE_20, 0, 0.4, 3.5, 0.0, row_ys=[]) == []


def test_rows_far_apart_are_joined_by_travel_not_one_long_stitch():
    recs = tatami(SQUARE_20, 0, 0.4, 3.5, 0.0, row_ys=[1.0, 1.4, 19.0, 19.4])
    assert_sane(recs, inside=SQUARE_20, max_jumps=0)
    assert {1.0, 1.4, 19.0, 19.4} <= set(_row_heights(recs))


def _inner_points(recs, y: float, stitch: float = 3.5) -> list[float]:
    """The needle points inside a row at height y, as fractions of a stitch past the grid's origin."""
    xs = sorted(x for x, yy, k in recs if k == STITCH and abs(yy - y) < 1e-9)
    return [round((x / stitch) % 1, 6) % 1 for x in xs[1:-1]]


def test_offsets_shift_each_rows_needle_points():
    shifts = [0.0, 0.5, 0.25]
    recs = tatami(SQUARE_20, 0, 0.4, 3.5, 0.0, offsets=lambda r: shifts[r % 3])
    for r in range(6):
        assert set(_inner_points(recs, 0.2 + 0.4 * r)) == {shifts[r % 3]}, r
    # The standard weave, written out, is what tatami does without the hook.
    plain = tatami(SQUARE_20, 45, 0.4, 3.5, 0.1)
    written = tatami(SQUARE_20, 45, 0.4, 3.5, 0.1, offsets=lambda r: (r % 3) / 3)
    assert [(round(x, 6), round(y, 6), k) for x, y, k in written] == [(round(x, 6), round(y, 6), k) for x, y, k in plain]


def test_forced_points_are_needle_points_that_nothing_crowds():
    recs = tatami(SQUARE_20, 0, 0.4, 3.5, 0.0, forced=lambda y, x0, x1: [7.0, 7.1, 0.1, 25.0])
    for r in range(50):
        xs = sorted(x for x, y, k in recs if k == STITCH and abs(y - (0.2 + 0.4 * r)) < 1e-9)
        # 7.0 is taken; 7.1 (crowding it), 0.1 (at the end) and 25 (off the row) are not.
        assert any(abs(x - 7.0) < 1e-9 for x in xs), r
        assert [x for x in xs if abs(x - 7.0) < 0.8] == [pytest.approx(7.0)], r
        assert max(b - a for a, b in zip(xs, xs[1:])) <= 3.5 + 1e-9, r
    assert_sane(recs, inside=SQUARE_20)


def test_forced_gets_the_ripple_on_a_wave_fill():
    asked = []

    def at_ten(y, x0, x1, bend=None):
        asked.append((y, bend(10.0)))
        return [10.0]

    recs = tatami(SQUARE_20, 0, 0.4, 3.5, 0.0, wave=(1.5, 8.0), forced=at_ten)
    # Every row has a needle at x = 10, where its ripple is.
    for y, bent in asked:
        assert any(k == STITCH and abs(x - 10.0) < 1e-9 and abs(yy - bent) < 1e-9 for x, yy, k in recs), y


def _row_ends(recs, y: float) -> tuple[float, float]:
    xs = [x for x, yy, k in recs if k == STITCH and abs(yy - y) < 1e-9]
    return min(xs), max(xs)


def test_end_shift_moves_the_ends_and_splits_long_steps():
    # Every other row pulled in 6 mm on the left: the steps between rows would be 6 mm long.
    pulled = tatami(SQUARE_20, 0, 0.4, 3.5, 0.0, end_shift=lambda r, x0, x1: (x0 + 6 * (r % 2), x1))
    for r in range(50):
        assert _row_ends(pulled, 0.2 + 0.4 * r)[0] == pytest.approx(6 * (r % 2)), r
    assert_sane(pulled, inside=SQUARE_20, max_stitch_mm=3.6, max_jumps=0)


def test_end_shift_can_reach_past_the_shape_without_jumps():
    out = tatami(SQUARE_20, 0, 0.4, 3.5, 0.0, end_shift=lambda r, x0, x1: (x0 - 0.6, x1 + 0.6))
    assert _row_ends(out, 0.2) == (pytest.approx(-0.6), pytest.approx(20.6))
    assert_sane(out, inside=SQUARE_20, tolerance_mm=0.61, max_jumps=0)


def test_a_row_is_always_sewn_however_its_ends_move():
    squashed = tatami(SQUARE_20, 0, 0.4, 3.5, 0.0, end_shift=lambda r, x0, x1: (x0 + 100, x1 - 100))
    assert len(_row_heights(squashed)) == 50


# ---------------------------------------------------------------- project features


def _old_features(lay):
    """The detector as it was before Phase 3 (copied unchanged), to compare the tables against."""
    used = set()
    if lay.get("travel_under"):
        used.add("travel_under")
    if lay.get("jumps_to_trims") is not None:
        used.add("trim_jumps_all")
    for it in lay.get("items") or []:
        if not isinstance(it, dict):
            continue
        p = it.get("params") if isinstance(it.get("params"), dict) else {}
        g = it.get("geometry") if isinstance(it.get("geometry"), dict) else {}
        if it.get("kind") in ("fill", "applique") and p.get("pattern") not in (None, "", "tatami"):
            used.add("fill_patterns")
        if it.get("kind") == "run" and p.get("style") == "motif":
            used.add("motif_lines")
        if it.get("kind") == "satin" and g.get("nodes") is not None:
            used.add("satin_ribbons")
        if it.get("kind") == "text" and isinstance(it.get("shape"), dict) and it["shape"].get("type") == "path":
            used.add("text_on_path")
        if any(isinstance(o, dict) and o.get("op") in ("delete_stitches", "move_stitch", "move_stitches") for o in it.get("ops") or []):
            used.add("stitch_edits")
    return used


#: The feature names LUDD 1.0.1 knows. Each later feature gets its own name beside them.
OLD_FEATURES = {"fill_patterns", "motif_lines", "satin_ribbons", "stitch_edits", "text_on_path", "travel_under",
                "trim_jumps_all"}


def test_known_features_unchanged():
    assert OLD_FEATURES <= project.KNOWN_FEATURES


def test_feature_tables_match_old_detector():
    items = [
        {"kind": "fill", "params": {"pattern": "wave"}},
        {"kind": "fill", "params": {"pattern": "tatami"}},
        {"kind": "fill", "params": {"pattern": ""}},
        {"kind": "applique", "params": {"pattern": "cross"}},
        {"kind": "run", "params": {"style": "motif"}},
        {"kind": "run", "params": {"style": "triple"}},
        {"kind": "satin", "geometry": {"nodes": []}},
        {"kind": "satin", "geometry": {"rail_a": []}},
        {"kind": "text", "shape": {"type": "path"}},
        {"kind": "text", "shape": {"type": "arch"}},
        {"kind": "file", "ops": [{"op": "move_stitch"}]},
        {"kind": "file", "ops": [{"op": "delete_block"}, "junk"]},
        {"kind": "fill", "params": "junk", "geometry": "junk"},
        "junk",
    ]
    layouts = [{}, {"travel_under": True}, {"jumps_to_trims": 0}, {"jumps_to_trims": None, "travel_under": False}]
    layouts += [{"items": [it]} for it in items]
    layouts.append({"items": items, "travel_under": True, "jumps_to_trims": 3})
    for lay in layouts:
        assert project._features(lay) == _old_features(lay), lay
    assert project._features(layouts[-1]) == OLD_FEATURES
