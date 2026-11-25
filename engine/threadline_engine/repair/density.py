"""Limit density for the fabric: the "density_limit" repair (P4-C3). Fills and satins in a stitch
file that are denser than the layout's fabric takes are remade at that fabric's normal spacing; the
limits live here and in fabrics.py."""

from __future__ import annotations

from ..layout.model import Block, LayoutError
from ..layout.passes import OpContext


def apply(blocks: list[Block], op: dict, ctx: OpContext) -> list[Block]:
    """The item op, run on the hoop at final size, with the layout's fabric (ctx.fabric)."""
    raise LayoutError("not built yet")
