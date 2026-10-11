"""LUDD project files (.ludd): everything needed to reopen a design exactly as it was.

A .ludd is a zip (projects from before the rename, .thl, open the same way):

    project.json        the layout (drawn objects and placed designs), reference images and settings
    designs/<sha>.<ext> a copy of every stitch file placed in the layout
    images/<sha>.<ext>  a copy of every reference image

Files are embedded, never linked: moving, renaming or deleting the originals, rebooting, or
opening the project on another PC can't lose them. Opened projects extract their files into a
content-addressed cache, so paths inside the app stay stable.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

from . import kept
from .storage import data_dir

FORMAT = "ludd-project"
OLD_FORMATS = {"threadline-project"}
EXT = ".ludd"
OLD_EXTS = {".thl"}
VERSION = 1
IMAGE_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "webp": "image/webp",
}
MAX_IMAGE_BYTES = 40 * 1024 * 1024


class ProjectError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


def _cache_dir() -> Path:
    d = data_dir() / "project-files"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _recovery_path() -> Path:
    d = data_dir() / "recovery"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"autosave{EXT}"


def _ext(path: str) -> str:
    return Path(path).suffix.lower().lstrip(".")


def _read(path: str, what: str) -> bytes:
    try:
        return Path(kept.readable(path)).read_bytes()
    except OSError as exc:
        raise ProjectError(f"Couldn't read the {what} {Path(path).name}: it may have been moved or deleted") from exc


def _member(folder: str, data: bytes, ext: str) -> str:
    return f"{folder}/{hashlib.sha256(data).hexdigest()[:32]}.{ext}"


# ---------------------------------------------------------------- images


def load_image(path: str) -> dict[str, Any]:
    """A picture for tracing: its bytes as a data URL for display, plus where it lives."""
    ext = _ext(path)
    if ext not in IMAGE_TYPES:
        raise ProjectError(f"Can't use .{ext} pictures. Use PNG, JPG, GIF, BMP or WebP.")
    data = _read(path, "picture")
    if len(data) > MAX_IMAGE_BYTES:
        raise ProjectError(f"{Path(path).name} is over {MAX_IMAGE_BYTES // (1024 * 1024)} MB; use a smaller copy")
    kept.keep(path, data)
    return {
        "name": Path(path).name,
        "path": path,
        "data_url": f"data:{IMAGE_TYPES[ext]};base64,{base64.b64encode(data).decode('ascii')}",
        "bytes": len(data),
    }


# ---------------------------------------------------------------- save / open


def _pack(project: dict[str, Any]) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Project JSON with paths replaced by embedded member names, plus the member bytes."""
    files: dict[str, bytes] = {}
    out = json.loads(json.dumps(project))  # deep copy, JSON-safe
    out["format"], out["version"] = FORMAT, VERSION
    out["saved_at"] = time.time()
    for it in (out.get("layout") or {}).get("items") or []:
        if it.get("path"):
            data = _read(it["path"], "design")
            name = _member("designs", data, _ext(it["path"]) or "bin")
            files[name] = data
            it["embedded"] = name
            it["original_name"] = Path(it["path"]).name
            del it["path"]
    for img in out.get("images") or []:
        data = _read(img["path"], "picture")
        name = _member("images", data, _ext(img["path"]) or "bin")
        files[name] = data
        img["embedded"] = name
        img["original_name"] = img.get("name") or Path(img["path"]).name
        del img["path"]
        img.pop("data_url", None)
    return out, files


def _write_zip(dest: Path, manifest: dict[str, Any], files: dict[str, bytes]) -> None:
    """Write atomically: a crash mid-save never leaves a half-written project."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".ludd-", suffix=".tmp", dir=dest.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("project.json", json.dumps(manifest, indent=1))
            for name, data in files.items():
                # Pictures and stitch files are already compressed or tiny; store them as they are.
                z.writestr(zipfile.ZipInfo(name), data, compress_type=zipfile.ZIP_STORED)
        os.replace(tmp, dest)
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
    except OSError as exc:
        raise ProjectError(f"Couldn't save {dest.name}: {exc.strerror or exc}") from exc
    return {"path": str(dest), "designs": sum(1 for n in files if n.startswith("designs/")),
            "images": sum(1 for n in files if n.startswith("images/"))}


def _safe_member(name: str, folder: str) -> bool:
    """Only accept names we write ourselves: folder/<hex>.<ext>, no paths."""
    parts = name.split("/")
    if len(parts) != 2 or parts[0] != folder:
        return False
    stem, _, ext = parts[1].partition(".")
    return len(stem) == 32 and all(c in "0123456789abcdef" for c in stem) and ext.isalnum() and len(ext) <= 5


def open_project(path: str) -> dict[str, Any]:
    p = Path(path)
    try:
        z = zipfile.ZipFile(p)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ProjectError(f"{p.name} isn't a LUDD project or is damaged") from exc
    with z:
        try:
            project = json.loads(z.read("project.json"))
        except (KeyError, json.JSONDecodeError) as exc:
            raise ProjectError(f"{p.name} is missing its project data") from exc
        if project.get("format") != FORMAT and project.get("format") not in OLD_FORMATS:
            raise ProjectError(f"{p.name} isn't a LUDD project")
        if int(project.get("version", 0)) > VERSION:
            raise ProjectError(f"{p.name} was saved by a newer LUDD; update to open it")
        cache = _cache_dir()

        def extract(name: str, folder: str) -> str:
            if not _safe_member(name, folder):
                raise ProjectError(f"{p.name} contains an unexpected file ({name})")
            target = cache / name.split("/")[1]
            if not target.exists():
                data = z.read(name)
                tmp = target.with_suffix(target.suffix + ".part")
                tmp.write_bytes(data)
                os.replace(tmp, target)
            return str(target)

        for it in (project.get("layout") or {}).get("items") or []:
            if it.get("embedded"):
                it["path"] = extract(it.pop("embedded"), "designs")
        for img in project.get("images") or []:
            img["path"] = extract(img.pop("embedded"), "images")
            img["data_url"] = load_image(img["path"])["data_url"]
            img["name"] = img.get("original_name") or img.get("name") or Path(img["path"]).name
    project["path"] = str(p)
    return project


# ---------------------------------------------------------------- autosave and recovery


def autosave(project: dict[str, Any]) -> dict[str, Any]:
    """Keep a recovery copy; written atomically, so a crash during autosave can't lose the last one."""
    manifest, files = _pack(project)
    manifest["recovered_from"] = project.get("path")
    _write_zip(_recovery_path(), manifest, files)
    return {"saved_at": manifest["saved_at"]}


def recovery() -> dict[str, Any] | None:
    """What an unclosed session left behind, if anything."""
    r = _recovery_path()
    if not r.exists():
        return None
    try:
        with zipfile.ZipFile(r) as z:
            m = json.loads(z.read("project.json"))
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError):
        return None
    items = (m.get("layout") or {}).get("items") or []
    return {
        "saved_at": m.get("saved_at"),
        "title": m.get("title") or (Path(m["recovered_from"]).stem if m.get("recovered_from") else ""),
        "items": len(items),
        "images": len(m.get("images") or []),
        "path": m.get("recovered_from"),
    }


def restore() -> dict[str, Any]:
    r = _recovery_path()
    if not r.exists():
        raise ProjectError("There's nothing to recover")
    project = open_project(str(r))
    # Saving should go back to the project it came from (or ask for a name), not the recovery file.
    project["path"] = project.pop("recovered_from", None)
    return project


def discard_recovery() -> None:
    _recovery_path().unlink(missing_ok=True)
