"""Layout model: the error, a placement's transform, a color block and small helpers that every
layout module shares. Imports nothing from the rest of the layout package."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import pyembroidery as pe

from .. import design


M = pe.COMMAND_MASK
SCALE_WARN = 0.20  # warn when an item is scaled more than ±20%


# A record while building: x, y (0.1 mm), command, item index (-1 = layout), source record index (-1 = added).
Rec = list


class LayoutError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


@dataclass
class Transform:
    x: float = 0.0  # mm
    y: float = 0.0
    rotate: float = 0.0  # degrees, clockwise on screen
    scale_x: float = 1.0
    scale_y: float = 1.0
    flip_x: bool = False  # mirror left-right
    flip_y: bool = False  # mirror top-bottom

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "Transform":
        d = d or {}
        t = cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})
        if t.scale_x <= 0 or t.scale_y <= 0:
            raise LayoutError("Size must be greater than zero")
        return t

    def is_identity(self) -> bool:
        return self == Transform()


@dataclass
class Block:
    thread: dict[str, str]
    recs: list[Rec]
    sources: list[tuple[int, int]] = field(default_factory=list)  # (item, source block)
    original: dict[str, str] | None = None  # the file's thread, before any recolor
    digitized: bool = False  # from a drawn object (not a stitch file)


def _thread_dict(t: pe.EmbThread | None) -> dict[str, str]:
    return design._thread(t)


def _stitch_bounds(recs: list[Rec]) -> tuple[float, float, float, float] | None:
    pts = [(r[0], r[1]) for r in recs if r[2] == pe.STITCH]
    if not pts:
        return None
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)


def _index(v: Any) -> int | None:
    """A record index from an op, or None if it isn't one (a damaged or hand-edited project)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 or v != int(v):
        return None
    return int(v)


def _mm(v: Any) -> float | None:
    """A finite distance from an op (missing counts as 0), or None if it isn't a number."""
    if v is None:
        return 0.0
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def _record_count(blocks: list[Block]) -> int:
    return 1 + max((r[4] for b in blocks for r in b.recs), default=-1)


def _thread_key(t: dict[str, str]) -> tuple[str, str, str]:
    return (t.get("color", "").lower(), t.get("brand", "").lower(), t.get("catalog", "") or t.get("name", "").lower())
