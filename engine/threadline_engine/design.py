"""Open, summarize, export and batch-convert stitch files via pyembroidery.

Imported stitch files are not objects: they are flat stitch lists, shown and
converted as-is. Units sent to the UI are millimetres (pyembroidery uses 0.1 mm).
"""

from __future__ import annotations

import os
import unicodedata
import uuid
from pathlib import Path
from typing import Any

import pyembroidery as pe

from .prepare import PES_MAX_STEPS, Options, prepare, write_settings

# Stitch record kinds sent to the UI. Keep in sync with apps/desktop/src/design/types.ts.
STITCH, JUMP, TRIM, STOP, COLOR_CHANGE, END = range(6)

_KIND = {
    pe.STITCH: STITCH,
    pe.JUMP: JUMP,
    pe.TRIM: TRIM,
    pe.STOP: STOP,
    pe.COLOR_CHANGE: COLOR_CHANGE,
    pe.NEEDLE_SET: COLOR_CHANGE,
    pe.END: END,
}

# Per-format settings, chosen by round-tripping real designs (see tests/test_golden.py).
WRITE_SETTINGS: dict[str, dict[str, Any]] = {
    # v6 keeps thread names and brands; Brother machines read the PEC block present in every version.
    "pes": {"version": 6},
    # JEF has no trim command. Without this, trims become plain jumps and are lost on short moves.
    "jef": {"trims": True},
}
READ_SETTINGS: dict[str, dict[str, Any]] = {
    "jef": {"trims": True},
}

# Listed by pyembroidery as embroidery formats but not useful to send to a machine.
HIDDEN_FORMATS = {"gcode"}

FALLBACK_THREAD = {"color": "#808080", "name": "", "catalog": "", "brand": ""}


class DesignError(Exception):
    """A user-facing problem with a file (unreadable, unsupported, ...)."""

    rpc_code = -32000  # rpc.APP_ERROR


def _ext(path: str | Path) -> str:
    return Path(path).suffix.lower().lstrip(".")


def formats() -> dict[str, list[dict[str, str]]]:
    """Extensions pyembroidery can read and write, embroidery formats only."""
    read, write = [], []
    for f in pe.supported_formats():
        if f.get("category") != "embroidery" or f["extension"] in HIDDEN_FORMATS:
            continue
        entry = {"ext": f["extension"], "description": f["description"]}
        if "reader" in f:
            read.append(entry)
        if "writer" in f:
            write.append(entry)
    key = lambda e: e["ext"]  # noqa: E731
    return {"read": sorted(read, key=key), "write": sorted(write, key=key)}


def _readable() -> set[str]:
    return {f["ext"] for f in formats()["read"]}


def _writable() -> set[str]:
    return {f["ext"] for f in formats()["write"]}


def load(path: str | Path) -> pe.EmbPattern:
    p = Path(path)
    if not p.is_file():
        raise DesignError(f"File not found: {p}")
    ext = _ext(p)
    if ext not in _readable():
        raise DesignError(f"Can't read .{ext} files" + (" (Embrilliance working files aren't supported)" if ext == "be" else ""))
    try:
        pattern = pe.read(str(p), READ_SETTINGS.get(ext))
    except Exception as exc:  # pyembroidery raises assorted errors on corrupt files
        raise DesignError(f"Couldn't read {p.name}: {exc}") from exc
    if pattern is None or not pattern.stitches:
        raise DesignError(f"Couldn't read {p.name}: no stitches found")
    return pattern


def _thread(t: pe.EmbThread | None) -> dict[str, str]:
    if t is None:
        return dict(FALLBACK_THREAD)
    return {
        "color": t.hex_color(),
        "name": t.description or "",
        "catalog": t.catalog_number or "",
        "brand": t.brand or "",
    }


