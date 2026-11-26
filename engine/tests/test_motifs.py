"""My motifs: a drawn line kept as a motif of your own (motifs.py, the motifs.* methods), the
copy a shape carries and sews (digitize/lines), and the whole path from saving one to reopening a
project on a computer that doesn't have it. Every test uses a data folder of its own (conftest)."""

import json
import math
import re
import statistics

import pytest
from shapely.geometry import LineString, Point, Polygon

import invariants
from steady_util import forget_stitches
from threadline_engine import layout, motifs, project, storage
from threadline_engine.digitize import lines
from threadline_engine.digitize.fills import motif
from threadline_engine.digitize.paths import flatten
from threadline_engine.digitize.stitches import STITCH, DigitizeError, FillParams, RunParams, generate
from threadline_engine.methods import dispatcher
from threadline_engine.names import _RESERVED

ENDS = "A motif runs from where it starts to where it ends; draw it left to right"
# A hill drawn left to right: up the screen (y down), so the motif sits above its line.
HILL = [[0, 0, "c"], [5, -3, "c"], [10, 0, "c"]]
THREAD = {"color": "#aa0000", "name": "Red", "catalog": "", "brand": ""}


def _c(*points):
    return [[x, y, "c"] for x, y in points]


def _folder():
    return storage.data_dir() / "motifs"


def _files():
    return sorted(p.name for p in _folder().glob("*")) if _folder().is_dir() else []


def _rpc(method, params=None):
    """One request through the dispatcher, as the app sends it; the answer as the app gets it."""
    out = dispatcher.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}))
    assert "result" in out, out.get("error")
    return json.loads(json.dumps(out["result"], allow_nan=False))


def _stitches(recs):
    return [(r[0], r[1]) for r in recs if r[2] == STITCH]


def _line_obj(unit, motif="user:hill", end=40.0, **params):
    return {"kind": "run", "geometry": {"nodes": _c((0, 0), (end, 0))},
            "params": {"style": "motif", "motif": motif, "motif_unit": unit, "tie_in": False, "tie_off": False,
                       **params}}


def _fill_obj(unit, motif="user:hill", **params):
    return {"kind": "fill", "geometry": {"outline": _c((0, 0), (40, 0), (40, 30), (0, 30))},
            "params": {"pattern": "motif", "motif": motif, "motif_unit": unit, "angle_deg": 0, "underlay": [], **params}}


# ---------------------------------------------------------------- saving


def test_save_normalizes_to_a_unit():
    # Drawn at a slant and away from the origin: first goes to (0, 0), last to (1, 0), the same
    # scale both ways, so every distance between points is kept in proportion.
    drawn = [(10, 10), (11, 7), (15, 14), (18, 16)]
    saved = motifs.save("Squiggle", _c(*drawn))
    unit = saved["unit"]
    assert unit[0] == [0, 0] and unit[-1] == [1, 0]
    assert len(unit) == len(drawn)
    chord = math.dist(drawn[0], drawn[-1])
    for i, a in enumerate(drawn):
        for j, b in enumerate(drawn):
            assert math.dist(unit[i], unit[j]) * chord == pytest.approx(math.dist(a, b), abs=1e-5), (i, j)
    # Not mirrored: each point stays on its side of the line from first to last.
    (x0, y0), (x1, y1) = drawn[0], drawn[-1]
    for (x, y), (_, v) in zip(drawn[1:-1], unit[1:-1]):
        side = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
        assert side * v > 0
    assert saved["id"] == "user:squiggle" and saved["name"] == "Squiggle"
    stored = json.loads((_folder() / "squiggle.json").read_text(encoding="utf-8"))
    assert stored == {"format": "ludd-motif", "version": 1, "name": "Squiggle", "unit": unit}


def test_a_curved_line_is_saved_as_it_flattens():
    curve = [[0, 0, "c"], [6, -4, "s"], [12, 0, "c"]]
    unit = motifs.save("Dome", curve)["unit"]
    poly, _ = flatten(curve, False)
    assert len(unit) == len(poly) > 3
    for (u, v), (x, y) in zip(unit, poly):
        assert (u * 12, v * 12) == pytest.approx((x, y), abs=1e-4)


