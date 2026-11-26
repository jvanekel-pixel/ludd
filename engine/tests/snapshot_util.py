"""Snapshot checks shared by the stitch tests.

check(suite, name, got) compares `got` with the entry `name` in snapshots/<suite>.json and records
it when there is none, except with CI set: then a missing entry fails, because one that isn't
committed protects nothing. After checking that new output is right, re-record with
UPDATE_SNAPSHOTS=1 (or all) for every suite, or a comma list of suite names.
"""

import hashlib
import json
import os
from pathlib import Path

import pyembroidery as pe
import pytest

from threadline_engine.digitize.stitches import JUMP, STITCH, TRIM

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"


def _recording(suite: str) -> bool:
    wanted = {s.strip() for s in os.environ.get("UPDATE_SNAPSHOTS", "").split(",")}
    return not wanted.isdisjoint(("1", "all", suite))


def check(suite: str, name: str, got: dict) -> None:
    """Compare `got` with snapshots/<suite>.json, or record it (see the top of this file)."""
    path = SNAPSHOT_DIR / f"{suite}.json"
    stored = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not _recording(suite):
        if name in stored:
            assert got == stored[name], (f"{name} stitches changed; review, then re-record with UPDATE_SNAPSHOTS=1\n"
                                         f"recorded: {stored[name]}\nnow:      {got}")
            return
        if os.environ.get("CI"):
            pytest.fail(f"no snapshot recorded for {name}: run the tests locally, review and commit snapshots/{suite}.json")
    stored[name] = got
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(stored, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def digest_recs(recs) -> dict:
    """generate()'s records as test_digitize records them: counts and a hash, to 0.001 mm."""
    rounded = [[round(x, 3), round(y, 3), k] for x, y, k in recs]
    return {
        "records": len(rounded),
        "stitches": sum(1 for r in rounded if r[2] == STITCH),
        "jumps": sum(1 for r in rounded if r[2] == JUMP),
        "trims": sum(1 for r in rounded if r[2] == TRIM),
        "sha1": hashlib.sha1(json.dumps(rounded).encode()).hexdigest(),
    }


def digest_pattern(pattern) -> dict:
    """A rendered pyembroidery pattern as test_layout_snapshots records it: the same counts and
    hash (to 0.01 of the pattern's units), plus the thread colors."""
    rounded = [[round(x, 2), round(y, 2), c & pe.COMMAND_MASK] for x, y, c in pattern.stitches]
    return {
        "records": len(rounded),
        "stitches": sum(1 for *_, c in rounded if c == pe.STITCH),
        "jumps": sum(1 for *_, c in rounded if c == pe.JUMP),
        "trims": sum(1 for *_, c in rounded if c == pe.TRIM),
        "threads": [t.hex_color() for t in pattern.threadlist],
        "sha1": hashlib.sha1(json.dumps(rounded).encode()).hexdigest(),
    }


class _Steadied:
    """A pattern's stitches with each coordinate rounded to a millionth of a unit."""

    def __init__(self, pattern):
        self.stitches = [(round(x, 6), round(y, 6), c) for x, y, c in pattern.stitches]
        self.threadlist = pattern.threadlist


def digest_pattern_steady(pattern) -> dict:
    """digest_pattern for suites where a stitch can land exactly on a rounding step, such as the
    middle of a row between two points that are whole thousandths of a mm. There the last digit of
    a sine, which is not the same on every computer, would decide which way the 0.001 mm rounds
    (the "bulge" case did that on both Macs). So each coordinate is first rounded to a millionth of
    a unit: every computer then rounds the same number. A stitch that really moves (by more than a
    rounding step) still changes the hash."""
    return digest_pattern(_Steadied(pattern))
