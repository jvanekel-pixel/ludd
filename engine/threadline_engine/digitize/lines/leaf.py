"""The leaf motif: a pair of leaves on a stem, one each side, angled along the line. The
laurel monogram frame is made with it, and any line can use it."""

from __future__ import annotations

from . import register_motif

# One leaf, drawn out from the stem along its outer edge to the tip and back along its inner edge.
_LEAF = [(0.15, 0.0), (0.25, -0.24), (0.44, -0.42), (0.80, -0.50), (0.70, -0.27), (0.50, -0.11), (0.30, -0.03),
         (0.15, 0.0)]

register_motif("leaf", [(0.0, 0.0), *_LEAF, *[(u, -v) for u, v in _LEAF[1:]], (1.0, 0.0)])
