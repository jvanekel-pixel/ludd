"""Your own motifs, kept as files in LUDD's data folder (motifs/<slug>.json).

A motif file is {"format": "ludd-motif", "version": 1, "name": ..., "unit": [[x, y], ...]}: one
repeat that starts at x = 0 and ends at x = 1. Saving a drawn line turns it into that: its first
point goes to (0, 0), its last to (1, 0), and everything is scaled by the same factor, so its
proportions hold. A shape that uses one carries a copy (params["motif_unit"]), so a project sews
the same on a computer that doesn't have it.

Nothing here ever treats a name or an id as a path, and nothing in the motif folder is replaced.
"""

from __future__ import annotations

import itertools
import json
import math
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

from .digitize import lines
from .digitize.paths import dist, flatten
from .digitize.stitches import DigitizeError, check_points
from .names import _RESERVED  # the names Windows keeps for devices, as name templates refuse them
from .storage import data_dir, write_json

FORMAT = "ludd-motif"
VERSION = 1
PREFIX = "user:"  # the id of one of your own is "user:<its file's name>"
MIN_ENDS_MM = 2.0
MAX_FILE_BYTES = 256 * 1024  # a 200-point motif is about 10 KB
MAX_NAME = 80
MAX_SLUG = 60
_SLUG = re.compile(r"_?[a-z0-9]+(?:-[a-z0-9]+)*")  # every file name LUDD gives one (never a path)

ENDS = "A motif runs from where it starts to where it ends; draw it left to right"
BUILTIN_NAMES = {"wave": "Wave", "zigzag": "Zigzag", "scallop": "Scallop",
                 "blanket": "Blanket stitch (applique edge)", "leaf": "Leaves"}


class MotifError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


def _folder() -> Path:
    return data_dir() / "motifs"


def _builtin(name: str) -> tuple[str, list[list[float]]]:
    return BUILTIN_NAMES.get(name, name.capitalize()), [[u, v] for u, v in lines.MOTIF_UNITS[name]]


def _clean_name(name: Any) -> str:
    """A name as it's shown: one line, no control characters, at most MAX_NAME characters."""
    if not isinstance(name, str):
        return ""
    text = "".join(" " if unicodedata.category(c).startswith("C") else c for c in name)
    return " ".join(text.split())[:MAX_NAME].rstrip()


def _slug(name: str) -> str:
    """A motif's name as a file name every computer takes: lower-case letters, digits and hyphens."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:MAX_SLUG].rstrip("-") or "motif"
    return f"_{slug}" if _RESERVED.fullmatch(slug) else slug


def _is_slug(stem: str) -> bool:
    return len(stem) <= MAX_SLUG + 10 and bool(_SLUG.fullmatch(stem)) and not _RESERVED.fullmatch(stem)


def _unit_of(value: Any) -> list[list[float]]:
    """A stored or imported unit, checked: one repeat from x = 0 to x = 1."""
    unit = lines.carried_unit(value)
    if unit is None:
        raise DigitizeError("This motif can't be used: it has no points.")
    if abs(unit[0][0]) > 1e-6 or abs(unit[-1][0] - 1) > 1e-6:
        raise DigitizeError("This motif can't be used: it doesn't run from its start to its end.")
    return [[u, v] for u, v in unit]


def _load(path: Path, label: str) -> tuple[Any, list[list[float]]]:
    """A motif file, checked before it's trusted: its name (as written) and its unit."""
    unreadable = f"Couldn't read {label}: it may have been moved or deleted."
    try:
        if not path.is_file():
            raise MotifError(unreadable)
        too_big = path.stat().st_size > MAX_FILE_BYTES
        if not too_big:
            with open(path, "rb") as f:
                raw = f.read(MAX_FILE_BYTES + 1)
            too_big = len(raw) > MAX_FILE_BYTES
    except (OSError, ValueError) as exc:
        raise MotifError(unreadable) from exc
    if too_big:
        raise MotifError(f"{label} is too big to be a LUDD motif.")
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, RecursionError) as exc:  # not text, not JSON, nested too deep
        raise MotifError(f"{label} isn't a LUDD motif file.") from exc
    version = data.get("version") if isinstance(data, dict) else None
    if not isinstance(data, dict) or data.get("format") != FORMAT or type(version) is not int or version < 1:
        raise MotifError(f"{label} isn't a LUDD motif file.")
    if version > VERSION:
        raise MotifError(f"{label} was made by a newer LUDD; update LUDD to use it.")
    try:
        return data.get("name"), _unit_of(data.get("unit"))
    except DigitizeError as exc:
        raise MotifError(f"{label}: {exc}") from exc


def _own_file(motif_id: Any) -> Path:
    """The file of one of your own motifs; any other id is refused."""
    gone = "That motif isn't in your list. It may have been deleted already."
    if not isinstance(motif_id, str) or not motif_id.startswith(PREFIX) or not _is_slug(motif_id[len(PREFIX):]):
        raise MotifError(gone)
    path = _folder() / f"{motif_id[len(PREFIX):]}.json"
    if not path.is_file():
        raise MotifError(gone)
    return path


def _store(name: str, unit: list[list[float]]) -> dict[str, Any]:
    """Keep a motif under a file name nothing else has."""
    folder = _folder()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        slug = _slug(name)
        for n in itertools.count(1):
            stem = slug if n == 1 else f"{slug}-{n}"
            if not os.path.lexists(folder / f"{stem}.json"):
                break
        write_json(folder / f"{stem}.json", {"format": FORMAT, "version": VERSION, "name": name, "unit": unit})
    except OSError as exc:
        raise MotifError(f"Couldn't save the motif: {exc.strerror or exc}. Is the disk full?") from exc
    return {"id": PREFIX + stem, "name": name, "unit": unit}


