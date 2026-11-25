"""LUDD project files (.ludd): everything needed to reopen a design exactly as it was.

A .ludd is a zip (projects from before the rename, .thl, open the same way):

    project.json        the layout (drawn objects and placed designs), reference images and settings
    designs/<sha>.<ext> a copy of every stitch file placed in the layout
    images/<sha>.<ext>  a copy of every reference image
    fonts/<sha>.<ext>   a copy of every font used by lettering

Files are embedded, never linked: moving, renaming or deleting the originals, rebooting, or
opening the project on another PC can't lose them. Opened projects extract their files into a
content-addressed cache, so paths inside the app stay stable. A project names no file outside
itself: paths in a project.json that don't come from its own embedded files are ignored.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import os
import sys
import tempfile
import time
import zipfile
import zlib
from pathlib import Path
from typing import Any, Callable

from . import kept
from .storage import data_dir

FORMAT = "ludd-project"
OLD_FORMATS = {"threadline-project"}
EXT = ".ludd"
OLD_EXTS = {".thl"}
# The newest project version this engine reads. Projects are stamped with the lowest version
# that can read them: 1 unless they use something LUDD 1.0.0 didn't know (see _features).
VERSION = 2
# Things a project can need that LUDD 1.0.0 (which reads version 1) would silently sew wrong.
# A project lists the ones it uses; a newer LUDD's additions are refused with "update to open it".
# KNOWN_FEATURES is made from the two tables in "what a project needs" below.
IMAGE_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "webp": "image/webp",
}
MAX_IMAGE_BYTES = 40 * 1024 * 1024
MAX_IMAGE_PIXELS = 120_000_000  # 120 megapixels: far more than tracing needs
# Largest member a project may hold (checked before reading, so a damaged or hostile file can't
# fill the memory or the disk).
MAX_MEMBER_BYTES = {"project.json": 32 * 1024 * 1024, "images": MAX_IMAGE_BYTES, "designs": 64 * 1024 * 1024,
                    "fonts": 64 * 1024 * 1024}
MAX_PICTURES = 64  # far more than anyone traces from; a hostile file can't list thousands (QA2 P1)
MAX_PICTURES_SHOWN = 440 * 1024 * 1024  # data URLs sent to the window: about 8 of the largest pictures
MAX_PROJECT_BYTES = 768 * 1024 * 1024  # all members together, unpacked (QA2 P1)
ITEM_KINDS = ("file", "run", "satin", "fill", "applique", "text")
STALE_TEMP_S = 3600  # a save's temp file older than this was left by a save that never finished


class ProjectError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


def _cache_dir() -> Path:
    d = data_dir() / "project-files"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _recovery_dir() -> Path:
    d = data_dir() / "recovery"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _recovery_path() -> Path:
    return _recovery_dir() / f"autosave{EXT}"


def _ext(path: str) -> str:
    return Path(path).suffix.lower().lstrip(".")


def _read(path: str, what: str, as_added: bool = False) -> bytes:
    try:
        return Path(kept.readable(path, as_added)).read_bytes()
    except OSError as exc:
        raise ProjectError(f"Couldn't read the {what} {Path(path).name}: it may have been moved or deleted") from exc


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:32]


def _member(folder: str, data: bytes, ext: str) -> str:
    return f"{folder}/{_digest(data)}.{ext}"


def _in_cache(path: str) -> bool:
    try:
        return Path(path).resolve().parent == _cache_dir().resolve()
    except OSError:
        return False


def _long(p: Path) -> str:
    """Windows paths of 260 characters or more need the extended-length form."""
    s = str(p)
    if sys.platform == "win32" and len(s) >= 240 and not s.startswith("\\\\?\\"):
        s = os.path.abspath(s)
        return "\\\\?\\UNC\\" + s[2:] if s.startswith("\\\\") else "\\\\?\\" + s
    return s


# ---------------------------------------------------------------- images


def load_image(path: str) -> dict[str, Any]:
    """A picture for tracing: its bytes as a data URL for display, plus where it lives."""
    ext = _ext(path)
    if ext not in IMAGE_TYPES:
        raise ProjectError(f"Can't use .{ext} pictures. Use PNG, JPG, GIF, BMP or WebP.")
    p = Path(kept.readable(path))
    try:
        size = p.stat().st_size
    except OSError:
        size = 0  # _read below says what's wrong
    if size > MAX_IMAGE_BYTES:
        raise ProjectError(f"{Path(path).name} is over {MAX_IMAGE_BYTES // (1024 * 1024)} MB; use a smaller copy")
    data = _read(path, "picture")
    if len(data) > MAX_IMAGE_BYTES:
        raise ProjectError(f"{Path(path).name} is over {MAX_IMAGE_BYTES // (1024 * 1024)} MB; use a smaller copy")
    _check_pixels(data, Path(path).name)
    kept.keep(path, data)
    return {
        "name": Path(path).name,
        "path": path,
        "data_url": f"data:{IMAGE_TYPES[ext]};base64,{base64.b64encode(data).decode('ascii')}",
        "bytes": len(data),
    }


def _check_pixels(data: bytes, name: str) -> None:
    """Refuse pictures with so many pixels that tracing them would run out of memory (only the
    header is read)."""
    import io
    import warnings

    from PIL import Image

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as im:
                w, h = im.size
    except Image.DecompressionBombError:
        w, h = MAX_IMAGE_PIXELS, 2
    except Exception as exc:  # noqa: BLE001 - not a picture Pillow can read
        raise ProjectError(f"{name} isn't a picture LUDD can read, or it's damaged") from exc
    if w * h > MAX_IMAGE_PIXELS:
        raise ProjectError(f"{name} has too many pixels to trace; use a smaller copy (at most about "
                           f"{MAX_IMAGE_PIXELS // 1_000_000} megapixels, for example 8000 × 6000)")


def _data_url_bytes(url: Any) -> bytes | None:
    """The picture inside a data: URL (the UI's copy), if there is one."""
    if not isinstance(url, str) or not url.startswith("data:") or ";base64," not in url:
        return None
    try:
        return base64.b64decode(url.split(";base64,", 1)[1], validate=False)
    except (binascii.Error, ValueError):
        return None


# ---------------------------------------------------------------- what a project needs


# Things a layout can use that LUDD 1.0.0 didn't know (it would open the project and sew it wrong).
# Add a row with every change to what a project can hold; KNOWN_FEATURES follows. A pattern or
# style added after 1.0.1 gets its own flag (fill_spiral, line_backstitch): 1.0.1 knows
# fill_patterns and would try to sew a pattern it has never heard of.
LAYOUT_FEATURES: dict[str, Callable[[dict], bool]] = {
    "travel_under": lambda layout: bool(layout.get("travel_under")),
    "trim_jumps_all": lambda layout: layout.get("jumps_to_trims") is not None,  # "Trim jumps longer than…" for the whole layout
}
ITEM_FEATURES: dict[str, Callable[[dict, dict, dict], bool]] = {  # (item, params, geometry)
    "fill_patterns": lambda it, p, g: it.get("kind") in ("fill", "applique") and p.get("pattern") not in (None, "", "tatami"),
    "motif_lines": lambda it, p, g: it.get("kind") == "run" and p.get("style") == "motif",
    "satin_ribbons": lambda it, p, g: it.get("kind") == "satin" and g.get("nodes") is not None,
    "text_on_path": lambda it, p, g: (it.get("kind") == "text" and isinstance(it.get("shape"), dict)
                                      and it["shape"].get("type") == "path"),
    "stitch_edits": lambda it, p, g: any(isinstance(o, dict) and o.get("op") in ("delete_stitches", "move_stitch", "move_stitches")
                                         for o in it.get("ops") or []),
    "fill_spiral": lambda it, p, g: it.get("kind") in ("fill", "applique") and p.get("pattern") == "spiral",
}
KNOWN_FEATURES = set(LAYOUT_FEATURES) | set(ITEM_FEATURES)


def _features(layout: dict[str, Any]) -> set[str]:
    """Things this layout uses that LUDD 1.0.0 didn't know (LAYOUT_FEATURES and ITEM_FEATURES)."""
    used: set[str] = {name for name, uses in LAYOUT_FEATURES.items() if uses(layout)}
    for it in layout.get("items") or []:
        if not isinstance(it, dict):
            continue
        p = it.get("params") if isinstance(it.get("params"), dict) else {}
        g = it.get("geometry") if isinstance(it.get("geometry"), dict) else {}
        used |= {name for name, uses in ITEM_FEATURES.items() if uses(it, p, g)}
    return used


# ---------------------------------------------------------------- save / open


def _pack(project: dict[str, Any], autosave: bool = False) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Project JSON with paths replaced by embedded member names, plus the member bytes.
    For an autosave, a file that can't be read is left out (or linked) instead of failing: the
    rest of the work is still worth keeping."""
    files: dict[str, bytes] = {}
    out = json.loads(json.dumps(project))  # deep copy, JSON-safe
    layout = out.get("layout") if isinstance(out.get("layout"), dict) else {}
    feats = _features(layout)
    out["format"], out["version"] = FORMAT, 2 if feats else 1
    out["features"] = sorted(feats)
    out["saved_at"] = time.time()
    pinned = kept.pinned(layout.get("items") or [])
    for it in layout.get("items") or []:
        if it.get("path"):
            try:
                # With edits, the bytes they were made on (QA2 P3), not a newer file on disk.
                data = _read(it["path"], "design", as_added=it["path"] in pinned)
            except ProjectError:
                if autosave:
                    continue  # linked: restore() trusts its own recovery file
                raise
            name = _member("designs", data, _ext(it["path"]) or "bin")
            files[name] = data
            it["embedded"] = name
            # A design from an opened project lives in the cache under its hash: keep its real name.
            if not (it.get("original_name") and _in_cache(it["path"])):
                it["original_name"] = Path(it["path"]).name
            del it["path"]
        if it.get("kind") == "text" and isinstance(it.get("font"), dict):
            _pack_font(it["font"], files)
    images = []
    for img in out.get("images") or []:
        try:
            data = _read(img["path"], "picture", as_added=True)  # what the canvas shows
        except (ProjectError, KeyError):
            # The UI still has the picture: use its copy.
            data = _data_url_bytes(img.get("data_url"))
            if data is None:
                if autosave:
                    continue
                raise ProjectError(f"Couldn't read the picture {img.get('name') or Path(str(img.get('path'))).name}: "
                                   "it may have been moved or deleted") from None
        name = _member("images", data, _ext(str(img.get("path") or img.get("name") or "")) or "png")
        files[name] = data
        img["embedded"] = name
        img["original_name"] = img.get("name") or Path(str(img.get("path"))).name
        img.pop("path", None)
        img.pop("data_url", None)
        images.append(img)
    if "images" in out:
        out["images"] = images
    return out, files


def _pack_font(font: dict[str, Any], files: dict[str, bytes]) -> None:
    """Embed the font file, so the lettering looks the same on a PC without the font. The file's
    path (which names the Windows account for fonts installed for one user) isn't saved."""
    path = font.pop("path", None)
    font.pop("embedded", None)
    if not path:
        return
    try:
        p = Path(str(path))
        if p.stat().st_size <= MAX_MEMBER_BYTES["fonts"]:
            data = p.read_bytes()
            name = _member("fonts", data, _ext(str(path)) or "ttf")
            files[name] = data
            font["embedded"] = name
            if not (font.get("original_name") and _in_cache(str(path))):
                font["original_name"] = p.name
    except OSError:
        pass  # not here: the family and style still find it where it's installed


def _replace(tmp: str, dest: str) -> None:
    """os.replace, retried for a moment: on Windows a virus scanner, a sync program or the
    Explorer preview often holds a just-written file for a fraction of a second."""
    for attempt in range(8):
        try:
            os.replace(tmp, dest)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.15 * (attempt + 1))


