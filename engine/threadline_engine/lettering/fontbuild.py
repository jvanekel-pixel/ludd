"""A stitch font made from a folder of single-letter stitch files (P5-C1)."""

from __future__ import annotations

from typing import Any

from .fonts import LetteringError

NOT_BUILT = "Making a stitch font from letter files isn't built yet"


def scan_letter_files(folder: str = "", files: list[str] | None = None) -> dict[str, Any]:
    """The letter files in `folder` (or the `files` named): {"files": [{path, name, guess,
    thumb, width_mm, height_mm, stitches, colors}], "common": {prefix, suffix}}."""
    raise LetteringError(NOT_BUILT)


def build_from_files(letters: list[dict[str, Any]], name: str, gap_pct: float = 8, dest: str = "") -> dict[str, Any]:
    """A version 2 .luddfont from `letters` [{path, char, dy_mm?}]: {path, glyphs,
    cap_height_mm, folder}. `dest` empty: a new file in LUDD's fonts folder."""
    raise LetteringError(NOT_BUILT)
