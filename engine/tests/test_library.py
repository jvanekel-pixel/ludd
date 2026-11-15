"""Design browser: designs in a folder, with pictures."""

import shutil
import sys
from pathlib import Path

import pytest

from threadline_engine import library

# The sample designs that ship with LUDD (committed, unlike the private fixtures/).
SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def test_scan_lists_designs_with_thumbnails_and_skips_other_files(tmp_path):
    for f in SAMPLES.glob("*"):
        if f.suffix.lower() in (".pes", ".jef"):
            shutil.copy(f, tmp_path / f.name)
    (tmp_path / "notes.be").write_bytes(b"not a stitch file")
    r = library.scan(str(tmp_path))
    pes = [d for d in r["designs"] if d["format"] == "PES"]
    assert len(pes) >= 2 and any(d["format"] == "JEF" for d in r["designs"])
    assert all(d["ok"] and d["thumb"].startswith("data:image/png;base64,") and d["stitches"] > 0 for d in pes)
    assert not any(d["name"].endswith(".be") for d in r["designs"])  # Embrilliance working files are not stitch files
    again = library.scan(str(tmp_path))
    assert again["designs"][0] is r["designs"][0]  # cached


def test_scan_filters_by_name(tmp_path):
    for f in SAMPLES.glob("*.pes"):
        shutil.copy(f, tmp_path / f.name)
    r = library.scan(str(tmp_path), query="flower")
    assert r["designs"] and all("flower" in d["name"].lower() for d in r["designs"])
    assert len(library.scan(str(tmp_path))["designs"]) > len(r["designs"])


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junctions")
def test_qa_junction_loops_are_not_followed(tmp_path):
    import _winapi

    lib = tmp_path / "lib"
    (lib / "sub").mkdir(parents=True)
    shutil.copy(SAMPLES / "Flower.pes", lib / "sub" / "Flower.pes")
    _winapi.CreateJunction(str(lib), str(lib / "sub" / "loop"))
    r = library.scan(str(lib))
    assert [d["name"] for d in r["designs"]] == ["Flower.pes"]
