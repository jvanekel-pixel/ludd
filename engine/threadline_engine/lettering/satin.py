"""True satin: each stroke of a letter as a satin column that follows it (P5-B1)."""

from __future__ import annotations

from typing import Any

from shapely.geometry import Polygon

from .fonts import LetteringError


def columns(shape: Polygon, size_mm: float) -> list[dict[str, Any]]:
    """The objects that sew one letter shape (mm, y down) as true satin: a satin column for each
    stroke, and satin-look fills, sewn first, for what isn't a stroke."""
    raise LetteringError("True satin isn't built yet")
