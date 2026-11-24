"""Auto-trace: click inside a shape in a picture (or on one of its lines) and get its outline
as editable points, a few guesses at a time (Tab shows the next one).

Classic image analysis with OpenCV: no AI, no network, a fraction of a second on any PC.

- A click inside an area grows a region from that spot until it meets a dark line or a clear
  change of color. The guesses differ in where they stop: at the middle of the bordering line
  (best under a satin border), at the inside of it, letting similar shades join, or only at
  dark lines.
- A click on a dark line follows the line's middle (its skeleton) and measures how wide it
  is, for a satin ribbon: first up to where it meets other lines, then straight on through.

Points come back in mm, about `spacing_mm` apart, with sharp corners kept as corners.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from . import kept
from .trace import Placement, TraceError, flatten, open_picture

MAX_SIDE_PX = 1200  # pictures are analysed at most this big
INK_DARK = 70  # gray level (0-255) below which a pixel is ink, whatever is around it
INK_LOCAL = 32  # or this much darker than its surroundings (and below INK_SOFT)
INK_SOFT = 120
INK_MAX_CHROMA = 70  # max - min of R, G, B: more colorful than this is a color, not ink
CORNER_DEG = 40  # a turn sharper than this, over about 1 mm, is a corner
MIN_SPACING_MM, MAX_SPACING_MM = 0.5, 15.0
MIN_HOLE_MM2 = 3.0
SAME_GUESS_IOU = 0.92


@dataclass
class Pic:
    smooth: np.ndarray  # uint8 [h, w, 3], noise removed, edges kept
    ink: np.ndarray  # uint8 [h, w], 1 = dark line
    ink_dt: np.ndarray  # float32: distance from each ink pixel to the nearest non-ink pixel
    ink_labels: np.ndarray  # int32: connected lines
    edges: np.ndarray  # float32 [h, w], 0..1: how sharply the color changes
    w: int
    h: int
    # Simplified colors: each pixel's color group, and each group's color (Lab). Shading and
    # soft edges fall into a few flat colors, so an area stops where the color clearly changes.
    groups: np.ndarray | None = None  # int32 [h, w]
    centres: np.ndarray | None = None  # float32 [k, 3]
    rgb: np.ndarray | None = None  # uint8 [h, w, 3], as loaded (for the AI model)


_cache: dict[str, tuple[float, Pic]] = {}


def analyse(img: Image.Image) -> Pic:
    img = flatten(img, MAX_SIDE_PX)  # 8-bit RGB on white paper (transparent counts as paper)
    rgb = np.ascontiguousarray(np.asarray(img, dtype=np.uint8))
    smooth = cv2.bilateralFilter(rgb, 7, 40, 7)
    gray = cv2.cvtColor(smooth, cv2.COLOR_RGB2GRAY)
    local = cv2.blur(gray, (21, 21))
    # Ink is dark and close to grey or black: a dark navy or brown area is a color, not a line.
    chroma = smooth.max(axis=2).astype(np.int16) - smooth.min(axis=2).astype(np.int16)
    darkish = (gray < INK_DARK) | ((gray < INK_SOFT) & (gray.astype(np.int16) < local.astype(np.int16) - INK_LOCAL))
    ink = (darkish & (chroma < INK_MAX_CHROMA)).astype(np.uint8)
    lab = cv2.cvtColor(smooth, cv2.COLOR_RGB2LAB).astype(np.float32)
    mag = np.zeros(gray.shape, np.float32)
    for ch in range(3):
        gx = cv2.Sobel(lab[..., ch], cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(lab[..., ch], cv2.CV_32F, 0, 1, ksize=3)
        mag += gx * gx + gy * gy
    mag = np.sqrt(mag)
    hi = float(np.percentile(mag, 99.5)) or 1.0
    edges = np.clip(mag / hi, 0, 1).astype(np.float32)
    dt = cv2.distanceTransform(ink, cv2.DIST_L2, 3)
    # A picture that is all ink has no edge to measure from: no line is wider than the picture.
    np.minimum(dt, float(max(ink.shape)), out=dt)
    _, labels = cv2.connectedComponents(ink, connectivity=8)
    h, w = gray.shape
    groups, centres = simplify_colors(smooth)
    return Pic(smooth, ink, dt, labels, edges, w, h, groups, centres, rgb)


SIMPLE_COLORS = 12


def simplify_colors(rgb: np.ndarray, k: int = SIMPLE_COLORS) -> tuple[np.ndarray, np.ndarray]:
    """Reduce a picture to its k main colors (k-means in Lab, on a sample of pixels, after a
    median blur that flattens noise and fine texture). Returns each pixel's group and the groups'
    colors."""
    flat = cv2.medianBlur(rgb, 5)
    lab = cv2.cvtColor(flat, cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    rng = np.random.default_rng(0)
    sample = lab[rng.choice(len(lab), size=min(len(lab), 40000), replace=False)]
    k = min(k, len(np.unique(sample.round(), axis=0)))
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    cv2.setRNGSeed(0)
    _, _, centres = cv2.kmeans(sample, max(1, k), None, crit, 3, cv2.KMEANS_PP_CENTERS)
    # Nearest group for every pixel, in chunks (keeps memory small on big pictures).
    groups = np.empty(len(lab), np.int32)
    for i in range(0, len(lab), 200000):
        d = ((lab[i : i + 200000, None, :] - centres[None]) ** 2).sum(-1)
        groups[i : i + 200000] = d.argmin(1)
    return groups.reshape(rgb.shape[:2]), centres


def prepare(path: str) -> Pic:
    p = Path(kept.readable(path, as_added=True))
    try:
        mtime = p.stat().st_mtime
    except OSError as exc:
        raise TraceError(f"Picture not found: {p.name}") from exc
    hit = _cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    pic = analyse(open_picture(p, MAX_SIDE_PX))
    if len(_cache) > 6:
        _cache.pop(next(iter(_cache)))
    _cache[path] = (mtime, pic)
    return pic


# ---------------------------------------------------------------- outlines to points


def _turns(pts: np.ndarray, k: int, closed: bool) -> np.ndarray:
    """Turning angle (radians) at each point, measured k points before and after."""
    n = len(pts)
    idx = np.arange(n)
    if closed:
        a, b = pts[(idx - k) % n], pts[(idx + k) % n]
    else:
        a, b = pts[np.clip(idx - k, 0, n - 1)], pts[np.clip(idx + k, 0, n - 1)]
    v1, v2 = pts - a, b - pts
    ang = np.abs(np.arctan2(v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0], (v1 * v2).sum(axis=1)))
    if not closed:
        ang[:k] = 0
        ang[n - k :] = 0
    return ang


def _smooth(pts: np.ndarray, r: int, closed: bool) -> np.ndarray:
    if r < 1 or len(pts) < 2 * r + 2:
        return pts
    k = np.ones(2 * r + 1) / (2 * r + 1)
    if closed:
        ext = np.concatenate([pts[-r:], pts, pts[:r]])
        return np.stack([np.convolve(ext[:, i], k, "valid") for i in range(2)], axis=1)
    out = pts.copy()
    for i in range(2):
        out[r:-r, i] = np.convolve(pts[:, i], k, "valid")
    return out


def to_nodes(px: np.ndarray, place: Placement, pic: Pic, spacing_mm: float, closed: bool) -> list[list[Any]]:
    """Points along a pixel outline (or line), about spacing_mm apart, corners kept sharp."""
    ppm = place.px_per_mm(pic)
    pts = _smooth(px.astype(np.float64), max(1, round(0.25 * ppm)), closed)
    n = len(pts)
    if n < 3:
        return []
    k = max(2, round(1.0 * ppm))
    k = min(k, max(1, n // 4))
    turn = _turns(pts, k, closed)
    # A corner turns about as much measured close up as further out; a tight curve turns
    # about half as much close up, so it stays a curve.
    wide = _turns(pts, min(2 * k, max(1, n // 3)), closed)
    corners = []
    sharp = (turn > math.radians(CORNER_DEG)) & (turn > 0.75 * wide)
    # On a closed outline, start scanning just after a gentle point, so no bend is split in two.
    shift = int(np.argmin(sharp)) if closed and sharp.any() and not sharp.all() else 0
    order = np.roll(np.arange(n), -shift)
    i = 0
    while i < n:
        if sharp[order[i]]:
            j = i
            while j < n and sharp[order[j]]:
                j += 1
            run = order[i:j]
            corners.append(int(run[int(np.argmax(turn[run]))]))
            i = j
        else:
            i += 1
    corners.sort()
    seg = np.hypot(*np.diff(np.vstack([pts, pts[:1]]) if closed else pts, axis=0).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    step = spacing_mm * ppm
    if closed:
        stops = corners or [int(np.argmin(pts[:, 1]))]  # no corners: start at the top
        picks: list[tuple[float, str]] = []
        for a, b in zip(stops, stops[1:] + [stops[0]]):
            s0, s1 = cum[a], cum[b] if b > a else cum[b] + total
            m = max(1, round((s1 - s0) / step))
            picks.append((s0, "c" if corners else "s"))
            picks += [(s0 + (s1 - s0) * t / m, "s") for t in range(1, m)]
        if len(picks) < 3:
            picks = [(total * t / 3, "s") for t in range(3)]
    else:
        stops = [0, *[c for c in corners if 0 < c < n - 1], n - 1]
        picks = []
        for a, b in zip(stops, stops[1:]):
            m = max(1, round((cum[b] - cum[a]) / step))
            picks.append((cum[a], "c"))
            picks += [(cum[a] + (cum[b] - cum[a]) * t / m, "s") for t in range(1, m)]
        picks.append((cum[n - 1], "c"))
    loop = np.vstack([pts, pts[:1]]) if closed else pts
    s_vals = np.array([p[0] % total if closed else p[0] for p in picks])
    xy = np.stack([np.interp(s_vals, cum[: len(loop)], loop[:, i]) for i in range(2)], axis=1)
    mm = place.to_mm(pic, xy)
    return [[round(float(x), 2), round(float(y), 2), kind] for (x, y), (_, kind) in zip(mm, picks)]


# ---------------------------------------------------------------- regions


def _region(pic: Pic, seed: tuple[int, int], tol: int, edge_thr: float | None) -> np.ndarray:
    """Pixels reachable from seed without crossing ink (or a color edge) and within tol of its color."""
    barrier = pic.ink.copy()
    if edge_thr is not None:
        barrier |= (pic.edges > edge_thr).astype(np.uint8)
    mask = np.zeros((pic.h + 2, pic.w + 2), np.uint8)
    mask[1:-1, 1:-1] = barrier
    if mask[seed[1] + 1, seed[0] + 1]:
        return np.zeros((pic.h, pic.w), np.uint8)
    flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE
    cv2.floodFill(pic.smooth, mask, seed, (0, 0, 0), (tol,) * 3, (tol,) * 3, flags)
    region = (mask[1:-1, 1:-1] == 255).astype(np.uint8)
    # Soak up the anti-aliased pixels along the edge.
    return cv2.morphologyEx(region, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))


def _group_links(pic: Pic) -> np.ndarray:
    """How many neighbouring pixel pairs join each pair of color groups (ink excluded)."""
    k = len(pic.centres)
    g = pic.groups
    ok = pic.ink == 0
    links = np.zeros((k, k), np.int64)
    for a, b, m in ((g[:, :-1], g[:, 1:], ok[:, :-1] & ok[:, 1:]), (g[:-1], g[1:], ok[:-1] & ok[1:])):
        diff = m & (a != b)
        np.add.at(links, (a[diff], b[diff]), 1)
    return links + links.T


def _simple_region(pic: Pic, seed: tuple[int, int], spread: int) -> np.ndarray:
    """The clicked area by simplified colors. From the clicked color it spreads into neighbouring
    colors that are close to it, band by band, so shading is followed but a clear change of color
    stops it. Spread (1-10) sets how close "close" is."""
    if pic.groups is None or pic.centres is None or pic.ink[seed[1], seed[0]]:
        return np.zeros((pic.h, pic.w), np.uint8)
    start = int(pic.groups[seed[1], seed[0]])
    # The joined colors only depend on the clicked color and the spread: label their connected
    # areas once, so every click (and every area of a whole picture) just looks its area up.
    cache = pic.__dict__.setdefault("_simple", {})
    if (start, spread) not in cache:
        if not hasattr(pic, "_links"):
            pic._links = _group_links(pic)  # type: ignore[attr-defined]
        links = pic._links  # type: ignore[attr-defined]
        step = 3 + 2.5 * spread  # biggest color step between neighbouring bands (Lab)
        reach = 15 + 9 * spread  # furthest from the clicked color overall
        sizes = np.bincount(pic.groups.ravel(), minlength=len(pic.centres))
        joined = {start}
        todo = [start]
        while todo:
            a = todo.pop()
            for b in np.nonzero(links[a])[0]:
                b = int(b)
                if b in joined:
                    continue
                # A real border, not a few stray pixels, and a small step in color.
                if links[a, b] < max(4, 0.002 * min(sizes[a], sizes[b])):
                    continue
                if np.linalg.norm(pic.centres[a] - pic.centres[b]) > step:
                    continue
                if np.linalg.norm(pic.centres[b] - pic.centres[start]) > reach:
                    continue
                joined.add(b)
                todo.append(b)
        member = np.zeros(len(pic.centres), np.uint8)
        member[list(joined)] = 1
        ok = member[pic.groups] & (pic.ink == 0)
        _, lab, st, _ = cv2.connectedComponentsWithStats(ok.astype(np.uint8), connectivity=4)
        if len(cache) > 12:
            cache.pop(next(iter(cache)))
        cache[(start, spread)] = (lab, st)
    lab, st = cache[(start, spread)]
    c = int(lab[seed[1], seed[0]])
    region = np.zeros((pic.h, pic.w), np.uint8)
    if not c:
        return region
    x, y, w, h = (int(v) for v in st[c, :4])
    x0, y0, x1, y1 = max(0, x - 3), max(0, y - 3), min(pic.w, x + w + 3), min(pic.h, y + h + 3)
    # Close small specks of another color inside (texture), not real holes.
    region[y0:y1, x0:x1] = cv2.morphologyEx((lab[y0:y1, x0:x1] == c).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return region


def _to_line_middle(pic: Pic, region: np.ndarray, max_px: int, block: np.ndarray | None = None) -> tuple[np.ndarray, float]:
    """Grow a region into the dark lines around it, up to their middle (under a satin border).
    Solid dark areas (a cartoon's pupils) are only entered by a line's half width; `block` (a dark
    background that is left out) not at all. Returns the grown region and the typical width of
    the bordering lines in pixels. Works on the region's surroundings only (fast on big pictures)."""
    bx, by, bw, bh = cv2.boundingRect((region > 0).astype(np.uint8))
    if not bw:
        return region, 0.0
    m = max_px + 4
    x0, y0, x1, y1 = max(0, bx - m), max(0, by - m), min(pic.w, bx + bw + m), min(pic.h, by + bh + m)
    reg = region[y0:y1, x0:x1]
    ink = pic.ink[y0:y1, x0:x1]
    if block is not None:
        ink = ink & (block[y0:y1, x0:x1] == 0)
    # How far each pixel is from the region (the same as growing it by a disc, but fast).
    away = cv2.distanceTransform((reg == 0).astype(np.uint8), cv2.DIST_L2, 5)
    band = (away <= max_px) & (ink > 0) & (reg == 0)
    if not band.any():
        return region, 0.0
    k3 = np.ones((3, 3), np.uint8)
    dt = pic.ink_dt[y0:y1, x0:x1]
    # The middle of each line (its ridge), from lines no wider than about max_px.
    ridge = (ink > 0) & (dt >= cv2.dilate(dt, k3) - 1e-3) & (dt <= max_px / 2)
    sample = dt[band & ridge]
    half = float(np.median(sample)) if len(sample) else float(np.median(dt[band]))
    # The soft, anti-aliased pixels between a color and its line count as line too.
    allowed = (cv2.dilate(ink, k3) | reg) > 0
    # An even offset by half the line width (plus the soft edge pixel), so the outline stays smooth.
    grown = (reg > 0) | ((away <= half + 1.0) & allowed)
    out = region.astype(np.uint8, copy=True)
    out[y0:y1, x0:x1] = cv2.morphologyEx(grown.astype(np.uint8), cv2.MORPH_CLOSE, k3)
    return out, 2 * half


def _hex(pixels: np.ndarray) -> str:
    """The typical color of some pixels, as #rrggbb (median, so stray pixels don't tint it)."""
    if not len(pixels):
        return "#000000"
    r, g, b = (int(v) for v in np.median(pixels.reshape(-1, 3), axis=0))
    return f"#{r:02x}{g:02x}{b:02x}"


def _same_outline(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return a.get("outline") == b.get("outline") and a.get("holes") == b.get("holes")


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    inter = np.count_nonzero(a & b)
    union = np.count_nonzero(a | b)
    return inter / union if union else 1.0


MIN_HOLE_WIDTH_MM = 1.5  # thinner "holes" are lines (a satin covers them): the fill goes under


def _part(cnts, hier, i: int, pic: Pic, place: Placement, spacing: float) -> dict[str, Any] | None:
    """One outline and its holes (real holes only: not specks, not thin lines)."""
    ppm = place.px_per_mm(pic)
    outline = to_nodes(cnts[i].reshape(-1, 2), place, pic, spacing, closed=True)
    if len(outline) < 3:
        return None
    holes = []
    child = hier[i][2]
    while child != -1:
        area = cv2.contourArea(cnts[child])
        perimeter = cv2.arcLength(cnts[child], True) or 1.0
        mean_width = 2 * area / perimeter  # a long thin hole has a small mean width
        if area >= MIN_HOLE_MM2 * ppm * ppm and mean_width >= MIN_HOLE_WIDTH_MM * ppm:
            h = to_nodes(cnts[child].reshape(-1, 2), place, pic, spacing, closed=True)
            if len(h) >= 3:
                holes.append(h)
        child = hier[child][0]
    return {"outline": outline, "holes": holes}


def _fill_candidate(pic: Pic, region: np.ndarray, seed: tuple[int, int], place: Placement, spacing: float) -> dict[str, Any] | None:
    """The guess as a fill: the part you clicked, plus any separate parts (from Shift+clicks)."""
    cnts, hier = cv2.findContours(region, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    hier = hier[0]
    ppm = place.px_per_mm(pic)
    min_area = (1.5 * ppm) ** 2
    outers = [i for i in range(len(cnts)) if hier[i][3] == -1 and cv2.contourArea(cnts[i]) >= min_area]
    if not outers:
        return None
    inside = [i for i in outers if cv2.pointPolygonTest(cnts[i], (float(seed[0]), float(seed[1])), False) >= 0]
    best = max(inside or outers, key=lambda i: cv2.contourArea(cnts[i]))
    main = _part(cnts, hier, best, pic, place, spacing)
    if not main:
        return None
    others = [p for p in (_part(cnts, hier, i, pic, place, spacing) for i in outers if i != best) if p]
    return {"kind": "fill", **main, "parts": others, "area_mm2": round(float(np.count_nonzero(region)) / ppm**2, 1)}


# ---------------------------------------------------------------- lines (satin ribbons)


_NB = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
# A 3x3 kernel that turns a 0/1 picture into each pixel's neighbour code (bit i = _NB[i]).
_CODE_KERNEL = np.zeros((3, 3), np.float32)
for _i, (_dx, _dy) in enumerate(_NB):
    _CODE_KERNEL[1 + _dy, 1 + _dx] = 1 << _i


def _codes(skel: np.ndarray) -> np.ndarray:
    """Each pixel's neighbours as an 8-bit code (bit i set when neighbour _NB[i] is on)."""
    code = cv2.filter2D(skel.astype(np.uint8), cv2.CV_32F, _CODE_KERNEL, borderType=cv2.BORDER_CONSTANT)
    return np.rint(code).astype(np.int32)


def _zhang_suen_luts() -> tuple[np.ndarray, np.ndarray]:
    """Zhang-Suen's two deletion tests, for each of the 256 neighbour codes."""
    # P2..P9 clockwise from north, as indexes into _NB.
    order = [_NB.index(d) for d in ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))]
    luts = (np.zeros(256, bool), np.zeros(256, bool))
    for code in range(256):
        p2, p3, p4, p5, p6, p7, p8, p9 = (code >> i & 1 for i in order)
        ring = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
        b = sum(ring[:8])
        trans = sum(1 for i in range(8) if ring[i] == 0 and ring[i + 1] == 1)
        if not (2 <= b <= 6 and trans == 1):
            continue
        luts[0][code] = p2 * p4 * p6 == 0 and p4 * p6 * p8 == 0
        luts[1][code] = p2 * p4 * p8 == 0 and p2 * p6 * p8 == 0
    return luts


_THIN_LUTS = _zhang_suen_luts()


def thin(img: np.ndarray) -> np.ndarray:
    """Zhang-Suen thinning: the one-pixel-wide middle of a shape (vectorised, on the part of the
    picture that has something in it)."""
    out = np.zeros(img.shape, bool)
    x, y, w, h = cv2.boundingRect((img > 0).astype(np.uint8))
    if not w:
        return out
    a = np.pad((img[y : y + h, x : x + w] > 0), 1)
    while True:
        changed = False
        for lut in _THIN_LUTS:
            kill = a & lut[_codes(a)]
            if kill.any():
                a[kill] = False
                changed = True
        if not changed:
            out[y : y + h, x : x + w] = a[1:-1, 1:-1]
            return out


def _neighbours(skel: np.ndarray, x: int, y: int) -> list[tuple[int, int]]:
    h, w = skel.shape
    return [(x + dx, y + dy) for dx, dy in _NB if 0 <= x + dx < w and 0 <= y + dy < h and skel[y + dy, x + dx]]


def _removable_lut() -> np.ndarray:
    """For each of the 256 ways a pixel's 8 neighbours can be set (bit i = _NB[i]): can the pixel
    go without splitting them? True when it has 2 or 3 neighbours that touch each other."""
    lut = np.zeros(256, bool)
    for code in range(256):
        nb = [_NB[i] for i in range(8) if code >> i & 1]
        if not 2 <= len(nb) <= 3:
            continue
        group = {nb[0]}
        todo = [nb[0]]
        while todo:
            a = todo.pop()
            for b in nb:
                if b not in group and max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 1:
                    group.add(b)
                    todo.append(b)
        lut[code] = len(group) == len(nb)
    return lut


_REMOVABLE = _removable_lut()


def _one_pixel(skel: np.ndarray) -> np.ndarray:
    """Remove stair-step pixels thinning leaves on diagonals: any pixel whose neighbours stay
    connected without it (and that isn't a line end) goes, so each line is one pixel wide.
    Vectorised: pixels two apart never share a neighbour, so each quarter of the pixels (by odd or
    even row and column) can be decided at once."""
    skel = skel.astype(bool, copy=True)
    h, w = skel.shape
    yy, xx = np.mgrid[0:h, 0:w]
    classes = [((yy % 2) == a) & ((xx % 2) == b) for a in (0, 1) for b in (0, 1)]
    changed = True
    while changed:
        changed = False
        for cls in classes:
            kill = skel & cls & _REMOVABLE[_codes(skel)]
            if kill.any():
                skel[kill] = False
                changed = True
    return skel


def _neighbour_counts(skel: np.ndarray) -> np.ndarray:
    k = np.ones((3, 3), np.float32)
    k[1, 1] = 0
    return np.rint(cv2.filter2D(skel.astype(np.float32), -1, k, borderType=cv2.BORDER_CONSTANT)).astype(np.int32)


def _prune(skel: np.ndarray, spur_px: int) -> np.ndarray:
    """Remove short whiskers (thinning leaves them at bumps on a line's edge)."""
    skel = skel.copy()
    ys, xs = np.nonzero(skel & (_neighbour_counts(skel) == 1))
    ends = list(zip(xs.tolist(), ys.tolist()))
    for x, y in ends:
        path = [(x, y)]
        prev = None
        cur = (x, y)
        while len(path) <= spur_px:
            nb = [p for p in _neighbours(skel, *cur) if p != prev and p not in path]
            if len(nb) != 1:
                break
            prev, cur = cur, nb[0]
            if len(_neighbours(skel, *cur)) > 2:  # reached a junction: this was a whisker
                for px, py in path:
                    skel[py, px] = False
                break
            path.append(cur)
    return skel


def _walk(skel: np.ndarray, start: tuple[int, int], first: tuple[int, int], seen: set, through: bool) -> list[tuple[int, int]]:
    """Follow the skeleton from start via first. At a fork, stop, or (through) go straightest."""
    path = [first]
    seen.add(first)
    prev = start
    cur = first
    while True:
        nb = [p for p in _neighbours(skel, *cur) if p not in seen]
        # Ignore neighbours that are also neighbours of where we came from (diagonal shortcuts).
        nb = [p for p in nb if max(abs(p[0] - prev[0]), abs(p[1] - prev[1])) > 1] or nb
        if not nb:
            return path
        if len(nb) > 1:
            if not through:
                return path
            back = path[max(0, len(path) - 6)]
            hx, hy = cur[0] - back[0], cur[1] - back[1]
            nb.sort(key=lambda p: -((p[0] - cur[0]) * hx + (p[1] - cur[1]) * hy) / (math.hypot(p[0] - cur[0], p[1] - cur[1]) * (math.hypot(hx, hy) or 1)))
        prev, cur = cur, nb[0]
        seen.add(cur)
        path.append(cur)
        if len(path) > 20000:
            return path


def _reach_tips(px: np.ndarray, reach: float, ends: tuple[bool, bool] = (True, True)) -> np.ndarray:
    """The middle of a line stops about half its width short of the rounded tip: reach it.
    `reach` is how far (pixels); `ends` says which ends are free line ends (not where lines meet)."""
    if len(px) <= 4 or not reach > 0:
        return px
    tips = []
    for end, inner in ((0, min(4, len(px) - 1)), (len(px) - 1, max(0, len(px) - 5))):
        d = px[end] - px[inner]
        dl = float(np.hypot(*d))
        tips.append(px[end] + d / dl * reach if dl > 1e-6 and ends[0 if end == 0 else 1] else None)
    parts = [t[None] for t in tips[:1] if t is not None] + [px] + [t[None] for t in tips[1:] if t is not None]
    return np.vstack(parts)


def _line_skeleton(pic: Pic, label: int) -> tuple[int, int, np.ndarray]:
    """The middle of one connected line (cropped to it), worked out once per picture: a busy
    picture's line network is slow to thin, and every click on it needs the same answer."""
    cache = pic.__dict__.setdefault("_skels", {})
    if label not in cache:
        ys, xs = np.nonzero(pic.ink_labels == label)
        x0, y0 = max(0, xs.min() - 2), max(0, ys.min() - 2)
        x1, y1 = min(pic.w, xs.max() + 3), min(pic.h, ys.max() + 3)
        comp = pic.ink_labels[y0:y1, x0:x1] == label
        dt = pic.ink_dt[y0:y1, x0:x1]
        skel = _prune(_one_pixel(thin(comp)), max(3, int(float(dt[comp].max()) * 1.5)))
        if len(cache) > 32:
            cache.pop(next(iter(cache)))
        cache[label] = (int(x0), int(y0), skel)
    return cache[label]


def _ribbon_candidates(pic: Pic, seed: tuple[int, int], place: Placement, spacing: float) -> list[dict[str, Any]]:
    label = int(pic.ink_labels[seed[1], seed[0]])
    ppm = place.px_per_mm(pic)
    x0, y0, skel = _line_skeleton(pic, label)
    dt = pic.ink_dt[y0 : y0 + skel.shape[0], x0 : x0 + skel.shape[1]]
    sy, sx = np.nonzero(skel)
    if not len(sx):
        return []
    lx, ly = seed[0] - x0, seed[1] - y0
    i = int(np.argmin((sx - lx) ** 2 + (sy - ly) ** 2))
    start = (int(sx[i]), int(sy[i]))
    out = []
    for through in (False, True):
        seen = {start}
        dirs = _neighbours(skel, *start)
        a = _walk(skel, start, dirs[0], seen, through) if dirs else []
        rest = [d for d in dirs if d not in seen]
        b = _walk(skel, start, rest[0], seen, through) if rest else []
        path = [*reversed(b), start, *a]
        if len(path) < max(4, 1.5 * ppm):
            continue
        closed = len(path) > 8 and max(abs(path[0][0] - path[-1][0]), abs(path[0][1] - path[-1][1])) <= 1
        width_px = min(2 * float(np.median([dt[y, x] for x, y in path])), 10.0 * ppm)
        width = min(max(width_px / ppm, 0.8), 10.0)
        px = np.array([(x + x0, y + y0) for x, y in path], dtype=np.float64)
        if not closed:
            px = _reach_tips(px, width_px / 2)
        nodes = to_nodes(px, place, pic, spacing, closed)
        if len(nodes) < 2:
            continue
        if out and len(out[0]["nodes"]) == len(nodes) and out[0]["nodes"] == nodes:
            continue
        on_line = np.array([pic.smooth[y + y0, x + x0] for x, y in path])
        out.append({"kind": "satin", "id": "line-through" if through else "line", "nodes": nodes, "width_mm": round(width, 2), "closed": closed, "color": _hex(on_line),
                    "label": "Satin along this line" if not through else "Satin along this line, through where lines meet"})
    return out


# ---------------------------------------------------------------- entry point


# id, label, how the area is found, grow to the middle of the bordering line
REGION_GUESSES = (
    ("simple", "Fill, by simplified colors", "simple", True),
    ("middle", "Fill, up to the middle of its outline", "color", True),
    ("inside", "Fill, inside its outline", "color", False),
    ("shades", "Fill, with similar shades joined", "shades", True),
    ("lines", "Fill, everything inside the dark lines", "lines", True),
)
SPREAD_MIN, SPREAD_MAX, SPREAD_DEFAULT = 1, 10, 5


def _guess_region(pic: Pic, seed: tuple[int, int], how: str, spread: int) -> np.ndarray:
    """One way of finding the clicked area. `spread` (1-10) is how readily it spreads into
    similar colors: low stops at the faintest change, high joins shades together."""
    f = spread / SPREAD_DEFAULT
    if how == "simple":
        return _simple_region(pic, seed, spread)
    if how == "color":
        return _region(pic, seed, round(22 * f), min(0.9, 0.3 + 0.03 * spread))
    if how == "shades":
        return _region(pic, seed, round(48 * f), None)
    return _region(pic, seed, 255, None)


def _seed_px(pic: Pic, place: Placement, pt: list[float]) -> tuple[int, int] | None:
    u, v = place.to_px(pic, np.asarray(pt, dtype=float).reshape(1, 2))[0]
    s = (int(round(u)), int(round(v)))
    return s if 0 <= s[0] < pic.w and 0 <= s[1] < pic.h else None


# ---------------------------------------------------------------- what's already traced

TUCK_MM = 0.3  # a guess fitted around your shapes tucks this far under them (no gap once sewn)
FIT_MIN_SHARE = 0.02  # fitted only when your shapes cover more than this share of the guess...
FIT_KEEP_SHARE = 0.25  # ...and at least this much of it is left (else it's the same thing again)
AI_AVOID_MAX = 6  # at most this many of your shapes are pointed out to the AI as "not this"


def _taken_mask(pic: Pic, place: Placement, taken: list[dict[str, Any]] | None) -> tuple[np.ndarray | None, list[tuple[int, int]]]:
    """Where shapes already drawn lie over the picture (pixels, shrunk by TUCK_MM so a fitted guess
    tucks under them), and a point well inside each (to tell the AI "not this")."""
    if not taken:
        return None, []
    from shapely.geometry import MultiPolygon, Polygon
    from shapely.ops import polylabel

    from .shapeops import _cutter

    mask = np.zeros((pic.h, pic.w), np.uint8)
    inside: list[tuple[int, int]] = []
    ppm = place.px_per_mm(pic)
    for obj in taken:
        try:
            area = _cutter(obj)
        except Exception:  # noqa: BLE001 - a shape that can't be read is simply not counted
            continue
        if area is None or area.is_empty:
            continue
        area = area.buffer(-TUCK_MM)
        polys = [area] if isinstance(area, Polygon) else list(area.geoms) if isinstance(area, MultiPolygon) else []
        for poly in polys:
            if poly.is_empty or poly.area < 0.5:
                continue
            rings = [np.asarray(poly.exterior.coords), *(np.asarray(r.coords) for r in poly.interiors)]
            px = [np.round(place.to_px(pic, r)).astype(np.int32) for r in rings]
            one = np.zeros_like(mask)
            cv2.fillPoly(one, [px[0]], 1)
            if len(px) > 1:
                cv2.fillPoly(one, px[1:], 0)
            mask |= one
            if poly.area * ppm * ppm >= 16:
                c = polylabel(poly, 0.2)
                u, v = place.to_px(pic, np.array([[c.x, c.y]]))[0]
                if 0 <= u < pic.w and 0 <= v < pic.h:
                    inside.append((int(round(u)), int(round(v))))
    return (mask if mask.any() else None), inside


def region(path: str, placement: dict[str, Any], at: list[float], spacing_mm: float = 3.0,
           add: list[list[float]] | None = None, subtract: list[list[float]] | None = None,
           spread: int = SPREAD_DEFAULT, use_ai: bool = False, taken: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Guesses for what was clicked at `at` (mm) on a picture, best first.

    `add` and `subtract` are more clicks (Shift+click, Alt+click): their areas are joined to, or
    cut out of, every guess. `spread` (1-10) is how readily an area spreads into similar colors.
    `use_ai`: also ask the AI tracing model, if it's installed (its guesses come first).
    `taken`: the shapes already drawn (layout objects). The guesses see the design as a whole:
    a guess that runs over them comes fitted around them (tucked TUCK_MM under, so nothing is
    sewn twice), with the full guess offered after; and the AI is told they're "not this".

    Returns {"candidates": [...], "ms"}. A fill guess: {"kind": "fill", "id", "label", "outline",
    "holes", "area_mm2", "line_width_mm", "color", "background"}; a line guess: {"kind": "satin",
    "id", "label", "nodes", "width_mm", "closed", "color"}. Points are [x, y, "c" | "s"] in mm.
    "ai_error" (plain words) is there when the AI was asked but couldn't run.
    """
    t0 = time.perf_counter()
    if not MIN_SPACING_MM <= spacing_mm <= MAX_SPACING_MM:
        raise TraceError(f"Point spacing must be between {MIN_SPACING_MM} and {MAX_SPACING_MM:.0f} mm")
    if not SPREAD_MIN <= spread <= SPREAD_MAX:
        raise TraceError(f"Spread must be between {SPREAD_MIN} and {SPREAD_MAX}")
    pic = prepare(path)
    place = Placement.from_dict(placement)
    seed = _seed_px(pic, place, at) if min(pic.w, pic.h) >= MIN_PICTURE_PX else None
    if seed is None:
        return {"candidates": [], "ms": round((time.perf_counter() - t0) * 1000, 1)}
    adds = [p for p in (_seed_px(pic, place, a) for a in add or []) if p and not pic.ink[p[1], p[0]]]
    subs = [p for p in (_seed_px(pic, place, a) for a in subtract or []) if p]
    ppm = place.px_per_mm(pic)
    reach = max(2, round(3 * ppm))
    candidates: list[dict[str, Any]] = []
    masks: list[np.ndarray] = []
    whole = pic.w * pic.h
    # Clicking on a shape already drawn means tracing that spot again: leave the guesses whole.
    taken_px, taken_inside = _taken_mask(pic, place, taken)
    if taken_px is not None and taken_px[seed[1], seed[0]]:
        taken_px = None
    full_later: list[dict[str, Any]] = []

    def one(r: np.ndarray, gid: str, label: str, line_px: float) -> dict[str, Any] | None:
        c = _fill_candidate(pic, r, seed, place, spacing_mm)
        if not c:
            return None
        c["id"] = gid
        c["label"] = label
        c["color"] = _hex(pic.smooth[(r > 0) & (pic.ink == 0)])
        if line_px:
            c["line_width_mm"] = round(min(max(line_px / ppm, 0.8), 10.0), 2)
        # The paper around everything: offer it, but last.
        c["background"] = bool(np.count_nonzero(r) > 0.6 * whole)
        if c["background"]:
            c["label"] = "The background (everything around the shapes)"
        return c

    def finish(r: np.ndarray, gid: str, label: str, line_px: float) -> None:
        if any(_iou(r, m) > SAME_GUESS_IOU for m in masks):
            return
        if taken_px is not None:
            n = np.count_nonzero(r)
            fitted = (r & (1 - taken_px)).astype(np.uint8)
            left = np.count_nonzero(fitted)
            if n and (n - left) > FIT_MIN_SHARE * n and left >= FIT_KEEP_SHARE * n:
                c = one(fitted, gid, label, line_px)
                if c:
                    masks.append(r)
                    c["label"] += ", fitted around your shapes"
                    c["fitted"] = True
                    candidates.append(c)
                    # The whole guess too (to sew on top of them), after the fitted ones.
                    full = one(r, gid + "-whole", label + ", over your shapes", line_px)
                    if full:
                        full_later.append(full)
                    return
        c = one(r, gid, label, line_px)
        if c:
            masks.append(r)
            candidates.append(c)

    ai_error = None
    if use_ai:
        from .ai import segment

        if segment.available():
            # The AI is an extra: if it can't run (a damaged model file), the usual guesses still come.
            # The shapes nearest the click are pointed out as "not this", so the AI's outline stops
            # at what's already drawn rather than taking it in again.
            near = sorted(taken_inside, key=lambda q: (q[0] - seed[0]) ** 2 + (q[1] - seed[1]) ** 2)
            avoid = near[:AI_AVOID_MAX] if taken_px is not None else []
            try:
                found = segment.masks(pic, [seed, *adds], [*subs, *avoid])
            except Exception as exc:  # noqa: BLE001 - any failure inside ONNX Runtime
                found = []
                ai_error = f"The AI tracing model couldn't run ({type(exc).__name__}). Showing the usual guesses; removing and downloading it again in Settings may help."
            for k, (m, score) in enumerate(found):
                r, line_px = _to_line_middle(pic, m, reach)
                finish(r, f"ai{k}", f"AI guess {k + 1} (sure: {round(min(score, 1.0) * 100)}%)", line_px)

    if pic.ink[seed[1], seed[0]]:
        # Inside a solid dark area (a black shape, a silhouette): outline it as a fill.
        solid = _solid_dark(pic, ppm)
        if solid[seed[1], seed[0]]:
            n, lab = cv2.connectedComponents(solid, connectivity=8)
            finish((lab == lab[seed[1], seed[0]]).astype(np.uint8), "dark", "Fill, this dark area", 0.0)
        candidates += _ribbon_candidates(pic, seed, place, spacing_mm)
    else:
        for gid, label, how, to_middle in REGION_GUESSES:
            r = _guess_region(pic, seed, how, spread)
            for a in adds:
                r = r | _guess_region(pic, a, how, spread)
            if np.count_nonzero(r) < 4:
                continue
            line_px = 0.0
            if to_middle:
                r, line_px = _to_line_middle(pic, r, reach)
            for sp in subs:
                cut = _guess_region(pic, sp, how, spread)
                if to_middle and cut.any():
                    cut, _ = _to_line_middle(pic, cut, reach)
                r = r & (1 - cut)
            finish(r.astype(np.uint8), gid, label, line_px)
    candidates += [c for c in full_later if not any(_same_outline(c, k) for k in candidates)]
    candidates.sort(key=lambda c: bool(c.get("background")))
    out: dict[str, Any] = {"candidates": candidates, "ms": round((time.perf_counter() - t0) * 1000, 1)}
    if ai_error:
        out["ai_error"] = ai_error
    return out


# ---------------------------------------------------------------- the whole picture at once


def _segments(skel: np.ndarray) -> list[tuple[list[tuple[int, int]], bool]]:
    """Every piece of a one-pixel skeleton between line ends and junctions (and closed loops).
    Returns (pixels, closed) per piece."""
    ys, xs = np.nonzero(skel)
    pix = set(zip(xs.tolist(), ys.tolist()))
    ny, nx = np.nonzero(skel & (_neighbour_counts(skel) != 2))
    nodes = set(zip(nx.tolist(), ny.tolist()))
    used: set[frozenset] = set()
    out = []
    for start in nodes:
        for nb in _neighbours(skel, *start):
            if frozenset((start, nb)) in used:
                continue
            path = [start, nb]
            used.add(frozenset((start, nb)))
            prev, cur = start, nb
            while cur not in nodes:
                nxt = [q for q in _neighbours(skel, *cur) if q != prev and frozenset((cur, q)) not in used]
                if not nxt:
                    break
                used.add(frozenset((cur, nxt[0])))
                prev, cur = cur, nxt[0]
                path.append(cur)
            out.append((path, False))
    # Loops with no ends or junctions (a ring, an O).
    seen = {p for path, _ in out for p in path}
    for p in sorted(pix - seen):
        if p in seen:
            continue
        loop = [p]
        seen.add(p)
        prev, cur = None, p
        while True:
            nxt = [q for q in _neighbours(skel, *cur) if q != prev and q not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            loop.append(cur)
        if len(loop) > 8:
            out.append((loop, True))
    return out


# A connected dark line that is mostly at least this wide is a shape to fill, not a line (bold
# lettering): one fill per letter instead of a patchwork of fills and satin pieces.
MIN_PICTURE_PX = 4  # a picture smaller than this has nothing to trace
BOLD_MM = 2.8
SOLID_MM = 3.0  # parts of a dark area wider than this are fills too
MIN_FILL_WIDTH_MM = 1.0  # thinner color areas (soft edges, glows) aren't sewn as fills
MIN_LINE_MM = 2.0  # shorter dark lines are specks
SAME_THREAD_DE = 10.0  # colors closer than this (CIE76) get one thread
BACKGROUND_DE = 12.0  # colors this close to the edge color count as background too


def _solid_dark(pic: Pic, ppm: float) -> np.ndarray:
    """Dark (ink) pixels to sew as fills rather than lines: the parts wider than SOLID_MM, and
    every connected dark shape whose strokes are mostly at least BOLD_MM wide."""
    cache = pic.__dict__.setdefault("_solid", {})
    key = round(ppm, 4)
    if key in cache:
        return cache[key]
    ink = pic.ink > 0
    solid_r = max(2, round(SOLID_MM / 2 * ppm))
    core = (ink & (pic.ink_dt >= solid_r)).astype(np.uint8)
    # Only real blobs: where a line's width wanders about SOLID_MM (or lines meet), the few wide
    # pixels would otherwise cut the line into a patchwork of small fills and satin pieces.
    n, lab, st, _ = cv2.connectedComponentsWithStats(core, connectivity=8)
    small = np.nonzero(st[:, cv2.CC_STAT_AREA] < solid_r * solid_r)[0]
    if n > 1 and len(small):
        core[np.isin(lab, small[small > 0])] = 0
    if not core.any():
        solid = np.zeros_like(ink)
    elif solid_r <= 30:
        disk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * solid_r + 3, 2 * solid_r + 3))
        solid = (cv2.dilate(core, disk) > 0) & ink
    else:
        # A picture placed very small has many pixels per mm, and a dilate's cost grows with the
        # disk: 14 s at 2 mm wide (QA2 T4). The distance to the core is the same test at a fixed cost.
        dist = cv2.distanceTransform((core == 0).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
        solid = (dist <= solid_r + 1) & ink
    # Each connected dark shape's typical stroke width, from the middle (ridge) of its strokes.
    ridge = ink & (pic.ink_dt >= cv2.dilate(pic.ink_dt, np.ones((3, 3), np.uint8)) - 1e-3)
    lab, val = pic.ink_labels[ridge], pic.ink_dt[ridge]
    if len(lab):
        order = np.lexsort((val, lab))
        lab, val = lab[order], val[order]
        labels, first, counts = np.unique(lab, return_index=True, return_counts=True)
        bold = labels[2 * val[first + counts // 2] >= BOLD_MM * ppm]
        if len(bold):
            member = np.zeros(int(pic.ink_labels.max()) + 1, bool)
            member[bold] = True
            solid |= member[pic.ink_labels] & ink
    if len(cache) > 4:
        cache.pop(next(iter(cache)))
    cache[key] = solid.astype(np.uint8)
    return cache[key]


def _background_groups(pic: Pic) -> np.ndarray | None:
    """Which color groups are the paper (or fabric): the color that fills most of the picture's
    edge, light or dark, plus colors very close to it. None when no one color holds the edge."""
    g = pic.groups
    if g is None or pic.centres is None:
        return None
    border = np.concatenate([g[0], g[-1], g[1:-1, 0], g[1:-1, -1]])
    counts = np.bincount(border, minlength=len(pic.centres))
    top = int(counts.argmax())
    near = _delta_e(pic.centres, pic.centres[top]) <= BACKGROUND_DE
    if counts[near].sum() < 0.5 * len(border):
        return None
    return near


def _cv_lab_to_cie(lab: np.ndarray) -> np.ndarray:
    """OpenCV's 8-bit Lab (L 0-255, a and b offset by 128) as CIE Lab."""
    lab = np.asarray(lab, np.float64).reshape(-1, 3)
    return np.stack([lab[:, 0] * 100 / 255, lab[:, 1] - 128, lab[:, 2] - 128], axis=1)


def _delta_e(cv_lab: np.ndarray, ref: np.ndarray) -> np.ndarray:
    return np.linalg.norm(_cv_lab_to_cie(cv_lab) - _cv_lab_to_cie(ref), axis=1)


def _hex_lab(colors: list[str]) -> np.ndarray:
    rgb = np.array([[int(c[i : i + 2], 16) for i in (1, 3, 5)] for c in colors], np.uint8).reshape(-1, 1, 3)
    return _cv_lab_to_cie(cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).reshape(-1, 3))


def _one_thread_per_color(shapes: list[dict[str, Any]], weights: list[float]) -> None:
    """Shades that are really one color (anti-aliasing, JPEG) get one thread: each color joins
    the closest bigger color within SAME_THREAD_DE. Changes the shapes' colors in place."""
    if not shapes:
        return
    colors = sorted({s["color"] for s in shapes})
    weight = dict.fromkeys(colors, 0.0)
    for s, w in zip(shapes, weights):
        weight[s["color"]] += w
    order = sorted(colors, key=lambda c: -weight[c])
    lab = dict(zip(colors, _hex_lab(colors)))
    keep: list[str] = []
    to: dict[str, str] = {}
    for c in order:
        best = min(keep, key=lambda k: float(np.linalg.norm(lab[k] - lab[c])), default=None)
        if best is not None and float(np.linalg.norm(lab[best] - lab[c])) <= SAME_THREAD_DE:
            to[c] = best
        else:
            keep.append(c)
            to[c] = c
    for s in shapes:
        s["color"] = to[s["color"]]


def _mean_width_px(region: np.ndarray) -> float:
    """2 x area / outline length: about how wide an area is (a thin ring has a small one)."""
    x, y, w, h = cv2.boundingRect(region)
    if not w:
        return 0.0
    crop = np.pad(region[y : y + h, x : x + w], 1)
    cnts, _ = cv2.findContours(crop, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    perimeter = sum(cv2.arcLength(c, True) for c in cnts) or 1.0
    return 2 * float(np.count_nonzero(crop)) / perimeter


def digitize_all(path: str, placement: dict[str, Any], spacing_mm: float = 3.0, spread: int = SPREAD_DEFAULT,
                 outlines: bool = True, skip_background: bool = True, min_area_mm2: float = 6.0) -> dict[str, Any]:
    """The whole picture as shapes: every area of color as a fill (out to the middle of its
    outline), solid dark areas as fills, and the dark lines as satin ribbons (or running stitch
    where they're too thin for satin). Biggest areas sew first, outlines last.

    `skip_background` leaves out the paper: the color that fills most of the picture's edge
    (light or dark), wherever it shows (inside letters too).

    Returns {"shapes": [...], "ms"}: fills {"kind": "fill", "outline", "holes", "color"},
    ribbons {"kind": "satin", "nodes", "width_mm", "closed", "color"}, thin lines {"kind": "run",
    "nodes", "closed", "color"}."""
    t0 = time.perf_counter()
    if not MIN_SPACING_MM <= spacing_mm <= MAX_SPACING_MM:
        raise TraceError(f"Point spacing must be between {MIN_SPACING_MM} and {MAX_SPACING_MM:.0f} mm")
    pic = prepare(path)
    place = Placement.from_dict(placement)
    if min(pic.w, pic.h) < MIN_PICTURE_PX:
        return {"shapes": [], "ms": round((time.perf_counter() - t0) * 1000, 1)}
    ppm = place.px_per_mm(pic)
    reach = max(2, round(3 * ppm))
    min_px = min_area_mm2 * ppm * ppm
    bg = _background_groups(pic) if skip_background else None
    bg_px = bg[pic.groups] if bg is not None else np.zeros((pic.h, pic.w), bool)

    # Solid dark areas are fills, not lines. A dark background (one mostly of the paper's color)
    # is left out with everything dark joined to it, and nothing grows into it.
    solid = _solid_dark(pic, ppm)
    s_cnt, s_lab, s_st, _ = cv2.connectedComponentsWithStats(solid, connectivity=8)
    dark_fills = []
    dropped_labels: set[int] = set()
    for c in range(1, s_cnt):
        if s_st[c, cv2.CC_STAT_AREA] < min_px:
            continue
        x, y, w, h = (int(v) for v in s_st[c, :4])
        m = np.zeros((pic.h, pic.w), np.uint8)
        m[y : y + h, x : x + w] = s_lab[y : y + h, x : x + w] == c
        if bg is not None and np.count_nonzero(m & bg_px) > 0.5 * s_st[c, cv2.CC_STAT_AREA]:
            dropped_labels.update(np.unique(pic.ink_labels[m > 0]).tolist())
            continue
        dark_fills.append((float(s_st[c, cv2.CC_STAT_AREA]), m))
    block = None
    if dropped_labels:
        member = np.zeros(int(pic.ink_labels.max()) + 1, bool)
        member[list(dropped_labels)] = True
        block = (member[pic.ink_labels] & (pic.ink > 0)).astype(np.uint8)
    lines_ink = ((pic.ink > 0) & (solid == 0)).astype(np.uint8)
    if block is not None:
        lines_ink &= 1 - block

    # One ink color: the dark lines and solid dark areas are one thread, not a shade per piece.
    ink_px = (pic.ink > 0) & (pic.ink_dt >= 1.5)
    if block is not None:
        ink_px &= block == 0
    ink_color = _hex(pic.smooth[ink_px]) if ink_px.any() else _hex(pic.smooth[pic.ink > 0])

    fills: list[tuple[float, dict[str, Any]]] = []
    assigned = np.zeros((pic.h, pic.w), np.uint8)
    free = pic.ink == 0
    # Patches of one simplified color, biggest first; each seeds an area of color.
    patches = []
    for g in range(len(pic.centres)):
        cnt, lab, st, _ = cv2.connectedComponentsWithStats(((pic.groups == g) & free).astype(np.uint8), connectivity=4)
        for c in range(1, cnt):
            if st[c, cv2.CC_STAT_AREA] >= min_px:
                patches.append((int(st[c, cv2.CC_STAT_AREA]), g, lab, c, tuple(int(v) for v in st[c, :4])))
    patches.sort(key=lambda t: -t[0])
    for area_px, g, lab, c, (x, y, w, h) in patches:
        patch = lab[y : y + h, x : x + w] == c
        if np.count_nonzero(patch & (assigned[y : y + h, x : x + w] > 0)) > 0.5 * area_px:
            continue
        dist = cv2.distanceTransform(np.pad(patch, 1).astype(np.uint8), cv2.DIST_L2, 3)[1:-1, 1:-1]
        sy, sx = np.unravel_index(int(np.argmax(dist)), dist.shape)
        seed = (int(sx) + x, int(sy) + y)
        r = _simple_region(pic, seed, spread) & (1 - assigned)
        if bg is not None and bg[g]:
            # The paper (around the shapes, or showing through a letter): left out. Only its own
            # colors are taken, so a pale shape it spreads into is still traced.
            assigned |= r & bg_px
            continue
        if bg is not None:
            r &= ~bg_px
        if np.count_nonzero(r) < min_px:
            continue
        assigned |= r
        if _mean_width_px(r) < MIN_FILL_WIDTH_MM * ppm:
            continue  # a soft edge or glow: too thin to sew as a fill
        grown, _ = _to_line_middle(pic, r, reach, block)
        cand = _fill_candidate(pic, grown, seed, place, spacing_mm)
        if not cand:
            continue
        color = _hex(pic.smooth[(r > 0) & (pic.ink == 0)])
        for part in [{"outline": cand["outline"], "holes": cand["holes"]}, *cand.get("parts", [])]:
            fills.append((float(np.count_nonzero(r)), {"kind": "fill", **part, "color": color}))

    for area, m in dark_fills:
        sy, sx = np.unravel_index(int(np.argmax(cv2.distanceTransform(m, cv2.DIST_L2, 3))), m.shape)
        cand = _fill_candidate(pic, m, (int(sx), int(sy)), place, spacing_mm)
        if cand:
            fills.append((area, {"kind": "fill", "outline": cand["outline"], "holes": cand["holes"], "color": ink_color}))
    fills.sort(key=lambda t: -t[0])
    shapes = [f for _, f in fills]
    weights = [a for a, _ in fills]

    # The dark lines, as satin ribbons along their middles (running stitch where too thin).
    if outlines and lines_ink.any():
        # Bridge the pixel-wide breaks JPEG leaves in thin lines (one line, not a row of specks).
        bridged = cv2.dilate(lines_ink, np.ones((3, 3), np.uint8)) & (1 - solid)
        if block is not None:
            bridged &= 1 - block
        skel = _prune(_one_pixel(thin(bridged)), max(3, round(1.0 * ppm)))
        ends = _neighbour_counts(skel) == 1
        for seg, closed in _segments(skel):
            width_px = min(2 * float(np.median([pic.ink_dt[y, x] for x, y in seg])), 10.0 * ppm)
            px = np.array(seg, dtype=np.float64)
            if not closed:
                # Reach the rounded tip at free line ends (not where lines meet).
                px = _reach_tips(px, width_px / 2, (bool(ends[seg[0][1], seg[0][0]]), bool(ends[seg[-1][1], seg[-1][0]])))
            if float(np.hypot(*np.diff(px, axis=0).T).sum()) < MIN_LINE_MM * ppm:
                continue  # a speck
            nodes = to_nodes(px, place, pic, spacing_mm, closed)
            if len(nodes) < 2:
                continue
            width = width_px / ppm
            if width >= 0.8:
                shapes.append({"kind": "satin", "nodes": nodes, "width_mm": round(min(width, 10.0), 2), "closed": closed, "color": ink_color})
            else:
                shapes.append({"kind": "run", "nodes": nodes, "closed": closed, "color": ink_color})
            weights.append(len(seg) * max(width_px, 1.0))
    _one_thread_per_color(shapes, weights)
    return {"shapes": shapes, "ms": round((time.perf_counter() - t0) * 1000, 1)}