def _sweep_temps(folder: Path) -> None:
    """Delete temp files left by saves that never finished (the program was killed mid-save)."""
    try:
        now = time.time()
        for f in folder.glob(".ludd-*.tmp"):
            try:
                if now - f.stat().st_mtime > STALE_TEMP_S:
                    f.unlink()
            except OSError:
                continue
    except OSError:
        pass


def _write_zip(dest: Path, manifest: dict[str, Any], files: dict[str, bytes]) -> None:
    """Write atomically: a crash mid-save never leaves a half-written project."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    _sweep_temps(dest.parent)
    fd, tmp = tempfile.mkstemp(prefix=".ludd-", suffix=".tmp", dir=_long(dest.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            with zipfile.ZipFile(fh, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("project.json", json.dumps(manifest, indent=1))
                for name, data in files.items():
                    # Pictures and stitch files are already compressed or tiny; store them as they are.
                    z.writestr(zipfile.ZipInfo(name), data, compress_type=zipfile.ZIP_STORED)
            fh.flush()
            os.fsync(fh.fileno())
        _replace(tmp, _long(dest))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def save(path: str, project: dict[str, Any]) -> dict[str, Any]:
    dest = Path(path)
    if dest.suffix.lower() in OLD_EXTS:
        dest = dest.with_suffix(EXT)
    elif dest.suffix.lower() != EXT:
        # Add, never replace: "Bob v1.2" must not become (and overwrite) "Bob v1.ludd".
        dest = dest.with_name(dest.name + EXT)
    manifest, files = _pack(project)
    try:
        _write_zip(dest, manifest, files)
    except PermissionError as exc:
        raise ProjectError(f"Couldn't save {dest.name}: it's in use by another program, or the folder can't be "
                           "written to. Close other programs using it and try again, or save under another name.") from exc
    except OSError as exc:
        raise ProjectError(f"Couldn't save {dest.name}: {exc.strerror or exc}") from exc
    return {"path": str(dest), "designs": sum(1 for n in files if n.startswith("designs/")),
            "images": sum(1 for n in files if n.startswith("images/")),
            "fonts": sum(1 for n in files if n.startswith("fonts/"))}


def _safe_member(name: Any, folder: str) -> bool:
    """Only accept names we write ourselves: folder/<hex>.<ext>, no paths."""
    if not isinstance(name, str):
        return False
    parts = name.split("/")
    if len(parts) != 2 or parts[0] != folder:
        return False
    stem, _, ext = parts[1].partition(".")
    return len(stem) == 32 and all(c in "0123456789abcdef" for c in stem) and ext.isalnum() and len(ext) <= 8


def _no_constants(name: str) -> Any:
    raise ValueError(f"{name} isn't allowed")


def _read_member(z: zipfile.ZipFile, name: str, limit: int, label: str) -> bytes:
    """One member's bytes, refusing any bigger than `limit` before reading it."""
    try:
        info = z.getinfo(name)
    except KeyError:
        raise ProjectError(f"{label} is damaged: a file inside it is missing ({name})") from None
    if info.file_size > limit:
        raise ProjectError(f"{label} is damaged or not a LUDD project: {name} is too big")
    try:
        return z.read(info)
    except (zipfile.BadZipFile, zlib.error, EOFError, ValueError, NotImplementedError, RuntimeError) as exc:
        raise ProjectError(f"{label} is damaged and can't be opened") from exc
    except OSError as exc:
        raise ProjectError(f"Couldn't read {label}: {exc.strerror or exc}") from exc


