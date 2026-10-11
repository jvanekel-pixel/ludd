"""Fabric presets: what the design is stitched on changes how it should be stitched.

Stretchy and lofty fabrics pull stitches in more (more pull compensation), need a firmer
foundation (more underlay) and a cut-away stabilizer; pile fabrics (towels, fleece) need a
topping so stitches don't sink. A preset sets the defaults; anything a user sets on an object wins.

Numbers are common digitizing starting points (woven cotton is the reference), to be confirmed
by stitch-outs (docs/stitchout-log.md).
"""

from __future__ import annotations

from typing import Any

DEFAULT_FABRIC = "woven"

# density: >1 sews rows closer together, <1 further apart (spacing is divided by it).
# underlay: how much foundation stitching goes under satins and fills: light | normal | heavy.
FABRICS: list[dict[str, Any]] = [
    {
        "id": "woven", "name": "Cotton or other woven", "examples": "Quilting cotton, shirts, tote bags, linen",
        "density": 1.0, "pull_comp_mm": 0.2, "underlay": "normal",
        "stabilizer": "Medium tear-away", "topping": None,
    },
    {
        "id": "denim", "name": "Denim or canvas", "examples": "Jeans, jackets, heavy bags",
        "density": 1.0, "pull_comp_mm": 0.15, "underlay": "light",
        "stabilizer": "Medium tear-away", "topping": None,
    },
    {
        "id": "knit", "name": "T-shirt knit", "examples": "T-shirts, jersey, polo shirts",
        "density": 0.9, "pull_comp_mm": 0.35, "underlay": "heavy",
        "stabilizer": "No-show mesh cut-away, fused or sprayed to the back", "topping": None,
    },
    {
        "id": "fleece", "name": "Fleece or sweatshirt", "examples": "Hoodies, sweatshirts, blankets",
        "density": 0.95, "pull_comp_mm": 0.35, "underlay": "heavy",
        "stabilizer": "Cut-away", "topping": "Water-soluble topping, so stitches sit on top of the pile",
    },
    {
        "id": "towel", "name": "Towel or terry", "examples": "Towels, bathrobes, bibs",
        "density": 1.1, "pull_comp_mm": 0.3, "underlay": "heavy",
        "stabilizer": "Tear-away or wash-away", "topping": "Water-soluble topping, so stitches don't sink into the loops",
    },
    {
        "id": "stretch", "name": "Stretchy sportswear", "examples": "Leggings, performance shirts, swimwear",
        "density": 0.85, "pull_comp_mm": 0.4, "underlay": "heavy",
        "stabilizer": "Two layers of no-show mesh cut-away", "topping": None,
    },
    {
        "id": "felt", "name": "Felt", "examples": "Craft felt, patches, ornaments",
        "density": 0.9, "pull_comp_mm": 0.1, "underlay": "light",
        "stabilizer": "Tear-away, or none for thick felt", "topping": None,
    },
]
_BY_ID = {f["id"]: f for f in FABRICS}


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
    base = float(p.get("spacing_mm", 0.4))
    p["spacing_mm"] = round(min(max(base / f["density"], 0.2), 3.0), 3)
    if p.get("pull_comp_mm") is None:
        p["pull_comp_mm"] = f["pull_comp_mm"]
        p["comp_by_width"] = kind == "satin"  # wider columns pull in more
    if p.get("underlay") is None:
        p["underlay"] = "auto"
        p["underlay_level"] = f["underlay"]
    if kind == "satin":
        p.setdefault("auto_widen", True)
    return {**obj, "params": p}


def advice(fabric_id: str | None) -> str:
    f = get(fabric_id)
    text = f"Stabilizer: {f['stabilizer']}."
    if f["topping"]:
        text += f" Topping: {f['topping']}."
    return text
