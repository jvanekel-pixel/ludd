"""Thin out spots where the needle hits over and over: the "declump" repair (P4-B3)."""

from __future__ import annotations

from ..layout.model import Block, LayoutError
from ..layout.passes import OpContext


def apply(blocks: list[Block], op: dict, ctx: OpContext) -> list[Block]:
    """The item op, run on the hoop at final size."""
    raise LayoutError("not built yet")
