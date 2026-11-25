"""Layouts: one or more stitch files placed together and edited without touching the files.

A layout is plain JSON (the UI keeps it and its undo history):

    {
      "items": [{
        "id": "a1", "path": "C:/designs/key.pes",
        "transform": {"x": 0, "y": 0, "rotate": 0, "scale_x": 1, "scale_y": 1, "flip_x": false, "flip_y": false},
        "threads": [null, {"color": "#123456", "name": "Navy", "catalog": "1043", "brand": "Madeira Rayon"}],
        "ops": [{"op": "delete_block", "block": 2}, {"op": "insert", "after": 120, "command": "stop"}]
      }],
      "merge_colors": false, "color_sort": false,
      "basting": {"enabled": false, "margin_mm": 5}
    }

Indices in ops and `threads` refer to the item's source file, so edits never shift each other.
Rendering returns the usual design summary plus, per record, which item and source record
it came from, so the UI can map a click or the player position back to an edit.

The package (it was one module, layout.py, until Phase 3):
  model    LayoutError, Transform, Block, small helpers (imports nothing from the package)
  files    placed stitch files: load, ops, transform
  objects  drawn shapes -> blocks
  text     lettering -> blocks
  joins    same-thread joins, cover, footprint, color sort
  extras   basting, knockdown, applique SVG
  passes   render hooks: item ops and passes (empty until a feature registers one)
  render   render, render_summary, check
  order    optimize_order
  export   export, preview_export, split

Every name the old module had is re-exported here: the same objects, so `layout._text_cache` is
the dict `text` uses. A test that replaces a module global patches the module that reads it
(`layout.files._CACHE_MAX`, not `layout._CACHE_MAX`).
"""

from __future__ import annotations

# The submodules, imported by name so PyInstaller sees each one.
from . import model, files, objects, text, joins, extras, passes, order  # noqa: F401  (render, export below)
from . import render as _render_module, export as _export_module  # noqa: F401

from shapely.geometry import LineString, MultiLineString  # noqa: F401  (old module names)

from .model import (M, SCALE_WARN, Block, LayoutError, Rec, Transform, _index, _mm, _record_count,  # noqa: F401
                    _stitch_bounds, _thread_dict, _thread_key)
from .files import (_CACHE_MAX, _apply_ops, _cache, _jumps_to_trims, _load, _move_stitches,  # noqa: F401
                    _split_blocks, _transform)
from .objects import (DEFAULT_THREAD, OBJECT_KINDS, OBJECT_LABEL, _OBJECT_CACHE_MAX, _generate_cached,  # noqa: F401
                      _object_blocks, _object_cache)
from .text import _letter_ring, _text_block, _text_cache, text_letters, text_to_shapes  # noqa: F401
from .joins import (COVER_CLOSE_MM, _blocks_overlap, _cover, _cover_cache, _footprint, _footprint_cache,  # noqa: F401
                    _join, _join_objects, _join_same_thread_objects, _merge_same, _sort_by_thread)
from .order import optimize_order  # noqa: F401
from .extras import (BASTING_MIN_MM, BASTING_STITCH_MM, BASTING_THREAD, KNOCKDOWN_SPACING_MM,  # noqa: F401
                     KNOCKDOWN_THREAD, _basting, _knockdown, _stitched_area, _xml, applique_svg, export_applique_svg)
# Last: these names are also submodules (render.py, export.py); the package's `render` and
# `export` are the functions, as they always were.
from .render import Rendered, _names, check, render, render_summary  # noqa: F401,E402
from .export import export, export_split, preview_export, split_plan  # noqa: F401,E402