def open_project(path: str, trust_paths: bool = False) -> dict[str, Any]:
    """Open a project. `trust_paths` (only for LUDD's own recovery file) keeps links to files an
    autosave couldn't embed; any other project can only use the files embedded in it."""
    p = Path(path)
    label = p.name
    try:
        z = zipfile.ZipFile(_long(p))
    except FileNotFoundError as exc:
        raise ProjectError(f"Couldn't find {label}: it may have been moved, renamed or deleted") from exc
    except PermissionError as exc:
        raise ProjectError(f"Couldn't open {label}: it's in use by another program, or not allowed") from exc
    except IsADirectoryError as exc:
        raise ProjectError(f"{label} is a folder, not a LUDD project") from exc
    except OSError as exc:
        raise ProjectError(f"Couldn't read {label}: {exc.strerror or exc}") from exc
    except (zipfile.BadZipFile, ValueError, EOFError) as exc:
        raise ProjectError(f"{label} isn't a LUDD project or is damaged") from exc
    with z:
        if "project.json" not in z.namelist():
            raise ProjectError(f"{label} isn't a LUDD project, or is damaged (its project data is missing)")
        raw = _read_member(z, "project.json", MAX_MEMBER_BYTES["project.json"], label)
        try:
            project = json.loads(raw.decode("utf-8-sig"), parse_constant=_no_constants)
        except (UnicodeDecodeError, ValueError, RecursionError) as exc:
            raise ProjectError(f"{label} is damaged: its project data can't be read") from exc
        if not isinstance(project, dict) or (project.get("format") != FORMAT and project.get("format") not in OLD_FORMATS):
            raise ProjectError(f"{label} isn't a LUDD project")
        version = project.get("version", 1)
        if not isinstance(version, int) or isinstance(version, bool):
            raise ProjectError(f"{label} is damaged: its version isn't a number")
        if version > VERSION:
            raise ProjectError(f"{label} was saved by a newer LUDD; update LUDD to open it")
        needs = project.get("features") or []
        if not isinstance(needs, list) or any(f not in KNOWN_FEATURES for f in needs):
            raise ProjectError(f"{label} uses things this LUDD doesn't have yet; update LUDD to open it")
        layout = project.get("layout")
        if layout is None:
            layout = project["layout"] = {"items": []}
        if not isinstance(layout, dict) or not isinstance(layout.get("items", []), list) or not isinstance(
                project.get("images", []), list):
            raise ProjectError(f"{label} is damaged: its layout can't be read")
        layout.setdefault("items", [])
        if any(not isinstance(it, dict) for it in layout["items"]) or any(
                not isinstance(im, dict) for im in project.get("images") or []):
            raise ProjectError(f"{label} is damaged: its layout can't be read")
        if len(project.get("images") or []) > MAX_PICTURES:
            raise ProjectError(f"{label} is damaged: it lists more than {MAX_PICTURES} pictures")
        if sum(zi.file_size for zi in z.infolist()) > MAX_PROJECT_BYTES:
            raise ProjectError(f"{label} is too big to open (over {MAX_PROJECT_BYTES // (1024 * 1024)} MB unpacked)")
        try:
            cache = _cache_dir()
        except OSError as exc:
            raise ProjectError(f"Couldn't open {label}: LUDD's data folder can't be written to "
                               f"({exc.strerror or exc}). Is the disk full?") from exc

        def extract(name: Any, folder: str) -> str:
            if not _safe_member(name, folder):
                raise ProjectError(f"{label} contains an unexpected file ({str(name)[:80]})")
            target = cache / name.split("/")[1]
            stem = target.name.partition(".")[0]
            try:
                if target.is_file() and _file_digest(target) == stem:
                    os.utime(target)  # in use: kept by the cache tidy-up
                    return str(target)
                data = _read_member(z, name, MAX_MEMBER_BYTES[folder], label)
                if _digest(data) != stem:
                    raise ProjectError(f"{label} is damaged: {name} doesn't match its contents")
                tmp = target.with_suffix(target.suffix + ".part")
                tmp.write_bytes(data)
                os.replace(tmp, target)
            except OSError as exc:
                raise ProjectError(f"Couldn't open {label}: LUDD's data folder can't be written to "
                                   f"({exc.strerror or exc}). Is the disk full?") from exc
            return str(target)

        for it in layout["items"]:
            embedded = it.pop("embedded", None)
            if embedded:
                it["path"] = extract(embedded, "designs")
                if it.get("original_name") and not it.get("name"):
                    it["name"] = str(it["original_name"])  # not the cache file's hash name
            elif not trust_paths:
                it.pop("path", None)  # a project names no file outside itself
            font = it.get("font")
            if it.get("kind") == "text" and isinstance(font, dict):
                f_embedded = font.pop("embedded", None)
                if f_embedded:
                    font["path"] = extract(f_embedded, "fonts")
                elif not trust_paths:
                    font.pop("path", None)  # found by family and style instead
        kept_items = [it for it in layout["items"] if not _damaged(it)]
        if len(kept_items) < len(layout["items"]):
            n = len(layout["items"]) - len(kept_items)
            project["notes"] = [f"{n} part{'s' if n != 1 else ''} of this project {'were' if n != 1 else 'was'} damaged "
                                "and left out. Save under a new name to keep the original file as it is."]
            layout["items"] = kept_items
        images = []
        urls: dict[str, str] = {}  # one data URL per picture file, however many entries share it
        shown = 0
        for img in project.get("images") or []:
            embedded = img.pop("embedded", None)
            if not embedded:
                if not (trust_paths and img.get("path")):
                    continue  # nothing to show
            else:
                img["path"] = extract(embedded, "images")
            try:
                if img["path"] not in urls:
                    urls[img["path"]] = load_image(img["path"])["data_url"]
                img["data_url"] = urls[img["path"]]
                shown += len(img["data_url"])
                if shown > MAX_PICTURES_SHOWN:
                    raise ProjectError(f"{label} has more picture data than LUDD can show at once; "
                                       "remove some pictures from it in the LUDD that saved it")
            except ProjectError:
                if embedded:
                    raise
                continue
            img["name"] = img.get("original_name") or img.get("name") or Path(img["path"]).name
            images.append(img)
        project["images"] = images
    project["path"] = str(p)
    return project


