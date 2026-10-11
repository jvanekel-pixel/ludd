"""Stitch Advisor: a model suggests how to stitch drawn shapes; the user accepts each suggestion.

For each shape the model gets a small picture (the reference picture under the shape, with the
shape's outline drawn on it, or the shape on its own) and a summary of its geometry. It answers
in JSON: stitch type, fill angle, density, underlay amount, and a sewing order, each with a
one-line reason. The answer is checked strictly against that shape; anything else is dropped.
Suggestions that match what the shape already has are left out.
"""

from __future__ import annotations

import io
import json
import math
from typing import Any

from PIL import Image, ImageDraw, ImageOps
from shapely.geometry import LineString, Polygon
from shapely.ops import polylabel

from .. import fabrics, kept
from ..digitize import stitches as dz
from ..digitize.paths import flatten
from .providers import AIError, Request, extract_json, require

MAX_OBJECTS = 12
CROP_PX = 320
STITCH_TYPES = ("run", "satin", "fill")
DENSITIES = {"light": 0.5, "normal": 0.4, "dense": 0.33}
LEVELS = ("light", "normal", "heavy")
REASON_MAX = 300

SYSTEM = """You are an expert machine-embroidery digitizer helping a beginner. For each shape you are
shown, suggest how to stitch it on a home embroidery machine. Rules of thumb: running stitch for
thin lines and details under 1.5 mm wide; satin for columns about 1.5 to 8 mm wide (borders,
lettering strokes); fill (tatami) for areas wider than about 8 mm. Fill angles run across the shape's
long direction and differ between neighbouring fills so they reflect light differently. Sew
background shapes before foreground ones, and large areas before details. Lighter density for
stretchy fabrics and big fills, denser for small or high-contrast shapes.

Answer with JSON only, exactly in this form:
{"objects": [{"id": "<shape id>", "stitch_type": "run" | "satin" | "fill", "angle_deg": <0-179 or null>,
  "density": "light" | "normal" | "dense" | null, "underlay": "light" | "normal" | "heavy" | null,
  "reason": "<one short sentence a beginner understands>"}],
 "order": ["<shape id>", ...] or null, "order_reason": "<one short sentence>" or null}
Use only the ids you were given. Give one entry per shape."""


# ---------------------------------------------------------------- what the model sees


def _ring(obj: dict[str, Any]) -> list[tuple[float, float]]:
    g = obj.get("geometry") or {}
    if obj["kind"] == "satin":
        a, _ = flatten(g.get("rail_a") or [])
        b, _ = flatten(g.get("rail_b") or [])
        return a + b[::-1] + a[:1]
    if obj["kind"] == "run":
        pts, _ = flatten(g.get("nodes") or [], bool(g.get("closed")))
        return pts
    pts, _ = flatten(g.get("outline") or [], True)
    return pts + pts[:1]


