"""RPC methods. Core: ping, engine info and shutdown, the file formats."""

from __future__ import annotations

import platform
import sys

from .. import __version__, design
from .registry import dispatcher


@dispatcher.method("ping")
def ping() -> str:
    return "pong"


@dispatcher.method("engine.info")
def engine_info() -> dict[str, str]:
    return {
        "version": __version__,
        "python": platform.python_version(),
        "platform": sys.platform,
    }


@dispatcher.method("engine.shutdown")
def engine_shutdown() -> bool:
    """Stop after answering. The app asks this when it quits, so the packaged engine exits by itself
    and deletes its unpacked files (being killed leaves them in the temp folder)."""
    dispatcher.stopping = True
    return True


@dispatcher.method("formats.list")
def formats_list() -> dict:
    return design.formats()