def _number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _damaged(it: dict[str, Any]) -> bool:
    """An item that would stop the whole design drawing ("Please report this"): an unknown kind
    (from a newer LUDD), a design file that isn't there, or settings of the wrong type (QA2 P4)."""
    kind = it.get("kind") or "file"
    if kind not in ITEM_KINDS or (kind == "file" and not isinstance(it.get("path"), str)):
        return True
    t = it.get("transform")
    if t is not None and (not isinstance(t, dict) or any(
            k in t and not _number(t[k]) for k in ("x", "y", "rotate", "scale_x", "scale_y"))):
        return True
    ops, threads = it.get("ops"), it.get("threads")
    if ops is not None and (not isinstance(ops, list) or not all(isinstance(o, dict) for o in ops)):
        return True
    if threads is not None and (not isinstance(threads, list) or not all(t is None or isinstance(t, dict) for t in threads)):
        return True
    return any(it.get(k) is not None and not isinstance(it[k], dict) for k in ("thread", "params", "geometry"))


def _file_digest(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:32]


# ---------------------------------------------------------------- autosave and recovery


def autosave(project: dict[str, Any]) -> dict[str, Any]:
    """Keep a recovery copy; written atomically, so a crash during autosave can't lose the last one."""
    manifest, files = _pack(project, autosave=True)
    manifest["recovered_from"] = project.get("path")
    _sweep_temps(_recovery_dir())
    _write_zip(_recovery_path(), manifest, files)
    return {"saved_at": manifest["saved_at"]}


