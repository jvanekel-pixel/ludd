"""RPC methods. Stitch fonts made from letter files (the font list itself is in text.py)."""

from __future__ import annotations

from ..lettering import fontbuild
from .registry import dispatcher


@dispatcher.method("fonts.scan_letter_files")
def fonts_scan_letter_files(folder: str = "", files: list | None = None) -> dict:
    """The single-letter designs in a folder (or the files picked), each with the character
    LUDD guesses it is."""
    return fontbuild.scan_letter_files(folder, files)


@dispatcher.method("fonts.build_from_files")
def fonts_build_from_files(letters: list, name: str, gap_pct: float = 8, dest: str = "") -> dict:
    """A stitch font from letter files, saved where the font list finds it."""
    return fontbuild.build_from_files(letters, name, gap_pct, dest)
