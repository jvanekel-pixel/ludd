"""Design open/export/convert on a synthetic pattern (runs in CI without private fixtures)."""

import json

import pyembroidery as pe
import pytest

from threadline_engine import design
from threadline_engine.methods import dispatcher


def make_pattern() -> pe.EmbPattern:
    """Two colors; a trim inside color 1, a stop without color change inside color 2."""
    p = pe.EmbPattern()
    p.add_thread(pe.EmbThread("#ff0000", "Red", "1001", brand="Madeira Rayon"))
    p.add_thread(pe.EmbThread("#0000ff", "Blue", "1002", brand="Madeira Rayon"))
    for x in range(0, 200, 20):
        p.stitch_abs(x, 0)
    p.trim()
    p.move_abs(0, 100)
    for x in range(0, 200, 20):
        p.stitch_abs(x, 100)
    p.color_change()
    for x in range(0, 300, 25):
        p.stitch_abs(x, 300)
    p.stop()
    for x in range(0, 300, 25):
        p.stitch_abs(x, 400)
    p.end()
    return p


@pytest.fixture
def pes_file(tmp_path):
    path = tmp_path / "sample.pes"
    pe.write(make_pattern(), str(path), {"version": 6})
    return path


def rpc(method, **params):
    return dispatcher.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}))


def test_open_reports_counts_size_and_threads(pes_file):
    d = design.open_design(str(pes_file))
    info = d["info"]
    assert info["stitches"] == 10 + 10 + 12 + 12
    assert info["stops"] == 1
    assert info["color_changes"] == 1
    assert info["trims"] >= 1
    assert info["colors"] == 2
    assert info["width_mm"] == pytest.approx(27.5)
    assert info["height_mm"] == pytest.approx(40.0)
    assert [t["name"] for t in d["threads"]] == ["Red", "Blue"]
    assert d["threads"][0]["color"] == "#ff0000"


def test_records_are_mm_and_blocks_cover_stitches(pes_file):
    d = design.open_design(str(pes_file))
    r = d["records"]
    assert len(r["x"]) == len(r["y"]) == len(r["kind"])
    stitches = [(x, y) for x, y, k in zip(r["x"], r["y"], r["kind"]) if k == design.STITCH]
    assert (19.0, 40.0) not in stitches and (27.5, 40.0) in stitches  # 0.1 mm -> mm
    # Blocks are contiguous, in order, and each holds stitches of one thread.
    assert [b["thread"] for b in d["blocks"]] == [0, 1]
    assert d["blocks"][0]["end"] < d["blocks"][1]["start"]
    in_blocks = sum(
        1 for b in d["blocks"] for k in r["kind"][b["start"] : b["end"]] if k == design.STITCH
    )
    assert in_blocks == d["info"]["stitches"]


@pytest.mark.parametrize("ext", ["pes", "jef", "dst", "exp", "vp3"])
def test_export_roundtrips_stitch_positions(pes_file, tmp_path, ext):
    out = tmp_path / f"out.{ext}"
    design.export(str(pes_file), str(out))
    a = design.open_design(str(pes_file))["records"]
    b = design.open_design(str(out))["records"]
    pts = lambda r: [(x, y) for x, y, k in zip(r["x"], r["y"], r["kind"]) if k == design.STITCH]  # noqa: E731
    pa, pb = pts(a), pts(b)
    assert len(pa) == len(pb)
    # VP3 re-centres the design and can round by one machine unit (0.1 mm). JEF is written centred
    # on the hoop (its header assumes so): the same stitches, moved as a whole.
    tol = 0.1 if ext == "vp3" else 0.0
    if ext == "jef":
        xs = [p[0] for p in pb]
        assert abs(min(xs) + max(xs)) <= 0.1 + 1e-9  # centred
        dx, dy = pb[0][0] - pa[0][0], pb[0][1] - pa[0][1]
        pb = [(x - dx, y - dy) for x, y in pb]
    assert max(max(abs(p[0] - q[0]), abs(p[1] - q[1])) for p, q in zip(pa, pb)) <= tol + 1e-9


