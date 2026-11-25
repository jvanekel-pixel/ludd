"""The numbers repair.preview reports for a design before and after (P4-B1): stitches, trims,
jumps, tiny stitches, the longest stitch, the densest spot and the most needle hits in one spot."""

from __future__ import annotations

from ..layout.model import LayoutError


def numbers(rendered, item: int) -> dict:
    """The preview's numbers for the rendered layout's item at position `item`."""
    raise LayoutError("not built yet")
