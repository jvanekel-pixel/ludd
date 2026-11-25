"""RPC methods. Lettering and fonts."""

from __future__ import annotations

from .. import layout as layout_module, lettering
from .registry import dispatcher


@dispatcher.method("text.to_shapes")
def text_to_shapes(item: dict) -> dict:
    """Lettering as drawn shapes, one per letter part, to edit like any other shape."""
    return layout_module.text_to_shapes(item)


@dispatcher.method("text.letter_frame")
def text_letter_frame(item: dict, at: list) -> list:
    """A point on the design (mm) in a text's own unturned frame, where its letters' chosen starts
    and ends are kept."""
    t = layout_module.Transform.from_dict(item.get("transform"))
    from ..jumps import _unturn

    return list(_unturn(t, (float(at[0]) - t.x, float(at[1]) - t.y)))


@dispatcher.method("fonts.list")
def fonts_list() -> list:
    return lettering.list_fonts()


@dispatcher.method("fonts.export_stitch_font")
def fonts_export_stitch_font(font: dict, dest: str, chars: str, cap_height_mm: float = 12.0, style: str = "satin", name: str = "") -> dict:
    return lettering.export_stitch_font(font, dest, chars, cap_height_mm, style, name)
