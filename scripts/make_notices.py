"""Write THIRD-PARTY-NOTICES.txt: the licences of everything LUDD's installer ships besides LUDD.

The installed app contains the Python engine's libraries (OpenCV, NumPy, Shapely/GEOS, ONNX
Runtime...), the frontend's npm packages and fonts (SIL Open Font License), and the Rust crates
in the app itself. Their licences ask for their notices to travel with the program.

Run with the engine's environment (build_engine.py calls it):
    uv run --project engine python scripts/make_notices.py [output file]
Offline: it reads what's already installed (engine/.venv, apps/desktop/node_modules, Cargo's
download folder) and never fetches anything.
"""

from __future__ import annotations

import hashlib
import importlib.metadata as md
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = ROOT / "apps" / "desktop"
OUT = DESKTOP / "src-tauri" / "binaries" / "THIRD-PARTY-NOTICES.txt"
LICENCE_FILE = re.compile(r"(^|[/\\])(LICEN[CS]E|COPYING|NOTICE|ThirdPartyNotices|OFL)[^/\\]*$", re.I)
# Everything in a wheel's licenses folder is a licence text, whatever it's called: pypdfium2 names
# PDFium's, and its libraries', after the licence ("LICENSES/Apache-2.0.txt").
LICENCES_FOLDER = re.compile(r"\.dist-info[/\\]licenses[/\\]", re.I)


class Notices:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.seen: set[str] = set()

    def add(self, title: str, licence: str, texts: list[tuple[str, str]]) -> None:
        self.parts.append(f"\n{'=' * 78}\n{title}\nLicence: {licence or 'see below'}\n{'=' * 78}\n")
        for name, text in texts:
            digest = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()
            if digest in self.seen:
                self.parts.append(f"\n[{name}: same text as given above]\n")
                continue
            self.seen.add(digest)
            self.parts.append(f"\n--- {name} ---\n{text.strip()}\n")

    def text(self) -> str:
        head = (
            "LUDD third-party notices\n\n"
            "LUDD is free software under the GNU General Public License, version 3 or later (see\n"
            "LICENSE). It includes the following software and fonts by others, under their own\n"
            "licences, which are reproduced here.\n"
        )
        return head + "".join(self.parts)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# --- Python (the engine) ------------------------------------------------------------------------


def python_dists() -> list[md.Distribution]:
    """The engine's runtime libraries (not test or build tools), plus PyInstaller's start-up code."""
    try:
        from packaging.requirements import Requirement
    except ImportError:  # pragma: no cover - packaging comes with PyInstaller
        Requirement = None  # type: ignore[assignment]
    found: dict[str, md.Distribution] = {}
    todo = ["threadline-engine", "pyinstaller"]
    while todo:
        name = todo.pop()
        key = re.sub(r"[-_.]+", "-", name).lower()
        if key in found:
            continue
        try:
            dist = md.distribution(name)
        except md.PackageNotFoundError:
            continue
        found[key] = dist
        if key == "pyinstaller":
            continue  # only its bootloader ships; its own dependencies are build tools
        for req in dist.requires or []:
            if Requirement is not None:
                r = Requirement(req)
                if r.marker and not r.marker.evaluate({"extra": ""}):
                    continue
                todo.append(r.name)
            else:
                todo.append(re.split(r"[ ;<>=!~\[(]", req, maxsplit=1)[0])
    found.pop("threadline-engine", None)
    return sorted(found.values(), key=lambda d: d.metadata["Name"].lower())


def licence_files(dist: md.Distribution) -> list[tuple[str, Path]]:
    """The licence texts a library's wheel carries, as (name, file)."""
    found = []
    for f in dist.files or []:
        if LICENCE_FILE.search(str(f)) or LICENCES_FOLDER.search(str(f)):
            p = Path(dist.locate_file(f))
            if p.is_file():
                found.append((str(f).replace("\\", "/"), p))
    return found


