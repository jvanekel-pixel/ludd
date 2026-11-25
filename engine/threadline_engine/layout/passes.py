"""Render hooks: edits on a placed stitch file (item ops) and steps that look across items (passes).

A new edit on a placed stitch file is an item op registered here; a step that looks across items is
a pass. With every registry empty, rendering is exactly what it was before the hooks existed.

- An item op runs for each op in an item's `ops` whose `op` names it, in list order:
  "local" ops before the item's transform (the file's own frame, 0.1 mm), "placed" ops after it
  (hoop millimetres x 10). Op names nobody registered are ignored, as they always were.
- An "after_items" pass runs once every item is rendered, before empty blocks are dropped and
  before the color sort; an "after_order" pass after sort, join and merge, before knockdown and basting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .model import Block, Transform


@dataclass
class OpContext:
    item: dict  # the layout item
    index: int  # its position in layout["items"]
    transform: Transform  # an op may replace it (e.g. to take over the scaling)
    center: tuple[float, float]  # in 0.1 mm, as _transform takes it
    fabric: str | None
    notes: list[str]  # plain-words notes; render turns them into warnings


ItemOp = Callable[[list[Block], dict, OpContext], list[Block]]  # (blocks, op, ctx) -> blocks
Pass = Callable[[list[Block], dict, list[dict]], list[Block]]  # (blocks, layout, warnings) -> blocks

ITEM_OPS_LOCAL: dict[str, ItemOp] = {}  # run before the item's transform (the file's own frame)
ITEM_OPS_PLACED: dict[str, ItemOp] = {}  # run after it (hoop millimeters x 10)
AFTER_ITEMS: list[tuple[str, Pass]] = []  # after every item is rendered, before color sort
AFTER_ORDER: list[tuple[str, Pass]] = []  # after sort, join and merge; before knockdown and basting

_STAGES = {"local": ITEM_OPS_LOCAL, "placed": ITEM_OPS_PLACED}
_PASSES = {"after_items": AFTER_ITEMS, "after_order": AFTER_ORDER}


def register_item_op(name: str, fn: ItemOp, *, stage: str) -> None:
    """Register an item op for stage "local" or "placed". A name registered twice raises."""
    if stage not in _STAGES:
        raise ValueError(f"Unknown item op stage: {stage}")
    if name in ITEM_OPS_LOCAL or name in ITEM_OPS_PLACED:
        raise ValueError(f"Item op already registered: {name}")
    _STAGES[stage][name] = fn


def register_pass(stage: str, name: str, fn: Pass) -> None:
    """Register a pass for stage "after_items" or "after_order". A name registered twice raises."""
    if stage not in _PASSES:
        raise ValueError(f"Unknown pass stage: {stage}")
    if any(n == name for n, _ in _PASSES[stage]):
        raise ValueError(f"Pass already registered: {name}")
    _PASSES[stage].append((name, fn))


def run_item_ops(registry: dict[str, ItemOp], blocks: list[Block], ctx: OpContext) -> list[Block]:
    """Each op in the item's `ops` that `registry` knows, in list order."""
    for o in ctx.item.get("ops") or []:
        name = o.get("op") if isinstance(o, dict) else None
        fn = registry.get(name) if isinstance(name, str) else None
        if fn is not None:
            blocks = fn(blocks, o, ctx)
    return blocks


def run_passes(stage: list[tuple[str, Pass]], blocks: list[Block], layout: dict, warnings: list[dict]) -> list[Block]:
    for _, fn in stage:
        blocks = fn(blocks, layout, warnings)
    return blocks
