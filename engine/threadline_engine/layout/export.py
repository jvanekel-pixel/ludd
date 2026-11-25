"""Saving a layout for a machine, the export preview and splitting across hoopings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import design, fabrics, quality, split
from ..prepare import Options, prepare, write_settings
from .model import LayoutError
from .render import _names, render


# ---------------------------------------------------------------- splitting across hoopings


def split_plan(layout: dict[str, Any], hoop: dict[str, Any], overlap_mm: float = 10.0) -> dict[str, Any]:
    """How a design too big for the hoop would be split: the hoopings and their alignment marks."""
    blocks, sections, grid, bounds = split.plan(render(layout).pattern, float(hoop["width_mm"]), float(hoop["height_mm"]), overlap_mm)
    return split.summary(blocks, sections, grid, bounds)


def export_split(layout: dict[str, Any], dest: str, hoop: dict[str, Any], overlap_mm: float = 10.0,
                 options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Save one file per hooping: "name 1 of 4.pes", "name 2 of 4.pes", …"""
    d = Path(dest).resolve()
    ext = design._ext(d)
    blocks, sections, grid, bounds = split.plan(render(layout).pattern, float(hoop["width_mm"]), float(hoop["height_mm"]), overlap_mm)
    opts = Options.from_dict(options)
    files, stops = [], 0
    n = len(sections)
    sources = {Path(it["path"]).resolve() for it in layout.get("items") or [] if it.get("path")}

    def names(stem: str) -> list[Path]:
        return [d.with_name(f"{stem} {sec.index + 1} of {n}{d.suffix}") for sec in sections]

    # Never replace files from an earlier split: "name (1) 1 of 3.pes" etc. instead.
    stem, k = d.stem, 0
    while any(p.exists() for p in names(stem)):
        k += 1
        stem = f"{d.stem} ({k})"
    for sec, out in zip(sections, names(stem)):
        if out in sources:
            raise LayoutError("Choose a different file name: saving over an original design isn't allowed")
        pattern, report = prepare(split.section_pattern(blocks, sec), opts, ext)
        design.write(pattern, out, write_settings(opts))
        stops += report.get("stops_added", 0)
        files.append(str(out))
    return {"paths": files, "stops_added": stops, **split.summary(blocks, sections, grid, bounds)}


def preview_export(layout: dict[str, Any], options: dict[str, Any] | None, ext: str | None) -> dict[str, Any]:
    r = render(layout)
    pattern, report = prepare(r.pattern, Options.from_dict(options), ext)
    # The quality checks belong in the last look before saving for the machine.
    report["warnings"] = report["warnings"] + quality.check(r.pattern, r.item_of, _names(r))["checks"]
    report["fabric_advice"] = fabrics.advice(layout.get("fabric"))
    return {**report, **design.summarize(pattern)}


def export(layout: dict[str, Any], dest: str, options: dict[str, Any] | None = None, keep_existing: bool = False) -> dict[str, Any]:
    """Save the design for a machine. `keep_existing`: never replace a file already there (save as
    "name (1).pes" instead), for batches such as one file per name."""
    d = Path(dest).resolve()
    if keep_existing:
        d = design._free_name(d)
    for it in layout.get("items") or []:
        if it.get("path") and Path(it["path"]).resolve() == d:
            raise LayoutError("Choose a different file name: saving over an original design isn't allowed")
    opts = Options.from_dict(options)
    pattern, report = prepare(render(layout).pattern, opts, design._ext(d))
    design.write(pattern, d, write_settings(opts))
    return {"path": str(d), **report}
