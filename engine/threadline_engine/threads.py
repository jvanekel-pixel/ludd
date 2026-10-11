"""Thread charts and color matching.

Built-in charts come from pyembroidery's machine palettes; users import others
(Madeira, Isacord, ...) from CSV. Matching uses CIEDE2000 in CIELAB.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
from pathlib import Path
from typing import Any

from pyembroidery.EmbThreadJef import get_thread_set as _jef_threads
from pyembroidery.EmbThreadPec import get_thread_set as _pec_threads

from .storage import data_dir


class ThreadError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


# ---------------------------------------------------------------- color math


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ThreadError(f"Not a hex color: {h!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """sRGB (D65) -> CIELAB."""

    def lin(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in rgb)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def ciede2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    """CIEDE2000 color difference (Sharma, Wu, Dalal 2005)."""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cbar = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cbar**7 / (Cbar**7 + 25**7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if C1p else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if C2p else 0.0

    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))

    Lbp = (L1 + L2) / 2
    Cbp = (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hbp = (h1p + h2p + 360) / 2
    else:
        hbp = (h1p + h2p - 360) / 2

    T = (
        1
        - 0.17 * math.cos(math.radians(hbp - 30))
        + 0.24 * math.cos(math.radians(2 * hbp))
        + 0.32 * math.cos(math.radians(3 * hbp + 6))
        - 0.20 * math.cos(math.radians(4 * hbp - 63))
    )
    dtheta = 30 * math.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cbp**7 / (Cbp**7 + 25**7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / math.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2 * dtheta)) * Rc
    return math.sqrt(
        (dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh)
    )


# ---------------------------------------------------------------- charts


def _builtin(chart_id: str, name: str, brand: str, threads) -> dict[str, Any]:
    seen, out = set(), []
    for t in threads:
        if t is None or t.catalog_number in seen:
            continue
        seen.add(t.catalog_number)
        out.append({"code": t.catalog_number or "", "name": t.description or "", "color": t.hex_color()})
    return {"id": chart_id, "name": name, "brand": brand, "builtin": True, "threads": out}


BUILTIN_CHARTS = {
    c["id"]: c
    for c in (
        _builtin("brother-palette", "Brother (machine palette)", "Brother", _pec_threads()),
        _builtin("janome", "Janome", "Janome", _jef_threads()),
    )
}


def _charts_dir() -> Path:
    return data_dir() / "threads"


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "chart"


def _summary(c: dict[str, Any]) -> dict[str, Any]:
    return {k: c[k] for k in ("id", "name", "brand", "builtin")} | {"count": len(c["threads"]), "mine": bool(c.get("mine"))}


def list_charts() -> list[dict[str, Any]]:
    """Chart summaries (no thread lists): My threads first, then built-ins, then imported."""
    charts = [my_threads(), *BUILTIN_CHARTS.values()]
    d = _charts_dir()
    if d.is_dir():
        for f in sorted(d.glob("*.json")):
            if f.stem == MY_THREADS:
                continue
            try:
                charts.append(json.loads(f.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
    return [_summary(c) for c in charts]


def get_chart(chart_id: str) -> dict[str, Any]:
    if chart_id == MY_THREADS:
        return my_threads()
    if chart_id in BUILTIN_CHARTS:
        return BUILTIN_CHARTS[chart_id]
    f = _charts_dir() / f"{chart_id}.json"
    if not f.is_file():
        raise ThreadError(f"Unknown thread chart: {chart_id}")
    return json.loads(f.read_text(encoding="utf-8"))


def _column_kind(header: str) -> str | None:
    """Classify a CSV header loosely: "Madeira Code", "Thread #", "Color Name", "HEX", "Red", ..."""
    h = re.sub(r"[^a-z0-9#]+", " ", header.lower()).strip()
    words = set(h.split())
    for kind, names in (("r", {"r", "red"}), ("g", {"g", "green"}), ("b", {"b", "blue"})):
        if h in names:
            return kind
    if words & {"hex", "html", "web", "rgb"}:
        return "hex"
    if words & {"code", "number", "no", "num", "#", "catalog", "id", "sku"}:
        return "code"
    if words & {"name", "description", "desc"} or h in ("color", "colour"):
        return "name"
    return None


def parse_csv(text: str) -> list[dict[str, str]]:
    """Parse a thread chart CSV. Needs a code column and either a hex column or R, G, B columns.

    Column names are matched loosely (e.g. "Number", "Color Name", "Red").
    """
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ThreadError("The CSV needs a header row and at least one thread")

    col: dict[str, int] = {}
    for i, h in enumerate(rows[0]):
        kind = _column_kind(h.strip().lstrip("﻿"))
        if kind and kind not in col:  # first matching column wins
            col[kind] = i
    # A "color"/"colour" column holding hex values is the hex column, not the name.
    if "hex" not in col and "name" in col and all(
        re.fullmatch(r"#?[0-9a-fA-F]{6}", r[col["name"]].strip()) for r in rows[1:] if len(r) > col["name"]
    ):
        col["hex"] = col.pop("name")
    if "code" not in col:
        raise ThreadError(f"No thread number column found (looked for: code, number). Columns: {', '.join(rows[0])}")
    if "hex" not in col and not {"r", "g", "b"} <= col.keys():
        raise ThreadError("No color column found: add a 'hex' column, or 'R', 'G' and 'B' columns")

    threads, bad = [], []
    for n, r in enumerate(rows[1:], start=2):
        cell = lambda k: r[col[k]].strip() if k in col and col[k] < len(r) else ""  # noqa: E731
        try:
            if "hex" in col:
                color = rgb_to_hex(*hex_to_rgb(cell("hex")))
            else:
                color = rgb_to_hex(*(max(0, min(255, int(float(cell(k))))) for k in "rgb"))
        except (ThreadError, ValueError):
            bad.append(n)
            continue
        if not cell("code"):
            bad.append(n)
            continue
        threads.append({"code": cell("code"), "name": cell("name"), "color": color})
    if not threads:
        raise ThreadError(f"No usable threads in the CSV (bad rows: {bad[:10]})")
    return threads


def import_csv(path: str, name: str, brand: str = "") -> dict[str, Any]:
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = p.read_text(encoding="latin-1")
    except OSError as exc:
        raise ThreadError(f"Couldn't read {p.name}: {exc.strerror}") from exc
    threads = parse_csv(text)
    name = name.strip() or p.stem
    chart_id = _slug(name)
    if chart_id in BUILTIN_CHARTS or chart_id == MY_THREADS:
        chart_id += "-custom"
    chart = {"id": chart_id, "name": name, "brand": brand.strip() or name, "builtin": False, "threads": threads}
    d = _charts_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{chart_id}.json").write_text(json.dumps(chart, indent=1), encoding="utf-8")
    return _summary(chart)


def delete_chart(chart_id: str) -> None:
    if chart_id in BUILTIN_CHARTS:
        raise ThreadError("Built-in charts can't be deleted")
    f = _charts_dir() / f"{chart_id}.json"
    if f.is_file():
        f.unlink()


def match(colors: list[str], chart_id: str, count: int = 3) -> list[list[dict[str, Any]]]:
    """For each hex color, the `count` closest threads in the chart with their ΔE2000."""
    chart = get_chart(chart_id)
    if not chart["threads"]:
        raise ThreadError(f"{chart['name']} has no threads yet")
    labs = [(t, rgb_to_lab(hex_to_rgb(t["color"]))) for t in chart["threads"]]
    out = []
    for c in colors:
        lab = rgb_to_lab(hex_to_rgb(c))
        ranked = sorted(((ciede2000(lab, tl), t) for t, tl in labs), key=lambda x: x[0])[:count]
        # Threads in My Threads carry their own brand; chart threads use the chart's.
        out.append([{**t, "brand": t.get("brand") or chart["brand"], "delta_e": round(d, 2)} for d, t in ranked])
    return out


# ---------------------------------------------------------------- my threads

MY_THREADS = "my-threads"


def _my_path() -> Path:
    return _charts_dir() / f"{MY_THREADS}.json"


def my_threads() -> dict[str, Any]:
    """The user's own spools, from any brand or none. Created empty on first use."""
    f = _my_path()
    if f.is_file():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"id": MY_THREADS, "name": "My threads", "brand": "", "builtin": False, "mine": True, "threads": []}


