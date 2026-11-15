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

from .storage import data_dir

_copies: dict[str, str] = {}


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
    _copies[str(path)] = str(target)


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


def readable(path: str, as_added: bool = False) -> str:
    """The original if it's still there, otherwise the private copy (if one was kept).

    With `as_added` (pictures), the private copy comes first: it holds the bytes the canvas shows,
    so a picture edited elsewhere after it was added doesn't get traced or saved instead of what's
    on screen. Adding the picture again (project.load_image) reads the original afresh."""
    copy = _copies.get(str(path))
    if as_added and copy and Path(copy).is_file():
        return copy
    if Path(path).is_file():
        return path
    return copy or path
