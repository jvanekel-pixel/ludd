"""Artwork import: an SVG, DXF or PDF drawing as the shapes LUDD would add for it.

Nothing is added to a design here: preview() answers with the shapes, and the app adds the ones
you accept. Artwork files are untrusted input. Only the one chosen file is read, once; nothing in
it is fetched, run or followed (links to other files and websites, XML entities, pictures and
cross-references are all left alone); and every size is capped, with a refusal in plain words.

The limits are rules about the file (counts and sizes), checked before any step that can't be
stopped partway; the time limit backs them up. What no rule can bound (reading a PDF, outlining a
big wide stroke) runs in a one-use child process that is stopped at the limit (child.py).

The readers (svg.py, dxf.py, pdf.py) turn a file into painted paths in millimeters at the file's
real size (model.py); convert.py turns those into fills, lines and satins.
"""

from __future__ import annotations

import os
import stat
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..rpc import REPLACED

MB = 1024 * 1024
MAX_BYTES = {"svg": 20 * MB, "dxf": 50 * MB, "pdf": 50 * MB}
MAX_SHAPES = 2000
MANY_SHAPES = 200
MAX_SIZE_MM = 1000.0  # the engine refuses bigger shapes (digitize.stitches.MAX_SHAPE_MM)
MAX_LENGTH_MM = 400_000.0  # of all the outlines together, at the size they come in
MAX_STITCHES = 400_000  # about what the whole artwork may take at LUDD's standard settings
MAX_COORDINATE = 1e9  # anything further out than this (in mm) isn't a drawing
TIME_LIMIT_S = 60.0  # well within the 120 s the app waits (feat/importArt.ts)
STROKE_MODES = ("auto", "lines", "satins")
TOO_SLOW = ("This artwork takes too long to read. Simplify it in your drawing program (fewer shapes and points), "
            "save it again and import that.")


class ArtError(Exception):
    """A plain-words refusal, shown to the user as it is."""

    rpc_code = -32000  # rpc.APP_ERROR


class Deadline:
    """Checked as the work goes on, so that a file that is slow to read is given up on, and a newer
    preview stops an older one (`replaced` is set). `since` (time.monotonic()): when the request
    arrived, so time spent waiting for the older preview to stop counts too."""

    def __init__(self, seconds: float | None = None, replaced: threading.Event | None = None,
                 since: float | None = None) -> None:
        start = time.monotonic() if since is None else since
        self.until = start + (TIME_LIMIT_S if seconds is None else seconds)
        self.replaced = replaced

    def left(self) -> float:
        return max(0.0, self.until - time.monotonic())

    def check(self) -> None:
        if self.replaced is not None and self.replaced.is_set():
            raise ArtError(REPLACED)
        if time.monotonic() > self.until:
            raise ArtError(TOO_SLOW)


@dataclass(frozen=True)
class Options:
    width_mm: float | None = None  # None: the file's real size
    strokes: str = "auto"  # auto | lines | satins
    spacing_mm: float = 3.0  # how far apart fitted points are, at most
    closed_as_fills: bool = False  # DXF: closed outlines come in as fills
    page: int = 0  # PDF: which page, from 0
    keep_background: bool = False  # the flagged background counts toward the size and middle

    @classmethod
    def from_dict(cls, d: Any) -> "Options":
        if d is None:
            d = {}
        if not isinstance(d, dict):
            raise ArtError("The import options must be a set of named settings")
        width = d.get("width_mm")
        if width is not None:
            width = _number(width, "The width")
            if not 1 <= width <= MAX_SIZE_MM:
                raise ArtError(f"The width must be between 1 and {MAX_SIZE_MM:.0f} mm")
        strokes = d.get("strokes") or "auto"
        if strokes not in STROKE_MODES:
            raise ArtError("Lines can come in as automatic, running stitch or satin")
        spacing = _number(d.get("spacing_mm", 3.0) if d.get("spacing_mm") is not None else 3.0, "The point spacing")
        if not 0.5 <= spacing <= 20:
            raise ArtError("The point spacing must be between 0.5 and 20 mm")
        page = d.get("page") or 0
        if isinstance(page, bool) or not isinstance(page, int) or page < 0:
            raise ArtError("The page must be a whole number, from 0")
        return cls(width, strokes, spacing, bool(d.get("closed_as_fills")), page, bool(d.get("keep_background")))


def _number(v: Any, what: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not -1e18 < v < 1e18:
        raise ArtError(f"{what} must be a number")
    return float(v)


def kind_of(path: str) -> str:
    """"svg", "dxf" or "pdf", from the file's name."""
    ext = Path(path).suffix.lower().lstrip(".")
    if ext == "svgz":
        raise ArtError("LUDD doesn't read compressed .svgz files: save the drawing as a plain .svg and import that.")
    if ext not in MAX_BYTES:
        raise ArtError("LUDD imports SVG, DXF and PDF artwork. To open a stitch file, use Open.")
    return ext


def read_once(path: str, kind: str) -> bytes:
    """The chosen file, whole, and no more than its size limit."""
    limit = MAX_BYTES[kind]
    too_big = ArtError(f"This {kind.upper()} file is bigger than {limit // MB} MB, more than LUDD imports. "
                       "Simplify the drawing in your drawing program (fewer shapes and points) and save it again.")
    try:
        info = os.stat(path)
        if not stat.S_ISREG(info.st_mode):
            raise ArtError("That isn't a file LUDD can import.")
        if info.st_size > limit:
            raise too_big
        with open(path, "rb") as fh:
            data = fh.read(limit + 1)
    except FileNotFoundError:
        raise ArtError("That file isn't there any more.") from None
    except OSError as exc:
        raise ArtError(f"Couldn't read the file: {exc.strerror or exc}") from None
    if len(data) > limit:
        raise too_big
    if not data.strip():
        raise ArtError("That file is empty.")
    return data


def preview(path: Any, options: Any = None, deadline: Deadline | None = None) -> dict[str, Any]:
    """{size_mm, scale_note, shapes, skipped, warnings, pages} for the artwork at `path`.
    `deadline` (TIME_LIMIT_S from now if not given) is where the work is given up on."""
    if not isinstance(path, str) or not path:
        raise ArtError("Choose a file to import.")
    kind = kind_of(path)
    opts = Options.from_dict(options)
    data = read_once(path, kind)
    deadline = deadline or Deadline()
    deadline.check()
    from . import convert

    try:
        if kind == "svg":
            from . import svg

            drawing = svg.read(data, deadline)
        elif kind == "dxf":
            from . import dxf

            drawing = dxf.read(data, opts, deadline)
        else:
            from . import pdf

            drawing = pdf.read(data, opts, deadline)
    except ArtError:
        raise
    except (RecursionError, MemoryError):
        raise ArtError("This file is too complex for LUDD to read. Simplify it in your drawing program.") from None
    except Exception as exc:  # noqa: BLE001 - whatever an untrusted file does to a parser is a refusal
        print(f"artwork import: reading a {kind} file failed:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise ArtError(f"LUDD couldn't read this {kind.upper()} file. It may be damaged, or use something LUDD "
                       "doesn't understand. Save it again from your drawing program and try that.") from exc
    from shapely.errors import GEOSException

    try:
        return convert.convert(drawing, opts, deadline)
    except (GEOSException, RecursionError, MemoryError):  # shapes too tangled to work out
        traceback.print_exc(file=sys.stderr)
        raise ArtError("LUDD couldn't work out the shapes in this drawing. Simplify it in your drawing program "
                       "(merge or tidy shapes that cross themselves) and save it again.") from None


__all__ = ["ArtError", "Deadline", "Options", "preview"]