def test_a_motif_line_drawn_left_to_right_sews_the_way_it_was_drawn():
    unit = motifs.save("Hill", HILL)["unit"]
    pts = _stitches(generate(_line_obj(unit, motif_mm=10, motif_width_mm=3))[0])
    ys = [y for _, y in pts]
    assert min(ys) == pytest.approx(-3, abs=0.05) and max(ys) == pytest.approx(0, abs=0.05)  # above, as drawn


@pytest.mark.parametrize("nodes,closed", [
    (HILL, True),  # a closed line
    (_c((0, 0), (5, 3), (1.9, 0)), False),  # its ends 1.9 mm apart
    (_c((0, 0), (5, 3), (0, 0)), False),  # ends where it started
    (_c((3, 3)), False),  # one point
    ([], False),
])
def test_save_refuses_a_closed_or_tiny_line(nodes, closed):
    with pytest.raises(motifs.MotifError, match=f"^{re.escape(ENDS)}$"):
        motifs.save("Bad", nodes, closed)
    assert _files() == []


def test_ends_exactly_two_mm_apart_are_enough():
    assert motifs.save("Short", _c((0, 0), (1, -2), (2, 0)))["unit"][-1] == [1, 0]


def test_save_refuses_too_many_points():
    zigzag = _c(*((i * 0.5, i % 2) for i in range(201)))
    with pytest.raises(motifs.MotifError, match="too many points for a motif.*201.*200"):
        motifs.save("Long", zigzag)
    assert motifs.save("Just fits", zigzag[:200])["unit"]


@pytest.mark.parametrize("nodes", [
    [[0, 0, "c"], [float("nan"), 1, "c"], [10, 0, "c"]],
    [[0, 0, "c"], ["x", 1, "c"], [10, 0, "c"]],
    [[0, 0, "c"], [5, 1, "c"], [1e9, 0, "c"]],
    [0, 1, 2],
    "a line",
    None,
])
def test_save_refuses_lines_that_arent_points(nodes):
    with pytest.raises(motifs.MotifError):
        motifs.save("Bad", nodes)
    assert _files() == []


@pytest.mark.parametrize("name", ["", "   ", "\t\n", None, 7])
def test_save_needs_a_name(name):
    with pytest.raises(motifs.MotifError, match="name"):
        motifs.save(name, HILL)


# ---------------------------------------------------------------- the list, deleting, files


def test_list_has_builtins_and_mine():
    before = motifs.list_motifs()
    assert [m["id"] for m in before] == list(lines.MOTIF_UNITS)
    assert all(m["builtin"] and m["name"] and m["unit"] == [list(p) for p in lines.MOTIF_UNITS[m["id"]]] for m in before)
    saved = motifs.save("Hill", HILL)
    after = motifs.list_motifs()
    assert after[: len(before)] == before
    assert after[len(before):] == [{"id": "user:hill", "name": "Hill", "builtin": False, "unit": saved["unit"]}]


def test_list_leaves_out_damaged_and_unusual_files():
    motifs.save("Hill", HILL)
    folder = _folder()
    (folder / "torn.json").write_text('{"format": "ludd-motif", "vers', encoding="utf-8")
    (folder / "other.json").write_text('{"format": "something-else"}', encoding="utf-8")
    (folder / "Not A Slug.json").write_text(json.dumps({"format": "ludd-motif", "version": 1, "name": "x",
                                                        "unit": [[0, 0], [1, 0]]}), encoding="utf-8")
    (folder / "nested.json").write_text("[" * 100000, encoding="utf-8")
    (folder / "folder.json").mkdir()
    assert [m["id"] for m in motifs.list_motifs() if not m["builtin"]] == ["user:hill"]


def test_delete_only_mine():
    motifs.save("Hill", HILL)
    for builtin in lines.MOTIF_UNITS:
        with pytest.raises(motifs.MotifError, match="built-in"):
            motifs.delete(builtin)
    for unknown in ["user:nope", "nope", "user:", "", None, 3]:
        with pytest.raises(motifs.MotifError):
            motifs.delete(unknown)
    assert _files() == ["hill.json"] and "wave" in lines.MOTIF_UNITS
    assert motifs.delete("user:hill") is None
    assert _files() == [] and all(m["builtin"] for m in motifs.list_motifs())
    with pytest.raises(motifs.MotifError):
        motifs.delete("user:hill")


