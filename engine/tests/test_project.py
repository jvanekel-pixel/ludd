"""Project files keep everything: the key test is deleting the originals and reopening."""

import base64
import json
import os
import zipfile

import pyembroidery as pe
import pytest

from threadline_engine import layout, project
from threadline_engine.project import ProjectError

# A 2x1 pixel PNG.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAYAAAD0In+KAAAAEUlEQVR4nGP4z8DwHwyBLAAz/gP9Tn9a5QAAAABJRU5ErkJggg=="
)


@pytest.fixture
def files(tmp_path):
    img = tmp_path / "photo.png"
    img.write_bytes(PNG)
    p = pe.EmbPattern()
    p.add_thread(pe.EmbThread("#ff0000", "Red"))
    for x in range(0, 200, 20):
        p.stitch_abs(x, 0)
    p.end()
    pes = tmp_path / "flower.pes"
    pe.write(p, str(pes), {"version": 6})
    return img, pes


def make_project(img, pes):
    return {
        "title": "Test",
        "layout": {
            "items": [
                {"id": "a", "path": str(pes), "transform": {"x": 3}, "threads": [], "ops": []},
                {"id": "b", "kind": "run", "geometry": {"nodes": [[0, 0, "c"], [10, 0, "c"]]}, "params": {},
                 "thread": {"color": "#00ff00", "name": "Green"}},
            ],
            "merge_colors": False, "color_sort": False, "basting": {"enabled": False, "margin_mm": 5},
        },
        "images": [{"id": "im", "name": "photo.png", "path": str(img), "x": -12.5, "y": 7.25, "width_mm": 80,
                    "height_mm": 40, "rotate": 15, "opacity": 0.4, "locked": True, "visible": True,
                    "data_url": "data:image/png;base64,xx"}],
        "machine": "brother-pe550d",
    }


def test_save_embeds_everything_and_reopens_after_originals_are_deleted(tmp_path, files):
    img, pes = files
    proj = make_project(img, pes)
    before = layout.render_summary(proj["layout"])

    out = tmp_path / "saved" / "my design"  # no extension: .ludd is added
    info = project.save(str(out), proj)
    assert info["path"].endswith("my design.ludd")
    assert info["designs"] == 1 and info["images"] == 1

    img.unlink()
    pes.unlink()  # the originals are gone (moved, deleted, other PC...)

    back = project.open_project(info["path"])
    im = back["images"][0]
    # Placement survives exactly.
    assert {k: im[k] for k in ("x", "y", "width_mm", "height_mm", "rotate", "opacity", "locked")} == {
        "x": -12.5, "y": 7.25, "width_mm": 80, "height_mm": 40, "rotate": 15, "opacity": 0.4, "locked": True}
    assert im["name"] == "photo.png"
    assert im["data_url"] == "data:image/png;base64," + base64.b64encode(PNG).decode()
    # The design renders identically from the embedded copy.
    after = layout.render_summary(back["layout"])
    assert after["records"]["x"] == before["records"]["x"]
    assert back["layout"]["items"][1]["kind"] == "run"
    assert back["path"] == info["path"]


def test_save_does_not_change_the_callers_project(tmp_path, files):
    img, pes = files
    proj = make_project(img, pes)
    snapshot = json.dumps(proj, sort_keys=True)
    project.save(str(tmp_path / "x.ludd"), proj)
    assert json.dumps(proj, sort_keys=True) == snapshot


def test_same_file_is_stored_once(tmp_path, files):
    img, pes = files
    proj = make_project(img, pes)
    proj["layout"]["items"].append({"id": "c", "path": str(pes), "transform": {}, "threads": [], "ops": []})
    out = project.save(str(tmp_path / "x.ludd"), proj)["path"]
    with zipfile.ZipFile(out) as z:
        assert sum(n.startswith("designs/") for n in z.namelist()) == 1


def test_missing_original_at_save_time_is_a_clear_error(tmp_path, files):
    img, pes = files
    proj = make_project(img, pes)
    img.unlink()
    with pytest.raises(ProjectError, match="moved or deleted"):
        project.save(str(tmp_path / "x.ludd"), proj)
    assert not (tmp_path / "x.ludd").exists()


