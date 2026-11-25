""""Don't sew what's hidden under shapes on top" (P4-A2): when layout["remove_overlap"] is on, a
drawn fill leaves out the part of itself that a shape sewn later covers, keeping a margin tucked
under the edge."""

from __future__ import annotations

from ..layout.model import LayoutError


def apply(layout: dict) -> dict:
    """The "before_items" pass: the layout with the covered parts added to the lower fills' holes."""
    settings = layout.get("remove_overlap")
    if isinstance(settings, dict) and settings.get("enabled"):
        raise LayoutError("not built yet")
    return layout