def test_export_import_round_trip(tmp_path):
    saved = motifs.save("Hill", HILL)
    sent = motifs.export(saved["id"], str(tmp_path / "sent"))  # no extension: .json added
    assert sent == {"path": str(tmp_path / "sent.json")}
    stored = json.loads((tmp_path / "sent.json").read_text(encoding="utf-8"))
    assert stored == {"format": "ludd-motif", "version": 1, "name": "Hill", "unit": saved["unit"]}
    again = motifs.import_file(sent["path"])
    assert again == {"id": "user:hill-2", "name": "Hill", "unit": saved["unit"]}
    motifs.delete("user:hill")
    motifs.delete("user:hill-2")
    assert motifs.import_file(sent["path"]) == {"id": "user:hill", "name": "Hill", "unit": saved["unit"]}


@pytest.mark.parametrize("motif", ["wave", "zigzag", "scallop", "blanket", "leaf"])
def test_a_built_in_motif_can_be_exported_and_imported_unchanged(motif, tmp_path):
    path = motifs.export(motif, str(tmp_path / f"{motif}.json"))["path"]
    again = motifs.import_file(path)
    assert again["unit"] == [list(p) for p in lines.MOTIF_UNITS[motif]]


def test_export_refuses_unknown_ids_and_the_motif_folder(tmp_path):
    motifs.save("Hill", HILL)
    for bad in ["user:nope", "nope", "user:../hill", None]:
        with pytest.raises(motifs.MotifError):
            motifs.export(bad, str(tmp_path / "x.json"))
    before = (_folder() / "hill.json").read_bytes()
    for inside in [_folder() / "hill.json", _folder() / "copy.json", _folder() / "sub" / ".." / "hill"]:
        with pytest.raises(motifs.MotifError):
            motifs.export("user:hill", str(inside))
    assert (_folder() / "hill.json").read_bytes() == before and _files() == ["hill.json"]
    for bad_dest in ["", None, str(tmp_path / "a\0b.json")]:
        with pytest.raises(motifs.MotifError):
            motifs.export("user:hill", bad_dest)
    assert not (tmp_path / "x.json").exists()


def test_export_refuses_a_destination_without_its_folder(tmp_path, monkeypatch):
    """Without the full path, the file would land wherever the engine happens to be running."""
    motifs.save("Hill", HILL)
    monkeypatch.chdir(tmp_path)
    for relative in ["foo.json", "foo", "./foo.json", "../foo.json", "sub/foo.json", "C:foo.json"]:
        with pytest.raises(motifs.MotifError, match="folder and all"):
            motifs.export("user:hill", relative)
    assert list(tmp_path.glob("*.json")) == [] and not (tmp_path.parent / "foo.json").exists()


def test_export_never_writes_into_ludds_own_data_folder(tmp_path):
    motifs.save("Hill", HILL)
    data = storage.data_dir()
    settings = data / "settings.json"
    settings.write_text('{"mine": true}', encoding="utf-8")
    inside = [data / "settings", data / "settings.json", data / "x", data / "fonts" / "x.json",
              data / "new" / ".." / "x"]
    if (data.parent / data.name.upper()).exists():  # a computer that ignores capital letters
        inside.append(data.parent / data.name.upper() / "settings")
    for dest in inside:
        with pytest.raises(motifs.MotifError, match="LUDD keeps"):
            motifs.export("user:hill", str(dest))
    assert settings.read_text(encoding="utf-8") == '{"mine": true}'
    assert sorted(p.name for p in data.iterdir()) == ["motifs", "settings.json"]


# ---------------------------------------------------------------- safety


EVIL_NAMES = ["../../evil", "..\\..\\evil", "C:\\Windows\\evil", "/etc/passwd", "a/b\\c", "..", ".hidden", "name:stream"]


