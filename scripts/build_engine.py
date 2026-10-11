"""Freeze the engine with PyInstaller into a Tauri sidecar binary.

Tauri expects sidecars named `<name>-<target-triple>[.exe]` under src-tauri/binaries.
Run from the repo root:  uv run --project engine python scripts/build_engine.py
"""

from __future__ import annotations

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


def main() -> None:
    work = ENGINE / "build"
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--onefile", "--noconfirm", "--clean",
            "--name", NAME,
            "--distpath", str(work / "dist"),
            "--workpath", str(work / "pyi"),
            "--specpath", str(work),
            "--paths", str(ENGINE),
            str(ENGINE / "entry.py"),
        ],
        check=True,
    )
    exe = ".exe" if sys.platform == "win32" else ""
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"{NAME}-{target_triple()}{exe}"
    shutil.copy2(work / "dist" / f"{NAME}{exe}", dest)
    print(f"sidecar -> {dest}")


if __name__ == "__main__":
    main()
