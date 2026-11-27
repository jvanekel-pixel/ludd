"""Helpers for the artwork import tests: ask the engine's art.preview the way the app does, and
read the shapes it gives back."""

from __future__ import annotations

import json
from pathlib import Path

import shapely
from shapely.geometry import LineString, Polygon

from threadline_engine.digitize.paths import flatten
from threadline_engine.digitize.stitches import fill_parts
from threadline_engine.methods import dispatcher

TRANSFORM = {"x": 0, "y": 0, "rotate": 0, "scale_x": 1, "scale_y": 1, "flip_x": False, "flip_y": False}


def ask(path, **options) -> dict:
    """The engine's raw answer to art.preview, through the RPC dispatcher."""
    line = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "art.preview",
                       "params": {"path": str(path), "options": options}})
    return json.loads(dispatcher.respond(line))


def preview(path, **options) -> dict:
    answer = ask(path, **options)
    assert "result" in answer, answer.get("error")
    return answer["result"]


def refusal(path, **options) -> str:
    """The plain-words refusal art.preview answers with (and never an engine bug)."""
    answer = ask(path, **options)
    assert "error" in answer, f"expected a refusal, got {str(answer)[:300]}"
    assert answer["error"]["code"] == -32000, answer["error"]
    return answer["error"]["message"]


def svg(body: str, size: str = 'width="100mm" height="50mm" viewBox="0 0 100 50"', extra: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" {size} {extra}>'
            f"{body}</svg>")


def write(tmp_path: Path, text: str | bytes, name: str = "art.svg") -> Path:
    path = tmp_path / name
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")
    return path


def kinds(result: dict) -> list[str]:
    return [s["kind"] for s in result["shapes"]]


def outline_points(nodes, closed: bool = True) -> list[tuple[float, float]]:
    """The curve through pen points, as the engine draws it."""
    return flatten(nodes, closed)[0]


def area_of(shape: dict) -> Polygon:
    """What a fill covers, the way the engine fills it."""
    g = shape["geometry"]
    parts = fill_parts(g["outline"], g.get("holes") or [])
    return parts[0] if len(parts) == 1 else shapely.union_all(parts)


def line_of(shape: dict) -> LineString:
    g = shape["geometry"]
    closed = bool(g.get("closed"))
    pts = outline_points(g["nodes"], closed)
    return LineString([*pts, pts[0]] if closed else pts)


def bounds(shape: dict) -> tuple[float, float, float, float]:
    return area_of(shape).bounds if shape["kind"] == "fill" else line_of(shape).bounds


def close(a, b, tol: float = 0.05) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def layout_of(result: dict, params: dict | None = None) -> dict:
    """The layout the app makes from a preview's shapes (with the engine's own default settings)."""
    items = []
    for i, shape in enumerate(result["shapes"]):
        items.append({"id": f"a{i}", "kind": shape["kind"], "geometry": shape["geometry"],
                      "params": dict((params or {}).get(shape["kind"], {})),
                      "thread": {"color": shape["color"], "name": "", "catalog": "", "brand": ""},
                      "transform": dict(TRANSFORM), "threads": [], "ops": []})
    return {"items": items, "merge_colors": False, "color_sort": False, "basting": {"enabled": False, "margin_mm": 5}}