@pytest.mark.parametrize("name", EVIL_NAMES)
def test_names_never_work_as_paths(name, tmp_path):
    saved = motifs.save(name, HILL)
    slug = saved["id"].removeprefix("user:")
    assert re.fullmatch(r"_?[a-z0-9]+(-[a-z0-9]+)*", slug), slug
    assert _files() == [f"{slug}.json"]
    everything = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert everything == [_folder() / f"{slug}.json"]  # nothing written anywhere else


@pytest.mark.parametrize("bad", ["user:..", "user:../hill", "user:..\\hill", "user:a/b", "user:C:\\x", "user:C:",
                                 "user:hill/../hill", "user:hill.json", "../hill", "user:/hill", "user:hill\0"])
def test_ids_never_work_as_paths(bad, tmp_path):
    motifs.save("Hill", HILL)
    outside = tmp_path / "threadline-data" / "hill.json"  # beside the motifs folder
    outside.write_text((_folder() / "hill.json").read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(motifs.MotifError):
        motifs.delete(bad)
    with pytest.raises(motifs.MotifError):
        motifs.export(bad, str(tmp_path / "out.json"))
    assert outside.exists() and _files() == ["hill.json"] and not (tmp_path / "out.json").exists()


@pytest.mark.parametrize("name", ["CON", "con", "Aux.1", "PRN", "nul.txt", "COM1", "com\u00b9", "LPT9", "lpt0 "])
def test_windows_device_names_are_made_safe(name):
    saved = motifs.save(name, HILL)
    slug = saved["id"].removeprefix("user:")
    assert not _RESERVED.fullmatch(slug) and (_folder() / f"{slug}.json").is_file()
    assert saved["name"] == name.strip()
    assert saved["id"] in [m["id"] for m in motifs.list_motifs()]
    motifs.delete(saved["id"])


def test_very_long_names_are_cut():
    saved = motifs.save("x" * 5000, HILL)
    assert len(saved["name"]) <= 80
    slug = saved["id"].removeprefix("user:")
    assert len(slug) <= 70 and _files() == [f"{slug}.json"]
    again = motifs.save("x" * 5000, HILL)
    assert again["id"] != saved["id"] and len(_files()) == 2


@pytest.mark.parametrize("name", ["Ünïcode motif", "\u6ce2\u5f62", "!!!"])
def test_names_in_any_language_are_kept(name):
    saved = motifs.save(name, HILL)
    assert saved["name"] == name
    assert [m["name"] for m in motifs.list_motifs() if not m["builtin"]] == [name]


def test_saving_and_importing_never_overwrite(tmp_path):
    _folder().mkdir(parents=True)
    (_folder() / "hill.json").write_text("keep me", encoding="utf-8")
    assert motifs.save("Hill", HILL)["id"] == "user:hill-2"
    assert motifs.save("hill", HILL)["id"] == "user:hill-3"
    path = motifs.export("user:hill-2", str(tmp_path / "hill.json"))["path"]
    assert motifs.import_file(path)["id"] == "user:hill-4"
    assert (_folder() / "hill.json").read_text(encoding="utf-8") == "keep me"
    assert _files() == ["hill-2.json", "hill-3.json", "hill-4.json", "hill.json"]


def _motif_file(tmp_path, content, name="in.json"):
    p = tmp_path / name
    p.write_bytes(content if isinstance(content, bytes) else
                  (content if isinstance(content, str) else json.dumps(content)).encode("utf-8"))
    return str(p)


GOOD = {"format": "ludd-motif", "version": 1, "name": "Bump", "unit": [[0, 0], [0.5, -0.3], [1, 0]]}


@pytest.mark.parametrize("content,says", [
    ({**GOOD, "padding": "x" * 300_000}, "too big"),
    ("not json", "isn't a LUDD motif"),
    ("[1, 2]", "isn't a LUDD motif"),
    ({**GOOD, "format": "ludd-project"}, "isn't a LUDD motif"),
    ({k: v for k, v in GOOD.items() if k != "version"}, "isn't a LUDD motif"),
    ({**GOOD, "version": "1"}, "isn't a LUDD motif"),
    ({**GOOD, "version": True}, "isn't a LUDD motif"),
    ({**GOOD, "version": 2}, "newer LUDD"),
    ({**GOOD, "unit": [[0, 0]]}, "can't be used"),
    ({**GOOD, "unit": [[0, 0], [0.5, "1"], [1, 0]]}, "can't be used"),
    ('{"format": "ludd-motif", "version": 1, "name": "x", "unit": [[0, 0], [0.5, NaN], [1, 0]]}', "can't be used"),
    ({**GOOD, "unit": [[0, 0], [0.5, 0.3], [0.5, 0]]}, "can't be used"),  # doesn't run from its start to its end
    ({**GOOD, "unit": [[0.2, 0], [1, 0]]}, "can't be used"),
    ({**GOOD, "unit": [[0, 0]] + [[i / 300, 0.1] for i in range(1, 300)] + [[1, 0]]}, "can't be used"),
    ("[" * 100000, "isn't a LUDD motif"),
    (b"\xff\xfe\x00garbage", "isn't a LUDD motif"),
])
def test_import_checks_the_file_first(content, says, tmp_path):
    with pytest.raises(motifs.MotifError, match=says):
        motifs.import_file(_motif_file(tmp_path, content))
    assert _files() == []


def test_import_checks_the_size_before_reading(tmp_path, monkeypatch):
    path = _motif_file(tmp_path, {**GOOD, "padding": "x" * 300_000})

    def no_reading(*args, **kwargs):
        raise AssertionError("a file that is too big must not be read")

    monkeypatch.setattr(storage, "read_json", no_reading)
    monkeypatch.setattr(json, "loads", no_reading)
    with pytest.raises(motifs.MotifError, match="too big"):
        motifs.import_file(path)


def test_import_refuses_missing_files_and_folders(tmp_path):
    for bad in [str(tmp_path / "gone.json"), str(tmp_path), "", None, str(tmp_path / "a\0b")]:
        with pytest.raises(motifs.MotifError):
            motifs.import_file(bad)
    assert _files() == []


@pytest.mark.parametrize("given,kept", [
    ("  Two   words\n", "Two words"),
    ("tab\there\x00now\x07", "tab here now"),
    ("x" * 500, "x" * 80),
    ("", "bump file"),  # no name in the file: the file's own
    (None, "bump file"),
    (12, "bump file"),
])
def test_import_cleans_the_name(given, kept, tmp_path):
    got = motifs.import_file(_motif_file(tmp_path, {**GOOD, "name": given}, "bump file.json"))
    assert got["name"] == kept


def test_import_reads_a_file_with_a_byte_order_mark(tmp_path):
    path = _motif_file(tmp_path, b"\xef\xbb\xbf" + json.dumps(GOOD).encode("utf-8"))
    assert motifs.import_file(path)["unit"] == GOOD["unit"]


def test_the_five_methods_answer_through_the_dispatcher(tmp_path):
    saved = _rpc("motifs.save", {"name": "Hill", "nodes": HILL})
    assert saved == {"id": "user:hill", "name": "Hill", "unit": [[0, 0], [0.5, -0.3], [1, 0]]}
    assert [m["id"] for m in _rpc("motifs.list")][-1] == "user:hill"
    out = _rpc("motifs.export", {"id": "user:hill", "dest": str(tmp_path / "h.json")})
    assert _rpc("motifs.import", {"path": out["path"]})["id"] == "user:hill-2"
    assert _rpc("motifs.delete", {"id": "user:hill"}) is None
    bad = dispatcher.handle_line(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "motifs.save",
                                             "params": {"name": "x", "nodes": HILL, "closed": True}}))
    assert bad["error"] == {"code": -32000, "message": ENDS}


