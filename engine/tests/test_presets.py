"""Stitch presets (P7-C4): a shape's settings kept under a name, shared as .luddpreset files.
A user's name never becomes a path, and a file is checked before it's trusted."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from threadline_engine import layout as L
from threadline_engine import presets
from threadline_engine.digitize import fills, lines
from threadline_engine.methods.registry import dispatcher

BLEND = [{"color": "#00aa00", "name": "Green", "catalog": "", "brand": ""}]
HILL = [[0.0, 0.0], [0.5, -0.4], [1.0, 0.0]]
BUILTINS = ["Light sketch fill", "Bold outline", "Redwork line", "Narrow satin border", "Felt applique"]


def preset(name="Mine", kind="fill", params=None, **extra):
    return {"name": name, "kind": kind, "params": {"spacing_mm": 0.6} if params is None else params, **extra}


def write(path: Path, data, raw: str | None = None) -> str:
    path.write_text(raw if raw is not None else json.dumps(data), encoding="utf-8")
    return str(path)


def a_file(tmp_path: Path, data: dict, name="in.luddpreset") -> str:
    return write(tmp_path / name, {"format": "ludd-preset", "version": 1, **data})


def mine():
    return [p for p in presets.list_presets() if not p["builtin"]]


def folder(data_dir: Path) -> Path:
    return data_dir / "presets"


def stored(data_dir: Path) -> list[str]:
    f = folder(data_dir)
    return sorted(p.name for p in f.iterdir()) if f.exists() else []


def test_save_list_delete_round_trip(isolated_data_dir):
    listed = presets.list_presets()
    assert [p["name"] for p in listed] == BUILTINS and all(p["builtin"] for p in listed)
    assert [p["kind"] for p in listed] == ["fill", "run", "run", "satin", "applique"]

    # A shape's own things, keys LUDD doesn't know and empty values are left out.
    shape = {"spacing_mm": 0.8, "pattern": "tatami", "underlay": ["edge"], "tie_in": False, "angle_deg": 30,
             "reverse": True, "start_mm": [1, 2], "end_mm": [3, 4], "angle_line": [[0, 0], [1, 1]],
             "angle_lines": [[[0, 0], [1, 1]]], "ripple_center": [0, 0], "blend_flip": True, "push_comp_mm": 0.3,
             "selected": True, "hand_pct": None}
    saved = presets.save(preset("Soft green", "fill", shape, note="  For\nbaby  blankets "))
    assert saved == {"id": "soft-green"}
    [p] = mine()
    assert p == {"id": "soft-green", "name": "Soft green", "kind": "fill", "builtin": False,
                 "params": {"spacing_mm": 0.8, "pattern": "tatami", "underlay": ["edge"], "tie_in": False},
                 "width_mm": None, "note": "For baby blankets"}
    assert stored(isolated_data_dir) == ["soft-green.luddpreset"]

    # The same name (however it's capitalized) is replaced only when asked.
    with pytest.raises(presets.PresetError, match="already have a preset called"):
        presets.save(preset("soft GREEN", "fill"))
    assert presets.save(preset("soft GREEN", "fill", {"spacing_mm": 0.5}), replace=True) == {"id": "soft-green"}
    assert [(p["name"], p["params"]) for p in mine()] == [("soft GREEN", {"spacing_mm": 0.5})]
    # Another kind may use the name too, in a file of its own.
    assert presets.save(preset("Soft green", "run", {"style": "bean"})) == {"id": "soft-green-2"}
    # A built-in's name stays its own.
    with pytest.raises(presets.PresetError, match="built-in"):
        presets.save(preset("bold outline", "run", {"style": "triple"}), replace=True)

    presets.delete("soft-green")
    assert [p["id"] for p in mine()] == ["soft-green-2"]
    with pytest.raises(presets.PresetError, match="isn't in your list"):
        presets.delete("soft-green")


@pytest.mark.parametrize("name", [
    "../../evil", "..\\..\\evil", "C:\\Windows\\evil", "/etc/passwd", "CON", "con.txt", "NUL", "nul", "COM1", "LPT1",
    "Aux.Backup", "COM¹", "a" * 500, "x\x00y", "日本語", "..evil..", "   Padded   ",
])
def test_names_cannot_escape_the_presets_folder(name, isolated_data_dir, tmp_path):
    outside = write(tmp_path / "keep.luddpreset", None, raw="not a preset")
    before = sorted(str(p) for p in tmp_path.rglob("*") if folder(isolated_data_dir) not in p.parents)
    saved = presets.save(preset(name))
    stem = saved["id"]
    assert stored(isolated_data_dir) == [f"{stem}.luddpreset"]
    # An ordinary file name every computer takes: lower-case letters, digits and hyphens, not too long.
    assert len(stem) <= 72 and all(c.isascii() and (c.islower() or c.isdigit() or c == "-") for c in stem)
    assert stem.split(".")[0] not in {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}
    [p] = mine()
    assert p["id"] == stem and "\x00" not in p["name"] and len(p["name"]) <= 80
    after = sorted(str(q) for q in tmp_path.rglob("*") if folder(isolated_data_dir) not in q.parents)
    assert [a for a in after if a not in before and Path(a) != folder(isolated_data_dir) and Path(a) != isolated_data_dir] == []
    presets.delete(stem)
    assert stored(isolated_data_dir) == [] and Path(outside).read_text() == "not a preset"


def test_a_name_is_needed(isolated_data_dir):
    for blank in ("", "   ", "\t\n", None, 7):
        with pytest.raises(presets.PresetError, match="Give the preset a name"):
            presets.save(preset(blank))
    assert stored(isolated_data_dir) == []


def test_deleting_and_exporting_only_reach_listed_presets(isolated_data_dir, tmp_path):
    victim = tmp_path / "victim.luddpreset"
    victim.write_text("keep me", encoding="utf-8")
    (isolated_data_dir / "other.luddpreset").parent.mkdir(parents=True, exist_ok=True)
    (isolated_data_dir / "other.luddpreset").write_text("{}", encoding="utf-8")
    for bad in ("../other", "..\\other", str(victim)[:-len(".luddpreset")], "CON", "a/b", "", None, 3, "builtin:nope"):
        with pytest.raises(presets.PresetError):
            presets.delete(bad)
        with pytest.raises(presets.PresetError):
            presets.export(bad, str(tmp_path / "out.luddpreset"))
    assert victim.read_text() == "keep me" and (isolated_data_dir / "other.luddpreset").exists()


@pytest.mark.parametrize("data, words", [
    ({"kind": "fill", "params": {"spacing_mm": 99}}, "Fill spacing must be between"),
    ({"kind": "fill", "params": {"stitch_mm": 0.1}}, "Fill stitch length must be between"),
    # A setting the file's own pattern doesn't use is checked too: another pattern could be chosen later.
    ({"kind": "fill", "params": {"pattern": "tatami", "spiral_mm": 100}}, "Ring spacing must be between"),
    ({"kind": "fill", "params": {"pattern": "blend", "blend": [BLEND[0]] * 4}}, "up to four colors"),
    ({"kind": "fill", "params": {"pattern": "blend", "blend": [{"color": "green"}]}}, "color"),
    ({"kind": "satin", "params": {"split_mm": 100}}, "Split satin stitches"),
    ({"kind": "satin", "params": {}, "width_mm": 40}, "width must be between"),
    ({"kind": "run", "params": {"stitch_mm": 40}}, "Stitch length must be between"),
    ({"kind": "run", "params": {"style": "single", "motif_mm": 100}}, "A motif repeats every"),
    ({"kind": "run", "params": {"style": "motif", "motif": "user:mine"}}, "doesn't carry it"),
    ({"kind": "run", "params": {"style": "motif", "motif": "user:x", "motif_unit": [[0, 0]] * 1000}}, "motif"),
    ({"kind": "applique", "params": {"cover_width_mm": 50}}, "applique border must be between"),
    ({"kind": "fill", "params": {"hand_pct": 400}}, "hand-sewn look"),
    ({"kind": "fill", "params": {"spacing_mm": "0.4"}}, "must be a number"),
    ({"kind": "fill", "params": {"spacing_mm": True}}, "must be a number"),
    ({"kind": "fill", "params": {"tie_in": "no"}}, "must be on or off"),
    ({"kind": "fill", "params": {"underlay": "edge"}}, "underlay"),
    ({"kind": "fill", "params": {"pattern": 3}}, "pattern"),
    ({"kind": "fill", "params": {"spacing_mm": 10**400}}, "far bigger"),
    ({"kind": "fill", "params": {"random_pct": 1e12}}, "far bigger"),
    ({"kind": "fill", "params": [1]}, "isn't a LUDD preset"),
    ({"params": {}}, "isn't a LUDD preset"),
    ({"kind": "fill", "params": {}, "name": 5}, "isn't a LUDD preset"),
])
def test_import_refuses_out_of_range_settings(data, words, isolated_data_dir, tmp_path):
    with pytest.raises(presets.PresetError, match=words):
        presets.import_file(a_file(tmp_path, {"name": "Bad", **data}))
    assert stored(isolated_data_dir) == []


@pytest.mark.parametrize("raw, words", [
    ('{"format": "ludd-preset", "version": 1, "name": "N", "kind": "fill", "params": {"spacing_mm": NaN}}', "isn't a LUDD preset"),
    ('{"format": "ludd-preset", "version": 1, "name": "N", "kind": "fill", "params": {"spacing_mm": -Infinity}}', "isn't a LUDD preset"),
    ('{"format": "ludd-preset", "version": 1, "name": "N", "kind": "fill", "params": {"spacing_mm": 1e999}}', "far bigger"),
    ('{"format": "ludd-motif", "version": 1, "name": "N", "unit": []}', "isn't a LUDD preset"),
    ('{"format": "ludd-preset", "version": "1", "name": "N", "kind": "fill", "params": {}}', "isn't a LUDD preset"),
    ("[" * 100_000, "isn't a LUDD preset"),
    ("not json", "isn't a LUDD preset"),
    ('{"format": "ludd-preset", "version": 1, "name": "N", "kind": "fill", "params": {}, "note": "' + "x" * 300_000 + '"}', "too big"),
])
def test_import_refuses_broken_and_hostile_files(raw, words, isolated_data_dir, tmp_path):
    with pytest.raises(presets.PresetError, match=words):
        presets.import_file(write(tmp_path / "bad.luddpreset", None, raw=raw))
    assert stored(isolated_data_dir) == []


def test_import_needs_a_real_file(tmp_path):
    for bad in ("", None, str(tmp_path / "missing.luddpreset"), str(tmp_path)):
        with pytest.raises(presets.PresetError):
            presets.import_file(bad)


@pytest.mark.parametrize("data", [
    {"kind": "fill", "params": {"pattern": "hexagons"}},
    {"kind": "run", "params": {"style": "chain"}},
    {"kind": "fill", "params": {"weave": "basket"}},
    {"kind": "fill", "params": {"feather": "top"}},
    {"kind": "fill", "params": {"pattern": "motif", "motif": "dragon"}},
    {"kind": "run", "params": {"motif": "dragon"}},
    {"kind": "satin", "params": {"underlay": ["foam"]}},
    {"kind": "satin", "params": {"underlay_level": "extreme"}},
    {"kind": "applique", "params": {"tack": "glue"}},
    {"kind": "fill", "params": {"tie_style": "knotty"}},
    {"kind": "fill", "params": {"sparkle_mm": 2}},
    {"kind": "satin", "params": {"cover_width_mm": 3}},
    {"kind": "patch", "params": {}},
    {"kind": "fill", "params": {}, "version": 2},
])
def test_import_refuses_a_newer_pattern(data, isolated_data_dir, tmp_path):
    with pytest.raises(presets.PresetError, match="newer LUDD"):
        presets.import_file(a_file(tmp_path, {"name": "Future", **data}))
    assert stored(isolated_data_dir) == []


def test_import_leaves_out_what_belongs_to_one_shape_and_stray_extras(isolated_data_dir, tmp_path):
    path = a_file(tmp_path, {"name": "Rows", "kind": "fill", "width_mm": 3, "extra_key": 1,
                             "params": {"spacing_mm": 0.5, "angle_deg": 10, "start_mm": [1, 1], "push_comp_mm": 0.2,
                                        "blend": [{"color": "#112233", "name": "N", "extra": "x"}]}})
    added = presets.import_file(path)
    assert added == {"id": "rows", "name": "Rows", "kind": "fill"}
    [p] = mine()
    assert p["params"] == {"spacing_mm": 0.5, "blend": [{"color": "#112233", "name": "N", "catalog": "", "brand": ""}]}
    assert p["width_mm"] is None


def test_export_then_import_is_equal(isolated_data_dir, tmp_path):
    saves = [
        preset("Blue blend", "fill", {"pattern": "blend", "blend": BLEND, "blend_balance": 0.5, "spacing_mm": 0.45,
                                      "underlay": ["tatami"], "weave": "brick", "tie_off": False}, note="Two greens"),
        preset("My hills", "run", {"style": "motif", "motif": "user:hill", "motif_unit": HILL, "motif_mm": 6,
                                   "motif_width_mm": 3, "stitch_mm": 2}),
        preset("Wide edge", "satin", {"spacing_mm": 0.35, "underlay": ["edge", "zigzag"], "split_mm": 7,
                                      "pull_comp_mm": 0.3}, width_mm=5.5),
    ]
    out = tmp_path / "shared"
    out.mkdir()
    for s in saves:
        presets.save(s)
    originals = mine()
    for p in originals:
        dest = presets.export(p["id"], str(out / p["name"]))["path"]
        assert Path(dest) == out / f"{p['name']}.luddpreset"
        data = json.loads(Path(dest).read_text(encoding="utf-8"))
        assert data["format"] == "ludd-preset" and data["version"] == 1
        # Importing it beside the original adds a second one, under its own name and file.
        added = presets.import_file(dest)
        assert added["name"] == f"{p['name']} (2)" and added["id"] != p["id"]
        copy = next(q for q in mine() if q["id"] == added["id"])
        assert {k: copy[k] for k in ("kind", "params", "width_mm", "note")} == {k: p[k] for k in ("kind", "params", "width_mm", "note")}
    # Without the originals, importing gives exactly them back.
    for p in originals:
        presets.delete(p["id"])
    for q in mine():
        presets.delete(q["id"])
    for p in originals:
        presets.import_file(str(out / f"{p['name']}.luddpreset"))
    strip = lambda q: {k: v for k, v in q.items() if k != "id"}  # noqa: E731
    assert [strip(q) for q in mine()] == [strip(p) for p in originals]
    # A built-in exports too, and exporting over a preset file writes it again.
    builtin = next(p for p in presets.list_presets() if p["name"] == "Narrow satin border")
    dest = presets.export(builtin["id"], str(out / "Wide edge.luddpreset"))["path"]
    assert json.loads(Path(dest).read_text(encoding="utf-8"))["name"] == "Narrow satin border"
    added = presets.import_file(dest)
    assert added["name"] == "Narrow satin border (2)"


def test_export_needs_a_full_path_outside_the_data_folder(isolated_data_dir, tmp_path):
    presets.save(preset())
    for bad in ("mine.luddpreset", "", "  ", "C:mine.luddpreset", str(tmp_path / "x\0y")):
        with pytest.raises(presets.PresetError):
            presets.export("mine", bad)
    for inside in (isolated_data_dir / "out.luddpreset", isolated_data_dir / "presets" / "mine.luddpreset",
                   isolated_data_dir / "presets" / "new.luddpreset"):
        with pytest.raises(presets.PresetError, match="somewhere else"):
            presets.export("mine", str(inside))
    other = tmp_path / "photo.luddpreset"
    other.write_bytes(b"\x89PNG not a preset")
    with pytest.raises(presets.PresetError, match="already exists"):
        presets.export("mine", str(other))
    assert other.read_bytes() == b"\x89PNG not a preset"
    with pytest.raises(presets.PresetError, match="device"):
        presets.export("mine", str(tmp_path / "CON"))
    with pytest.raises(presets.PresetError, match="Couldn't save"):
        presets.export("mine", str(other / "under-a-file"))
    assert stored(isolated_data_dir) == ["mine.luddpreset"]


def test_builtins_cannot_be_deleted(isolated_data_dir):
    for p in presets.list_presets():
        assert p["id"].startswith("builtin:")
        with pytest.raises(presets.PresetError, match="built-in presets can't be deleted"):
            presets.delete(p["id"])
    assert [p["name"] for p in presets.list_presets()] == BUILTINS


def test_broken_files_in_the_folder_are_left_out_and_never_overwritten(isolated_data_dir):
    presets.save(preset("One"))
    (folder(isolated_data_dir) / "mine.luddpreset").write_text("{broken", encoding="utf-8")
    (folder(isolated_data_dir) / "Not A Slug.luddpreset").write_text("{}", encoding="utf-8")
    assert [p["id"] for p in mine()] == ["one"]
    assert presets.save(preset("Mine")) == {"id": "mine-2"}
    assert (folder(isolated_data_dir) / "mine.luddpreset").read_text(encoding="utf-8") == "{broken"


def _known(p: dict) -> bool:
    """Whether this engine knows the preset's style and pattern."""
    params = p["params"]
    return params.get("style", "single") in lines.REGISTRY and params.get("pattern", "tatami") in fills.REGISTRY


