"""Machine profiles: formats, hoops, cutting behavior and limits.

Built-ins live here; users can add or override profiles as JSON files in
<data dir>/machines/*.json with the same shape (schema: schemas/machine.schema.json).
"""

from __future__ import annotations

import json
import math
from typing import Any

from .storage import data_dir


class ProfileError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


# "cuts": where the machine cuts thread on its own.
#   "trim"         - honors trim commands in the file
#   "color_change" - only at color changes/stops (cut-stops can emulate trims)
#   "none"         - never; every cut is by hand
BUILTIN_MACHINES: list[dict[str, Any]] = [
    {
        "id": "brother-pe550d",
        "name": "Brother PE550D",
        "brand": "Brother",
        "formats": ["pes"],
        "needles": 1,
        "hoops": [{"id": "4x4", "name": '4" × 4" (10 × 10 cm)', "width_mm": 100, "height_mm": 100}],
        "cuts": "color_change",
        "max_stitch_mm": None,
        "max_stitches": None,
        "max_colors": None,
        "notes": (
            "Cuts automatically only at the end of each color (Operation Manual 888-M36, p. 26); "
            "it has no jump stitch trim setting. Use cut-stops to cut jump threads."
        ),
    },
    {
        "id": "janome-generic",
        "name": "Janome (generic)",
        "brand": "Janome",
        "formats": ["jef"],
        "needles": 1,
        "hoops": [
            {"id": "sq14", "name": "SQ14 (14 × 14 cm)", "width_mm": 140, "height_mm": 140},
            {"id": "a", "name": "A (12.6 × 11 cm)", "width_mm": 126, "height_mm": 110},
            {"id": "re20b", "name": "RE20b (14 × 20 cm)", "width_mm": 140, "height_mm": 200},
            {"id": "sq20b", "name": "SQ20b (20 × 20 cm)", "width_mm": 200, "height_mm": 200},
        ],
        "cuts": "trim",
        "max_stitch_mm": 12.7,
        "max_stitches": None,
        "max_colors": None,
        "notes": "Generic profile; check hoop sizes and trim support against your model.",
    },
]

REQUIRED = {"id", "name", "formats", "hoops", "cuts"}


def _positive(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0


def _validate(p: dict[str, Any], source: str) -> dict[str, Any]:
    """The profile with defaults filled in, or ProfileError in plain words (schemas/machine.schema.json)."""
    if not isinstance(p, dict):
        raise ProfileError(f"{source}: not a machine profile")
    missing = REQUIRED - p.keys()
    if missing:
        raise ProfileError(f"{source}: missing {', '.join(sorted(missing))}")
    if not isinstance(p.get("id"), str) or not p["id"] or not isinstance(p.get("name"), str):
        raise ProfileError(f"{source}: id and name must be text")
    if p["cuts"] not in ("trim", "color_change", "none"):
        raise ProfileError(f"{source}: cuts must be trim, color_change or none")
    if not isinstance(p["formats"], list) or not p["formats"] or not all(isinstance(f, str) and f for f in p["formats"]):
        raise ProfileError(f"{source}: formats must list at least one file type, like \"pes\"")
    if not isinstance(p["hoops"], list) or not p["hoops"] or not all(
            isinstance(h, dict) and {"id", "width_mm", "height_mm"} <= h.keys() for h in p["hoops"]):
        raise ProfileError(f"{source}: each hoop needs id, width_mm, height_mm")
    for h in p["hoops"]:
        if not all(_positive(h[k]) for k in ("width_mm", "height_mm")):
            raise ProfileError(f"{source}: hoop {h['id']}: width_mm and height_mm must be numbers above 0")
    for k in ("max_stitch_mm", "max_stitches", "max_colors"):
        if p.get(k) is not None and not _positive(p[k]):
            raise ProfileError(f"{source}: {k} must be a number above 0, or null for no limit")
    return {
        "brand": "",
        "needles": 1,
        "max_stitch_mm": None,
        "max_stitches": None,
        "max_colors": None,
        "notes": "",
        **p,
        "hoops": [{"name": h["id"], **h} for h in p["hoops"]],
    }


def list_machines() -> list[dict[str, Any]]:
    """Built-ins plus user profiles; a user profile with a built-in's id replaces it."""
    by_id = {m["id"]: _validate(m, m["id"]) | {"builtin": True} for m in BUILTIN_MACHINES}
    d = data_dir() / "machines"
    if d.is_dir():
        for f in sorted(d.glob("*.json")):
            try:
                # utf-8-sig: Notepad may save a byte-order mark at the start.
                p = _validate(json.loads(f.read_text(encoding="utf-8-sig")), f.name)
            except (OSError, ValueError, TypeError, AttributeError, ProfileError):
                continue  # a broken user file shouldn't hide the others
            by_id[p["id"]] = p | {"builtin": False}
    return list(by_id.values())


def get_machine(machine_id: str) -> dict[str, Any]:
    for m in list_machines():
        if m["id"] == machine_id:
            return m
    raise ProfileError(f"Unknown machine: {machine_id}")


def get_hoop(machine: dict[str, Any], hoop_id: str | None) -> dict[str, Any]:
    if hoop_id is None:
        return machine["hoops"][0]
    for h in machine["hoops"]:
        if h["id"] == hoop_id:
            return h
    raise ProfileError(f"{machine['name']} has no hoop {hoop_id}")
