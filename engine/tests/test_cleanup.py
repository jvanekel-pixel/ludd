"""Deleting the temp folders that killed engine runs leave behind."""

import sys

import pytest

from threadline_engine import cleanup


def bundle(tmp_path, name, marked=True):
    d = tmp_path / name
    (d / "numpy").mkdir(parents=True)
    (d / "numpy" / "x.pyd").write_bytes(b"x" * 100)
    if marked:
        (d / cleanup.MARKER).write_text("LUDD")
    return d


def test_only_our_left_behind_folders_are_found(tmp_path):
    own = bundle(tmp_path, "_MEI1")
    old = bundle(tmp_path, "_MEI2")
    bundle(tmp_path, "_MEI3", marked=False)  # another program's
    (tmp_path / "other").mkdir()
    assert cleanup.stale_bundles(own) == [old]


@pytest.mark.skipif(sys.platform != "win32", reason="the sweep runs on Windows only")
def test_sweep_deletes_unused_folders_and_keeps_one_in_use(tmp_path):
    own = bundle(tmp_path, "_MEI1")
    old = bundle(tmp_path, "_MEI2")
    busy = bundle(tmp_path, "_MEI3")
    other = bundle(tmp_path, "_MEI4", marked=False)
    with open(busy / "numpy" / "x.pyd", "rb"):  # a running engine has its files open
        assert cleanup.sweep(own) == 1
        assert not old.exists() and busy.exists() and other.exists() and own.exists()
    assert (busy / cleanup.MARKER).exists()  # nothing inside the busy one was touched


def test_sweep_does_nothing_outside_the_packaged_engine():
    assert cleanup.sweep() == 0  # running from source: no unpacked folder
