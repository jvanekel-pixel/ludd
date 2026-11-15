"""The packaging scripts: the frozen-engine smoke test and the third-party notices (QA packaging)."""

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import make_notices  # noqa: E402


def test_smoke_script_passes_on_the_engine():
    # The same check the build runs on the frozen engine, here on the source one.
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "smoke_engine.py"), sys.executable, "-m", "threadline_engine"],
        capture_output=True, text=True, timeout=300, cwd=Path(__file__).resolve().parents[1],
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "smoke: ok" in r.stdout


def test_notices_cover_the_engine_libraries_but_not_test_tools():
    names = {d.metadata["Name"].lower() for d in make_notices.python_dists()}
    assert {"numpy", "shapely", "opencv-python-headless", "pyembroidery", "pyinstaller"} <= names
    assert "pytest" not in names and "threadline-engine" not in names


def test_notices_text_keeps_each_licence_once():
    n = make_notices.Notices()
    n.add("a 1", "MIT", [("LICENSE", "Permission is hereby granted")])
    n.add("b 2", "MIT", [("LICENSE", "Permission is hereby granted")])
    text = n.text()
    assert text.count("Permission is hereby granted") == 1 and "a 1" in text and "b 2" in text