def _key(t: dict[str, str]) -> tuple[str, str]:
    """Identity of a spool: brand + number, or the color for custom spools without a number."""
    return (t.get("brand", "").strip().lower(), t.get("code", "").strip().lower() or t["color"].lower())


def _save_my(chart: dict[str, Any]) -> dict[str, Any]:
    d = _charts_dir()
    d.mkdir(parents=True, exist_ok=True)
    _my_path().write_text(json.dumps(chart, indent=1), encoding="utf-8")
    return chart


def my_add(spools: list[dict[str, str]]) -> dict[str, Any]:
    """Add spools ({code?, name?, color, brand?}). Re-adding one already owned does nothing."""
    chart = my_threads()
    have = {_key(t) for t in chart["threads"]}
    for s in spools:
        t = {
            "code": str(s.get("code", "")).strip(),
            "name": str(s.get("name", "")).strip(),
            "color": rgb_to_hex(*hex_to_rgb(s["color"])),
            "brand": str(s.get("brand", "")).strip(),
        }
        if _key(t) not in have:
            chart["threads"].append(t)
            have.add(_key(t))
    return _save_my(chart)


def my_remove(spools: list[dict[str, str]]) -> dict[str, Any]:
    chart = my_threads()
    drop = {_key({"color": "", **s}) for s in spools}
    chart["threads"] = [t for t in chart["threads"] if _key(t) not in drop]
    return _save_my(chart)