def summarize(pattern: pe.EmbPattern) -> dict[str, Any]:
    """Records, color blocks, threads and counts for display."""
    xs: list[float] = []
    ys: list[float] = []
    kinds: list[int] = []
    counts = {"stitches": 0, "jumps": 0, "trims": 0, "stops": 0, "color_changes": 0}
    blocks: list[dict[str, int]] = []
    block_start, thread_idx = 0, 0

    for x, y, cmd in pattern.stitches:
        kind = _KIND.get(cmd & pe.COMMAND_MASK)
        if kind is None:  # sequins, speed changes, etc.: not shown in M1
            continue
        i = len(kinds)
        xs.append(round(x / 10, 2))
        ys.append(round(y / 10, 2))
        kinds.append(kind)
        if kind == STITCH:
            counts["stitches"] += 1
        elif kind == JUMP:
            counts["jumps"] += 1
        elif kind == TRIM:
            counts["trims"] += 1
        elif kind == STOP:
            counts["stops"] += 1
        elif kind == COLOR_CHANGE:
            counts["color_changes"] += 1
            blocks.append({"thread": thread_idx, "start": block_start, "end": i})
            block_start, thread_idx = i + 1, thread_idx + 1
        elif kind == END:
            break
    blocks.append({"thread": thread_idx, "start": block_start, "end": len(kinds)})
    # Drop empty blocks (e.g. a color change right before END) but keep thread numbering.
    blocks = [b for b in blocks if any(kinds[j] == STITCH for j in range(b["start"], b["end"]))]

    threads = [_thread(pattern.threadlist[i] if i < len(pattern.threadlist) else None) for i in range(thread_idx + 1)]

    if counts["stitches"]:
        sx = [x for x, k in zip(xs, kinds) if k == STITCH]
        sy = [y for y, k in zip(ys, kinds) if k == STITCH]
        bounds = [min(sx), min(sy), max(sx), max(sy)]
    else:
        bounds = [0.0, 0.0, 0.0, 0.0]

    return {
        "info": {
            **counts,
            "colors": len(blocks),
            "width_mm": round(bounds[2] - bounds[0], 1),
            "height_mm": round(bounds[3] - bounds[1], 1),
            "bounds_mm": bounds,
        },
        "threads": threads,
        "blocks": blocks,
        "records": {"x": xs, "y": ys, "kind": kinds},
    }


def open_design(path: str) -> dict[str, Any]:
    p = Path(path)
    return {"path": str(p), "name": p.name, "format": _ext(p), **summarize(load(p))}


# Names Windows keeps for devices, whatever the extension ("CON.pes" can't be a file).
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def color_steps(pattern: pe.EmbPattern) -> int:
    """Colour steps as the machine sees them: one per colour, plus one per colour change and stop."""
    return 1 + sum(1 for *_, c in pattern.stitches if c & pe.COMMAND_MASK in (pe.COLOR_CHANGE, pe.STOP))


def _ascii(s: str | None) -> str | None:
    if not s:
        return s
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def _for_format(pattern: pe.EmbPattern, ext: str) -> pe.EmbPattern:
    """A copy adjusted for the writer of `ext` (the original is never changed)."""
    if ext == "pes" and any(not (s or "").isascii() for t in pattern.threadlist
                            for s in (t.description, t.catalog_number, t.brand, t.chart)):
        # pyembroidery writes a thread name's length in characters but its bytes in UTF-8, so one
        # "ü" shifts the rest of the PES thread table. Plain letters keep it readable ("Grün" -> "Grun").
        p = pattern.copy()
        p.threadlist = []
        for t in pattern.threadlist:
            n = pe.EmbThread(t.hex_color(), _ascii(t.description), _ascii(t.catalog_number),
                             brand=_ascii(t.brand), chart=_ascii(t.chart))
            p.threadlist.append(n)
        pattern = p
    if ext in ("pes", "pec") and pattern.stitches:
        # Brother machines (the PE550D at least) read a PES design from its top-left corner: its
        # stitches must run from (0, 0) to its width and height, as Embrilliance and PE-Design write
        # them. Centred on (0, 0), the machine showed it shifted up and left by half its size,
        # mostly outside the hoop, and it couldn't be moved back. The machine centres it itself.
        x0, y0, _, _ = pattern.bounds()
        if x0 or y0:
            p = pattern.copy()
            p.stitches = [[x - x0, y - y0, c] for x, y, c in pattern.stitches]
            pattern = p
    if ext == "jef":
        # The JEF header describes the design as centred on the hoop (extents are half its size each
        # way), so put its centre there. Designs from many programs have their corner at (0, 0).
        pts = [(x, y) for x, y, c in pattern.stitches if c & pe.COMMAND_MASK == pe.STITCH]
        if pts:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            cx, cy = round((min(xs) + max(xs)) / 2), round((min(ys) + max(ys)) / 2)
            if cx or cy:
                p = pattern.copy()
                p.stitches = [[x - cx, y - cy, c] for x, y, c in pattern.stitches]
                pattern = p
    return pattern


