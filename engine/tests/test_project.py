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


def _zip(path, manifest, members=None):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("project.json", manifest if isinstance(manifest, str) else json.dumps(manifest))
        for name, data in (members or {}).items():
            z.writestr(name, data)
    return str(path)


GOOD = {"format": "ludd-project", "version": 1, "layout": {"items": []}, "images": []}


def test_qa_reopened_designs_keep_their_own_name_through_resaving(tmp_path, files):
    img, pes = files
    proj = make_project(img, pes)
    first = project.open_project(project.save(str(tmp_path / "a"), proj)["path"])
    item = first["layout"]["items"][0]
    assert item["original_name"] == "flower.pes" and item["name"] == "flower.pes"
    again = project.open_project(project.save(str(tmp_path / "b"), first)["path"])
    assert again["layout"]["items"][0]["original_name"] == "flower.pes"


def test_qa_projects_say_what_they_need_and_newer_ones_are_refused(tmp_path, files):
    img, pes = files
    plain = project.save(str(tmp_path / "plain"), make_project(img, pes))["path"]
    with zipfile.ZipFile(plain) as z:
        m = json.loads(z.read("project.json"))
    assert m["version"] == 1 and m["features"] == []  # LUDD 1.0.0 can still open it
    proj = make_project(img, pes)
    proj["layout"]["travel_under"] = True
    proj["layout"]["items"].append({"id": "f", "kind": "fill", "geometry": {"outline": [[0, 0, "c"], [9, 0, "c"], [9, 9, "c"]]},
                                    "params": {"pattern": "stipple"}, "thread": {"color": "#000000"}})
    newer = project.save(str(tmp_path / "newer"), proj)["path"]
    with zipfile.ZipFile(newer) as z:
        m = json.loads(z.read("project.json"))
    assert m["version"] == 2 and m["features"] == ["fill_patterns", "travel_under"]  # 1.0.0 says "update"
    assert project.open_project(newer)["layout"]["travel_under"] is True
    with pytest.raises(ProjectError, match="update LUDD"):
        project.open_project(_zip(tmp_path / "future.ludd", {**GOOD, "version": 2, "features": ["hologram_fill"]}))


def test_phase4_projects_name_the_repairs_inserts_and_overlap_they_use():
    """Each changes what is sewn, so an older LUDD must refuse the project instead of sewing it wrong."""
    def one(ops):
        return {"items": [{"id": "a", "path": "x.pes", "ops": ops}]}

    for name in ("filter_small", "declump", "density_limit", "rebuild", "remove_hidden"):
        assert project._features(one([{"op": name}])) == {"stitch_repairs"}, name
    for name in ("insert_stitch", "insert_jump", "lock_jump"):
        assert project._features(one([{"op": name}])) == {"stitch_inserts"}, name
    assert project._features(one([{"op": "delete_block"}, "junk", {"op": ["rebuild"]}])) == set()
    assert project._features({"remove_overlap": {"enabled": True, "keep_mm": 1}}) == {"remove_overlap"}
    for off in ({"enabled": False, "keep_mm": 1}, "junk", None):
        assert project._features({"remove_overlap": off}) == set(), off
    assert {"stitch_repairs", "stitch_inserts", "remove_overlap"} <= project.KNOWN_FEATURES


@pytest.mark.parametrize("manifest, message", [
    ("[]", "isn't a LUDD project"),
    (json.dumps({**GOOD, "version": "abc"}), "version"),
    (json.dumps({**GOOD, "layout": {"items": {"a": 1}}}), "layout"),
    (json.dumps({**GOOD, "layout": {"items": ["x"]}}), "layout"),
    ('{"format":"ludd-project","version":1,"layout":{"items":[]},"x":NaN}', "can't be read"),
    ("{not json", "can't be read"),
])
def test_qa_wrong_shaped_projects_get_a_plain_message(tmp_path, manifest, message):
    with pytest.raises(ProjectError, match=message):
        project.open_project(_zip(tmp_path / "bad.ludd", manifest))