def _mine() -> list[dict[str, Any]]:
    """Your own motifs, by name; files that aren't whole motifs are left out."""
    try:
        files = sorted(_folder().glob("*.json"))
    except OSError:
        return []
    found = []
    for f in files:
        if not _is_slug(f.stem):
            continue
        try:
            name, unit = _load(f, f.name)
        except MotifError:
            continue
        found.append({"id": PREFIX + f.stem, "name": _clean_name(name) or f.stem, "builtin": False, "unit": unit})
    return sorted(found, key=lambda m: (m["name"].casefold(), m["id"]))


def list_motifs() -> list[dict[str, Any]]:
    """The built-in motifs and your own: [{"id", "name", "builtin", "unit"}]."""
    builtins = []
    for motif_id in lines.MOTIF_UNITS:
        name, unit = _builtin(motif_id)
        builtins.append({"id": motif_id, "name": name, "builtin": True, "unit": unit})
    return builtins + _mine()


def _unit_from_line(nodes: Any, closed: Any) -> list[list[float]]:
    """A drawn line as one repeat: its first point at (0, 0), its last at (1, 0), the same scale
    along and across."""
    if closed or not isinstance(nodes, list) or len(nodes) < 2:
        raise MotifError(ENDS)
    try:
        if not all(math.isfinite(float(c)) for n in nodes for c in (n[0], n[1])):
            raise MotifError("This line has a point that isn't a number.")
        poly = flatten(nodes, False)[0]
        check_points(poly, "line")
    except (TypeError, ValueError, IndexError, KeyError, OverflowError) as exc:
        raise MotifError("This line has a point that isn't a number.") from exc
    except DigitizeError as exc:
        raise MotifError(f"{exc}") from exc
    (ax, ay), (bx, by) = poly[0], poly[-1]
    if round(dist(poly[0], poly[-1]), 6) < MIN_ENDS_MM:
        raise MotifError(ENDS)
    if len(poly) > lines.MAX_UNIT_POINTS:
        raise MotifError(f"This line has too many points for a motif ({len(poly)}; the most is "
                         f"{lines.MAX_UNIT_POINTS}). Draw it smaller, or with fewer curves.")
    dx, dy = bx - ax, by - ay
    square = dx * dx + dy * dy
    unit = [[round(((x - ax) * dx + (y - ay) * dy) / square, 6) + 0.0,
             round((dx * (y - ay) - dy * (x - ax)) / square, 6) + 0.0] for x, y in poly]
    unit[0], unit[-1] = [0.0, 0.0], [1.0, 0.0]
    return unit


def save(name: str, nodes: list, closed: bool = False) -> dict[str, Any]:
    """Keep a drawn line as a motif of your own: {"id", "name", "unit"}."""
    title = _clean_name(name)
    if not title:
        raise MotifError("Give the motif a name.")
    return _store(title, _unit_from_line(nodes, closed))


def delete(motif_id: str) -> None:
    """Delete one of your own motifs. Shapes that use it keep their copy."""
    if isinstance(motif_id, str) and motif_id in lines.MOTIF_UNITS:
        raise MotifError("The built-in motifs can't be deleted.")
    path = _own_file(motif_id)
    try:
        path.unlink()
    except OSError as exc:
        raise MotifError(f"Couldn't delete the motif: {exc.strerror or exc}") from exc


def _in_data_folder(path: Path) -> bool:
    """Whether a path is in LUDD's own data folder (your motifs, settings, fonts and so on). A
    path that can't be checked counts as inside: nothing is written where LUDD can't tell."""
    folder = data_dir()
    try:
        if path.resolve().is_relative_to(folder.resolve()):
            return True
        # The same folder under another spelling (upper and lower case on a Mac or Windows).
        return folder.is_dir() and any(p.is_dir() and os.path.samefile(p, folder) for p in path.parents)
    except (OSError, ValueError):
        return True


def export(motif_id: str, dest: str) -> dict[str, Any]:
    """Save a motif (one of yours, or a built-in) as a file: {"path"}."""
    if isinstance(motif_id, str) and motif_id in lines.MOTIF_UNITS:
        name, unit = _builtin(motif_id)
    else:
        own = _own_file(motif_id)
        name, unit = _load(own, own.name)
        name = _clean_name(name) or own.stem
    if not isinstance(dest, str) or not dest.strip() or "\0" in dest or not Path(dest).name:
        raise MotifError("Choose where to save the motif file.")
    path = Path(dest)
    if not path.is_absolute():  # "C:foo.json" too: it would land wherever the engine is running
        raise MotifError("Saving a motif needs a full path, from the drive or top folder down. "
                         "Choose where to save it.")
    if path.suffix.lower() != ".json":
        path = path.with_name(path.name + ".json")  # added, never replacing: "Bob v1.2" stays whole
    if _in_data_folder(path):
        raise MotifError("Save the copy somewhere else: LUDD keeps its own files in that folder.")
    try:
        write_json(path, {"format": FORMAT, "version": VERSION, "name": name, "unit": unit})
    except (OSError, ValueError) as exc:
        raise MotifError(f"Couldn't save {path.name}: {getattr(exc, 'strerror', None) or exc}") from exc
    return {"path": str(path)}


def import_file(path: str) -> dict[str, Any]:
    """Add a motif from a file: {"id", "name", "unit"}."""
    if not isinstance(path, str) or not path.strip():
        raise MotifError("Choose a motif file to import.")
    source = Path(path)
    name, unit = _load(source, source.name or path)
    return _store(_clean_name(name) or _clean_name(source.stem) or "Motif", unit)
