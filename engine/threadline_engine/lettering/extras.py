"""What a text sews besides its letters: a shadow before them, and an outline and a monogram's
frame after them (P5-D3 and P5-D2)."""

from __future__ import annotations

from typing import Any


def build(spec: dict[str, Any], letters: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(before, after): extra shapes sewn before the letters (a shadow) and after them (an
    outline, a frame).

    `spec` is what the letters were laid out from (lettering.TEXT_SPEC_KEYS; missing ones are
    None). `letters` are the letter parts as they will be sewn, single-letter changes included,
    in the text's own unturned frame (mm). Each extra is a shape like a letter part (kind,
    geometry, params) with what it is ("extra": "shadow", "outline" or "frame") and its
    "thread" (None: the text's)."""
    return [], []
