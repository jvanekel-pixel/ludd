"""Stitch presets: one shape's stitch settings kept under a name (the presets.* methods).

A preset file (.luddpreset) is {"format": "ludd-preset", "version": 1, "name": ..., "kind":
"run" | "satin" | "fill" | "applique", "params": {...}, "width_mm"?: a satin ribbon's width,
"note"?: ...}. Yours are kept in LUDD's data folder (presets/<slug>.luddpreset); five come built
in.

A preset never holds what belongs to one shape: its direction and angle lines, where it starts
and ends, a ripple's middle, which way round a blend's colors run, or push compensation. A file is
checked before it's trusted: its size, format, version and kind, each setting's type, and every
setting by the kind's own from_dict. A setting, style or pattern this version doesn't know means
a newer LUDD made it.

Nothing here treats a name or an id as a path, and only files in the presets folder are replaced
or deleted. (An export replaces nothing but another preset file you chose in the save window.)
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
import os
import re
import unicodedata
from dataclasses import fields
from pathlib import Path
from typing import Any

from .digitize import fills, lines
from .digitize import stitches as dz
from .digitize.applique import AppliqueParams
from .digitize.rows.weave import WEAVES
from .motifs import _in_data_folder
from .names import _RESERVED  # the names Windows keeps for devices, as name templates refuse them
from .storage import data_dir, write_json

FORMAT = "ludd-preset"
VERSION = 1
EXT = ".luddpreset"
BUILTIN = "builtin:"  # ids of the built-in presets; no file is ever named like one
KINDS = ("run", "satin", "fill", "applique")
KIND_PLURAL = {"run": "lines", "satin": "satins", "fill": "fills", "applique": "appliques"}
MAX_FILE_BYTES = 256 * 1024  # the biggest preset (a motif of your own) is about 10 KB
MAX_NAME = 80
MAX_NOTE = 200
MAX_SLUG = 60
MAX_NUMBER = 100_000  # no setting is anywhere near this
SATIN_WIDTH_MM = (0.5, 12.0)  # the widths the app gives a satin ribbon
_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")  # every file name LUDD gives one (never a path)

# What belongs to one shape, never to a preset.
ONE_SHAPE = frozenset({"angle_deg", "reverse", "start_mm", "end_mm", "angle_line", "angle_lines",
                       "ripple_center", "blend_flip", "push_comp_mm", "carve"})
# Lock stitches are read outside the settings classes (stitches.generate_parts).
LOCKS = frozenset({"tie_in", "tie_off", "tie_style"})
_NOT_SETTINGS = frozenset({"extra", "underlay_spacing_mm"})  # fields from_dict never reads

_ON_OFF = frozenset({"comp_by_width", "auto_widen", "placement", "tie_in", "tie_off"})
# Settings chosen by name: the names this version has, and what to call the choice.
_CHOICES = {
    "style": (lambda: lines.REGISTRY, "line style"),
    "pattern": (lambda: fills.REGISTRY, "fill pattern"),
    "weave": (lambda: WEAVES, "weave"),
    "feather": (lambda: ("none", "left", "right", "both"), "feathered side"),
    "underlay_level": (lambda: dz.UNDERLAY_LEVELS, "underlay amount"),
    "tack": (lambda: ("zigzag", "run"), "tack-down"),
    "tie_style": (lambda: ("standard", "triangle", "backtack"), "lock stitch shape"),
    "motif_side": (lambda: ("center", "left", "right"), "motif side"),
    "blackwork_lattice": (lambda: ("diamonds", "grid", "honeycomb", "crossed"), "blackwork lattice"),
}
_UNDERLAYS = {"satin": ("center", "edge", "zigzag"), "fill": ("edge", "tatami")}
_COLOR = re.compile(r"#[0-9a-fA-F]{6}")

_BUILT_IN = (
    ("light-sketch-fill", "Light sketch fill", "fill",
     {"pattern": "tatami", "spacing_mm": 1.0, "stitch_mm": 3.5, "underlay": [], "hand_pct": 40}, None,
     "Open, slightly uneven rows with nothing under them, like a pencil sketch."),
    ("bold-outline", "Bold outline", "run", {"style": "bean", "stitch_mm": 2.5}, None,
     "Each stitch sewn three times, for a bold line."),
    ("redwork-line", "Redwork line", "run", {"style": "redwork", "stitch_mm": 2.5}, None,
     "Out along the line and back again, the way redwork is sewn."),
    ("narrow-satin-border", "Narrow satin border", "satin", {"spacing_mm": 0.4, "underlay": ["center"]}, 2.0,
     "A 2 mm satin with a run of stitches under its middle."),
    ("felt-applique", "Felt applique", "applique", {"cover_width_mm": 2.5, "tack": "run", "placement": True}, None,
     "A narrow border over a straight tack-down, for felt and other fabric that doesn't fray."),
)


class PresetError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


def settings_of(kind: str) -> frozenset[str]:
    """The settings a preset of this kind may hold: the ones this engine reads for it."""
    if kind == "run":
        known = {f.name for f in fields(dz.RunParams)} | {k for s in lines.REGISTRY.values() for k in s.params} | LOCKS
    elif kind == "satin":
        known = {f.name for f in fields(dz.SatinParams)} | LOCKS
    elif kind == "fill":
        known = ({f.name for f in fields(dz.FillParams)} | {k for p in fills.REGISTRY.values() for k in p.params}
                 | {"underlay_level"} | LOCKS)
    else:
        known = {f.name for f in fields(AppliqueParams)} | {"spacing_mm"}
    return frozenset(known) - ONE_SHAPE - _NOT_SETTINGS


# ---------------------------------------------------------------- checking


def _text(value: Any, limit: int) -> str:
    """Text as it's shown: one line, no control characters, at most `limit` characters."""
    if not isinstance(value, str):
        return ""
    plain = "".join(" " if unicodedata.category(c).startswith("C") else c for c in value)
    return " ".join(plain.split())[:limit].rstrip()


