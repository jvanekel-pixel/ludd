"""Lettering: text from TrueType/OpenType fonts (or LUDD stitch fonts) as stitched letters.

Each letter's outline becomes fill objects (outer shapes with their holes). Two looks:
  satin  long side-to-side stitches across each stroke, like satin lettering (rows narrower
         than the maximum stitch become single stitches); the angle is chosen per letter to
         cross its strokes best
  fill   tatami, for big, bold letters

Text can run along a straight line, over an arc, under an arc, round a circle, or as a
three-letter monogram. Stitch fonts (.luddfont) are an open JSON format: letters as LUDD
objects, which can be made from any installed font and then hand-tuned.

The package (it was one module, lettering.py, until Phase 5):
  fonts     installed fonts, outline fonts as loaded, kerning, letter shapes
  glyphs    each character as a letter: outline fonts and stitch fonts
  place     putting letters together: lines, arches, circles, a drawn line, centring
  monogram  the monogram layout
  fontfile  stitch fonts: reading them, and making one from an installed font

Every name the old module had is re-exported here: the same objects. A test that replaces a
module global patches the module that reads it (`lettering.fonts.list_fonts`, not
`lettering.list_fonts`). layout/text.py calls `lettering.layout_text` through this package.
"""

from __future__ import annotations

# The submodules, imported by name so PyInstaller sees each one.
from . import fonts, fontfile, glyphs, place, monogram  # noqa: F401

from .fonts import (FONT_EXTS, INDEX_VERSION, STAND_IN_FAMILIES, STITCH_FONT_EXTS, STITCH_FONT_FORMATS,  # noqa: F401
                    LetteringError, LoadedFont, _FlattenPen, _fonts, _glyph_shapes, _gpos_pair, _gpos_subtables,
                    _is_symbol, _load, _names, _signed_area, _stamp, _winding, _x_advance, font_dirs, font_stamp,
                    list_fonts, resolve_font, substitute_font)
from .fontfile import EXTRA_CHARS, _free_path, _load_stitch_font, export_stitch_font, stitch_font_dir  # noqa: F401
from .glyphs import (SATIN_MAX_STITCH_MM, SMALL_TEXT_MM, Glyph, _Missing, _PARAMS, _Scale, _check_letter_object,  # noqa: F401
                     _fill_object, _near_letter, _outline_glyphs, _satin_angle, _stitch_font_glyphs)
from .place import _Turn, _along_path, _centre, _clean_text, _move, layout_text, turn_with  # noqa: F401
