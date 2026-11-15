"""Tidying up after the packaged engine.

The installed engine is a PyInstaller one-file program: each run unpacks itself (about 180 MB)
into a `_MEI…` folder in the temp folder and deletes it when it exits normally. A run that was
killed (a crash, a forced quit, a power cut) leaves its folder behind. At startup the engine
deletes folders left by earlier runs of LUDD's engine: only folders holding our marker file, and
only ones no running engine is using.
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
from pathlib import Path

# Bundled into every packaged engine (scripts/build_engine.py) so its folder can be recognised.
MARKER = "ludd-engine-bundle.txt"


def stale_bundles(own: Path) -> list[Path]:
    """Folders next to ours, left by earlier runs of this engine."""
    return [d for d in own.parent.glob("_MEI*") if d != own and d.is_dir() and (d / MARKER).is_file()]


def remove_if_unused(folder: Path) -> bool:
    """Delete a left-behind folder if no running program is using it. On Windows a folder whose
    files are open can't be renamed, so it's renamed first: if that fails, it's in use and stays."""
    gone = folder.with_name(folder.name + "-old")
    try:
        os.rename(folder, gone)
    except OSError:
        return False
    shutil.rmtree(gone, ignore_errors=True)
    return True


def sweep(own: Path | None = None) -> int:
    """Delete stale engine folders. Windows only: elsewhere a folder in use can be renamed, so
    there's no safe test (and macOS and Linux clear their temp folders themselves)."""
    if own is None:
        mei = getattr(sys, "_MEIPASS", None)
        if not getattr(sys, "frozen", False) or not mei:
            return 0
        own = Path(mei)
    if sys.platform != "win32":
        return 0
    return sum(remove_if_unused(d) for d in stale_bundles(own))


def sweep_in_background() -> None:
    threading.Thread(target=sweep, daemon=True, name="sweep-temp").start()


__all__ = ["MARKER", "remove_if_unused", "stale_bundles", "sweep", "sweep_in_background"]