# ---------------------------------------------------------------- the copy a shape carries


def _numbers(n):
    return [[i / (n - 1), 0.1 if 0 < i < n - 1 else 0] for i in range(n)]


@pytest.mark.parametrize("unit", [
    _numbers(300),
    _numbers(201),
    [[0, 0]],
    [],
    [[0, 0], [0.5, float("nan")], [1, 0]],
    [[0, 0], [float("inf"), 0.2], [1, 0]],
    [[0, 0], [0.5, "0.2"], [1, 0]],
    [[0, 0], [0.5, True], [1, 0]],
    [[0, 0], [0.5], [1, 0]],
    [[0, 0], [0.5, 0.2, 1], [1, 0]],
    [[0, 0], 0.5, [1, 0]],
    [[0, 0], [0.5, 1e12], [1, 0]],
    "00",
    {"u": 0},
    7,
])
def test_bad_motif_unit_is_refused(unit):
    """Done-when: a motif carried by a shape is checked before it's sewn."""
    for params in (lambda: RunParams.from_dict({"style": "motif", "motif": "user:x", "motif_unit": unit}),
                   lambda: FillParams.from_dict({"pattern": "motif", "motif": "user:x", "motif_unit": unit})):
        with pytest.raises(DigitizeError, match="^This motif can't be used: "):
            params()
    with pytest.raises(DigitizeError):
        generate(_line_obj(unit))


