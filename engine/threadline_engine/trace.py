"""Trace Assist: propose the next point while tracing a picture (Tab to accept).

Classic image analysis, no AI and no network: it runs in milliseconds on any PC.

On first use a picture gets two maps:
  darkness  how dark each pixel is (lines in line art are ridges of darkness)
  edges     how sharply brightness changes (the outline of a filled area)

Each suggestion fans candidate points out ahead of the last point (within ±35° of the
current heading, at a few distances), scores them by how strongly the map runs along the
way, how smoothly they continue, and whether they would double back; then nudges the winner
onto the exact middle of the line (or the edge) and reports how confident it is.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

from . import kept

MAX_SIDE_PX = 1600  # pictures are analysed at most this big (plenty for tracing, fast to compute)
FAN_DEG = 35
FAN_STEP_DEG = 5
SAMPLES = 9  # along each candidate segment
MIN_CONFIDENCE = 0.28
CORNER_DEG = 50  # a turn sharper than this makes the accepted point a corner


class TraceError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


@dataclass
class Maps:
    darkness: np.ndarray  # float32 [h, w], 0..1
    edges: np.ndarray  # float32 [h, w], 0..1
    w: int
    h: int
    mode: str  # suggested mode: "center" (line art) or "edge" (filled shapes, photos)
    p90: dict[str, float]


_cache: dict[str, tuple[float, Maps]] = {}


def _box_blur(a: np.ndarray, r: int) -> np.ndarray:
    """Separable box blur with an integral image (fast at any radius)."""
    if r <= 0:
        return a
    k = 2 * r + 1
    p = np.pad(a, ((r + 1, r), (0, 0)), mode="edge")
    c = np.cumsum(p, axis=0, dtype=np.float64)
    a = ((c[k:] - c[:-k]) / k).astype(np.float32)
    p = np.pad(a, ((0, 0), (r + 1, r)), mode="edge")
    c = np.cumsum(p, axis=1, dtype=np.float64)
    return ((c[:, k:] - c[:, :-k]) / k).astype(np.float32)


def _normalise(a: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(a, 2), np.percentile(a, 99.5)
    if hi - lo < 1e-6:
        return np.zeros_like(a)
    return np.clip((a - lo) / (hi - lo), 0, 1).astype(np.float32)


def analyse(img: Image.Image) -> Maps:
    img = img.convert("RGBA")
    # Transparent areas count as white paper.
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    gray = Image.alpha_composite(bg, img).convert("L")
    scale = min(1.0, MAX_SIDE_PX / max(gray.size))
    if scale < 1:
        gray = gray.resize((max(1, round(gray.width * scale)), max(1, round(gray.height * scale))), Image.LANCZOS)
    g = np.asarray(gray, dtype=np.float32) / 255.0
    smooth = _box_blur(_box_blur(g, 1), 1)
    darkness = _normalise(1.0 - smooth)
    gx = np.zeros_like(smooth)
    gy = np.zeros_like(smooth)
    gx[:, 1:-1] = smooth[:, 2:] - smooth[:, :-2]
    gy[1:-1, :] = smooth[2:, :] - smooth[:-2, :]
    edges = _normalise(np.hypot(gx, gy))
    # Line art: mostly light with a little dark ink. Otherwise follow edges.
    dark_share = float((darkness > 0.5).mean())
    mode = "center" if dark_share < 0.22 else "edge"
    h, w = darkness.shape
    p90 = {
        "center": float(np.percentile(darkness[darkness > 0.05], 90)) if (darkness > 0.05).any() else 1.0,
        "edge": float(np.percentile(edges[edges > 0.05], 90)) if (edges > 0.05).any() else 1.0,
    }
    return Maps(darkness, edges, w, h, mode, p90)


def prepare(path: str) -> Maps:
    p = Path(kept.readable(path))
    try:
        mtime = p.stat().st_mtime
    except OSError as exc:
        raise TraceError(f"Picture not found: {p.name}") from exc
    hit = _cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        with Image.open(p) as im:
            # Phone photos: turn the picture the way it's shown on screen.
            maps = analyse(ImageOps.exif_transpose(im))
    except OSError as exc:
        raise TraceError(f"Couldn't read {p.name} for tracing") from exc
    if len(_cache) > 8:
        _cache.pop(next(iter(_cache)))
    _cache[path] = (mtime, maps)
    return maps


# ---------------------------------------------------------------- placement (mm <-> picture pixels)


@dataclass
class Placement:
    x: float
    y: float
    width_mm: float
    height_mm: float
    rotate: float

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Placement":
        return cls(float(d["x"]), float(d["y"]), float(d["width_mm"]), float(d["height_mm"]), float(d.get("rotate", 0)))

    def to_px(self, m: Maps, pts: np.ndarray) -> np.ndarray:
        a = math.radians(-self.rotate)
        ca, sa = math.cos(a), math.sin(a)
        dx, dy = pts[..., 0] - self.x, pts[..., 1] - self.y
        lx, ly = dx * ca - dy * sa, dx * sa + dy * ca
        u = (lx / self.width_mm + 0.5) * m.w - 0.5
        v = (ly / self.height_mm + 0.5) * m.h - 0.5
        return np.stack([u, v], axis=-1)

    def to_mm(self, m: Maps, px: np.ndarray) -> np.ndarray:
        lx = ((px[..., 0] + 0.5) / m.w - 0.5) * self.width_mm
        ly = ((px[..., 1] + 0.5) / m.h - 0.5) * self.height_mm
        a = math.radians(self.rotate)
        ca, sa = math.cos(a), math.sin(a)
        return np.stack([lx * ca - ly * sa + self.x, lx * sa + ly * ca + self.y], axis=-1)

    def px_per_mm(self, m: Maps) -> float:
        return (m.w / self.width_mm + m.h / self.height_mm) / 2


def _sample(field: np.ndarray, uv: np.ndarray) -> np.ndarray:
    """Bilinear sample; outside the picture counts as 0."""
    h, w = field.shape
    u, v = uv[..., 0], uv[..., 1]
    inside = (u >= 0) & (v >= 0) & (u <= w - 1) & (v <= h - 1)
    u = np.clip(u, 0, w - 1.001)
    v = np.clip(v, 0, h - 1.001)
    u0, v0 = np.floor(u).astype(int), np.floor(v).astype(int)
    fu, fv = u - u0, v - v0
    val = (field[v0, u0] * (1 - fu) * (1 - fv) + field[v0, u0 + 1] * fu * (1 - fv)
           + field[v0 + 1, u0] * (1 - fu) * fv + field[v0 + 1, u0 + 1] * fu * fv)
    return np.where(inside, val, 0.0)


# ---------------------------------------------------------------- suggestions


def _heading(pts: np.ndarray) -> tuple[float | None, float]:
    """Direction of travel (radians) from the last few points, and the last turn (radians)."""
    if len(pts) < 2:
        return None, 0.0
    segs = np.diff(pts[-4:], axis=0)
    lens = np.hypot(segs[:, 0], segs[:, 1])
    segs = segs[lens > 1e-9]
    if not len(segs):
        return None, 0.0
    weights = np.arange(1, len(segs) + 1, dtype=float) ** 2  # recent segments count most
    units = segs / np.hypot(segs[:, 0], segs[:, 1])[:, None]
    v = (units * weights[:, None]).sum(axis=0)
    turn = 0.0
    if len(units) >= 2:
        a, b = units[-2], units[-1]
        turn = math.atan2(a[0] * b[1] - a[1] * b[0], float(a[0] * b[0] + a[1] * b[1]))
    return math.atan2(v[1], v[0]), turn


def _refine(field: np.ndarray, p: np.ndarray, direction: float, reach: float) -> np.ndarray:
    """Slide a point sideways (across the travel direction) onto the strongest part of the line."""
    n = np.array([-math.sin(direction), math.cos(direction)])
    offsets = np.linspace(-reach, reach, 9)
    cands = p[None, :] + offsets[:, None] * n[None, :]
    vals = _sample(field, cands)
    return cands[int(np.argmax(vals))]


def _half_widths(darkness: np.ndarray, c: np.ndarray, direction: float, max_px: float) -> tuple[float, float]:
    """How far the dark stroke extends to each side of a centre point (in px)."""
    n = np.array([-math.sin(direction), math.cos(direction)])
    centre = float(_sample(darkness, c[None, :])[0])
    if centre < 0.1:
        return 0.0, 0.0
    steps = np.linspace(0, max_px, max(4, int(max_px * 2)))
    out = []
    for sgn in (1, -1):
        vals = _sample(darkness, c[None, :] + sgn * steps[:, None] * n[None, :])
        below = np.nonzero(vals < centre * 0.5)[0]
        out.append(float(steps[below[0]]) if len(below) else float(max_px))
    return out[0], out[1]


def suggest(path: str, placement: dict[str, Any], points: list[list[float]], step_mm: float = 3.0,
            mode: str = "auto", closed: bool = False, satin: bool = False) -> dict[str, Any]:
    """Next point(s) for the shape being drawn.

    `points` are the shape's points so far in mm (for a satin, the centres of its rungs).
    Returns {"ghost": [x, y] | None, "confidence", "corner", "alternatives": [[x, y]...],
    "mode", "close": bool, "rails": [[ax, ay], [bx, by]] (satin only), "ms"}.
    """
    t0 = time.perf_counter()
    maps = prepare(path)
    place = Placement.from_dict(placement)
    use = maps.mode if mode == "auto" else mode
    if satin:
        use = "center"
    field = maps.darkness if use == "center" else maps.edges
    ppm = place.px_per_mm(maps)

    pts_mm = np.asarray(points, dtype=float).reshape(-1, 2)
    if not len(pts_mm):
        return {"ghost": None, "confidence": 0.0, "mode": use, "ms": 0.0}
    pts = place.to_px(maps, pts_mm)
    p = pts[-1]
    heading, last_turn = _heading(pts)
    step_px = max(1.5, step_mm * ppm)
    # Shorter steps on tight curves, a little longer on straight runs.
    step_px *= 0.65 if abs(last_turn) > math.radians(25) else 1.0

    if heading is None:
        angles = np.radians(np.arange(0, 360, 10, dtype=float))
    else:
        angles = heading + np.radians(np.arange(-FAN_DEG, FAN_DEG + 0.1, FAN_STEP_DEG, dtype=float))
    dists = np.array([0.7, 1.0, 1.3]) * step_px
    A, D = np.meshgrid(angles, dists, indexing="ij")
    A, D = A.ravel(), D.ravel()
    ends = p[None, :] + np.stack([np.cos(A), np.sin(A)], axis=-1) * D[:, None]

    ts = np.linspace(1 / SAMPLES, 1, SAMPLES)
    along = p[None, None, :] + (ends - p)[:, None, :] * ts[None, :, None]
    strength = _sample(field, along).mean(axis=1)
    end_val = _sample(field, ends)
    scale = max(maps.p90[use], 1e-3)
    strength_n = np.clip(strength / scale, 0, 1.2)
    end_n = np.clip(end_val / scale, 0, 1.2)

    if heading is None:
        continuity = np.ones_like(A)
        smooth = np.zeros_like(A)
    else:
        diff = np.angle(np.exp(1j * (A - heading)))
        continuity = np.cos(diff)
        smooth = np.abs(diff - last_turn) / math.radians(FAN_DEG)

    # Don't double back onto the line already traced (except to close a shape at its start).
    penalty = np.zeros_like(A)
    if len(pts) > 2:
        older = pts[:-2]
        dmin = np.min(np.hypot(ends[:, None, 0] - older[None, :, 0], ends[:, None, 1] - older[None, :, 1]), axis=1)
        penalty = np.where(dmin < 0.6 * step_px, 1.0, 0.0)
        if closed and len(pts) >= 4:
            near_start = np.hypot(ends[:, 0] - pts[0, 0], ends[:, 1] - pts[0, 1]) < 1.2 * step_px
            penalty = np.where(near_start, 0.0, penalty)

    score = 0.55 * strength_n + 0.25 * end_n + 0.15 * continuity - 0.08 * smooth - penalty
    order = np.argsort(-score)
    best = order[0]
    ghost_px = _refine(field, ends[best], A[best], max(2.0, 0.3 * ppm))
    confidence = float(np.clip(min(strength_n[best], end_n[best]) * (0.6 + 0.4 * max(continuity[best], 0)), 0, 1))
    if penalty[best] > 0:
        confidence = 0.0

    # A second branch at a junction: a strong candidate heading clearly elsewhere.
    alternatives = []
    for k in order[1:]:
        if score[k] < 0.75 * score[best] or penalty[k] > 0:
            break
        if abs(np.angle(np.exp(1j * (A[k] - A[best])))) > math.radians(30):
            alternatives.append(_refine(field, ends[k], A[k], max(2.0, 0.3 * ppm)))
            break

    turn = 0.0 if heading is None else abs(float(np.angle(np.exp(1j * (A[best] - heading)))))
    close = bool(closed and len(pts) >= 4 and np.hypot(*(ghost_px - pts[0])) < 1.2 * step_px)
    out: dict[str, Any] = {
        "ghost": place.to_mm(maps, ghost_px).round(2).tolist() if confidence >= MIN_CONFIDENCE else None,
        "confidence": round(confidence, 3),
        "corner": turn > math.radians(CORNER_DEG),
        "alternatives": [place.to_mm(maps, a).round(2).tolist() for a in alternatives] if confidence >= MIN_CONFIDENCE else [],
        "mode": use,
        "close": close,
    }
    if satin and out["ghost"] is not None:
        wl, wr = _half_widths(maps.darkness, ghost_px, A[best], 15 * ppm)
        n = np.array([-math.sin(A[best]), math.cos(A[best])])
        rails = np.stack([ghost_px + n * wl, ghost_px - n * wr])
        out["rails"] = place.to_mm(maps, rails).round(2).tolist()
    out["ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return out


def info(path: str) -> dict[str, Any]:
    m = prepare(path)
    return {"mode": m.mode, "width_px": m.w, "height_px": m.h}
