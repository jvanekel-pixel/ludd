"""Private copies of the pictures and stitch files a user adds.

A file is copied the moment it's added, so the design keeps working (and can still be saved, with
the file embedded) if the original is moved, renamed, deleted or on a USB stick that's unplugged
before the first save.
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from .storage import data_dir, read_json, write_json

# Which original each private copy came from. Also kept in project-files/index.json, so a new
# engine (after a crash or the Restart engine button) still finds the copy of a file that's gone
# (QA2 P2: only this dict held it, and a restart forgot every copy).
_copies: dict[str, str] = {}
_loaded = False
INDEX = "index.json"
MAX_INDEX = 2000  # most recent files remembered


def _load() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        saved = read_json(data_dir() / "project-files" / INDEX)
    except (OSError, ValueError):
        return
    if isinstance(saved, dict):
        for k, v in saved.items():
            # Only names of copies in this folder: the index can't point anywhere else.
            if isinstance(k, str) and isinstance(v, str) and Path(v).name == v and k not in _copies:
                _copies[k] = v


def _dir() -> Path:
    d = data_dir() / "project-files"
    d.mkdir(parents=True, exist_ok=True)
    return d


# Copies not used for this long are deleted at startup (a saved project holds its own copies;
# these only matter for work that was never saved).
KEEP_DAYS = 90


def keep(path: str, data: bytes) -> None:
    """Remember a private copy of `data`, the current contents of `path`. Best effort: a full or
    read-only data folder never stops a file being added."""
    ext = Path(path).suffix.lower().lstrip(".") or "bin"
    try:
        target = _dir() / f"{hashlib.sha256(data).hexdigest()[:32]}.{ext}"
        if target.exists():
            os.utime(target)  # in use again: kept by prune()
        else:
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.write_bytes(data)
            os.replace(tmp, target)
    except OSError:
        return
    _load()
    _copies.pop(str(path), None)
    _copies[str(path)] = target.name  # newest last
    while len(_copies) > MAX_INDEX:
        _copies.pop(next(iter(_copies)))
    try:
        write_json(_dir() / INDEX, _copies)
    except OSError:
        pass  # best effort, like the copy itself


def prune(days: float = KEEP_DAYS) -> int:
    """Delete private copies (and half-written ones) not used for `days` days. Run at startup,
    before anything is opened. Returns how many files went."""
    d = data_dir() / "project-files"
    if not d.is_dir():
        return 0
    cutoff = time.time() - days * 86400
    gone = 0
    for f in d.iterdir():
        try:
            mtime = f.stat().st_mtime
            if f.is_file() and (mtime < cutoff or (f.suffix == ".part" and mtime < time.time() - 3600)):
                f.unlink()
                gone += 1
        except OSError:
            continue
    return gone


def has_edits(item: dict) -> bool:
    """A placed stitch file with edits tied to its colour and stitch numbers: recolours, deleted
    colours or stitches, inserted stops or trims, moved stitches. Such an item sews from the copy
    taken when the file was added (as_added), so a file re-saved elsewhere later can't put those
    edits on other stitches (QA2 P3). "Trim jumps" doesn't name any stitch, so it doesn't count."""
    threads = item.get("threads")
    ops = item.get("ops")
    return bool((isinstance(threads, list) and any(threads))
                or (isinstance(ops, list) and any(not isinstance(o, dict) or o.get("op") != "jumps_to_trims" for o in ops)))


def pinned(items: list) -> set[str]:
    """Paths of placed stitch files that sew from their private copy: any item on that file has
    edits (two items on one file always sew the same bytes)."""
    return {it["path"] for it in items if isinstance(it, dict) and isinstance(it.get("path"), str) and has_edits(it)}


def readable(path: str, as_added: bool = False) -> str:
    """The original if it's still there, otherwise the private copy (if one was kept).

    With `as_added` (pictures, and stitch files with edits: has_edits), the private copy comes first: it holds the bytes the canvas shows,
    so a picture edited elsewhere after it was added doesn't get traced or saved instead of what's
    on screen. Adding the picture again (project.load_image) reads the original afresh."""
    _load()
    name = _copies.get(str(path))
    copy = str(data_dir() / "project-files" / name) if name else None
    if copy and not Path(copy).is_file():
        copy = None  # tidied away
    if as_added and copy:
        return copy
    if Path(path).is_file():
        return path
    return copy or path
