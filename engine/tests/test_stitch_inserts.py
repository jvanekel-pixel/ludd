"""Stitch editing on a placed stitch file (Phase 4, Track B): insert a stitch, insert a jump, lock
both sides of a jump. Inserts name stitches by their number in the file, so they go in first and
later moves and deletes can name an inserted stitch by its own number."""

import math

import pyembroidery as pe
import pytest

from test_repair_cleanup import J, S, T, lay, records, render, runs_of, src_of, write
from threadline_engine import design, kept, layout, quality
from threadline_engine.digitize.stitches import TIE_MM
from threadline_engine.layout import files
from threadline_engine.layout.model import Block

# Two thread runs, 10 mm and 6 mm long, with a trim and a jump between them.
NEAR = [(0, 0), (20, 0), (40, 0), (60, 0), (80, 0), (100, 0)]
FAR = [(300, 0), (320, 0), (340, 0), (360, 0)]
NEW = 40  # a number no stitch in the file has


@pytest.fixture
def path(tmp_path):
    return write(tmp_path / "two.pes", NEAR, FAR)


def insert_after(path, point, index=NEW, **extra):
    return {"op": "insert_stitch", "after": src_of(path, point), "index": index, **extra}


def move(index, dx=0.0, dy=0.0):
    return {"op": "move_stitches", "indices": [index], "dx_mm": dx, "dy_mm": dy, "local": True}


def delete(*indices):
    return {"op": "delete_stitches", "indices": list(indices)}


def at(recs, src):
    """The position in `recs` of the stitch numbered `src`."""
    return next(i for i, (x, y, k, s) in enumerate(recs) if s == src and k == S)


def test_insert_stitch_lands_midway_and_can_be_moved(path):
    op = insert_after(path, (20, 0))
    plain = records(render(path))
    got = records(render(path, [op]))
    i = at(got, NEW)
    assert got[i] == (30, 0, S, NEW)
    assert got[i - 1][3] == op["after"] and got[i + 1][:3] == (40, 0, S)
    assert got[:i] + got[i + 1:] == plain  # nothing else changed
    moved = records(render(path, [op, move(NEW, dy=1.5)]))
    assert moved[at(moved, NEW)] == (30, 15, S, NEW)
    assert [r for r in moved if r[3] != NEW] == plain


def test_insert_stitch_goes_where_it_is_told_in_the_files_frame(path):
    op = insert_after(path, (20, 0), x_mm=3.5, y_mm=0.5)
    got = records(render(path, [op]))
    assert got[at(got, NEW)][:2] == (35, 5)
    # The place is in the file's own frame: it turns and resizes with the design.
    turned = records(render(path, [insert_after(path, (20, 0), x_mm=3.0, y_mm=0.0)],
                            transform={"rotate": 90, "scale_x": 2, "scale_y": 2}))
    i = at(turned, NEW)
    mid = [(turned[i - 1][k] + turned[i + 1][k]) / 2 for k in (0, 1)]
    assert turned[i][:2] == pytest.approx(mid)


def test_inserted_stitch_can_be_deleted(path):
    op = insert_after(path, (20, 0))
    assert records(render(path, [op, delete(NEW)])) == records(render(path))
    # A stop after the inserted stitch goes after it, as after any stitch.
    got = records(render(path, [op, {"op": "insert", "after": NEW, "command": "stop"}]))
    i = at(got, NEW)
    assert got[i + 1][:3] == (30, 0, pe.STOP) and got[i + 2][:2] == (40, 0)


def test_inserts_go_in_first_and_in_list_order(path):
    first, second = insert_after(path, (20, 0)), {"op": "insert_stitch", "after": NEW, "index": NEW + 1}
    got = records(render(path, [first, second]))
    assert [r[:2] for r in got[at(got, NEW) - 1:at(got, NEW) + 3]] == [(20, 0), (30, 0), (35, 0), (40, 0)]
    # An edit made earlier in the list still names the inserted stitch: inserts go in first.
    got = records(render(path, [delete(NEW + 1), first, second]))
    numbers = [r[3] for r in got]
    assert NEW in numbers and NEW + 1 not in numbers


def test_insert_jump_makes_the_move_a_jump(path):
    after = src_of(path, (40, 0))
    r = render(path, [{"op": "insert_jump", "after": after}])
    got = records(r)
    i = at(got, after)
    assert got[i + 1] == (60, 0, J, -1) and got[i + 2][:3] == (60, 0, S)
    assert runs_of(got) == [NEAR[:3], NEAR[3:], FAR]
    segs, _ = quality._segments(r.pattern)
    assert [4.0, 0.0, 6.0, 0.0] not in segs.tolist()  # no thread sewn across