def test_good_motif_units_are_accepted():
    for unit in (_numbers(2), _numbers(200), [(0.0, 0.0), (0.5, -0.5), (1.0, 0.0)]):
        assert lines.carried_unit(unit) == [(float(u), float(v)) for u, v in unit]
    assert lines.carried_unit(None) is None


def test_a_motif_line_without_its_unit_is_unknown():
    with pytest.raises(DigitizeError, match="^Unknown motif: user:hill$"):
        generate(_line_obj(None))


def test_a_built_in_name_with_a_carried_unit_sews_the_unit():
    """The engine sews the copy a shape carries, whatever the name says."""
    flat = [[0, 0], [0.5, 0], [1, 0]]
    ys = [y for _, y in _stitches(generate(_line_obj(flat, motif="wave"))[0])]
    assert max(ys) - min(ys) < 1e-6


# ---------------------------------------------------------------- the sizing rule


def test_a_carried_unit_is_sewn_as_wide_as_the_width_setting():
    """Built-in motifs are about 1 across; a motif of your own is scaled so Width means the same."""
    hill = [[0, 0], [0.5, -0.3], [1, 0]]
    assert lines.sewn_unit([(u, v) for u, v in hill], 4, 2.5) == [(0, 0), (0.5, pytest.approx(-1)), (1, 0)]
    assert lines.sewn_unit(None, 4, 2.5) is None
    both_sides = [(0, 0), (0.25, 0.5), (0.75, -1.5), (1, 0)]
    assert [v for _, v in lines.sewn_unit(both_sides, 4, 2.5)] == pytest.approx([0, 0.25, -0.75, 0])
    # Points that make no difference once sewn are left out; corners stay.
    crowded = [(0, 0), (0.25, 0.2501), (0.5, 0.5), (0.5001, 0.4999), (0.75, 0.25), (1, 0)]
    assert [u for u, _ in lines.sewn_unit(crowded, 4, 2)] == [0, 0.5, 1]


@pytest.mark.parametrize("flat", [[(0, 0), (1, 0)], [(0, 0), (0.5, 1e-9), (1, 0)], [(0, 0.4), (1, 0.4)]])
def test_a_flat_motif_sews_flat(flat):
    assert {v for _, v in lines.sewn_unit(flat, 4, 2.5)} == {0}
    ys = [y for _, y in _stitches(generate(_line_obj([list(p) for p in flat]))[0])]
    assert max(ys) - min(ys) < 1e-6


def test_a_unit_far_off_its_line_stays_near_it():
    """A hand-edited unit nowhere near its line can't fling stitches far away."""
    off = [[0, 900.0], [0.5, 900.001], [1, 900.0]]
    pts = _stitches(generate(_line_obj(off, motif_width_mm=10))[0])
    assert max(abs(y) for _, y in pts) <= 100


@pytest.mark.parametrize("repeat,width", [(4, 1.2), (5, 1.5), (10, 3.0), (7, 4.0)])
def test_the_width_setting_is_how_wide_a_motif_of_your_own_sews(repeat, width):
    hill = [[0, 0], [0.5, -0.3], [1, 0]]
    pts = _stitches(generate(_line_obj(hill, motif_mm=repeat, motif_width_mm=width, end=repeat * 5))[0])
    ys = [y for _, y in pts]
    assert max(ys) - min(ys) == pytest.approx(width, abs=0.01)
    peaks = sorted(x for x, y in pts if y == pytest.approx(-width, abs=0.01))
    assert [b - a for a, b in zip(peaks, peaks[1:])] == pytest.approx([repeat] * 4, abs=0.01)


