"""RPC methods. Artwork import (SVG, DXF, PDF): a preview of the shapes it would become."""

from __future__ import annotations

from ..layout import LayoutError
from .registry import dispatcher


@dispatcher.method("art.preview", background=True)
def art_preview(path: str, options: dict | None = None) -> dict:
    """{size_mm, scale_note, shapes, skipped, warnings} for the artwork at `path`; nothing is
    added to a design here."""
    raise LayoutError("not built yet")
