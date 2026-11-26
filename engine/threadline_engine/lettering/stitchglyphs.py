"""Letters made of stitches: the glyphs of a version 2 stitch font (P5-C1).

A stitched letter is a letter part of kind "stitches" whose geometry.nodes are its stitches
([x, y, k] in mm from the letter's origin on the baseline, y down; k is "s" stitch, "j" jump or
"t" trim), so placing, slanting, bending and single-letter changes move it like any other part."""

from __future__ import annotations

from typing import Any

from .fonts import LetteringError

NOT_BUILT = "Letters made of stitches aren't built yet"


def letter_objects(font: dict[str, Any], glyph: dict[str, Any], scale: float) -> list[dict[str, Any]]:
    """A version 2 font's glyph as letter parts, scaled by `scale`: one per color block of the
    glyph, each with its color number ("color_index", 0 first) and, in a font with several
    colors, the font's thread for that color ("thread"). A one-color font's parts have no thread:
    they sew in the text's."""
    raise LetteringError(NOT_BUILT)


def size_notes(path: str, size_mm: float) -> list[str]:
    """What to say about letters `size_mm` tall from the stitch font at `path` (layout_text asks
    once per text): stitched letters resize like stitch files, so far from the font's own height
    they need a note. Nothing until P5-C1."""
    return []


def records(obj: dict[str, Any]) -> list[tuple[float, float, int]]:
    """A "stitches" part's stitches as (x mm, y mm, pyembroidery command)."""
    raise LetteringError(NOT_BUILT)