def test_an_inserted_jump_goes_to_the_next_stitch_that_is_sewn(path):
    after = src_of(path, (40, 0))
    jump = {"op": "insert_jump", "after": after}
    next_ = src_of(path, (60, 0))
    got = records(render(path, [jump, move(next_, dy=1.0)]))
    i = at(got, after)
    assert got[i + 1][:3] == (60, 10, J) and got[i + 2][:2] == (60, 10)
    got = records(render(path, [jump, delete(next_)]))
    i = at(got, after)
    assert got[i + 1][:3] == (80, 0, J) and got[i + 2][:2] == (80, 0)


def test_a_move_that_is_a_jump_already_is_left_alone(path):
    assert records(render(path, [{"op": "insert_jump", "after": src_of(path, (100, 0))}])) == records(render(path))


def lock_sides(got, before_stitch, after_stitch):
    """The three records after each of the two stitches."""
    i, c = at(got, before_stitch), at(got, after_stitch)
    return (got[i], got[i + 1:i + 4]), (got[c], got[c + 1:c + 4])


def test_lock_jump_adds_three_short_stitches_each_side(path):
    before_stitch, after_stitch = src_of(path, (100, 0)), src_of(path, (300, 0))
    plain = records(render(path))
    got = records(render(path, [{"op": "lock_jump", "after": before_stitch}]))
    assert len(got) == len(plain) + 6
    for anchor, added in lock_sides(got, before_stitch, after_stitch):
        assert [r[2:] for r in added] == [(S, -1)] * 3
        walk = [anchor[:2]] + [r[:2] for r in added]
        for a, b in zip(walk, walk[1:]):
            assert 0 < math.dist(a, b) / 10 <= TIE_MM + 0.05
        # Each lock ends where it began, so the trim, the jump and the next stitch are as they were.
        assert added[-1][:2] == anchor[:2]
        assert all(r[1] == 0 for r in added)  # along the thread already there
    i = at(got, before_stitch)
    assert [r[2] for r in got[i + 4:i + 6]] == [T, J]
    assert all(80 <= r[0] <= 100 for r in got[i + 1:i + 4])
    c = at(got, after_stitch)
    assert all(300 <= r[0] <= 320 for r in got[c + 1:c + 4])


def test_the_lock_stays_with_its_stitches(path):
    before_stitch, after_stitch = src_of(path, (100, 0)), src_of(path, (300, 0))
    lock = {"op": "lock_jump", "after": before_stitch}
    got = records(render(path, [lock, move(before_stitch, dy=2.0)]))
    for r in lock_sides(got, before_stitch, after_stitch)[0][1]:
        assert math.dist(r[:2], (100, 20)) / 10 <= TIE_MM + 0.05
    # The stitch before the jump deleted: the lock goes on the one that's left, whichever came first.
    previous = src_of(path, (80, 0))
    for ops in ([lock, delete(before_stitch)], [delete(before_stitch), {"op": "lock_jump", "after": previous}]):
        got = records(render(path, ops))
        i = at(got, previous)
        assert [r[2:] for r in got[i + 1:i + 4]] == [(S, -1)] * 3 and got[i + 3][:2] == (80, 0), ops
        assert not [r for r in got if r[3] == before_stitch and r[2] == S]


def test_both_jumps_round_a_single_stitch_can_be_locked(tmp_path):
    path = write(tmp_path / "dot.pes", NEAR, [(200, 0)], FAR)
    one, two = src_of(path, (100, 0)), src_of(path, (200, 0))
    for ops in ([{"op": "lock_jump", "after": one}, {"op": "lock_jump", "after": two}],
                [{"op": "lock_jump", "after": two}, {"op": "lock_jump", "after": one}]):
        got = records(render(path, ops))
        assert len(got) == len(records(render(path))) + 12, ops
        i = at(got, two)
        assert [r[2:] for r in got[i + 1:i + 7]] == [(S, -1)] * 6 and got[i + 7][2] == T, ops


def test_edits_after_a_locked_stitch_leave_its_lock_whole(path):
    # The first stitch after the jump carries three lock stitches.
    first = src_of(path, (300, 0))
    lock = {"op": "lock_jump", "after": src_of(path, (100, 0))}
    locked = records(render(path, [lock]))
    for op in ({"op": "insert_stitch", "after": first, "index": NEW}, {"op": "insert_jump", "after": first}):
        got = records(render(path, [lock, op]))
        i = at(got, first)
        assert got[i:i + 4] == locked[at(locked, first):at(locked, first) + 4], op
        assert got[i + 4][:2] == ((310, 0) if op["op"] == "insert_stitch" else (320, 0)), op
    # And a lock's stitches lead toward a stitch far enough to give them their full length.
    tied = write_tied(path)
    got = records(render(tied, [{"op": "lock_jump", "after": src_of(tied, (100, 0))}]))
    i = at(got, src_of(tied, (100, 0)))
    assert min(r[0] for r in got[i + 1:i + 4]) == pytest.approx(100 - TIE_MM * 10)