def recovery() -> dict[str, Any] | None:
    """What an unclosed session left behind, if anything. A recovery copy that can't be read is
    moved aside (kept, never offered again)."""
    r = _recovery_path()
    if not r.exists():
        return None
    try:
        with zipfile.ZipFile(r) as z:
            m = json.loads(_read_member(z, "project.json", MAX_MEMBER_BYTES["project.json"], r.name),
                           parse_constant=_no_constants)
        items = (m.get("layout") or {}).get("items") or []
        info = {
            "saved_at": m.get("saved_at"),
            "title": str(m.get("title") or (Path(str(m["recovered_from"])).stem if m.get("recovered_from") else "")),
            "items": len(items),
            "images": len(m.get("images") or []),
            "path": m.get("recovered_from"),
        }
    except (zipfile.BadZipFile, ProjectError, ValueError, RecursionError, AttributeError, TypeError, EOFError):
        _set_aside(r)
        return None
    except OSError:
        return None  # locked for a moment, perhaps: offered next time
    return info


def _set_aside(r: Path) -> Path | None:
    """Keep a recovery copy that can't be used, out of the way of new autosaves."""
    dest = r.with_name(f"unrecovered-{time.strftime('%Y%m%d-%H%M%S')}{EXT}")
    try:
        os.replace(r, dest)
        return dest
    except OSError:
        return None


def restore() -> dict[str, Any]:
    r = _recovery_path()
    if not r.exists():
        raise ProjectError("There's nothing to recover")
    project = open_project(str(r), trust_paths=True)
    # Saving should go back to the project it came from (or ask for a name), not the recovery file.
    project["path"] = project.pop("recovered_from", None)
    return project


def discard_recovery(keep: bool = False) -> None:
    """Delete the recovery copy, or with `keep` (it couldn't be recovered) move it aside."""
    r = _recovery_path()
    if keep and r.exists():
        _set_aside(r)
    else:
        r.unlink(missing_ok=True)
