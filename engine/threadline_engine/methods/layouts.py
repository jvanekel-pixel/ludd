"""RPC methods. Layouts: render, check, export, split, shortest order, applique cut file."""

from __future__ import annotations

from .. import layout as layout_module
from .registry import dispatcher


@dispatcher.method("layout.render")
def layout_render(layout: dict) -> dict:
    return layout_module.render_summary(layout)


@dispatcher.method("layout.preview_export")
def layout_preview_export(layout: dict, options: dict | None = None, ext: str | None = None) -> dict:
    return layout_module.preview_export(layout, options, ext)


@dispatcher.method("layout.export")
def layout_export(layout: dict, dest: str, options: dict | None = None, keep_existing: bool = False) -> dict:
    return layout_module.export(layout, dest, options, keep_existing)


@dispatcher.method("layout.check", background=True)
def layout_check(layout: dict, heatmap: bool = False) -> dict:
    """Off the main loop, so an edit's render never waits for the checks: only the render (which
    uses the shared caches, and is usually already cached) takes the lock."""
    with dispatcher.lock:
        r = layout_module.render(layout)
    return layout_module.check(layout, heatmap, rendered=r)


@dispatcher.method("layout.split_plan")
def layout_split_plan(layout: dict, hoop: dict, overlap_mm: float = 10.0) -> dict:
    return layout_module.split_plan(layout, hoop, overlap_mm)


@dispatcher.method("layout.export_split")
def layout_export_split(layout: dict, dest: str, hoop: dict, overlap_mm: float = 10.0, options: dict | None = None) -> dict:
    return layout_module.export_split(layout, dest, hoop, overlap_mm, options)


@dispatcher.method("applique.export_svg")
def applique_export_svg(layout: dict, dest: str) -> dict:
    return layout_module.export_applique_svg(layout, dest)


@dispatcher.method("layout.optimize_jumps")
def layout_optimize_jumps(layout: dict) -> dict:
    """Where each piece starts and ends, so jumps between same-thread pieces are shortest."""
    from ..jumps import optimize_jumps

    return optimize_jumps(layout)


@dispatcher.method("layout.optimize_order")
def layout_optimize_order(layout: dict) -> dict:
    return layout_module.optimize_order(layout)


@dispatcher.method("layout.branch_plan")
def layout_branch_plan(layout: dict, ids: list) -> dict:
    """Can the shapes `ids` be sewn as one path? {ok, reason, order} (order: every item id, the
    branch's members moved next to each other)."""
    from ..layout.branch import branch_plan

    return branch_plan(layout, ids)
