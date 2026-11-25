"""RPC methods. Repairs: what a placed stitch file's repairs would change, before accepting them."""

from __future__ import annotations

from collections import Counter
from typing import Any

import pyembroidery as pe

from .. import kept, quality
from .. import layout as layout_module
from ..layout.model import LayoutError
from ..repair import stats
from .registry import dispatcher

#: The order repairs are written in, whatever order they're given (feat/repair/steps.ts).
REPAIR_ORDER = ("rebuild", "filter_small", "declump", "density_limit", "remove_hidden")


def _is_repair(op: Any) -> bool:
    return isinstance(op, dict) and isinstance(op.get("op"), str) and op["op"] in kept.REPAIR_OPS


def _with_repairs(item: dict, repairs: list) -> dict:
    """The item with its repair ops replaced by `repairs`: one of each (the last given wins), after
    its other edits, in REPAIR_ORDER."""
    chosen = {o["op"]: o for o in repairs if _is_repair(o)}
    others = [o for o in item.get("ops") or [] if not _is_repair(o)]
    return {**item, "ops": others + [chosen[name] for name in REPAIR_ORDER if name in chosen]}


def _stitch_file(layout: Any, item_id: str) -> int:
    """The position of the stitch file called `item_id` in the layout."""
    items = layout.get("items") if isinstance(layout, dict) else None
    for i, item in enumerate(items or []):
        if isinstance(item, dict) and str(item.get("id", i)) == str(item_id):
            if item.get("kind") not in (None, "file"):
                raise LayoutError("Repairs work on stitch files, not on shapes or lettering.")
            return i
    raise LayoutError("That design isn't in the layout any more.")


def _stitches(rendered, item: int) -> tuple[set[int], Counter]:
    """The item's stitches as sewn: the numbers of those from its file (or added by stitch
    editing), and where the ones a repair added are."""
    numbered: set[int] = set()
    added: Counter = Counter()
    for (x, y, command), owner, src in zip(rendered.pattern.stitches, rendered.item_of, rendered.src_of):
        if owner == item and command & pe.COMMAND_MASK == pe.STITCH:
            if src >= 0:
                numbered.add(src)
            else:
                added[(round(x, 2), round(y, 2))] += 1
    return numbered, added


def _ranges(numbers: list[int]) -> list[list[int]]:
    """Sorted numbers as [from, to) ranges."""
    out: list[list[int]] = []
    for n in numbers:
        if out and out[-1][1] == n:
            out[-1][1] = n + 1
        else:
            out.append([n, n + 1])
    return out


def _notes(rendered, item: int) -> list[str]:
    """What the render said about the item, without its name in front."""
    name = f"{rendered.items[item]['name']}: "
    return [w["message"].removeprefix(name) for w in rendered.warnings if w["code"].startswith(f"item_{item}_")]


@dispatcher.method("repair.preview", background=True)
def repair_preview(layout: dict, item_id: str, ops: list) -> dict:
    """The design as it is, and with `item_id`'s repair ops replaced by `ops` (P4-B1): the numbers
    before and after, the stitches taken out (ranges of `src`, [from, to)), how many were added,
    the densest a spot should be, and notes in plain words."""
    item = _stitch_file(layout, item_id)
    if not isinstance(ops, list):
        raise LayoutError("The repairs to try must be a list.")
    items = layout["items"]
    changed = {**layout, "items": [*items[:item], _with_repairs(items[item], ops), *items[item + 1:]]}
    # Off the main loop (it renders the design twice), taking the lock only for each render (they
    # use the shared caches), so an edit's render can run in between.
    with dispatcher.lock:
        before = layout_module.render(layout)
    with dispatcher.lock:
        after = layout_module.render(changed)
    was, was_added = _stitches(before, item)
    now, now_added = _stitches(after, item)
    return {
        "before": stats.numbers(before, item),
        "after": stats.numbers(after, item),
        "removed": _ranges(sorted(was - now)),
        "added": len(now - was) + sum((now_added - was_added).values()),
        "limit": quality.DENSE_MM_PER_MM2,
        "notes": _notes(after, item),
    }
