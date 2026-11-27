"""The last-digit test, for snapshot suites that use the steady digests (snapshot_util).

Another computer's maths library can give a sine or cosine that is one last digit off, and a
stitch that lies on a rounding step, or a choice between two equally good things, must not turn
on it (Phase 5's "bulge" snapshot did, on both Macs). So a suite nudges every sine and cosine,
makes its stitches again and expects the recorded ones:

    forget_stitches()
    try:
        nudge_trig(monkeypatch, seed, dz, blend)
        ...render each case and compare its steady digest with the recorded one...
    finally:
        monkeypatch.undo()
        forget_stitches()  # nothing worked out with the nudged maths may reach another test
"""

import math
import random

from shapely import affinity

from threadline_engine import jumps, lettering
from threadline_engine.layout import objects as layout_objects
from threadline_engine.layout import text as text_pipeline


def _nudged(real, rng):
    def f(*x):
        v = real(*x)
        return math.nextafter(v, rng.choice((-math.inf, v, math.inf))) if v else v

    return f


class LastDigitNoise:
    """The math module with every sine and cosine (or the functions named) off by one last digit,
    up or down or not at all, at random: what another computer's maths library can give."""

    def __init__(self, seed, names=("sin", "cos")):
        self._rng = random.Random(seed)
        self._names = names

    def __getattr__(self, name):
        real = getattr(math, name)
        if name not in self._names:
            return real
        return _nudged(real, self._rng)


def nudge_trig(monkeypatch, seed, *modules, rotations=False, names=("sin", "cos")):
    """Give each of `modules` (ones that use `math`) the noisy maths (`names`), until
    monkeypatch.undo(). `rotations`: also nudge shapely's rotate(), which calls cos and sin imported
    by name."""
    for i, module in enumerate(modules):
        monkeypatch.setattr(module, "math", LastDigitNoise(seed + 100 * i, names))
    if rotations:
        rng = random.Random(seed + 997)
        monkeypatch.setattr(affinity, "cos", _nudged(math.cos, rng))
        monkeypatch.setattr(affinity, "sin", _nudged(math.sin, rng))


def forget_stitches():
    """Empty what a render keeps, so the next one works every stitch out again."""
    text_pipeline._text_cache.clear()
    layout_objects._object_cache.clear()
    lettering.extras._cache.clear()
    jumps.forget()