def _newer(label: str, what: str) -> PresetError:
    return PresetError(f"{label} was made by a newer LUDD (it has {what} this version doesn't know). "
                       "Update LUDD to use it.")


def _check_numbers(value: Any, label: str, depth: int = 0) -> None:
    """Every number in a setting is an ordinary one."""
    if isinstance(value, bool) or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        if (isinstance(value, float) and not math.isfinite(value)) or abs(value) > MAX_NUMBER:
            raise PresetError(f"{label} has a number far bigger than any setting. It may be damaged.")
        return
    if depth > 4:
        raise PresetError(f"{label} isn't a LUDD preset.")
    for inner in value.values() if isinstance(value, dict) else value if isinstance(value, list) else ():
        _check_numbers(inner, label, depth + 1)


def _blend(value: Any, label: str) -> list[dict[str, str]]:
    """A blend's other colors: up to three threads, kept as just their color and names."""
    if not isinstance(value, list) or not all(isinstance(t, dict) for t in value):
        raise PresetError(f"{label}: The blend's colors must be a list of threads")
    if len(value) > 3:
        raise PresetError(f"{label}: A blend takes up to four colors")
    threads = []
    for t in value:
        color = t.get("color")
        if not isinstance(color, str) or not _COLOR.fullmatch(color):
            raise PresetError(f"{label}: A blend color isn't a color")
        threads.append({"color": color, **{k: _text(t.get(k), MAX_NAME) for k in ("name", "catalog", "brand")}})
    return threads


def _value(kind: str, key: str, value: Any, label: str) -> Any:
    """One setting, checked for its type and the names it can take."""
    if key in _ON_OFF:
        if not isinstance(value, bool):
            raise PresetError(f"{label}: The setting {key} must be on or off")
        return value
    if key in _CHOICES or key == "motif":
        if not isinstance(value, str):
            raise PresetError(f"{label}: The setting {key} must be text")
        if key != "motif" and value not in _CHOICES[key][0]():
            raise _newer(label, f"a {_CHOICES[key][1]}, “{_text(value, 40)}”,")
        return value
    if key == "underlay":
        if value == "auto":
            return value
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise PresetError(f"{label}: The setting underlay must be a list of underlay names")
        if set(value) - set(_UNDERLAYS[kind]):
            raise _newer(label, "an underlay")
        return list(value)
    if key == "blend":
        return _blend(value, label)
    if key == "motif_unit":
        try:
            unit = lines.carried_unit(value)
        except dz.DigitizeError as exc:
            raise PresetError(f"{label}: {exc}") from exc
        return [[u, v] for u, v in unit]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PresetError(f"{label}: The setting {key} must be a number")
    return value