def test_a_saved_motif_chosen_at_the_defaults_sews_with_its_drawn_proportions():
    """The app sets Width = Repeat x the motif's span when you pick one of yours: it then sews as
    a smaller (or bigger) copy of the line you drew, on a line (Repeat 4) and a fill (Repeat 5)."""
    drawn = [(0, 0), (3, -6), (8, 2), (14, -1), (20, 0)]  # 20 mm long, 8 mm from top to bottom
    unit = motifs.save("Peaks", _c(*drawn))["unit"]
    span = max(v for _, v in unit) - min(v for _, v in unit)
    assert span == pytest.approx(0.4)
    for repeat in (4, 5):
        width = repeat * span  # the app's rule (feat/motifs.ts, drawnSize)
        scale = repeat / 20
        expected = LineString([(x * scale + k * repeat, y * scale) for k in range(6) for x, y in drawn])
        line = _stitches(generate(_line_obj(unit, motif_mm=repeat, motif_width_mm=width, end=repeat * 6))[0])
        assert max(expected.distance(Point(p)) for p in line) <= 0.01
        for x, y in drawn:  # every corner you drew is a needle point, as many times as it repeats
            corner = (x * scale + 2 * repeat, y * scale)
            assert min(math.dist(corner, p) for p in line) <= 0.01, corner
        ys = [y for _, y in line]
        assert max(ys) - min(ys) == pytest.approx(8 * scale, abs=0.01)
        # The motif fill: each row is the same shape, repeating every Repeat mm.
        params = FillParams.from_dict(_fill_obj(unit, motif_mm=repeat, motif_width_mm=width)["params"])
        shape = Polygon([(0, 0), (40, 0), (40, 30), (0, 30)])
        rows = [piece for row in motif._rows(shape, params, params.stitch_mm) for piece in row]
        whole = [r for r in rows if min(y for _, y in r) > 0.05 and max(y for _, y in r) < 29.95]  # not cut
        assert len(whole) >= 10
        for row in whole:
            top = min(y for _, y in row)
            assert max(y for _, y in row) - top == pytest.approx(8 * scale, abs=0.01)
            peaks = sorted({round(x, 3) for x, y in row if y < top + 0.001})
            assert len(peaks) > 2 and [b - a for a, b in zip(peaks, peaks[1:])] == pytest.approx(
                [repeat] * (len(peaks) - 1), abs=0.01)


@pytest.mark.parametrize("repeat", [4, 12])
def test_a_curved_motif_sews_in_stitches_a_machine_can_sew(repeat):
    """A drawn curve is saved as many points close together; sewn small, each would be a stitch a
    third of a millimeter long, and they'd pile up. Only the points its shape needs are sewn."""
    curve = [[0, 0, "c"], [5, -6, "s"], [10, 0, "s"], [15, 6, "s"], [20, 0, "c"]]
    unit = motifs.save("S curve", curve)["unit"]
    assert len(unit) > 100
    span = max(v for _, v in unit) - min(v for _, v in unit)
    pts = _stitches(generate(_line_obj(unit, motif_mm=repeat, motif_width_mm=repeat * span, end=repeat * 4))[0])
    steps = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    assert statistics.median(steps) >= 0.7 and min(steps) >= 0.3, (statistics.median(steps), min(steps))
    # Still the curve you drew, within 0.12 mm either way.
    drawn, _ = flatten(curve, False)
    expected = LineString([(x * repeat / 20 + k * repeat, y * repeat / 20) for k in range(4) for x, y in drawn])
    assert expected.hausdorff_distance(LineString(pts)) <= 0.12
    # The same in a motif fill.
    fill = _stitches(generate(_fill_obj(unit, motif_mm=repeat, motif_width_mm=repeat * span))[0])
    assert statistics.median(math.dist(a, b) for a, b in zip(fill, fill[1:])) >= 0.7


def test_a_motif_of_your_own_passes_the_invariants():
    unit = motifs.save("Hill", HILL)["unit"]
    for obj in (_line_obj(unit, motif_mm=6, motif_width_mm=2), _fill_obj(unit, motif_mm=6, motif_width_mm=2)):
        recs = generate(obj)[0]
        invariants.assert_sane(recs)
        invariants.assert_deterministic(lambda: generate(obj)[0])
        for dx, dy in [(10, -7.5), (0.1234, 33.333), (-250.7, 1000.9)]:
            invariants.assert_moves_with_shape(obj, dx, dy)