def test_qa_missing_locked_and_odd_files_say_what_happened(tmp_path):
    with pytest.raises(ProjectError, match="Couldn't find gone.ludd"):
        project.open_project(str(tmp_path / "gone.ludd"))
    (tmp_path / "dir.ludd").mkdir()
    with pytest.raises(ProjectError, match="folder|Couldn't open|Couldn't read"):
        project.open_project(str(tmp_path / "dir.ludd"))
    member = "images/" + "a" * 32 + ".png"
    with pytest.raises(ProjectError, match="missing"):
        project.open_project(_zip(tmp_path / "m.ludd", {**GOOD, "images": [{"embedded": member}]}))
    # No layout at all opens as an empty design; a picture without its file is left out.
    p = project.open_project(_zip(tmp_path / "e.ludd", {"format": "ludd-project", "version": 1, "images": [{"id": "x"}]}))
    assert p["layout"]["items"] == [] and p["images"] == []


def test_qa_oversized_members_are_refused_before_reading(tmp_path):
    bomb = tmp_path / "bomb.ludd"
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as z:
        with z.open("project.json", "w", force_zip64=True) as f:
            f.write(json.dumps(GOOD).encode())
            for _ in range(34):
                f.write(b" " * (1 << 20))
    assert bomb.stat().st_size < 1 << 20
    with pytest.raises(ProjectError, match="too big"):
        project.open_project(str(bomb))


def test_qa_members_must_match_their_hash_and_a_bad_cache_copy_is_replaced(tmp_path):
    import hashlib

    real = b"real design bytes"
    name = hashlib.sha256(real).hexdigest()[:32]
    member = f"designs/{name}.pes"
    with pytest.raises(ProjectError, match="doesn't match"):
        project.open_project(_zip(tmp_path / "evil.ludd", {**GOOD, "layout": {"items": [{"id": "x", "embedded": member}]}},
                                  {member: b"something else"}))
    cached = project._cache_dir() / f"{name}.pes"
    assert not cached.exists()
    cached.write_bytes(b"planted earlier")  # e.g. by an older LUDD
    p = project.open_project(_zip(tmp_path / "ok.ludd", {**GOOD, "layout": {"items": [{"id": "x", "embedded": member}]}},
                                  {member: real}))
    assert open(p["layout"]["items"][0]["path"], "rb").read() == real


# Not a word that can turn up in a path: macOS temp folders start with /private/, which once matched.
SECRET_WORDS = "top-secret-9f3a-contents"