def _check_motif(kind: str, params: dict[str, Any], label: str) -> None:
    motif = params.get("motif")
    if motif is None:
        return
    if motif.startswith("user:"):
        used = params.get("style") == "motif" if kind == "run" else params.get("pattern") == "motif"
        if used and not params.get("motif_unit"):
            raise PresetError(f"{label} uses a motif of your own but doesn't carry it.")
    elif motif not in lines.MOTIF_UNITS:
        raise _newer(label, f"a motif, “{_text(motif, 40)}”,")


def _check_ranges(kind: str, params: dict[str, Any], label: str) -> None:
    """Every setting checked as the kind's own from_dict checks it, and the settings of styles
    and patterns not chosen too: they can be chosen later."""
    checker = {"run": dz.RunParams, "satin": dz.SatinParams, "fill": dz.FillParams, "applique": AppliqueParams}[kind]
    try:
        checker.from_dict(params)
    except dz.DigitizeError as exc:
        raise PresetError(f"{label}: {exc}") from exc
    registry = lines.REGISTRY if kind == "run" else fills.REGISTRY if kind == "fill" else {}
    for entry in registry.values():
        for key, spec in entry.params.items():
            if key in params and not spec.lo <= params[key] <= spec.hi:
                raise PresetError(f"{label}: {spec.refusal()}")
    if kind == "run" and not (1.5 <= params.get("motif_mm", 4) <= 20 and 0.5 <= params.get("motif_width_mm", 2.5) <= 10):
        raise PresetError(f"{label}: A motif repeats every 1.5 to 20 mm and is 0.5 to 10 mm wide")


def _width(value: Any, label: str) -> float | None:
    if value is None:
        return None
    lo, hi = SATIN_WIDTH_MM
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
        raise PresetError(f"{label}: A satin's width must be between {lo:g} and {hi:g} mm")
    return float(value)


def check(data: Any, label: str, strict: bool = True) -> dict[str, Any]:
    """A preset's name (as given), kind, settings, width and note, checked and tidied. `strict`
    (a file): a setting this version doesn't know is refused, as made by a newer LUDD; saving a
    shape's settings leaves such a key out instead. A preset file is labeled by its name."""
    broken = PresetError(f"{label} isn't a LUDD preset.")
    if not isinstance(data, dict) or not isinstance(data.get("kind"), str) or not isinstance(data.get("params"), dict):
        raise broken
    kind, note = data["kind"], data.get("note")
    if kind not in KINDS:
        raise _newer(label, f"a kind of shape, “{_text(kind, 40)}”,")
    if note is not None and not isinstance(note, str):
        raise broken
    known = settings_of(kind)
    params: dict[str, Any] = {}
    for key, value in data["params"].items():
        if key in ONE_SHAPE or value is None:
            continue
        if key not in known:
            if strict:
                raise _newer(label, f"a setting, “{_text(str(key), 40)}”,")
            continue
        _check_numbers(value, label)
        params[key] = _value(kind, key, value, label)
    _check_motif(kind, params, label)
    _check_ranges(kind, params, label)
    width = _width(data.get("width_mm"), label) if kind == "satin" else None
    return {"name": data.get("name"), "kind": kind, "params": params, "width_mm": width,
            "note": _text(note, MAX_NOTE) or None}


# ---------------------------------------------------------------- files


def _folder() -> Path:
    return data_dir() / "presets"


