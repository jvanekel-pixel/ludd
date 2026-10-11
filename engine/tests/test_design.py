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
    # VP3 re-centres the design and can round by one machine unit (0.1 mm).
    tol = 0.1 if ext == "vp3" else 0.0
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