SHAPES = {
    "run": {"nodes": [[0, 0, "s"], [20, 5, "s"], [40, 0, "s"]]},
    "satin": {"nodes": [[0, 20, "s"], [20, 25, "s"], [40, 20, "s"]], "width_mm": 2},
    "fill": {"outline": [[0, 30, "c"], [30, 30, "c"], [30, 50, "c"], [0, 50, "c"]]},
    "applique": {"outline": [[0, 60, "c"], [30, 60, "c"], [30, 80, "c"], [0, 80, "c"]]},
}
T = {"x": 0, "y": 0, "rotate": 0, "scale_x": 1, "scale_y": 1, "flip_x": False, "flip_y": False}


def test_builtins_pass_their_checks_and_sew():
    """Each built-in is checked like any imported preset and sews on a sample shape. (One whose
    style another part of this phase adds is checked once it's there.)"""
    checked = []
    for p in presets.list_presets():
        if not _known(p):
            continue
        clean = presets.check({k: p[k] for k in ("name", "kind", "params", "width_mm", "note")}, p["name"])
        assert clean["params"] == p["params"] and clean["width_mm"] == p["width_mm"]
        geometry = dict(SHAPES[p["kind"]])
        if p["width_mm"]:
            geometry["width_mm"] = p["width_mm"]
        item = {"id": "a", "kind": p["kind"], "geometry": geometry, "params": p["params"],
                "thread": {"color": "#aa0000"}, "transform": T, "threads": [], "ops": []}
        render = L.render({"items": [item], "merge_colors": False, "color_sort": False, "basting": {"enabled": False, "margin_mm": 5}})
        assert len(render.pattern.stitches) > 10, p["name"]
        checked.append(p["name"])
    assert {"Light sketch fill", "Bold outline", "Narrow satin border", "Felt applique"} <= set(checked)