def _slug(name: str) -> str:
    """A preset's name as a file name every computer takes, made as thread chart ids are:
    lower-case letters, digits and hyphens, never a Windows device name."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:MAX_SLUG].rstrip("-")
    if not slug:
        slug = "preset-" + hashlib.sha1(name.casefold().encode("utf-8")).hexdigest()[:8]
    return f"preset-{slug}" if _RESERVED.fullmatch(slug) else slug


def _is_id(preset_id: Any) -> bool:
    return (isinstance(preset_id, str) and len(preset_id) <= MAX_SLUG + 12 and bool(_ID.fullmatch(preset_id))
            and not _RESERVED.fullmatch(preset_id))


def _read(path: Path, label: str) -> dict[str, Any]:
    """The preset a file holds, as written (its size, JSON, format and version checked)."""
    unreadable = f"Couldn't read {label}: it may have been moved or deleted."
    try:
        if not path.is_file():
            raise PresetError(unreadable)
        too_big = path.stat().st_size > MAX_FILE_BYTES
        if not too_big:
            with open(path, "rb") as f:
                raw = f.read(MAX_FILE_BYTES + 1)
            too_big = len(raw) > MAX_FILE_BYTES
    except (OSError, ValueError) as exc:
        raise PresetError(unreadable) from exc
    if too_big:
        raise PresetError(f"{label} is too big to be a LUDD preset.")

    def refuse(constant: str) -> float:
        raise ValueError(f"not a number: {constant}")

    try:
        data = json.loads(raw.decode("utf-8-sig"), parse_constant=refuse)
    except (ValueError, RecursionError) as exc:  # not text, not JSON, NaN, nested too deep
        raise PresetError(f"{label} isn't a LUDD preset.") from exc
    version = data.get("version") if isinstance(data, dict) else None
    if not isinstance(data, dict) or data.get("format") != FORMAT or type(version) is not int or version < 1:
        raise PresetError(f"{label} isn't a LUDD preset.")
    if version > VERSION:
        raise PresetError(f"{label} was made by a newer LUDD; update LUDD to use it.")
    if data.get("name") is not None and not isinstance(data["name"], str):
        raise PresetError(f"{label} isn't a LUDD preset.")
    return data


def _load(path: Path, label: str) -> dict[str, Any]:
    """A preset file, checked before it's trusted."""
    return check(_read(path, label), label)


def _file(name: str, preset: dict[str, Any]) -> dict[str, Any]:
    extras = {k: preset[k] for k in ("width_mm", "note") if preset.get(k) is not None}
    return {"format": FORMAT, "version": VERSION, "name": name, "kind": preset["kind"], "params": preset["params"], **extras}


def _entry(preset_id: str, name: str, preset: dict[str, Any], builtin: bool) -> dict[str, Any]:
    return {"id": preset_id, "name": name, "kind": preset["kind"], "params": preset["params"],
            "width_mm": preset["width_mm"], "note": preset["note"], "builtin": builtin}


def _built_in() -> list[dict[str, Any]]:
    return [_entry(BUILTIN + slug, name, {"kind": kind, "params": copy.deepcopy(params), "width_mm": width, "note": note}, True)
            for slug, name, kind, params, width, note in _BUILT_IN]


def _mine() -> list[dict[str, Any]]:
    """Your own presets, by name; files that aren't whole, usable presets are left out."""
    try:
        files = sorted(_folder().glob(f"*{EXT}"))
    except OSError:
        return []
    found = []
    for f in files:
        if not _is_id(f.stem):
            continue
        try:
            preset = _load(f, f.name)
        except PresetError:
            continue
        found.append(_entry(f.stem, _text(preset["name"], MAX_NAME) or f.stem, preset, False))
    return sorted(found, key=lambda p: (p["name"].casefold(), p["id"]))


def list_presets() -> list[dict[str, Any]]:
    """The built-in presets and your own."""
    return _built_in() + _mine()


def _own_file(preset_id: Any) -> Path:
    """The file of one of your own presets; any other id is refused."""
    gone = "That preset isn't in your list. It may have been deleted already."
    if not _is_id(preset_id):
        raise PresetError(gone)
    path = _folder() / f"{preset_id}{EXT}"
    if not path.is_file():
        raise PresetError(gone)
    return path


def _names(kind: str) -> set[str]:
    return {p["name"].casefold() for p in list_presets() if p["kind"] == kind}


def _write_new(name: str, preset: dict[str, Any]) -> str:
    """Keep a preset under a file name nothing else has; its id."""
    folder = _folder()
    folder.mkdir(parents=True, exist_ok=True)
    slug = _slug(name)
    for n in itertools.count(1):
        stem = slug if n == 1 else f"{slug}-{n}"
        if not os.path.lexists(folder / f"{stem}{EXT}"):
            break
    write_json(folder / f"{stem}{EXT}", _file(name, preset))
    return stem