def write(pattern: pe.EmbPattern, dest: str | Path, extra: dict[str, Any] | None = None) -> None:
    """Write a machine file. The file appears only when it's complete: a failure part-way leaves
    whatever was there before untouched."""
    dest = Path(dest)
    ext = _ext(dest)
    if not ext:
        raise DesignError(f"Add the file type to the name, for example {dest.name.rstrip('.')}.pes")
    if ext not in _writable():
        raise DesignError(f"Can't save .{ext} files. Choose a name ending in .pes, .jef or another machine format.")
    if os.name == "nt" and dest.name.split(".")[0].strip().upper() in RESERVED_NAMES:
        raise DesignError(f"“{dest.stem}” is a name Windows keeps for itself. Choose another file name.")
    if not any(c & pe.COMMAND_MASK == pe.STITCH for *_, c in pattern.stitches):
        raise DesignError("There's nothing to sew: this design has no stitches.")
    if ext == "pes" and color_steps(pattern) > PES_MAX_STEPS:
        raise DesignError(
            f"A PES file holds at most {PES_MAX_STEPS} color steps; this design has {color_steps(pattern)} "
            "(colors plus stops). Use fewer cut-stops (a longer minimum jump) or fewer colors.")
    pattern = _for_format(pattern, ext)
    # Stitches longer than the format allows are sewn in pieces (pyembroidery would otherwise jump
    # half way with the needle up and lay only half the stitch).
    settings = {"long_stitch_contingency": pe.CONTINGENCY_LONG_STITCH_SEW_TO, **WRITE_SETTINGS.get(ext, {}), **(extra or {})}
    tmp = dest.with_name(f".{dest.stem}.{uuid.uuid4().hex[:8]}.part{dest.suffix}")
    try:
        pe.write(pattern, str(tmp), settings)
        os.replace(tmp, dest)
    except Exception as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        why = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
        raise DesignError(f"Couldn't write {dest.name}: {why}") from exc


def preview_export(src: str, options: dict[str, Any] | None = None, ext: str | None = None) -> dict[str, Any]:
    """What an export with these options would produce, without writing anything."""
    pattern, report = prepare(load(src), Options.from_dict(options), ext)
    return {**report, **summarize(pattern)}


def export(src: str, dest: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    s, d = Path(src).resolve(), Path(dest).resolve()
    if s == d:
        raise DesignError("Choose a different file name: exporting over the original isn't allowed")
    opts = Options.from_dict(options)
    pattern, report = prepare(load(s), opts, _ext(d))
    write(pattern, d, write_settings(opts))
    return {"path": str(d), **report}


def _free_name(path: Path) -> Path:
    """`name.pes`, or `name (1).pes` etc. if that exists. Never overwrite."""
    if not path.exists():
        return path
    n = 1
    while (candidate := path.with_name(f"{path.stem} ({n}){path.suffix}")).exists():
        n += 1
    return candidate


def convert_folder(
    src_dir: str, dest_dir: str, ext: str, recursive: bool = False, options: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Convert every readable design in src_dir to `ext` under dest_dir, mirroring subfolders.

    `options` (machine, cut_stops) apply to every file; per-design thread changes are ignored.
    """
    opts = Options.from_dict({**(options or {}), "threads": []})
    ext = ext.lower().lstrip(".")
    if ext not in _writable():
        raise DesignError(f"Can't write .{ext} files")
    src, dest = Path(src_dir), Path(dest_dir)
    if not src.is_dir():
        raise DesignError(f"Folder not found: {src}")

    readable = _readable()
    if recursive:
        # Walk the folders, but not into links or Windows junctions (they can loop, or lead anywhere).
        files = []
        for root, dirs, names in os.walk(src, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(root, d).is_symlink() or Path(root, d).is_junction())]
            files += [Path(root, n) for n in names]
        files.sort()
    else:
        files = sorted(src.iterdir())
    converted, failed, skipped = [], [], []
    dest_resolved = dest.resolve()
    # Saving into a folder inside the source: don't convert what an earlier run saved there. (The
    # list of files is taken before anything is written, so saving into the source folder itself,
    # or a folder that contains it, is fine: new files never overwrite, see _free_name.)
    inside = dest_resolved != src.resolve() and dest_resolved.is_relative_to(src.resolve())
    for f in files:
        if not f.is_file():
            continue
        if inside and f.resolve().is_relative_to(dest_resolved):
            continue
        if _ext(f) not in readable:
            skipped.append(str(f))
            continue
        out = dest / f.relative_to(src).with_suffix("." + ext)
        try:
            pattern, report = prepare(load(f), opts, ext)
            out.parent.mkdir(parents=True, exist_ok=True)
            out = _free_name(out)
            write(pattern, out, write_settings(opts))
            converted.append({"src": str(f), "dest": str(out), **report})
        except DesignError as exc:
            failed.append({"src": str(f), "error": str(exc)})
    return {"converted": converted, "failed": failed, "skipped": skipped}
