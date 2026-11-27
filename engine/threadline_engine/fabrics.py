"""Fabric presets: what the design is stitched on changes how it should be stitched.

Stretchy and lofty fabrics pull stitches in more (more pull compensation), need a firmer
foundation (more underlay) and a cut-away stabilizer; pile fabrics (towels, fleece) need a
topping so stitches don't sink. A preset sets the defaults; anything a user sets on an object wins.

Numbers are common digitizing starting points (woven cotton is the reference), to be confirmed
by stitch-outs (docs/stitchout-log.md).
"""

from __future__ import annotations

import math
from typing import Any

DEFAULT_FABRIC = "woven"

# density: >1 sews rows closer together, <1 further apart (spacing is divided by it).
# underlay: how much foundation stitching goes under satins and fills: light | normal | heavy.
# push_comp_mm: how much shorter ends would be drawn for push ("End trim"); nothing reads it yet
# (push compensation isn't built).
FABRICS: list[dict[str, Any]] = [
    {
        "id": "woven", "name": "Cotton or other woven", "examples": "Quilting cotton, shirts, tote bags, linen",
        "density": 1.0, "pull_comp_mm": 0.2, "underlay": "normal", "push_comp_mm": 0.2,
        "stabilizer": "Medium tear-away", "topping": None,
    },
    {
        "id": "denim", "name": "Denim or canvas", "examples": "Jeans, jackets, heavy bags",
        "density": 1.0, "pull_comp_mm": 0.15, "underlay": "light", "push_comp_mm": 0.15,
        "stabilizer": "Medium tear-away", "topping": None,
    },
    {
        "id": "knit", "name": "T-shirt knit", "examples": "T-shirts, jersey, polo shirts",
        "density": 0.9, "pull_comp_mm": 0.35, "underlay": "heavy", "push_comp_mm": 0.3,
        "stabilizer": "No-show mesh cut-away, fused or sprayed to the back", "topping": None,
    },
    {
        "id": "fleece", "name": "Fleece or sweatshirt", "examples": "Hoodies, sweatshirts, blankets",
        "density": 0.95, "pull_comp_mm": 0.35, "underlay": "heavy", "push_comp_mm": 0.3,
        "stabilizer": "Cut-away", "topping": "Water-soluble topping, so stitches sit on top of the pile",
        "knockdown": True,
    },
    {
        "id": "towel", "name": "Towel or terry", "examples": "Towels, bathrobes, bibs",
        "density": 1.1, "pull_comp_mm": 0.3, "underlay": "heavy", "push_comp_mm": 0.3,
        "stabilizer": "Tear-away or wash-away", "topping": "Water-soluble topping, so stitches don't sink into the loops",
        "knockdown": True,
    },
    {
        "id": "stretch", "name": "Stretchy sportswear", "examples": "Leggings, performance shirts, swimwear",
        "density": 0.85, "pull_comp_mm": 0.4, "underlay": "heavy", "push_comp_mm": 0.35,
        "stabilizer": "Two layers of no-show mesh cut-away", "topping": None,
    },
    {
        "id": "felt", "name": "Felt", "examples": "Craft felt, patches, ornaments",
        "density": 0.9, "pull_comp_mm": 0.1, "underlay": "light", "push_comp_mm": 0.1,
        "stabilizer": "Tear-away, or none for thick felt", "topping": None,
    },
]
_BY_ID = {f["id"]: f for f in FABRICS}

# Limit density for this fabric (repair/density.py): in a placed stitch file, fills and satins whose
# spacing is under the first number (mm, on woven cotton) are remade at the second. Each fabric
# divides both by its density factor, as it does every spacing. First guesses, to be tuned with the
# stitch-outs (Phase 16). Satin spacing is between stitches on one side.
DENSITY_LIMITS: dict[str, tuple[float, float]] = {
    "fill": (0.33, 0.40),
    "satin": (0.30, 0.36),
}


def get(fabric_id: str | None) -> dict[str, Any]:
    return _BY_ID.get(fabric_id or DEFAULT_FABRIC, _BY_ID[DEFAULT_FABRIC])


def apply(obj: dict[str, Any], fabric_id: str | None) -> dict[str, Any]:
    """The object with its stitch settings for this fabric. Settings the user left on automatic
    (no pull compensation or underlay of their own) come from the fabric; spacing is scaled."""
    kind = obj.get("kind")
    if kind not in ("satin", "fill"):
        return obj
    f = get(fabric_id)
    p = dict(obj.get("params") or {})
    try:
        base = float(p["spacing_mm"]) if p.get("spacing_mm") is not None else 0.4
    except (TypeError, ValueError):
        base = math.nan  # left for the stitch type to refuse in plain words (QA2 S6)
    # Kept within what each stitch type accepts (satin 0.15-3 mm, fill 0.2-5 mm).
    lo, hi = (0.15, 3.0) if kind == "satin" else (0.2, 5.0)
    if math.isfinite(base) and base > 0:
        p["spacing_mm"] = round(min(max(base / f["density"], lo), hi), 3)
    # (0, negative or not a number: left as it is, so the stitch type says what's wrong instead of
    # quietly sewing at the densest setting.)
    if p.get("pull_comp_mm") is None:
        p["pull_comp_mm"] = f["pull_comp_mm"]
        p["comp_by_width"] = kind == "satin"  # wider columns pull in more
    if p.get("underlay") is None:
        p["underlay"] = "auto"
        p["underlay_level"] = f["underlay"]
    elif p["underlay"] == "auto":  # chosen by width already (True satin letters): at the fabric's amount
        p.setdefault("underlay_level", f["underlay"])
    if kind == "satin":
        p.setdefault("auto_widen", True)
    return {**obj, "params": p}


def advice(fabric_id: str | None) -> str:
    f = get(fabric_id)
    text = f"Stabilizer: {f['stabilizer']}."
    if f["topping"]:
        text += f" Topping: {f['topping']}."
    if f.get("knockdown"):
        text += " For small lettering or detail, turn on Knockdown stitches (Ctrl+Shift+N) to flatten the pile first."
    return text
