"""Leave out a placed stitch file's stitches that lie under designs sewn after it: the
"remove_hidden" repair (P4-A1).

Held: the competitive review says removing hidden stitches under merged designs is patented, and the
owner hasn't had the patent checked (the Phase 4 spec's owner decision 1), so it isn't built. The
Repair dialog leaves it out, nothing adds the op, and a project that asks for it says so plainly
instead of sewing it as if it had been done."""

from __future__ import annotations

from ..layout.model import Block, LayoutError


def _asked(layout: dict) -> bool:
    return any(isinstance(o, dict) and o.get("op") == "remove_hidden"
               for item in layout.get("items") or [] if isinstance(item, dict)
               for o in item.get("ops") or [])


def apply(blocks: list[Block], layout: dict, warnings: list[dict]) -> list[Block]:
    """The "after_items" pass."""
    if _asked(layout):
        raise LayoutError("not built yet")
    return blocks