def test_qa_a_project_names_no_file_outside_itself(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text(SECRET_WORDS)
    hostile = {**GOOD, "layout": {"items": [
        {"id": "a", "path": str(secret)},
        {"id": "t", "kind": "text", "text": "Hi", "font": {"path": str(secret), "family": "Arial", "style": "Regular"}},
    ]}, "images": [{"id": "i", "path": str(secret)}]}
    p = project.open_project(_zip(tmp_path / "h.ludd", hostile))
    # The design item, left with no file, is dropped with a note (QA2 P4); the text keeps no font path.
    assert [it["id"] for it in p["layout"]["items"]] == ["t"] and "path" not in p["layout"]["items"][0]["font"]
    assert p["notes"] and p["images"] == []
    out = project.save(str(tmp_path / "resaved"), p)
    with zipfile.ZipFile(out["path"]) as z:
        assert not any(SECRET_WORDS.encode() in z.read(n) for n in z.namelist())


def test_qa_fonts_travel_with_the_project_without_the_users_folder_name(tmp_path, files):
    img, pes = files
    font_dir = tmp_path / "Users" / "Somebody" / "AppData" / "Fonts"
    font_dir.mkdir(parents=True)
    font = font_dir / "Fancy.ttf"
    font.write_bytes(b"pretend font bytes")
    proj = make_project(img, pes)
    proj["layout"]["items"].append({"id": "t", "kind": "text", "text": "Anna",
                                    "font": {"path": str(font), "index": 0, "family": "Fancy", "style": "Regular"}})
    out = project.save(str(tmp_path / "lettering"), proj)
    assert out["fonts"] == 1
    with zipfile.ZipFile(out["path"]) as z:
        manifest = z.read("project.json").decode()
    assert "Somebody" not in manifest
    font.unlink()  # another PC
    back = project.open_project(out["path"])
    f = back["layout"]["items"][2]["font"]
    assert open(f["path"], "rb").read() == b"pretend font bytes" and f["family"] == "Fancy"
    assert f["original_name"] == "Fancy.ttf"


def test_qa_autosave_keeps_the_rest_when_a_picture_cant_be_read(tmp_path, files):
    img, pes = files
    proj = make_project(img, pes)
    proj["images"][0]["path"] = str(tmp_path / "never-read.png")
    proj["images"][0].pop("data_url")
    project.autosave(proj)
    info = project.recovery()
    assert info["items"] == 2 and info["images"] == 0
    # A save uses the UI's own copy of the picture when the file is gone.
    proj["images"][0]["data_url"] = "data:image/png;base64," + base64.b64encode(PNG).decode()
    saved = project.save(str(tmp_path / "with-copy"), proj)
    assert saved["images"] == 1
    assert project.open_project(saved["path"])["images"][0]["data_url"] == proj["images"][0]["data_url"]


def test_qa_an_unreadable_recovery_copy_is_set_aside_not_offered_forever(tmp_path):
    r = project._recovery_path()
    _zip(r, "[]")
    assert project.recovery() is None
    assert not r.exists() and list(r.parent.glob("unrecovered-*.ludd"))
    _zip(r, GOOD)
    project.discard_recovery(keep=True)
    assert not r.exists() and len(list(r.parent.glob("unrecovered-*.ludd"))) >= 1


def test_qa_save_waits_for_a_file_held_for_a_moment_and_tidies_old_temp_files(tmp_path, files, monkeypatch):
    img, pes = files
    old_tmp = tmp_path / ".ludd-old.tmp"
    old_tmp.write_bytes(b"x")
    os.utime(old_tmp, (0, 0))
    real, tries = os.replace, []

    def held(src, dst):
        tries.append(dst)
        if len(tries) < 3:
            raise PermissionError(32, "The process cannot access the file")
        return real(src, dst)

    monkeypatch.setattr(project.os, "replace", held)
    project.save(str(tmp_path / "held.ludd"), make_project(img, pes))
    assert len(tries) == 3 and (tmp_path / "held.ludd").exists()
    assert not old_tmp.exists()

    def always(src, dst):
        raise PermissionError(32, "The process cannot access the file")

    monkeypatch.setattr(project.os, "replace", always)
    monkeypatch.setattr(project.time, "sleep", lambda s: None)
    with pytest.raises(ProjectError, match="in use by another program"):
        project.save(str(tmp_path / "held.ludd"), make_project(img, pes))


@pytest.mark.skipif(os.name != "nt", reason="Windows path length limit")
def test_qa_long_paths_save_and_open(tmp_path, files):
    img, pes = files
    # A folder as long as Windows allows, and a short name: the save's temp file name is longer
    # than the 259-character limit even though the project's own name isn't.
    folder = tmp_path
    while 245 - len(str(folder)) > 42:  # leaves the last name 1 to 41 letters, never none
        folder = folder / ("d" * 40)
    folder = folder / ("e" * (245 - len(str(folder)) - 1))
    folder.mkdir(parents=True)
    dest = folder / "design.ludd"
    assert len(str(dest)) == 257
    out = project.save(str(dest), make_project(img, pes))
    assert len(project.open_project(out["path"])["layout"]["items"]) == 2


def test_qa_pictures_with_too_many_pixels_are_refused_plainly(tmp_path, monkeypatch):
    img = tmp_path / "huge.png"
    img.write_bytes(PNG)
    monkeypatch.setattr(project, "MAX_IMAGE_PIXELS", 1)
    with pytest.raises(ProjectError, match="too many pixels"):
        project.load_image(str(img))
    (tmp_path / "fake.png").write_bytes(b"not a picture")
    with pytest.raises(ProjectError, match="isn't a picture"):
        project.load_image(str(tmp_path / "fake.png"))


def test_qa_old_data_is_copied_over_when_both_folders_exist(tmp_path, monkeypatch):
    from threadline_engine import storage

    monkeypatch.delenv("THREADLINE_DATA_DIR", raising=False)
    monkeypatch.setattr(storage, "_base_dir", lambda: tmp_path)
    monkeypatch.setattr(storage, "_checked", set())
    (tmp_path / "Threadline" / "threads").mkdir(parents=True)
    (tmp_path / "Threadline" / "threads" / "my-threads.json").write_text("old")
    (tmp_path / "Threadline" / "threads" / "madeira.json").write_text("old chart")
    (tmp_path / "Ludd" / "threads").mkdir(parents=True)
    (tmp_path / "Ludd" / "threads" / "my-threads.json").write_text("new")
    assert storage.data_dir() == tmp_path / "Ludd"
    assert (tmp_path / "Ludd" / "threads" / "my-threads.json").read_text() == "new"  # never replaced
    assert (tmp_path / "Ludd" / "threads" / "madeira.json").read_text() == "old chart"
    assert (tmp_path / "Ludd" / storage.MIGRATED_MARK).exists()
    # Once only: a chart deleted afterwards doesn't come back.
    (tmp_path / "Ludd" / "threads" / "madeira.json").unlink()
    monkeypatch.setattr(storage, "_checked", set())
    storage.data_dir()
    assert not (tmp_path / "Ludd" / "threads" / "madeira.json").exists()


def test_qa_private_copies_unused_for_months_are_tidied(tmp_path):
    from threadline_engine import kept

    old = kept._dir() / ("a" * 32 + ".pes")
    old.write_bytes(b"old")
    os.utime(old, (0, 0))
    fresh = tmp_path / "fresh.pes"
    fresh.write_bytes(b"fresh")
    kept.keep(str(fresh), b"fresh")
    assert kept.prune() == 1
    assert not old.exists() and kept.readable(str(tmp_path / "gone")) == str(tmp_path / "gone")
    fresh.unlink()
    assert open(kept.readable(str(fresh)), "rb").read() == b"fresh"


def test_added_files_survive_the_original_being_deleted_before_the_first_save(tmp_path, files):
    img, pes = files
    project.load_image(str(img))  # adding the picture keeps a private copy
    layout.render_summary(make_project(img, pes)["layout"])  # so does showing the design
    img.unlink()
    pes.unlink()
    info = project.save(str(tmp_path / "late.ludd"), make_project(img, pes))
    assert info["designs"] == 1 and info["images"] == 1


def test_qa2_p1_a_tiny_project_cant_make_gigabytes_of_picture_data(tmp_path):
    """QA2 P1: pictures sharing one embedded member each got their own ~53 MB data URL (12 entries
    in a 39 KB file: 624 MB); nothing limited the count or the total unpacked size."""
    import hashlib

    png = PNG + b"\0" * (39 << 20)
    member = "images/" + hashlib.sha256(png).hexdigest()[:32] + ".png"
    many = {**GOOD, "images": [{"id": str(i), "embedded": member} for i in range(12)]}
    path = tmp_path / "many.ludd"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.json", json.dumps(many))
        z.writestr(member, png)
    assert path.stat().st_size < 1 << 20
    with pytest.raises(ProjectError, match="more picture data"):
        project.open_project(str(path))
    lots = {**GOOD, "images": [{"id": str(i), "embedded": member} for i in range(project.MAX_PICTURES + 1)]}
    with pytest.raises(ProjectError, match="more than"):
        project.open_project(_zip(tmp_path / "lots.ludd", lots))
    # Two pictures of the same small file still open, sharing one data URL.
    small = "images/" + hashlib.sha256(PNG).hexdigest()[:32] + ".png"
    two = {**GOOD, "images": [{"id": "a", "embedded": small}, {"id": "b", "embedded": small}]}
    p = project.open_project(_zip(tmp_path / "two.ludd", two, {small: PNG}))
    assert len(p["images"]) == 2 and p["images"][0]["data_url"] is p["images"][1]["data_url"]


def test_qa2_p1_total_unpacked_size_is_limited(tmp_path, monkeypatch):
    monkeypatch.setattr(project, "MAX_PROJECT_BYTES", 1000)
    with pytest.raises(ProjectError, match="too big"):
        project.open_project(_zip(tmp_path / "big.ludd", GOOD, {"designs/x.pes": b"x" * 2000}))


@pytest.mark.parametrize("item", [
    {"id": "a", "path": None},
    {"id": "a", "kind": "sequins"},
    {"id": "a", "kind": "run", "transform": {"scale_x": "2"}},
    {"id": "a", "kind": "run", "transform": {"rotate": None}},
    {"id": "a", "kind": "run", "ops": "oops"},
    {"id": "a", "kind": "run", "ops": [5]},
    {"id": "a", "kind": "run", "threads": ["red"]},
    {"id": "a", "kind": "run", "thread": "red"},
    {"id": "a", "kind": "run", "params": [1]},
])
def test_qa2_p4_a_damaged_item_is_left_out_with_a_note_not_a_blank_canvas(tmp_path, item):
    """QA2 P4: any dict item opened, then every render failed with "Please report this"."""
    good = {"id": "ok", "kind": "run", "geometry": {"nodes": [[0, 0, "c"], [10, 0, "c"]]}, "params": {}}
    p = project.open_project(_zip(tmp_path / "d.ludd", {**GOOD, "layout": {"items": [item, good]}}))
    assert [it["id"] for it in p["layout"]["items"]] == ["ok"]
    assert "1 part of this project was damaged" in p["notes"][0]
    assert layout.render(p["layout"]).blocks


def test_qa2_p2_private_copies_are_found_again_after_the_engine_restarts(tmp_path, files, monkeypatch):
    """QA2 P2: which original a private copy came from was only in memory, so after a crash
    restart (or Restart engine) a design whose original was gone couldn't be shown or saved."""
    from threadline_engine import kept

    img, pes = files
    proj = make_project(img, pes)
    project.load_image(str(img))
    layout.render_summary(proj["layout"])
    img.unlink()
    pes.unlink()
    # A new engine: nothing in memory.
    monkeypatch.setattr(kept, "_copies", {})
    monkeypatch.setattr(kept, "_loaded", False)
    monkeypatch.setattr(layout.files, "_cache", {})
    assert layout.render(proj["layout"]).blocks
    out = project.save(str(tmp_path / "after-restart"), proj)
    assert out["designs"] == 1 and out["images"] == 1
    # The index names copies in its own folder only.
    (kept._dir() / kept.INDEX).write_text(json.dumps({"x": "../../secret.txt", "y": "C:/secret.txt"}))
    monkeypatch.setattr(kept, "_copies", {})
    monkeypatch.setattr(kept, "_loaded", False)
    assert kept.readable("x") == "x" and kept.readable("y") == "y"


def test_qa2_d12_guides_and_color_sets_survive_save_and_reopen(tmp_path, files):
    """QA2 D12: nothing tested that the layout's guides and color sets come back."""
    img, pes = files
    proj = make_project(img, pes)
    proj["layout"]["guides"] = {"x": [10.5, -3], "y": [0]}
    proj["layout"]["colorways"] = [{"name": "Spring", "threads": {"b": {"color": "#00aa00", "name": "Leaf"}}}]
    out = project.save(str(tmp_path / "guides"), proj)
    back = project.open_project(out["path"])["layout"]
    assert back["guides"] == proj["layout"]["guides"]
    assert back["colorways"] == proj["layout"]["colorways"]