def add_python(n: Notices) -> None:
    import platform

    base = Path(sys.base_prefix)
    py = [(p.name, read(p)) for p in (base / "LICENSE.txt", base / "LICENSE") if p.is_file()]
    n.add(f"Python {platform.python_version()}", "PSF-2.0", py)
    for dist in python_dists():
        meta = dist.metadata
        licence = meta.get("License-Expression") or (meta.get("License") or "").splitlines()[0:1]
        licence = licence if isinstance(licence, str) else (licence[0] if licence else "")
        n.add(f"{meta['Name']} {dist.version} (Python)", licence, [(name, read(p)) for name, p in licence_files(dist)])


# --- npm (the window's code and fonts) ----------------------------------------------------------


def find_package(name: str, start: Path) -> Path | None:
    """Node's lookup: node_modules/<name> in `start` or any folder above it."""
    for folder in [start, *start.parents]:
        p = folder / "node_modules" / name
        if (p / "package.json").is_file():
            return p
    return None


def npm_packages() -> list[tuple[str, Path]]:
    pkg = json.loads(read(DESKTOP / "package.json"))
    found: dict[str, Path] = {}
    todo = [(name, DESKTOP) for name in pkg.get("dependencies", {})]  # devDependencies don't ship
    while todo:
        name, start = todo.pop()
        where = find_package(name, start)
        if where is None:
            continue
        real = Path(os.path.realpath(where))
        meta = json.loads(read(real / "package.json"))
        key = f"{meta.get('name', name)}@{meta.get('version', '?')}"
        if key in found:
            continue
        found[key] = real
        # pnpm keeps a package's own dependencies next to it, so look from where it really is.
        todo += [(d, real) for d in meta.get("dependencies", {})]
    return sorted(found.items())


def add_npm(n: Notices) -> None:
    if not (DESKTOP / "node_modules").is_dir():
        print("make_notices: warning: apps/desktop/node_modules is missing (run pnpm install first)")
        return
    for key, path in npm_packages():
        meta = json.loads(read(path / "package.json"))
        licence = meta.get("license") or ""
        texts = [(p.name, read(p)) for p in sorted(path.iterdir()) if p.is_file() and LICENCE_FILE.search(p.name)]
        n.add(f"{key} (JavaScript)", licence if isinstance(licence, str) else json.dumps(licence), texts)


# --- Rust (the app itself) ----------------------------------------------------------------------


def add_rust(n: Notices) -> None:
    lock = DESKTOP / "src-tauri" / "Cargo.lock"
    if os.environ.get("CI"):
        # A fresh build machine hasn't downloaded the crates' sources yet (the build does it later).
        import subprocess

        subprocess.run(["cargo", "fetch", "--locked", "--manifest-path", str(lock.parent / "Cargo.toml")], check=False)
    cargo_home = Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo"))
    registries = list((cargo_home / "registry" / "src").glob("*"))
    crates = re.findall(r'\[\[package\]\]\nname = "([^"]+)"\nversion = "([^"]+)"\nsource = "registry', read(lock).replace("\r\n", "\n"))
    missing = []
    for name, version in crates:
        src = next((r / f"{name}-{version}" for r in registries if (r / f"{name}-{version}").is_dir()), None)
        if src is None:
            missing.append(f"{name} {version}")
            continue
        toml = read(src / "Cargo.toml") if (src / "Cargo.toml").is_file() else ""
        m = re.search(r'^license\s*=\s*"([^"]+)"', toml, re.M)
        texts = [(p.name, read(p)) for p in sorted(src.iterdir()) if p.is_file() and LICENCE_FILE.search(p.name)]
        n.add(f"{name} {version} (Rust)", m.group(1) if m else "", texts)
    if missing:
        n.add("Other Rust crates (sources not downloaded when this file was made)", "see crates.io",
              [("list", "\n".join(missing))])


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    n = Notices()
    add_python(n)
    add_npm(n)
    add_rust(n)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(n.text(), encoding="utf-8", newline="\n")
    print(f"notices -> {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
