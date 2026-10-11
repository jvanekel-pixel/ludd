"""Prepare a stitch pattern for a machine: recolor, cut-stops, and limit checks.

Nothing here changes the source file; export applies these to a copy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import pyembroidery as pe

from . import profiles

M = pe.COMMAND_MASK
TIE_MM = 0.7  # length of each lock stitch


@dataclass
class CutStops:
    """Turn travels into same-color stops so machines that only cut at color changes cut them.

    By default only travels the digitizer marked with a trim are converted: untrimmed
    jumps are often meant to be covered by later stitching.
    """

    enabled: bool = False
    min_jump_mm: float = 3.0
    include_untrimmed: bool = False
    tie: bool = True

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "CutStops":
        if not d:
            return cls()
        return cls(
            enabled=bool(d.get("enabled", False)),
            min_jump_mm=float(d.get("min_jump_mm", 3.0)),
            include_untrimmed=bool(d.get("include_untrimmed", False)),
            tie=bool(d.get("tie", True)),
        )


@dataclass
class Options:
    machine: str | None = None
    hoop: str | None = None
    # Per original thread index: replacement thread, or None to keep it.
    threads: list[dict[str, str] | None] = field(default_factory=list)
    cut_stops: CutStops = field(default_factory=CutStops)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "Options":
        d = d or {}
        return cls(
            machine=d.get("machine"),
            hoop=d.get("hoop"),
            threads=list(d.get("threads") or []),
            cut_stops=CutStops.from_dict(d.get("cut_stops")),
        )


def _unit(dx: float, dy: float) -> tuple[float, float]:
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n > 1e-9 else (1.0, 0.0)


def apply_threads(pattern: pe.EmbPattern, threads: list[dict[str, str] | None]) -> None:
    for i, t in enumerate(threads):
        if t is None or i >= len(pattern.threadlist):
            continue
        brand = t.get("brand", "")
        pattern.threadlist[i] = pe.EmbThread(
            t.get("color", "#000000"), t.get("name", ""), t.get("catalog", ""), brand=brand, chart=brand
        )


def travels(stitches: list[list[Any]]):
    """Yield (start, end, has_trim, from_xy, to_xy) for each jump/trim run between two stitches
    of the same color. Indices are into `stitches`; end is exclusive."""
    n = len(stitches)
    last: tuple[float, float] | None = None  # last stitch in the current color
    i = 0
    while i < n:
        x, y, c = stitches[i]
        k = c & M
        if k == pe.STITCH:
            last = (x, y)
            i += 1
        elif k in (pe.JUMP, pe.TRIM):
            j, has_trim = i, False
            while j < n and stitches[j][2] & M in (pe.JUMP, pe.TRIM):
                has_trim |= stitches[j][2] & M == pe.TRIM
                j += 1
            if last is not None and j < n and stitches[j][2] & M == pe.STITCH:
                yield i, j, has_trim, last, (stitches[j][0], stitches[j][1])
            i = j
        else:  # color change, stop, end, ...: a new color or a cut starts
            last = None
            i += 1


def add_cut_stops(pattern: pe.EmbPattern, opts: CutStops) -> int:
    """Rewrite pattern.stitches in place. Returns the number of stops added."""
    src = pattern.stitches
    convert = {}
    for start, end, has_trim, a, b in travels(src):
        dist_mm = math.hypot(b[0] - a[0], b[1] - a[1]) / 10
        if (has_trim or opts.include_untrimmed) and dist_mm >= opts.min_jump_mm:
            convert[start] = end

    if not convert:
        return 0

    tie = TIE_MM * 10
    out: list[list[Any]] = []
    prev: tuple[float, float] | None = None  # stitch before the last one, for tie-off direction
    last: tuple[float, float] | None = None
    tie_in = False
    i, n = 0, len(src)
    while i < n:
        x, y, c = src[i]
        k = c & M
        if i in convert:
            end = convert[i]
            ax, ay = last  # travels() guarantees a stitch before
            if opts.tie and prev is not None:
                ux, uy = _unit(ax - prev[0], ay - prev[1])
                out.append([ax - ux * tie, ay - uy * tie, pe.STITCH])
                out.append([ax, ay, pe.STITCH])
            out.append([ax, ay, pe.STOP])
            out.extend([sx, sy, sc] for sx, sy, sc in src[i:end] if sc & M == pe.JUMP)
            tie_in = opts.tie
            prev = last = None
            i = end
            continue
        out.append([x, y, c])
        if k == pe.STITCH:
            if tie_in:
                # Lock: B -> B+d -> B, heading toward the next stitch.
                nxt = src[i + 1] if i + 1 < n and src[i + 1][2] & M == pe.STITCH else None
                ux, uy = _unit(nxt[0] - x, nxt[1] - y) if nxt else (1.0, 0.0)
                out.append([x + ux * tie, y + uy * tie, pe.STITCH])
                out.append([x, y, pe.STITCH])
                tie_in = False
            prev, last = last, (x, y)
        elif k not in (pe.JUMP, pe.TRIM):
            prev = last = None
        i += 1
    pattern.stitches = out
    return len(convert)


def meaningful_trims(pattern: pe.EmbPattern) -> int:
    return sum(1 for *_, has_trim, _a, _b in travels(pattern.stitches) if has_trim)


def _stitch_bounds(pattern: pe.EmbPattern) -> tuple[float, float, float, float]:
    pts = [(x, y) for x, y, c in pattern.stitches if c & M == pe.STITCH]
    if not pts:
        return 0, 0, 0, 0
    xs, ys = zip(*pts)
    return min(xs) / 10, min(ys) / 10, max(xs) / 10, max(ys) / 10


def check(pattern: pe.EmbPattern, opts: Options, ext: str | None, stops_added: int) -> list[dict[str, str]]:
    """Warnings for exporting `pattern` to `ext` for the chosen machine. level: error | warning | info."""
    warnings: list[dict[str, str]] = []
    if not opts.machine:
        return warnings
    machine = profiles.get_machine(opts.machine)
    hoop = profiles.get_hoop(machine, opts.hoop)
    name = machine["name"]

    x0, y0, x1, y1 = _stitch_bounds(pattern)
    w, h = x1 - x0, y1 - y0
    hw, hh = hoop["width_mm"], hoop["height_mm"]
    if w > hw + 1e-6 or h > hh + 1e-6:
        if w <= hh and h <= hw:
            warnings.append({"level": "warning", "code": "hoop_rotate", "message": (
                f"The design is {w:.1f} × {h:.1f} mm, bigger than the {hoop['name']} hoop ({hw:g} × {hh:g} mm) "
                "this way round. Rotate it 90° on the machine to fit.")})
        else:
            warnings.append({"level": "error", "code": "hoop_too_big", "message": (
                f"The design is {w:.1f} × {h:.1f} mm and won't fit the {hoop['name']} hoop ({hw:g} × {hh:g} mm). "
                "The machine will refuse it or stitch off the edge.")})

    if ext and ext not in machine["formats"]:
        warnings.append({"level": "warning", "code": "format", "message": (
            f"The {name} reads {', '.join(f.upper() for f in machine['formats'])}, not {ext.upper()}.")})

    stitches = sum(1 for *_, c in pattern.stitches if c & M == pe.STITCH)
    if machine["max_stitches"] and stitches > machine["max_stitches"]:
        warnings.append({"level": "error", "code": "max_stitches", "message": (
            f"{stitches:,} stitches is more than the {name} accepts ({machine['max_stitches']:,}).")})

    steps = 1 + sum(1 for *_, c in pattern.stitches if c & M in (pe.COLOR_CHANGE, pe.STOP))
    if machine["max_colors"] and steps > machine["max_colors"]:
        warnings.append({"level": "error", "code": "max_colors", "message": (
            f"The design has {steps} color steps (color changes plus stops); the {name} accepts "
            f"{machine['max_colors']}." + (" Use a longer minimum jump to add fewer cut-stops." if stops_added else ""))})

    if machine["cuts"] == "color_change" and not opts.cut_stops.enabled:
        trims = meaningful_trims(pattern)
        if trims:
            warnings.append({"level": "info", "code": "trims_ignored", "message": (
                f"The {name} only cuts at color changes, so it will skip this design's {trims} trims and leave "
                "jump threads to snip by hand. Turn on cut-stops to have it cut them.")})
    if stops_added:
        warnings.append({"level": "info", "code": "stops_added", "message": (
            f"Added {stops_added} cut-stops. The machine will stop, tie off and cut at each one; "
            "press Start to carry on (no thread change needed).")})
    return warnings


def prepare(pattern: pe.EmbPattern, opts: Options, ext: str | None) -> tuple[pe.EmbPattern, dict[str, Any]]:
    """Return a prepared copy of `pattern` and a report."""
    p = pattern.copy()  # EmbPattern.__deepcopy__ is broken in pyembroidery 1.5
    p.stitches = [list(st) for st in pattern.stitches]
    apply_threads(p, opts.threads)
    stops = add_cut_stops(p, opts.cut_stops) if opts.cut_stops.enabled else 0
    return p, {"stops_added": stops, "warnings": check(p, opts, ext, stops)}


def write_settings(opts: Options) -> dict[str, Any]:
    """Extra pyembroidery write settings from the machine profile."""
    if not opts.machine:
        return {}
    m = profiles.get_machine(opts.machine)
    return {"max_stitch": m["max_stitch_mm"] * 10} if m["max_stitch_mm"] else {}
