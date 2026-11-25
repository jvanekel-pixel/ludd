"""Rendering a layout into one stitch pattern, its summary for the UI and the quality checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyembroidery as pe

from .. import design, fabrics, kept, quality
from . import passes
from .extras import BASTING_MIN_MM, _basting, _knockdown
from .files import _apply_ops, _load, _move_stitches, _split_blocks, _transform
from .joins import _join_same_thread_objects, _merge_same, _sort_by_thread
from .model import SCALE_WARN, Block, LayoutError, Transform, _mm, _stitch_bounds
from .objects import OBJECT_KINDS, OBJECT_LABEL, _object_blocks
from .text import _text_block


@dataclass
class Rendered:
    pattern: pe.EmbPattern
    item_of: list[int]
    src_of: list[int]
    blocks: list[Block]
    items: list[dict[str, Any]]
    warnings: list[dict[str, str]]


def render(layout: dict[str, Any]) -> Rendered:
    whole = layout.get("items") or []
    if not whole:
        raise LayoutError("Nothing to show: the layout has no designs")
    # Render hooks (layout/passes.py): passes that change the layout before any item is made.
    layout, warnings = passes.run_before_items(layout)
    items = layout.get("items") or []
    all_blocks: list[Block] = []
    item_info: list[dict[str, Any]] = []

    # "Trim jumps longer than …" for the whole design (older projects keep it as an op per item).
    jt_mm = _mm(layout.get("jumps_to_trims")) if layout.get("jumps_to_trims") is not None else None
    pinned = kept.pinned(items)

    for idx, it in enumerate(items):
        if it.get("kind") == "text":
            block, text_warnings, centre, parts = _text_block(it, idx, layout.get("fabric"))
            text_warnings = list(text_warnings)
            blocks = _apply_ops([block], it.get("ops") or [], jt_mm, text_warnings, generated=True)
            b = _stitch_bounds([r for blk in blocks for r in blk.recs])
            name = it.get("name") or f"“{str(it.get('text', '')).strip()[:24]}”"
            item_info.append({
                "id": it.get("id", str(idx)),
                "name": name,
                "kind": "text",
                "letters": parts,
                "center_mm": list(centre),
                "bounds_mm": [v / 10 for v in b] if b else None,
                "source_size_mm": None,
            })
            warnings += [{"level": "warning", "code": f"text_{idx}_{n}", "message": f"{name}: {w}"} for n, w in enumerate(text_warnings)]
            all_blocks.extend(blk for blk in blocks if blk.recs)
            continue
        if it.get("kind", "file") in OBJECT_KINDS:
            blocks, geo, obj_warnings = _object_blocks(it, idx, layout.get("fabric"))
            obj_warnings = list(obj_warnings)
            blocks = _apply_ops(blocks, it.get("ops") or [], jt_mm, obj_warnings, generated=True)
            # A shape measures as itself, whatever a pass left out of it: the size boxes, the
            # selection and alignment use these bounds, and a typed width resizes from them.
            measured = blocks
            if idx < len(whole) and whole[idx] is not it:
                measured = _apply_ops(_object_blocks(whole[idx], idx, layout.get("fabric"))[0],
                                      it.get("ops") or [], jt_mm, [], generated=True)
            b = _stitch_bounds([r for blk in measured for r in blk.recs])
            name = it.get("name") or f"{OBJECT_LABEL[it['kind']]} {idx + 1}"
            item_info.append({
                "id": it.get("id", str(idx)),
                "name": name,
                "kind": it["kind"],
                "center_mm": [geo["center"][0] + geo["t"].x, geo["center"][1] + geo["t"].y],
                "bounds_mm": [v / 10 for v in b] if b else None,
                "source_size_mm": None,
            })
            warnings += [{"level": "warning", "code": f"object_{idx}_{n}", "message": f"{name}: {w}"}
                         for n, w in enumerate(obj_warnings)]
            all_blocks.extend(blk for blk in blocks if blk.recs)
            continue
        src = _load(it["path"], it["path"] in pinned)
        blocks = _split_blocks(src, idx)
        center_b = _stitch_bounds([r for b in blocks for r in b.recs])
        center = ((center_b[0] + center_b[2]) / 2, (center_b[1] + center_b[3]) / 2) if center_b else (0.0, 0.0)
        for b, t in enumerate(it.get("threads") or []):
            if t and b < len(blocks):
                blocks[b].thread = {k: str(t.get(k, "")) for k in ("color", "name", "catalog", "brand")}
        notes: list[str] = []  # plain-words notes about this item's edits and repairs
        blocks = _apply_ops(blocks, it.get("ops") or [], jt_mm, notes)
        _move_stitches(blocks, it.get("ops") or [], local=True)
        t = Transform.from_dict(it.get("transform"))
        # Render hooks (layout/passes.py): registered item ops, in the file's own frame, then placed.
        ctx = passes.OpContext(it, idx, t, center, layout.get("fabric"), notes)
        blocks = passes.run_item_ops(passes.ITEM_OPS_LOCAL, blocks, ctx)
        t = ctx.transform
        _transform(blocks, t, center)
        _move_stitches(blocks, it.get("ops") or [], local=False)
        blocks = passes.run_item_ops(passes.ITEM_OPS_PLACED, blocks, ctx)
        b = _stitch_bounds([r for blk in blocks for r in blk.recs])
        name = it.get("name") or Path(it["path"]).name
        warnings += [{"level": "warning", "code": f"item_{idx}_{n}", "message": f"{name}: {w}"}
                     for n, w in enumerate(ctx.notes)]
        item_info.append({
            "id": it.get("id", str(idx)),
            "name": name,
            "kind": "file",
            "center_mm": [center[0] / 10 + t.x, center[1] / 10 + t.y],
            "bounds_mm": [v / 10 for v in b] if b else None,
            "source_size_mm": [(center_b[2] - center_b[0]) / 10, (center_b[3] - center_b[1]) / 10] if center_b else [0, 0],
        })
        for axis, s in (("width", t.scale_x), ("height", t.scale_y)):
            if abs(s - 1) > SCALE_WARN + 1e-9:
                warnings.append({"level": "warning", "code": f"scale_{idx}_{axis}", "message": (
                    f"{name} is resized to {s * 100:.0f}% {axis}. Beyond about ±20% stitches get too dense "
                    "or too sparse, because resizing a stitch file doesn't add or remove stitches. "
                    "Rebuild stitches at this size (Alt+Shift+R) fixes this.")})
                break
        all_blocks.extend(blk for blk in blocks if blk.recs)

    all_blocks = passes.run_passes(passes.AFTER_ITEMS, all_blocks, layout, warnings)
    # A colour whose stitches were all deleted (stitch editing) sews nothing: leave it out, so the
    # file has no empty colour change and its thread list stays in step with the stitches.
    all_blocks = [b for b in all_blocks if any(r[2] == pe.STITCH for r in b.recs)]
    if not all_blocks:
        raise LayoutError("There are no stitches left: everything was deleted")
    # Colours are sorted first, so moves are judged on the order the design is really sewn in.
    held = 0
    if layout.get("color_sort"):
        all_blocks, held = _sort_by_thread(all_blocks)
    all_blocks = _join_same_thread_objects(all_blocks, bool(layout.get("travel_under", False)))
    if layout.get("color_sort"):
        all_blocks = _merge_same(all_blocks)
        if held:
            warnings.append({"level": "info", "code": "color_sort", "message": (
                f"Some colors are still sewn more than once ({held} part{'s' if held > 1 else ''}): sewing them earlier "
                "would hide them under shapes that are meant to be underneath.")})
    elif layout.get("merge_colors"):
        all_blocks = _merge_same(all_blocks)
    all_blocks = passes.run_passes(passes.AFTER_ORDER, all_blocks, layout, warnings)

    knockdown = layout.get("knockdown") or {}
    if knockdown.get("enabled"):
        block = _knockdown(all_blocks, float(knockdown.get("margin_mm", 2.0)), knockdown.get("thread"))
        if block:
            all_blocks.insert(0, block)

    basting = layout.get("basting") or {}
    if basting.get("enabled"):
        margin = _mm(basting.get("margin_mm", 5))
        margin = 5.0 if margin is None else margin
        fit = basting.get("fit_mm")
        b = _stitch_bounds([r for blk in all_blocks for r in blk.recs])
        if b and isinstance(fit, list) and len(fit) == 2 and all(_mm(v) for v in fit):
            # The box shouldn't be what makes the design too big for the hoop: bring it in to fit,
            # but no closer than BASTING_MIN_MM.
            room = min(float(fit[0]) - (b[2] - b[0]) / 10, float(fit[1]) - (b[3] - b[1]) / 10) / 2 - 0.1
            if room < margin:
                margin = max(BASTING_MIN_MM, room)
                if -0.1 <= room < BASTING_MIN_MM:  # the design fits; with the box it doesn't
                    warnings.append({"level": "warning", "code": "basting_fit", "message": (
                        "The basting box makes the design bigger than the hoop. Turn the basting box off, "
                        "or make the design a little smaller.")})
        box = _basting(all_blocks, margin)
        if box:
            all_blocks.insert(0, box)

    pattern = pe.EmbPattern()
    item_of: list[int] = []
    src_of: list[int] = []
    for n, blk in enumerate(all_blocks):
        if n:
            last = pattern.stitches[-1] if pattern.stitches else [0, 0, 0]
            pattern.stitches.append([last[0], last[1], pe.COLOR_CHANGE])
            item_of.append(-1)
            src_of.append(-1)
        t = blk.thread
        pattern.add_thread(pe.EmbThread(t.get("color", "#000000"), t.get("name", ""), t.get("catalog", ""),
                                        brand=t.get("brand", ""), chart=t.get("brand", "")))
        for x, y, k, item, src in blk.recs:
            pattern.stitches.append([x, y, k])
            item_of.append(item)
            src_of.append(src)
    pattern.stitches.append([pattern.stitches[-1][0] if pattern.stitches else 0,
                             pattern.stitches[-1][1] if pattern.stitches else 0, pe.END])
    return Rendered(pattern, item_of, src_of, all_blocks, item_info, warnings)


def render_summary(layout: dict[str, Any]) -> dict[str, Any]:
    """The design summary the UI draws, plus item bounds and record provenance."""
    r = render(layout)
    summary = design.summarize(r.pattern)
    n = len(summary["records"]["kind"])
    summary["records"]["item"] = r.item_of[:n]
    summary["records"]["src"] = r.src_of[:n]
    # Every output block maps back to the source blocks it came from (several after merging).
    non_empty = [b for b in r.blocks if any(rec[2] == pe.STITCH for rec in b.recs)]
    for out_block, blk in zip(summary["blocks"], non_empty):
        out_block["sources"] = [{"item": i, "block": b} for i, b in blk.sources]
        out_block["original"] = blk.original
    title = layout.get("title") or ""
    first = next((it["path"] for it in layout["items"] if it.get("path")), "")
    if title:
        name = title
    elif not first:
        name = "New design"
    elif len(layout["items"]) == 1:
        name = Path(first).name
    else:
        name = f"{Path(first).stem} + {len(layout['items']) - 1} more"
    summary.update({
        "path": first,
        "name": name,
        "format": design._ext(first) if first else "ludd",
        "items": r.items,
        "warnings": r.warnings,
    })
    return summary


def _names(r: Rendered) -> dict[int, str]:
    """Drawn objects and lettering by item index (the ones whose shapes the checks compare)."""
    return {i: info["name"] for i, info in enumerate(r.items) if info["kind"] in ("satin", "fill", "applique", "text")}


def check(layout: dict[str, Any], heatmap: bool = False, rendered: "Rendered | None" = None) -> dict[str, Any]:
    """Quality checks on the design as it will be sewn, plus (optionally) the density map, and
    the stabilizer to use on the chosen fabric. `rendered`: render(layout), if already made."""
    r = rendered if rendered is not None else render(layout)
    out = quality.check(r.pattern, r.item_of, _names(r), heatmap)
    for c in out["checks"]:
        if "item" in c and 0 <= c["item"] < len(r.items):
            c["item_id"] = r.items[c["item"]]["id"]
    fabric = fabrics.get(layout.get("fabric"))
    out["fabric"] = {"id": fabric["id"], "name": fabric["name"], "advice": fabrics.advice(fabric["id"])}
    return out
