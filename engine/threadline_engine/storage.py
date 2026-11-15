"""Where the engine keeps user data (thread charts, My threads, machine profiles, fonts, recovery)."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


APP_DIR = "Ludd"
OLD_APP_DIR = "Threadline"  # the app's working name before Oct 11, 2026
# Left in the new folder once the old folder's data has been brought over.
MIGRATED_MARK = ".moved-from-threadline"

_checked: set[Path] = set()


def data_dir() -> Path:
    """Per-user data folder. THREADLINE_DATA_DIR overrides it (used by tests)."""
    override = os.environ.get("THREADLINE_DATA_DIR")
    if override:
        return Path(override)
    base = _base_dir()
    new, old = base / APP_DIR, base / OLD_APP_DIR
    if new not in _checked:
        _checked.add(new)
        _carry_over(old, new)
    return new


def _carry_over(old: Path, new: Path) -> None:
    """Bring the data from the old name over once (thread charts, My threads, machines, fonts):
    move the folder if it's alone, otherwise copy whatever the new folder lacks (never replacing)."""
    if not old.is_dir() or (new / MIGRATED_MARK).exists():
        return
    if not new.exists():
        try:
            old.rename(new)
            return
        except OSError:
            pass  # in use: copy instead
    try:
        for src in old.rglob("*"):
            dest = new / src.relative_to(old)
            if src.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            elif not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
        (new / MIGRATED_MARK).write_text(f"Data from {old} was copied here.\n", encoding="utf-8")
    except OSError as exc:
        print(f"couldn't bring over data from {old}: {exc}", file=sys.stderr, flush=True)


def _base_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base


def write_json(path: Path, obj: Any) -> None:
    """Write a user file atomically (temp file, then replace): a crash or a full disk mid-write
    leaves the old file, never half of one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_json(path: Path) -> Any:
    """A user JSON file (a byte-order mark, as Notepad writes, is fine). Raises ValueError for a
    file that isn't JSON, OSError if it can't be read."""
    return json.loads(path.read_bytes().decode("utf-8-sig"))
