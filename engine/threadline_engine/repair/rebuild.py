"""Rebuild a resized stitch file's fills, satins and runs at the new size, with the original
spacing and stitch length: the "rebuild" repair (P4-C2)."""

from __future__ import annotations

from ..layout.model import Block, LayoutError
from ..layout.passes import OpContext


def apply(blocks: list[Block], op: dict, ctx: OpContext) -> list[Block]:
    """The item op, run in the file's own frame, before the item's transform. It takes over the
    scaling: it writes the stitches at final size and sets ctx.transform's scale to 1."""
    raise LayoutError("not built yet")
