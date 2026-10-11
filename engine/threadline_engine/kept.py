"""Private copies of the pictures and stitch files a user adds.

A file is copied the moment it's added, so the design keeps working (and can still be saved, with
the file embedded) if the original is moved, renamed, deleted or on a USB stick that's unplugged
before the first save.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .storage import data_dir

_copies: dict[str, str] = {}


def _dir() -> Path:
    d = data_dir() / "project-files"
    d.mkdir(parents=True, exist_ok=True)
    return d


def keep(path: str, data: bytes) -> None:
    """Remember a private copy of `data`, the current contents of `path`."""
    ext = Path(path).suffix.lower().lstrip(".") or "bin"
    target = _dir() / f"{hashlib.sha256(data).hexdigest()[:32]}.{ext}"
    if not target.exists():
        tmp = target.with_suffix(target.suffix + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, target)
    _copies[str(path)] = str(target)


def readable(path: str) -> str:
    """The original if it's still there, otherwise the private copy (if one was kept)."""
    if Path(path).is_file():
        return path
    return _copies.get(str(path), path)
