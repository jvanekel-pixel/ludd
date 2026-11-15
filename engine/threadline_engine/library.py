"""Design browser: the embroidery designs in a folder (and its subfolders), each with a small
picture, its size, stitch count and colors, so you can find one without opening each.

Thumbnails are drawn from the stitches (each in its thread color) and kept in memory, so
browsing the same folder again is instant.
"""

from __future__ import annotations

import base64
import io
import os
import time
from pathlib import Path
from typing import Any

import pyembroidery as pe
from PIL import Image, ImageDraw

from . import design

THUMB_PX = 160
MAX_FILES = 600
M = pe.COMMAND_MASK


class LibraryError(Exception):
    rpc_code = -32000


_thumbs: dict[str, tuple[float, dict[str, Any]]] = {}


def _hex_rgb(color: str) -> tuple[int, int, int]:
    c = (color or "#000000").lstrip("#")
    try:
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except (ValueError, IndexError):
        return (0, 0, 0)


def thumbnail(pattern: pe.EmbPattern, size: int = THUMB_PX) -> str:
    """A PNG data URL of the design's stitches, in thread colors, on white."""
    pts = [(x, y) for x, y, c in pattern.stitches if c & M == pe.STITCH]
    img = Image.new("RGB", (size, size), "white")
    if not pts:
        return _png(img)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    pad = 6
    scale = (size - 2 * pad) / max(x1 - x0, y1 - y0, 1)
    ox = (size - (x1 - x0) * scale) / 2
    oy = (size - (y1 - y0) * scale) / 2
    draw = ImageDraw.Draw(img)
    threads = [_hex_rgb(design._thread(t)["color"]) for t in pattern.threadlist] or [(0, 0, 0)]
    block = 0
    last = None
    for x, y, c in pattern.stitches:
        k = c & M
        if k in (pe.COLOR_CHANGE, pe.NEEDLE_SET):
            block += 1
            last = None
            continue
        if k != pe.STITCH:
            last = None
            continue
        p = (ox + (x - x0) * scale, oy + (y - y0) * scale)
        if last:
            draw.line([last, p], fill=threads[min(block, len(threads) - 1)], width=1)
        last = p
    return _png(img)


def _png(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def entry(path: Path) -> dict[str, Any]:
    key = str(path)
    mtime = path.stat().st_mtime
    hit = _thumbs.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        pattern = design.load(path)
        s = design.summarize(pattern)
        info = s["info"]
        e = {"path": key, "name": path.name, "format": path.suffix.lstrip(".").upper(), "ok": True,
             "width_mm": info["width_mm"], "height_mm": info["height_mm"], "stitches": info["stitches"],
             "colors": info["colors"], "thumb": thumbnail(pattern)}
    except Exception as exc:  # a damaged or unsupported file: list it, say why
        e = {"path": key, "name": path.name, "format": path.suffix.lstrip(".").upper(), "ok": False, "error": str(exc)[:200]}
    if len(_thumbs) > 3000:
        _thumbs.pop(next(iter(_thumbs)))
    _thumbs[key] = (mtime, e)
    return e


MAX_FOLDERS = 5000


def _walk(root: Path, recursive: bool):
    """The files in `root` (and its subfolders), each folder once: links and junctions that lead
    back up the tree (or anywhere else) aren't followed."""
    seen: set[tuple[int, int]] = set()
    todo = [root]
    while todo and len(seen) < MAX_FOLDERS:
        d = todo.pop()
        try:
            st = d.stat()
            key = (st.st_dev, st.st_ino)
            if key in seen:
                continue
            seen.add(key)
            with os.scandir(d) as it:
                entries = list(it)
        except OSError:
            continue
        for e in entries:
            try:
                if e.is_symlink() or (hasattr(e, "is_junction") and e.is_junction()):
                    continue
                if e.is_dir(follow_symlinks=False):
                    if recursive:
                        todo.append(Path(e.path))
                elif e.is_file(follow_symlinks=False):
                    yield Path(e.path)
            except OSError:
                continue


def scan(folder: str, recursive: bool = True, query: str = "") -> dict[str, Any]:
    """Designs in `folder` LUDD can open, newest first (at most MAX_FILES), optionally only those
    whose name contains `query`. Returns {"folder", "designs": [...], "more": bool, "ms"}."""
    t0 = time.perf_counter()
    root = Path(folder)
    if not root.is_dir():
        raise LibraryError(f"Folder not found: {folder}")
    readable = design._readable()
    files = []
    q = query.strip().lower()
    for f in _walk(root, recursive):
        try:
            if f.suffix.lower().lstrip(".") in readable and (not q or q in f.name.lower()):
                files.append((f.stat().st_mtime, f))
        except OSError:
            continue
    files.sort(key=lambda t: -t[0])
    more = len(files) > MAX_FILES
    designs = [entry(f) for _, f in files[:MAX_FILES]]
    return {"folder": str(root), "designs": designs, "more": more, "ms": round((time.perf_counter() - t0) * 1000, 1)}
