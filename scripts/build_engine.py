"""Freeze the engine with PyInstaller into a Tauri sidecar binary.

Tauri expects sidecars named `<name>-<target-triple>[.exe]` under src-tauri/binaries.
Run from the repo root:  uv run --project engine python scripts/build_engine.py
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"
OUT = ROOT / "apps" / "desktop" / "src-tauri" / "binaries"
NAME = "threadline-engine"


def target_triple() -> str:
    try:
        out = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True).stdout
        return next(l.split(": ", 1)[1] for l in out.splitlines() if l.startswith("host: "))
    except (OSError, subprocess.CalledProcessError, StopIteration):
        pass
    arch = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "aarch64", "aarch64": "aarch64"}[platform.machine().lower()]
    return {
        "win32": f"{arch}-pc-windows-msvc",
        "darwin": f"{arch}-apple-darwin",
        "linux": f"{arch}-unknown-linux-gnu",
    }[sys.platform]


# Libraries that come with a dependency but that LUDD never uses (OpenCV's video I/O is ~30 MB).
DROP_BINARIES = ("opencv_videoio_ffmpeg",)


def main() -> None:
    work = ENGINE / "build"
    work.mkdir(exist_ok=True)
    # Write the spec first, so unused libraries can be left out before bundling.
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller.utils.cliutils.makespec",
            "--onefile",
            "--name", NAME,
            "--specpath", str(work),
            "--paths", str(ENGINE),
            # Marks the unpacked folder as ours, so a later run can delete it if it's left behind.
            "--add-data", f"{ENGINE / 'ludd-engine-bundle.txt'}{os.pathsep}.",
            str(ENGINE / "entry.py"),
        ],
        check=True,
    )
    spec = work / f"{NAME}.spec"
    text = spec.read_text(encoding="utf-8")
    drop = f"\na.binaries = [b for b in a.binaries if not any(d in b[0] for d in {DROP_BINARIES!r})]\n"
    if "\npyz = PYZ(" not in text:
        raise SystemExit("build_engine: PyInstaller's spec changed, so unused libraries can't be left out")
    text = text.replace("\npyz = PYZ(", drop + "pyz = PYZ(", 1)
    spec.write_text(text, encoding="utf-8")
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--distpath", str(work / "dist"),
            "--workpath", str(work / "pyi"),
            str(spec),
        ],
        check=True,
    )
    exe = ".exe" if sys.platform == "win32" else ""
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"{NAME}-{target_triple()}{exe}"
    shutil.copy2(work / "dist" / f"{NAME}{exe}", dest)
    print(f"sidecar -> {dest}")
    check_dropped(work / "pyi" / NAME)
    # Run what users get, not just the source (see smoke_engine.py).
    subprocess.run([sys.executable, str(ROOT / "scripts" / "smoke_engine.py"), str(dest)], check=True)
    # The licences of what the installer ships besides LUDD (a bundle resource next to the engine).
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_notices.py"), str(OUT / "THIRD-PARTY-NOTICES.txt")], check=True)


def check_dropped(pyi: Path) -> None:
    """The libraries in DROP_BINARIES must really be out of the bundle."""
    tocs = list(pyi.glob("PKG-*.toc"))
    if not tocs:
        print(f"build_engine: warning: no PKG table of contents in {pyi}, so what was left out isn't checked")
        return
    for toc in tocs:
        text = toc.read_text(encoding="utf-8", errors="replace")
        for d in DROP_BINARIES:
            if d in text:
                raise SystemExit(f"build_engine: {d} is still in the bundle ({toc.name})")


if __name__ == "__main__":
    main()
