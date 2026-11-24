"""Golden round-trip tests on real designs.

Always on the committed samples/ (PES and JEF, the owner's formats), so CI tests them too;
plus fixtures/, the user's own (often purchased) designs, which isn't committed and is used
when present.
"""

from pathlib import Path

import pytest

from threadline_engine import design

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"
SAMPLES = ROOT / "samples"
READABLE = {f["ext"] for f in design.formats()["read"]}


def designs_in(folder: Path, exts: set[str]) -> list[Path]:
    return sorted(p for p in folder.glob("*") if p.suffix.lower().lstrip(".") in exts) if folder.is_dir() else []


FILES = designs_in(SAMPLES, {"pes", "jef"}) + designs_in(FIXTURES, READABLE)

# Known pyembroidery JEF quirk: a STOP may be written as a color change (BMOFACE.PES: final stop).
# On Janome machines both pause the machine; we accept it but keep the total of the two the same.


def stitch_points(d):
    r = d["records"]
    return [(x, y) for x, y, k in zip(r["x"], r["y"], r["kind"]) if k == design.STITCH]


def shifted(points, like):
    """`points` moved so their bounds start where `like`'s do (positions are whole 0.1 mm)."""
    b = like["info"]["bounds_mm"]
    if not points:
        return points
    dx, dy = b[0] - min(x for x, _ in points), b[1] - min(y for _, y in points)
    return [(round(x + dx, 1), round(y + dy, 1)) for x, y in points]


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


def test_committed_samples_are_tested():
    """CI has no fixtures/: the PES and JEF round trips must still run there (QA: they all skipped)."""
    kinds = {p.suffix.lower() for p in FILES if p.parent == SAMPLES}
    assert {".pes", ".jef"} <= kinds


@pytest.mark.parametrize("path", FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_opens(path):
    d = design.open_design(str(path))
    assert d["info"]["stitches"] > 0
    assert d["info"]["width_mm"] > 0 and d["info"]["height_mm"] > 0
    assert len(d["threads"]) >= d["info"]["colors"]


@pytest.mark.parametrize("ext", ["pes", "jef", "dst"])
@pytest.mark.parametrize("path", FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_roundtrip(path, ext, tmp_path):
    src = design.open_design(str(path))
    out = tmp_path / f"out.{ext}"
    design.export(str(path), str(out))
    back = design.open_design(str(out))

    if ext in ("jef", "pes"):
        # JEF puts the design's centre on the hoop centre, PES its top-left corner at (0, 0) (as
        # Brother machines read it): the same stitches, moved as a whole.
        assert shifted(stitch_points(back), src) == stitch_points(src)
        assert (back["info"]["width_mm"], back["info"]["height_mm"]) == (src["info"]["width_mm"], src["info"]["height_mm"])
    else:
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


def test_pes_files_start_at_the_top_left_corner_like_embrilliance(tmp_path):
    """Brother machines read a PES design from its top-left corner: written centred on (0, 0), the
    PE550D showed it shifted up and left by half its size, mostly outside the hoop. Embrilliance's
    files (the fixtures) run from (0, 0); LUDD's must too, whatever the design's position."""
    import pyembroidery as pe

    for f in sorted(FIXTURES.glob("*.PES")):
        assert pe.read(str(f)).extents()[:2] == (0, 0), f.name
    p = pe.EmbPattern()
    p.add_thread(pe.EmbThread("#ff0000", "Red"))
    for x, y in [(-300, -200), (300, -200), (300, 250), (-300, 250)]:
        p.add_stitch_absolute(pe.STITCH, x, y)
    p.end()
    out = tmp_path / "corner.pes"
    design.write(p, out)
    back = pe.read(str(out))
    assert back.extents() == (0, 0, 600, 450)


SAMPLE_PROJECTS = sorted(SAMPLES.glob("*.ludd"))


@pytest.mark.parametrize("ludd", SAMPLE_PROJECTS, ids=lambda p: p.stem)
def test_qa2_p6_sample_projects_sew_like_their_shipped_files(ludd, tmp_path):
    """Decision 6: each sample project (saved by LUDD 1.0.0) rendered and exported to PES must
    match the PES shipped beside it, so a change to how old projects sew is made on purpose
    (regenerate with scripts/make_samples.py and add a stitch-out row)."""
    from threadline_engine import layout, project

    proj = project.open_project(str(ludd))
    shipped = ludd.with_suffix(".pes")
    if not shipped.exists():  # applique and the split banner ship as projects only
        assert layout.render_summary(proj["layout"])["info"]["stitches"] > 0
        return
    out = tmp_path / "now.pes"
    layout.export(proj["layout"], str(out))
    now, want = design.open_design(str(out)), design.open_design(str(shipped))
    assert now["records"] == want["records"]
    assert [t["color"] for t in now["threads"]] == [t["color"] for t in want["threads"]]
