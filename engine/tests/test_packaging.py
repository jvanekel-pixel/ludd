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


def test_qa2_d11_every_version_number_agrees():
    """QA2 D11: release.yml compares only the tag with tauri.conf.json; a missed file (the
    engine's __version__ shows in the status bar and Settings) would ship silently."""
    import json
    import re
    import tomllib

    import threadline_engine

    root = Path(__file__).resolve().parents[2]
    desktop = root / "apps" / "desktop"
    found = {
        "apps/desktop/package.json": json.loads((desktop / "package.json").read_text("utf-8"))["version"],
        "tauri.conf.json": json.loads((desktop / "src-tauri" / "tauri.conf.json").read_text("utf-8"))["version"],
        "Cargo.toml": tomllib.loads((desktop / "src-tauri" / "Cargo.toml").read_text("utf-8"))["package"]["version"],
        "engine/pyproject.toml": tomllib.loads((root / "engine" / "pyproject.toml").read_text("utf-8"))["project"]["version"],
        "threadline_engine.__version__": threadline_engine.__version__,
    }
    lock = (desktop / "src-tauri" / "Cargo.lock").read_text("utf-8").replace("\r\n", "\n")
    found["Cargo.lock"] = re.search(r'name = "threadline"\nversion = "([^"]+)"', lock).group(1)
    assert len(set(found.values())) == 1, found