def save(preset: Any, replace: bool = False) -> dict[str, Any]:
    """Keep a shape's settings as a preset of your own: {"id"}. One with the same name (for the
    same kind of shape) is replaced only when `replace` says so."""
    if not isinstance(preset, dict):
        raise PresetError("There's nothing to save as a preset.")
    name = _text(preset.get("name"), MAX_NAME)
    if not name:
        raise PresetError("Give the preset a name.")
    clean = check(preset, f"“{name}”", strict=False)
    if any(p["kind"] == clean["kind"] and p["name"].casefold() == name.casefold() for p in _built_in()):
        raise PresetError(f"“{name}” is a built-in preset. Give yours another name.")
    same = [p for p in _mine() if p["kind"] == clean["kind"] and p["name"].casefold() == name.casefold()]
    if same and not replace:
        raise PresetError(f"You already have a preset called “{same[0]['name']}” for {KIND_PLURAL[clean['kind']]}.")
    try:
        if same:
            write_json(_folder() / f"{same[0]['id']}{EXT}", _file(name, clean))
            return {"id": same[0]["id"]}
        return {"id": _write_new(name, clean)}
    except OSError as exc:
        raise PresetError(f"Couldn't save the preset: {exc.strerror or exc}. Is the disk full?") from exc


def delete(preset_id: Any) -> None:
    """Delete one of your own presets."""
    if isinstance(preset_id, str) and preset_id.startswith(BUILTIN):
        raise PresetError("The built-in presets can't be deleted.")
    path = _own_file(preset_id)
    try:
        path.unlink()
    except OSError as exc:
        raise PresetError(f"Couldn't delete the preset: {exc.strerror or exc}") from exc


def _find(preset_id: Any) -> dict[str, Any]:
    if isinstance(preset_id, str) and preset_id.startswith(BUILTIN):
        found = next((p for p in _built_in() if p["id"] == preset_id), None)
        if found is None:
            raise PresetError("That built-in preset isn't one LUDD has.")
        return found
    path = _own_file(preset_id)
    preset = _load(path, path.name)
    return {**preset, "name": _text(preset["name"], MAX_NAME) or path.stem}


def _is_preset_file(path: Path) -> bool:
    try:
        return _read(path, path.name) is not None
    except PresetError:
        return False


def export(preset_id: Any, dest: Any) -> dict[str, Any]:
    """Save a preset (yours or a built-in) as a file to share: {"path"}."""
    preset = _find(preset_id)
    if not isinstance(dest, str) or not dest.strip() or "\0" in dest or not Path(dest).name:
        raise PresetError("Choose where to save the preset file.")
    path = Path(dest)
    if not path.is_absolute():  # "C:mine" too: it would land wherever the engine is running
        raise PresetError("Saving a preset needs a full path, from the drive or top folder down. Choose where to save it.")
    if path.suffix.lower() != EXT:
        path = path.with_name(path.name + EXT)  # added, never replacing: "Bob v1.2" stays whole
    if _RESERVED.fullmatch(path.name):
        raise PresetError(f"Windows keeps the name “{path.name}” for a device. Choose another name.")
    if _in_data_folder(path):
        raise PresetError("Save the copy somewhere else: LUDD keeps its own files in that folder.")
    if os.path.lexists(path) and not _is_preset_file(path):
        raise PresetError(f"{path.name} already exists and isn't a LUDD preset. Choose another name.")
    try:
        write_json(path, _file(preset["name"], preset))
    except (OSError, ValueError) as exc:
        raise PresetError(f"Couldn't save {path.name}: {getattr(exc, 'strerror', None) or exc}") from exc
    return {"path": str(path)}


def import_file(path: Any) -> dict[str, Any]:
    """Add a preset from a file: {"id", "name", "kind"}. One whose name is already taken is
    added under a numbered name; nothing is replaced."""
    if not isinstance(path, str) or not path.strip() or "\0" in path:
        raise PresetError("Choose a preset file to import.")
    source = Path(path)
    preset = _load(source, source.name or path)
    base = _text(preset["name"], MAX_NAME) or _text(source.stem, MAX_NAME) or "Preset"
    taken = _names(preset["kind"])
    name = base
    for n in itertools.count(2):
        if name.casefold() not in taken:
            break
        name = f"{base[:MAX_NAME - len(str(n)) - 3].rstrip()} ({n})"
    try:
        preset_id = _write_new(name, preset)
    except OSError as exc:
        raise PresetError(f"Couldn't add the preset: {exc.strerror or exc}. Is the disk full?") from exc
    return {"id": preset_id, "name": name, "kind": preset["kind"]}


__all__ = ["PresetError", "check", "delete", "export", "import_file", "list_presets", "save", "settings_of"]
