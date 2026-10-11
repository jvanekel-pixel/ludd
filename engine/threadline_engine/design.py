"""Open, summarize, export and batch-convert stitch files via pyembroidery.

Imported stitch files are not objects: they are flat stitch lists, shown and
converted as-is. Units sent to the UI are millimetres (pyembroidery uses 0.1 mm).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyembroidery as pe

from .prepare import Options, prepare, write_settings

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


def write(pattern: pe.EmbPattern, dest: str | Path, extra: dict[str, Any] | None = None) -> None:
    ext = _ext(dest)
    if ext not in _writable():
        raise DesignError(f"Can't write .{ext} files")
    try:
        pe.write(pattern, str(dest), {**WRITE_SETTINGS.get(ext, {}), **(extra or {})})
    except Exception as exc:
        raise DesignError(f"Couldn't write {Path(dest).name}: {exc}") from exc


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
    files = sorted(src.rglob("*") if recursive else src.iterdir())
    converted, failed, skipped = [], [], []
    dest_resolved = dest.resolve()
    for f in files:
        if not f.is_file():
            continue
        if f.resolve().is_relative_to(dest_resolved):  # don't re-convert our own output
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