@pytest.mark.parametrize("ext", ["pes", "jef"])
def test_export_keeps_trim_and_stop(pes_file, tmp_path, ext):
    out = tmp_path / f"out.{ext}"
    design.export(str(pes_file), str(out))
    info = design.open_design(str(out))["info"]
    assert info["stops"] == 1
    assert info["trims"] >= 1
    assert info["color_changes"] == 1


def test_pes_export_keeps_thread_names(pes_file, tmp_path):
    out = tmp_path / "out.pes"
    design.export(str(pes_file), str(out))
    assert [t["name"] for t in design.open_design(str(out))["threads"]] == ["Red", "Blue"]


def test_export_refuses_to_overwrite_source(pes_file):
    with pytest.raises(design.DesignError, match="over the original"):
        design.export(str(pes_file), str(pes_file))


def test_unreadable_files_give_user_facing_errors(tmp_path):
    be = tmp_path / "x.be"
    be.write_bytes(b"BRITONLEAPBE015BE")
    with pytest.raises(design.DesignError, match="Embrilliance"):
        design.open_design(str(be))
    with pytest.raises(design.DesignError, match="not found"):
        design.open_design(str(tmp_path / "missing.pes"))
    bad = tmp_path / "bad.pes"
    bad.write_bytes(b"garbage")
    with pytest.raises(design.DesignError):
        design.open_design(str(bad))


def test_design_errors_use_app_error_code(tmp_path):
    resp = rpc("design.open", path=str(tmp_path / "missing.pes"))
    assert resp["error"]["code"] == -32000
    assert "not found" in resp["error"]["message"]


def test_formats_lists_pes_and_jef_both_ways():
    f = design.formats()
    for ext in ("pes", "jef", "dst"):
        assert ext in {e["ext"] for e in f["read"]}
        assert ext in {e["ext"] for e in f["write"]}
    assert "pdf" not in {e["ext"] for e in f["write"]}  # non-embroidery outputs hidden
    assert "gcode" not in {e["ext"] for e in f["write"]}


def test_convert_folder(tmp_path, pes_file):
    src = pes_file.parent
    (src / "notes.txt").write_text("hi")
    (src / "broken.dst").write_bytes(b"")
    sub = src / "sub"
    sub.mkdir()
    pe.write(make_pattern(), str(sub / "inner.pes"))
    dest = tmp_path / "out"

    flat = design.convert_folder(str(src), str(dest), "jef")
    assert [c["dest"] for c in flat["converted"]] == [str(dest / "sample.jef")]
    assert [f["src"] for f in flat["failed"]] == [str(src / "broken.dst")]
    assert str(src / "notes.txt") in flat["skipped"]

    again = design.convert_folder(str(src), str(dest), ".JEF", recursive=True)
    dests = sorted(c["dest"] for c in again["converted"])
    assert dests == sorted([str(dest / "sample (1).jef"), str(dest / "sub" / "inner.jef")])
    assert design.open_design(str(dest / "sub" / "inner.jef"))["info"]["stitches"] == 44


# ---------------------------------------------------------------- phase 4 (QA medium and low findings)

import os  # noqa: E402

M = pe.COMMAND_MASK


def _many_colours(n):
    p = pe.EmbPattern()
    for i in range(n):
        p.add_thread(pe.EmbThread("#%06x" % ((i * 977 + 13) & 0xFFFFFF), f"T{i}"))
    for i in range(n):
        p.stitch_abs(i * 5, 0)
        p.stitch_abs(i * 5 + 3, 3)
        if i < n - 1:
            p.color_change()
    p.end()
    return p


def test_qa4_a_failed_save_leaves_the_old_file_alone(tmp_path, monkeypatch):
    good = tmp_path / "keep.pes"
    design.write(_many_colours(3), good)
    before = good.read_bytes()

    def broken(pattern, filename, settings=None):
        with open(filename, "wb") as f:
            f.write(b"half a fi")
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(design.pe, "write", broken)
    with pytest.raises(design.DesignError, match="disk on fire"):
        design.write(_many_colours(3), good)
    assert good.read_bytes() == before
    assert [f.name for f in tmp_path.iterdir()] == ["keep.pes"]  # no half-written temp file left