def test_failed_save_keeps_the_previous_file(tmp_path, files, monkeypatch):
    img, pes = files
    dest = tmp_path / "x.ludd"
    project.save(str(dest), make_project(img, pes))
    good = dest.read_bytes()

    def boom(*a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(project.zipfile.ZipFile, "writestr", boom)
    with pytest.raises((ProjectError, OSError)):
        project.save(str(dest), make_project(img, pes))
    assert dest.read_bytes() == good
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".ludd-")]


def test_rejects_non_projects_and_unsafe_members(tmp_path):
    bad = tmp_path / "bad.ludd"
    bad.write_text("not a zip")
    with pytest.raises(ProjectError, match="isn't a LUDD project"):
        project.open_project(str(bad))
    evil = tmp_path / "evil.ludd"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("project.json", json.dumps({
            "format": "ludd-project", "version": 1, "images": [],
            "layout": {"items": [{"embedded": "designs/../../escape.pes"}]},
        }))
    with pytest.raises(ProjectError, match="unexpected file"):
        project.open_project(str(evil))
    newer = tmp_path / "newer.ludd"
    with zipfile.ZipFile(newer, "w") as z:
        z.writestr("project.json", json.dumps({"format": "ludd-project", "version": 99}))
    with pytest.raises(ProjectError, match="newer"):
        project.open_project(str(newer))


def test_images(tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(PNG)
    info = project.load_image(str(img))
    assert info["data_url"].startswith("data:image/png;base64,") and info["bytes"] == len(PNG)
    with pytest.raises(ProjectError, match="Can't use"):
        project.load_image(str(tmp_path / "a.tiff"))
    with pytest.raises(ProjectError, match="moved or deleted"):
        project.load_image(str(tmp_path / "gone.png"))


def test_autosave_recovery_cycle(tmp_path, files):
    img, pes = files
    assert project.recovery() is None
    proj = {**make_project(img, pes), "path": str(tmp_path / "work.ludd")}
    project.autosave(proj)
    info = project.recovery()
    assert info["items"] == 2 and info["images"] == 1 and info["title"] == "Test"
    restored = project.restore()
    assert restored["path"] == str(tmp_path / "work.ludd")  # saves go back to the real file
    assert restored["images"][0]["opacity"] == 0.4
    project.discard_recovery()
    assert project.recovery() is None
    with pytest.raises(ProjectError):
        project.restore()


def test_opens_projects_saved_before_the_rename(tmp_path, files):
    """Threadline was the working name: its .thl projects still open."""
    img, pes = files
    out = project.save(str(tmp_path / "old.ludd"), make_project(img, pes))["path"]
    old = tmp_path / "old.thl"
    with zipfile.ZipFile(out) as src, zipfile.ZipFile(old, "w") as dst:
        for name in src.namelist():
            data = src.read(name)
            if name == "project.json":
                m = json.loads(data)
                m["format"] = "threadline-project"
                data = json.dumps(m).encode()
            dst.writestr(name, data)
    reopened = project.open_project(str(old))
    assert len(reopened["images"]) == 1 and reopened["path"] == str(old)


def test_data_folder_moves_to_the_new_name(tmp_path, monkeypatch):
    from threadline_engine import storage

    monkeypatch.delenv("THREADLINE_DATA_DIR", raising=False)
    monkeypatch.setattr(storage, "_base_dir", lambda: tmp_path)
    (tmp_path / "Threadline" / "threads").mkdir(parents=True)
    (tmp_path / "Threadline" / "threads" / "my.json").write_text("{}")
    assert storage.data_dir() == tmp_path / "Ludd"
    assert (tmp_path / "Ludd" / "threads" / "my.json").exists()
    assert not (tmp_path / "Threadline").exists()


def test_a_dot_in_the_name_is_kept(tmp_path, files):
    img, pes = files
    out = project.save(str(tmp_path / "Bob v1.2"), make_project(img, pes))["path"]
    assert out.endswith("Bob v1.2.ludd")


def test_added_files_survive_the_original_being_deleted_before_the_first_save(tmp_path, files):
    img, pes = files
    project.load_image(str(img))  # adding the picture keeps a private copy
    layout.render_summary(make_project(img, pes)["layout"])  # so does showing the design
    img.unlink()
    pes.unlink()
    info = project.save(str(tmp_path / "late.ludd"), make_project(img, pes))
    assert info["designs"] == 1 and info["images"] == 1