def test_a_resized_motif_line_keeps_its_motif_size():
    """Resizing with the handles makes the line longer, not the motif bigger."""
    unit = [[0, 0], [0.5, -0.3], [1, 0]]
    item = {**_line_obj(unit, motif_mm=5, motif_width_mm=2, end=20), "id": "a", "thread": THREAD,
            "transform": {"scale_x": 2, "scale_y": 2}}
    forget_stitches()
    block = layout.render({"items": [item]}).blocks[0]
    pts = [(x / 10, y / 10) for x, y, k, *_ in block.recs if k == STITCH]
    ys = [y for _, y in pts]
    assert max(ys) - min(ys) == pytest.approx(2, abs=0.05)  # still 2 mm wide
    peaks = sorted(x for x, y in pts if y < min(ys) + 0.05)
    assert [b - a for a, b in zip(peaks, peaks[1:])] == pytest.approx([5] * (len(peaks) - 1), abs=0.05)
    assert len(peaks) == 8  # 40 mm of line now


# ---------------------------------------------------------------- done-when 4


def test_shape_carries_its_motif(tmp_path):
    """Done-when 4: a line saved as a motif is used in a motif line and a motif fill, and the
    project reopens on a computer that doesn't have the motif, sewing the same."""
    saved = _rpc("motifs.save", {"name": "My hill", "nodes": [[0, 0, "c"], [3, -4, "c"], [7, 1, "c"], [10, 0, "c"]]})
    assert saved["id"] == "user:my-hill"
    carried = {"motif": saved["id"], "motif_unit": saved["unit"]}
    transform = {"x": 0, "y": 0, "rotate": 0, "scale_x": 1, "scale_y": 1, "flip_x": False, "flip_y": False}
    line = {"id": "l", "kind": "run", "thread": THREAD, "transform": transform, "threads": [], "ops": [],
            "geometry": {"nodes": _c((-30, 20), (30, 20))},
            "params": {"style": "motif", "motif_mm": 5, "motif_width_mm": 2.5, **carried}}
    fill = {"id": "f", "kind": "fill", "thread": {**THREAD, "color": "#0000aa"}, "transform": transform,
            "threads": [], "ops": [], "geometry": {"outline": _c((-20, -20), (20, -20), (20, 10), (-20, 10))},
            "params": {"pattern": "motif", "angle_deg": 20, "spacing_mm": 0.4, "stitch_mm": 3.5, **carried}}
    design = {"items": [line, fill], "merge_colors": False, "color_sort": False,
              "basting": {"enabled": False, "margin_mm": 5}}
    forget_stitches()
    before = _rpc("layout.render", {"layout": design})
    # The motif really is used: the built-in wave sews something else.
    wave = {**design, "items": [{**it, "params": {**it["params"], "motif": "wave", "motif_unit": None}}
                                for it in design["items"]]}
    assert _rpc("layout.render", {"layout": wave})["records"] != before["records"]

    path = str(tmp_path / "carried.ludd")
    _rpc("project.save", {"path": path, "project_data": {"title": "t", "layout": design, "images": []}})
    for f in _folder().iterdir():
        f.unlink()
    _folder().rmdir()  # a computer that has no motifs of its own
    assert all(m["builtin"] for m in _rpc("motifs.list"))
    forget_stitches()  # nothing kept from before
    opened = _rpc("project.open", {"path": path})
    assert [it["params"]["motif_unit"] for it in opened["layout"]["items"]] == [saved["unit"]] * 2
    after = _rpc("layout.render", {"layout": opened["layout"]})
    assert after["records"] == before["records"]
    assert after["threads"] == before["threads"]
    assert after["warnings"] == before["warnings"]
    stored = json.loads(__import__("zipfile").ZipFile(path).read("project.json"))
    assert {"user_motifs", "fill_motif", "motif_lines"} <= set(stored["features"])
    assert project.VERSION >= stored["version"] == 2