def test_qa4_pes_over_255_colour_steps_says_so_before_writing(tmp_path):
    design.write(_many_colours(255), tmp_path / "ok.pes")
    with pytest.raises(design.DesignError, match="at most 255 color steps"):
        design.write(_many_colours(256), tmp_path / "many.pes")
    assert not (tmp_path / "many.pes").exists()


def test_qa4_accented_thread_names_keep_the_pes_thread_table_readable(tmp_path):
    p = pe.EmbPattern()
    names = ["Grün", "Café au lait", "Plain", "Blue"]
    cols = ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]
    for n, c in zip(names, cols):
        p.add_thread(pe.EmbThread(c, n, "1001", brand="Madeira"))
    for i in range(4):
        p.stitch_abs(i * 50, 0)
        p.stitch_abs(i * 50 + 30, 0)
        if i < 3:
            p.color_change()
    p.end()
    design.write(p, tmp_path / "u.pes")
    back = pe.read(str(tmp_path / "u.pes"))
    assert [t.hex_color() for t in back.threadlist] == cols
    assert [t.description for t in back.threadlist] == ["Grun", "Cafe au lait", "Plain", "Blue"]
    assert p.threadlist[0].description == "Grün"  # the design itself is unchanged


def test_qa4_long_stitches_are_sewn_in_pieces_not_jumped(tmp_path):
    p = pe.EmbPattern()
    p.add_thread(pe.EmbThread("#ff0000", "R"))
    p.stitch_abs(0, 0)
    p.stitch_abs(144, 0)  # 14.4 mm: longer than JEF's 12.7 mm
    p.stitch_abs(0, 0)
    p.end()
    design.write(p, tmp_path / "long.jef")
    back = pe.read(str(tmp_path / "long.jef"), {"trims": True})
    kinds = [c & M for *_, c in back.stitches if c & M != pe.END]
    assert pe.JUMP not in kinds[1:] and pe.TRIM not in kinds
    assert kinds.count(pe.STITCH) >= 5


def test_qa4_jef_is_centred_on_the_hoop(tmp_path):
    p = pe.EmbPattern()
    p.add_thread(pe.EmbThread("#ff0000", "R"))
    for x in range(0, 501, 50):
        p.stitch_abs(x, 200)
    p.end()
    design.write(p, tmp_path / "c.jef")
    xs = [x for x, y, c in pe.read(str(tmp_path / "c.jef")).stitches if c & M == pe.STITCH]
    assert min(xs) == -max(xs) == -250


def test_qa4_nothing_to_sew_is_refused_before_touching_the_file(tmp_path):
    p = pe.EmbPattern()
    p.add_thread(pe.EmbThread("#ff0000", "R"))
    p.move_abs(100, 100)
    p.end()
    for ext in ("pes", "jef"):
        with pytest.raises(design.DesignError, match="nothing to sew"):
            design.write(p, tmp_path / f"e.{ext}")
        assert not (tmp_path / f"e.{ext}").exists()


def test_qa4_plain_messages_for_odd_file_names(tmp_path):
    with pytest.raises(design.DesignError, match="for example noext.pes"):
        design.write(make_pattern(), tmp_path / "noext")
    with pytest.raises(design.DesignError, match="Choose a name ending in .pes"):
        design.write(make_pattern(), tmp_path / "x.qqq")
    if os.name == "nt":
        with pytest.raises(design.DesignError, match="Windows keeps"):
            design.write(make_pattern(), tmp_path / "CON.pes")


def test_qa4_batch_convert_into_the_source_folder_converts(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    pe.write(make_pattern(), str(src / "a.pes"))
    r = design.convert_folder(str(src), str(src), "jef")
    assert len(r["converted"]) == 1 and (src / "a.jef").exists()
    r = design.convert_folder(str(src), str(tmp_path), "jef")  # a folder that holds the source
    assert len(r["converted"]) >= 1