def summarize(obj: dict[str, Any]) -> dict[str, Any]:
    """Numbers a digitizer would look at: size, area, width of columns, current settings."""
    ring = _ring(obj)
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    out: dict[str, Any] = {
        "id": obj["id"],
        "current_type": obj["kind"],
        "size_mm": [round(max(xs) - min(xs), 1), round(max(ys) - min(ys), 1)],
    }
    p = obj.get("params") or {}
    if obj["kind"] == "satin":
        pairs = dz.satin_pairs((obj["geometry"] or {})["rail_a"], obj["geometry"]["rail_b"], 1.0)
        widths = sorted(math.dist(a, b) for a, b in pairs)
        out["column_width_mm"] = {"min": round(widths[0], 1), "typical": round(widths[len(widths) // 2], 1), "max": round(widths[-1], 1)}
        out["length_mm"] = round(LineString([((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in pairs]).length, 1)
    elif obj["kind"] == "run":
        out["length_mm"] = round(LineString(ring).length, 1) if len(ring) > 1 else 0
    else:
        poly = Polygon(ring).buffer(0)
        out["area_mm2"] = round(poly.area, 1)
        # Widest part: the biggest circle that fits inside the shape.
        inner = polylabel(poly, 0.2) if poly.geom_type == "Polygon" else poly.centroid
        out["widest_mm"] = round(2 * poly.boundary.distance(inner), 1)
        out["fill_angle_deg"] = p.get("angle_deg", 45)
    if obj["kind"] in ("satin", "fill"):
        out["density"] = _density_name(p.get("spacing_mm", 0.4))
    return out


def _density_name(spacing: float) -> str:
    return min(DENSITIES, key=lambda k: abs(DENSITIES[k] - float(spacing)))


def _picture_under(images: list[dict[str, Any]], box: tuple[float, float, float, float], size: tuple[int, int]) -> Image.Image | None:
    """The reference picture under a box (mm), resampled to `size` pixels; None if there isn't one."""
    x0, y0, x1, y1 = box
    for im in reversed(images):
        if not im.get("visible", True) or not im.get("path"):
            continue
        try:
            with Image.open(kept.readable(im["path"])) as src:
                pic = ImageOps.exif_transpose(src).convert("RGB")
        except OSError:
            continue
        w_mm, h_mm = float(im["width_mm"]), float(im["height_mm"])
        a = math.radians(-float(im.get("rotate", 0)))
        ca, sa = math.cos(a), math.sin(a)
        sx, sy = (x1 - x0) / size[0], (y1 - y0) / size[1]
        # Output pixel (u, v) -> mm -> picture-local mm (unrotated) -> picture pixel.
        kx, ky = pic.width / w_mm, pic.height / h_mm
        cx, cy = float(im["x"]), float(im["y"])
        ox, oy = x0 - cx, y0 - cy
        coeffs = (
            kx * ca * sx, -kx * sa * sy, kx * (ca * ox - sa * oy) + pic.width / 2,
            ky * sa * sx, ky * ca * sy, ky * (sa * ox + ca * oy) + pic.height / 2,
        )
        crop = pic.transform(size, Image.Transform.AFFINE, coeffs, resample=Image.Resampling.BILINEAR, fillcolor=(255, 255, 255))
        # Only use a picture that actually lies under the shape.
        if crop.convert("L").getextrema() != (255, 255):
            return crop
    return None


def render_crop(obj: dict[str, Any], images: list[dict[str, Any]]) -> bytes:
    ring = _ring(obj)
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    m = max(w, h) * 0.2 + 2
    box = (min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m)
    bw, bh = box[2] - box[0], box[3] - box[1]
    scale = CROP_PX / max(bw, bh)
    size = (max(16, round(bw * scale)), max(16, round(bh * scale)))
    picture = _picture_under(images, box, size)
    base = picture or Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(base)
    pts = [((x - box[0]) * scale, (y - box[1]) * scale) for x, y in ring]
    color = (obj.get("thread") or {}).get("color", "#1f3a93")
    if len(pts) > 2 and obj["kind"] != "run" and picture is None:
        draw.polygon(pts, fill=color)
    draw.line(pts, fill=(230, 30, 80), width=3)
    buf = io.BytesIO()
    base.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def build_request(layout: dict[str, Any], images: list[dict[str, Any]], ids: list[str] | None) -> tuple[Request, list[dict[str, Any]]]:
    objs = [it for it in layout.get("items") or [] if it.get("kind") in ("run", "satin", "fill")]
    if ids:
        objs = [o for o in objs if o["id"] in set(ids)]
    if not objs:
        raise AIError("Select a drawn shape (line, satin or fill) for the Stitch Advisor to look at")
    objs = objs[:MAX_OBJECTS]
    fabric = fabrics.get(layout.get("fabric"))
    summaries = [summarize(o) for o in objs]
    text = (
        f"Fabric: {fabric['name']}.\n"
        f"There are {len(objs)} shapes, in the current sewing order. Picture 1 shows shape 1, and so on:"
        " the red line is the shape's outline (over the picture being traced, if there is one).\n\n"
        + "\n".join(f"Shape {n + 1}: {json.dumps(s)}" for n, s in enumerate(summaries))
    )
    req = Request(system=SYSTEM, text=text, images=[render_crop(o, images) for o in objs], json_out=True, max_tokens=1500)
    return req, objs


# ---------------------------------------------------------------- checking the answer


def validate(answer: Any, objs: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep only well-formed suggestions about the shapes that were sent, that would change something."""
    if not isinstance(answer, dict) or not isinstance(answer.get("objects"), list):
        raise AIError("The model's answer wasn't in the expected form, so nothing was changed. Try again.")
    by_id = {o["id"]: o for o in objs}
    proposals, dropped, seen = [], 0, set()
    for e in answer["objects"]:
        o = by_id.get(e.get("id")) if isinstance(e, dict) else None
        st = e.get("stitch_type") if isinstance(e, dict) else None
        reason = e.get("reason") if isinstance(e, dict) else None
        if o is None or o["id"] in seen or st not in STITCH_TYPES or not isinstance(reason, str) or not reason.strip():
            dropped += 1
            continue
        angle, density, level = e.get("angle_deg"), e.get("density"), e.get("underlay")
        if (angle is not None and not isinstance(angle, (int, float))) or (density is not None and density not in DENSITIES) \
                or (level is not None and level not in LEVELS):
            dropped += 1
            continue
        seen.add(o["id"])
        p = o.get("params") or {}
        change: dict[str, Any] = {}
        if st != o["kind"]:
            change["stitch_type"] = st
        target = st
        if target == "fill" and angle is not None:
            a = float(angle) % 180
            if o["kind"] != "fill" or abs(((a - float(p.get("angle_deg", 45))) + 90) % 180 - 90) > 5:
                change["angle_deg"] = round(a)
        if target in ("satin", "fill") and density and (o["kind"] != target or _density_name(p.get("spacing_mm", 0.4)) != density):
            change["density"] = density
        if target in ("satin", "fill") and level:
            change["underlay"] = level
        if not change:
            continue
        proposals.append({"id": o["id"], "change": change, "reason": reason.strip()[:REASON_MAX]})
    order = answer.get("order")
    order_out = None
    current = [o["id"] for o in objs]
    if isinstance(order, list) and sorted(map(str, order)) == sorted(current) and list(order) != current:
        r = answer.get("order_reason")
        order_out = {"ids": list(order), "reason": r.strip()[:REASON_MAX] if isinstance(r, str) and r.strip() else "A better sewing order."}
    elif order is not None and not (isinstance(order, list) and list(order) == current):
        dropped += 1
    return {"proposals": proposals, "order": order_out, "dropped": dropped}


def advise(layout: dict[str, Any], images: list[dict[str, Any]], ids: list[str] | None) -> dict[str, Any]:
    provider = require("advisor", "vision")
    req, objs = build_request(layout, images, ids)
    return validate(extract_json(provider.ask(req)), objs)
