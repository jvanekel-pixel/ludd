"""Golden round-trip tests on real designs in fixtures/.

fixtures/ holds the user's own (often purchased) designs and is not committed,
so these tests skip when it's empty (e.g. in CI).
"""

from pathlib import Path

import pytest

from threadline_engine import design

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
READABLE = {f["ext"] for f in design.formats()["read"]}
FILES = sorted(p for p in FIXTURES.glob("*") if p.suffix.lower().lstrip(".") in READABLE) if FIXTURES.is_dir() else []

pytestmark = pytest.mark.skipif(not FILES, reason="no fixture designs in fixtures/")

# Known pyembroidery JEF quirk: a STOP may be written as a color change (BMOFACE.PES: final stop).
# On Janome machines both pause the machine; we accept it but keep the total of the two the same.


def stitch_points(d):
    r = d["records"]
    return [(x, y) for x, y, k in zip(r["x"], r["y"], r["kind"]) if k == design.STITCH]


def real_trims(d):
    """Trims that cut thread after stitching (a trim right after a color change is redundant)."""
    n, sewn = 0, False
    for k in d["records"]["kind"]:
        if k == design.STITCH:
            sewn = True
        elif k == design.TRIM:
            n += sewn
            sewn = False
        elif k == design.COLOR_CHANGE:
            sewn = False
    return n


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_opens(path):
    d = design.open_design(str(path))
    assert d["info"]["stitches"] > 0
    assert d["info"]["width_mm"] > 0 and d["info"]["height_mm"] > 0
    assert len(d["threads"]) >= d["info"]["colors"]


@pytest.mark.parametrize("ext", ["pes", "jef", "dst"])
@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_roundtrip(path, ext, tmp_path):
    src = design.open_design(str(path))
    out = tmp_path / f"out.{ext}"
    design.export(str(path), str(out))
    back = design.open_design(str(out))

    assert stitch_points(back) == stitch_points(src)
    assert back["info"]["bounds_mm"] == src["info"]["bounds_mm"]

    if ext == "pes":
        assert real_trims(back) == real_trims(src)
        assert back["info"]["stops"] == src["info"]["stops"]
        assert back["info"]["color_changes"] == src["info"]["color_changes"]
        assert [t["color"] for t in back["threads"]] == [t["color"] for t in src["threads"]]
    elif ext == "jef":
        pauses = lambda d: d["info"]["stops"] + d["info"]["color_changes"]  # noqa: E731
        assert pauses(back) == pauses(src)
        # A stop turned color change also cuts, so it may absorb the trim at the same spot.
        assert real_trims(back) >= real_trims(src) - (src["info"]["stops"] - back["info"]["stops"])