def test_every_setting_of_the_new_line_styles_and_locks_is_known():
    """Once the new line styles, lock stitches and blackwork are in the engine, presets keep
    their settings. (Lock stitches' shape is read outside the settings classes.)"""
    assert {"tie_in", "tie_off", "tie_style"} <= presets.settings_of("run") & presets.settings_of("satin") & presets.settings_of("fill")
    assert not presets.settings_of("applique") & {"tie_style", "style", "pattern"}
    for kind in ("run", "satin", "fill", "applique"):
        assert not presets.settings_of(kind) & {"angle_deg", "reverse", "start_mm", "end_mm", "angle_line", "angle_lines",
                                                  "ripple_center", "blend_flip", "push_comp_mm", "carve", "extra",
                                                  "underlay_spacing_mm"}, kind
    if "redwork" not in lines.REGISTRY:
        pytest.skip("the new line styles aren't in this engine yet")
    assert {"motif_side", "stem_width_mm", "knot_mm", "knot_gap_mm"} <= presets.settings_of("run")
    assert {"blackwork_mm", "blackwork_lattice"} <= presets.settings_of("fill")


def test_through_the_rpc(isolated_data_dir, tmp_path):
    def call(method, **params):
        out = dispatcher.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}))
        return out

    assert call("presets.save", preset=preset("Mine"))["result"] == {"id": "mine"}
    names = [p["name"] for p in call("presets.list")["result"]]
    assert names == [*BUILTINS, "Mine"]
    dest = call("presets.export", id="mine", dest=str(tmp_path / "m"))["result"]["path"]
    assert call("presets.import", path=dest)["result"]["name"] == "Mine (2)"
    assert call("presets.delete", id="mine")["result"] is None
    refused = call("presets.delete", id="builtin:bold-outline")["error"]
    assert refused["code"] == -32000 and "built-in" in refused["message"]
