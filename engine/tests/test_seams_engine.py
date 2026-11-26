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

from threadline_engine import layout, project
from threadline_engine.digitize import fills, lines
from threadline_engine.digitize.fills import FillPattern, Param
from threadline_engine.digitize.stitches import DigitizeError, FillParams
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


# ---------------------------------------------------------------- line styles


def test_line_styles_and_motifs_registered():
    assert list(lines.REGISTRY) == ["single", "triple", "bean", "motif"]
    assert list(lines.MOTIF_UNITS)[:4] == ["wave", "zigzag", "scallop", "blanket"]  # LUDD 1.0's, in their order
    assert all(callable(s.points) for s in lines.REGISTRY.values())


# ---------------------------------------------------------------- methods


def test_rpc_method_list_matches_the_manifest():
    names = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(names) == 64
    assert sorted(dispatcher._methods) == names


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
