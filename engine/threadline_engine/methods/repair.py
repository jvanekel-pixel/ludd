"""RPC methods. Repairs: what a placed stitch file's repairs would change, before accepting them."""

from __future__ import annotations

from ..layout.model import LayoutError
from .registry import dispatcher


@dispatcher.method("repair.preview", background=True)
def repair_preview(layout: dict, item_id: str, ops: list) -> dict:
    """The design as it is, and with `item_id`'s repair ops replaced by `ops` (P4-B1): the numbers
    before and after, the stitches taken out (ranges of `src`, [from, to)), how many were added,
    the densest a spot should be, and notes in plain words."""
    raise LayoutError("not built yet")
