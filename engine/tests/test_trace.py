"""Trace Assist on synthetic pictures: does Tab keep you on the line, fast enough?

Plan targets: at least 70% of outline points accepted with Tab, under 30 ms per suggestion.
Each test simulates a user: press Tab while a ghost point is offered, otherwise click the
right point by hand, and measure how many points Tab placed.
"""

import math
import time

import numpy as np
import pytest
from PIL import Image, ImageDraw

from threadline_engine import trace

PX_PER_MM = 8.0
SIZE = 800
PLACE = {"x": 0, "y": 0, "width_mm": SIZE / PX_PER_MM, "height_mm": SIZE / PX_PER_MM, "rotate": 0}


def px_to_mm(u, v):
    return [(u + 0.5) / PX_PER_MM - SIZE / PX_PER_MM / 2, (v + 0.5) / PX_PER_MM - SIZE / PX_PER_MM / 2]


def mm_to_px(p):
    return (p[0] + SIZE / PX_PER_MM / 2) * PX_PER_MM - 0.5, (p[1] + SIZE / PX_PER_MM / 2) * PX_PER_MM - 0.5


def save(tmp_path, draw_fn, name):
    img = Image.new("RGB", (SIZE, SIZE), "white")
    draw_fn(ImageDraw.Draw(img))
    path = tmp_path / name
    img.save(path)
    return str(path)


def walk(path, start, second, on_line, true_next, steps, **kw):
    """Simulate tracing: accept ghosts with Tab when offered and on the line; else click by hand."""
    pts = [start, second]
    accepted = manual = 0
    times = []
    for _ in range(steps):
        t = time.perf_counter()
        r = trace.suggest(path, PLACE, pts, **kw)
        times.append((time.perf_counter() - t) * 1000)
        if r["ghost"] is not None and on_line(r["ghost"]):
            pts.append(r["ghost"])
            accepted += 1
        else:
            pts.append(true_next(pts[-1]))
            manual += 1
    return pts, accepted, manual, times


def test_follows_a_line_art_circle(tmp_path):
    c, r = SIZE / 2, 300
    path = save(tmp_path, lambda d: d.ellipse([c - r, c - r, c + r, c + r], outline="black", width=6), "circle.png")
    assert trace.info(path)["mode"] == "center"

    def on_line(p):
        u, v = mm_to_px(p)
        return abs(math.hypot(u - c, v - c) - r) < 0.5 * PX_PER_MM  # within 0.5 mm of the line

    def at(a):
        return px_to_mm(c + r * math.cos(a), c + r * math.sin(a))

    def true_next(p):
        u, v = mm_to_px(p)
        return at(math.atan2(v - c, u - c) + 3 * PX_PER_MM / r)

    pts, accepted, manual, times = walk(path, at(0), at(3 * PX_PER_MM / r), on_line, true_next, 70)
    assert accepted / (accepted + manual) >= 0.9
    assert all(on_line(p) for p in pts)
    assert sorted(times)[int(len(times) * 0.95)] < 30, f"p95 {sorted(times)[int(len(times) * 0.95)]:.1f} ms"


def test_follows_the_edge_of_a_filled_square_and_stops_at_corners(tmp_path):
    a, b = 200, 600
    path = save(tmp_path, lambda d: d.rectangle([a, a, b, b], fill="black"), "square.png")
    assert trace.info(path)["mode"] == "edge"
    corners = [(a, a), (b, a), (b, b), (a, b)]

    def dist_to_square(u, v):
        return min(
            min(abs(u - a), abs(u - b)) if a - 4 <= v <= b + 4 else 1e9,
            min(abs(v - a), abs(v - b)) if a - 4 <= u <= b + 4 else 1e9,
        )

    def on_line(p):
        return dist_to_square(*mm_to_px(p)) < 0.6 * PX_PER_MM

    def true_next(p):
        # Walk clockwise 3 mm, turning at corners (what a user would click).
        u, v = mm_to_px(p)
        step = 3 * PX_PER_MM
        if abs(v - a) < 6 and u < b - 6:
            return px_to_mm(min(u + step, b), a)
        if abs(u - b) < 6 and v < b - 6:
            return px_to_mm(b, min(v + step, b))
        if abs(v - b) < 6 and u > a + 6:
            return px_to_mm(max(u - step, a), b)
        return px_to_mm(a, max(v - step, a))

    pts, accepted, manual, _ = walk(path, px_to_mm(a + 10, a), px_to_mm(a + 34, a), on_line, true_next, 60, closed=True)
    assert accepted / (accepted + manual) >= 0.7
    assert all(on_line(p) for p in pts)
    del corners


def test_satin_mode_measures_the_stroke(tmp_path):
    def draw(d):
        pts = [(x, 400 + 120 * math.sin(x / 90)) for x in range(80, 720, 4)]
        d.line(pts, fill="black", width=24, joint="curve")

    path = save(tmp_path, draw, "wave.png")
    start = px_to_mm(80, 400 + 120 * math.sin(80 / 90))
    second = px_to_mm(100, 400 + 120 * math.sin(100 / 90))
    r = trace.suggest(path, PLACE, [start, second], satin=True)
    assert r["ghost"] is not None and "rails" in r
    (ax, ay), (bx, by) = r["rails"]
    width_mm = math.hypot(bx - ax, by - ay)
    assert 2.2 < width_mm < 3.8  # the stroke is 24 px = 3 mm wide


def test_junctions_offer_a_second_branch(tmp_path):
    def draw(d):
        d.line([(100, 400), (400, 400)], fill="black", width=6)
        d.line([(400, 400), (700, 400)], fill="black", width=6)
        d.line([(400, 400), (700, 200)], fill="black", width=6)

    path = save(tmp_path, draw, "fork.png")
    pts = [px_to_mm(364, 400), px_to_mm(398, 400)]  # arriving at the fork
    r = trace.suggest(path, PLACE, pts, step_mm=4)
    assert r["ghost"] is not None
    assert len(r["alternatives"]) == 1
    branches = [r["ghost"], r["alternatives"][0]]
    vs = sorted(mm_to_px(b)[1] for b in branches)
    assert vs[0] < 395 and abs(vs[1] - 400) < 4  # one goes up the branch, one straight on


def test_no_ghost_on_a_blank_picture(tmp_path):
    path = save(tmp_path, lambda d: None, "blank.png")
    r = trace.suggest(path, PLACE, [[0, 0], [3, 0]])
    assert r["ghost"] is None


def test_placement_round_trip_with_rotation():
    m = trace.Maps(np.zeros((100, 200), np.float32), np.zeros((100, 200), np.float32), 200, 100, "center", {"center": 1, "edge": 1})
    pl = trace.Placement(12, -5, 80, 40, 30)
    mm = np.array([[3.0, 4.0], [-20.0, 7.5]])
    back = pl.to_mm(m, pl.to_px(m, mm))
    assert np.allclose(back, mm)
    # The picture's centre pixel lands on the placement centre.
    assert np.allclose(pl.to_mm(m, np.array([99.5, 49.5])), [12, -5])


def test_missing_picture_is_a_clear_error(tmp_path):
    with pytest.raises(trace.TraceError, match="not found"):
        trace.suggest(str(tmp_path / "nope.png"), PLACE, [[0, 0]])