def write_tied(path):
    """NEAR ending in a 0.1 mm tie stitch, as bought designs do."""
    return write(path.replace(".pes", "-tied.pes"), NEAR[:-1] + [(99, 0), (100, 0)], FAR)


def test_the_lock_survives_the_clean_up_repairs(path):
    lock = {"op": "lock_jump", "after": src_of(path, (100, 0))}
    repairs = [{"op": "filter_small", "min_mm": 0.4}, {"op": "declump", "max_hits": 3}]
    assert records(render(path, [lock, *repairs])) == records(render(path, [lock]))


def test_a_jump_with_nothing_after_it_in_its_color_is_locked_before_it():
    first = [[0, 0, S, 0, 0], [20, 0, S, 0, 1], [40, 0, S, 0, 2], [200, 0, J, 0, 3]]
    second = [[200, 0, S, 0, 5], [220, 0, S, 0, 6]]
    blocks = [Block({}, [list(r) for r in first]), Block({}, [list(r) for r in second])]
    notes: list[str] = []
    out = files._apply_ops(blocks, [{"op": "lock_jump", "after": 2}], notes=notes)
    assert [r[2:] for r in out[0].recs[3:6]] == [[S, 0, -1]] * 3 and out[0].recs[6] == first[3]
    assert out[1].recs == second and not notes


def stale_notes(path, ops):
    blocks = files._split_blocks(design.load(path), 0)
    original = [list(r) for b in blocks for r in b.recs]
    notes: list[str] = []
    out = files._apply_ops(blocks, ops, notes=notes)
    assert [r for b in out for r in b.recs] == original
    return notes


def test_stale_insert_is_skipped_with_a_note(path):
    gone = [{"op": "insert_stitch", "after": 999, "index": 1000}, {"op": "insert_jump", "after": 999},
            {"op": "lock_jump", "after": 999}]
    notes = stale_notes(path, gone)
    assert len(notes) == 1 and notes[0].startswith("3 ") and "left out" in notes[0] and "Add them again" in notes[0]
    # One at a time reads right; a lock with no jump after its stitch, and a stitch added after the
    # last of its color with no place of its own, have nowhere to go either.
    for op in (gone[0], {"op": "lock_jump", "after": src_of(path, (20, 0))},
               {"op": "insert_stitch", "after": src_of(path, (360, 0)), "index": NEW},
               {"op": "insert_jump", "after": src_of(path, (360, 0))}):
        notes = stale_notes(path, [op])
        assert len(notes) == 1 and notes[0].startswith("1 ") and "was left out" in notes[0], op
    # A number another stitch already has would make later edits land on both: left out too.
    assert stale_notes(path, [insert_after(path, (20, 0), index=src_of(path, (60, 0)))])
    # In the whole design, the edit is simply left out.
    assert records(render(path, gone)) == records(render(path))


def test_damaged_insert_ops_are_ignored(path):
    after = src_of(path, (20, 0))
    junk = [{"op": "insert_stitch", "after": "x", "index": NEW}, {"op": "insert_stitch", "after": after, "index": -1},
            {"op": "insert_stitch", "after": after}, {"op": "insert_jump"}, {"op": "lock_jump", "after": 1.5}]
    assert stale_notes(path, junk) == []
    got = records(render(path, [insert_after(path, (20, 0), x_mm="far", y_mm=0)]))
    assert got[at(got, NEW)][:2] == (30, 0)  # no usable place: halfway to the next


def test_drawn_shapes_have_no_stitch_inserts():
    run = {"id": "r", "kind": "run", "geometry": {"nodes": [[0, 0, "c"], [20, 0, "c"]]}, "params": {},
           "thread": {"color": "#000000"}}
    edited = {**run, "ops": [{"op": "insert_stitch", "after": 1, "index": 999}, {"op": "insert_jump", "after": 1}]}
    assert layout.render({"items": [edited]}).pattern.stitches == layout.render({"items": [run]}).pattern.stitches


def test_inserts_pin_the_file_repairs_do_not(tmp_path):
    for name in ("insert_stitch", "insert_jump", "lock_jump"):
        assert kept.has_edits({"ops": [{"op": name, "after": 1}]}), name
    for name in kept.REPAIR_OPS:
        assert not kept.has_edits({"ops": [{"op": name}]}), name
    path = write(tmp_path / "f.pes", NEAR)
    render(path)  # added to the design: a private copy is kept
    added = insert_after(path, (20, 0))
    write(tmp_path / "f.pes", [(0, 50), (50, 50), (100, 50), (150, 50)])  # re-saved elsewhere later
    assert runs_of(records(render(path, [added]))) == [NEAR[:2] + [(30, 0)] + NEAR[2:]]
    repaired = layout.render(lay(path, [{"op": "filter_small", "min_mm": 0.4}]))  # follows the file
    assert runs_of(records(repaired))[0][0] == (0, 50)
