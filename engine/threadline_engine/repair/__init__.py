"""Repairs for placed stitch files, and "Don't sew what's hidden" for drawn fills. Each is registered
on a render hook (layout/passes.py). A repair is an edit on the item, applied when the design is
drawn or saved; the stitch file on disk is never changed.

  small      remove tiny stitches: the "filter_small" op, on the hoop
  clumps     thin out spots the needle hits over and over: "declump", on the hoop
  density    limit density for the fabric: "density_limit", on the hoop
  rebuild    remake fills, satins and runs at a new size: "rebuild", in the file's own frame
  recognize  find the fills, satins and runs inside a stitch run
  hidden     leave out stitches under designs sewn later: "remove_hidden", after every item (held)
  overlap    drawn fills leave out what shapes on top cover: "remove_overlap", before any item
  stats      the numbers repair.preview reports
"""

from __future__ import annotations

from ..layout import passes
from . import clumps, density, hidden, overlap, rebuild, recognize, small, stats  # noqa: F401 (PyInstaller sees each)

passes.register_item_op("rebuild", rebuild.apply, stage="local")
passes.register_item_op("filter_small", small.apply, stage="placed")
passes.register_item_op("declump", clumps.apply, stage="placed")
passes.register_item_op("density_limit", density.apply, stage="placed")
passes.register_pass("before_items", "remove_overlap", overlap.apply)
passes.register_pass("after_items", "remove_hidden", hidden.apply)
