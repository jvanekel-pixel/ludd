"""Where the engine keeps user data (thread charts, My threads, machine profiles, fonts, recovery)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


APP_DIR = "Ludd"
OLD_APP_DIR = "Threadline"  # the app's working name before Oct 11, 2026


def data_dir() -> Path:
    """Per-user data folder. THREADLINE_DATA_DIR overrides it (used by tests)."""
    override = os.environ.get("THREADLINE_DATA_DIR")
    if override:
        return Path(override)
    base = _base_dir()
    new, old = base / APP_DIR, base / OLD_APP_DIR
    # Carry over data from the old name once (thread charts, My threads, recovery).
    if not new.exists() and old.is_dir():
        try:
            old.rename(new)
        except OSError:
            return old
    return new


def _base_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base
