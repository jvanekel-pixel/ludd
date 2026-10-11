"""Make the Windows installer's pictures from the LUDD mark (apps/desktop/src-tauri/installer/).

Run from the repo root (Windows, with Microsoft Edge installed):
    uv run --no-project --with pillow python scripts/make_installer_art.py

- sidebar.bmp (164 x 314): the welcome and finish pages: the mark and wordmark on ink.
- header.bmp (150 x 57): the top right of the other pages: the mark and wordmark on white.
NSIS wants 24-bit BMPs at exactly these sizes. Pages are drawn as HTML and photographed by
Edge in headless mode at 2x, then scaled down for crisp edges.
"""

from __future__ import annotations

import base64
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from make_manual_pdf import BONE, EDGE, INK, LIME, font, mark  # noqa: E402

OUT = ROOT / "apps" / "desktop" / "src-tauri" / "installer"
SCALE = 2


def page(body: str, w: int, h: int, bg: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: "Archivo"; src: url({font("archivo-latin-wdth-normal.woff2")}) format("woff2"); font-weight: 100 900; font-stretch: 62% 125%; }}
@font-face {{ font-family: "Space Mono"; src: url({font("space-mono-latin-400-normal.woff2")}) format("woff2"); }}
html, body {{ margin: 0; width: {w * SCALE}px; height: {h * SCALE}px; overflow: hidden; background: {bg}; }}
body {{ zoom: {SCALE}; }}
.word {{ font-family: "Archivo"; font-weight: 900; font-stretch: 62%; letter-spacing: 0.02em; line-height: 1; }}
.mono {{ font-family: "Space Mono"; text-transform: uppercase; }}
</style></head><body>{body}</body></html>"""


SIDEBAR = f"""<div style="width:164px;height:314px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:{BONE}">
  {mark(BONE, INK, LIME, 104)}
  <div class="word" style="font-size:54px;margin-top:10px">LUDD</div>
  <div style="width:34px;height:3px;background:{LIME};border-radius:2px;margin:14px 0 12px"></div>
  <div class="mono" style="font-size:7.5px;letter-spacing:0.18em;text-align:center;line-height:1.7;color:#B5AEA3">Free + open-source<br>embroidery</div>
</div>"""

HEADER = f"""<div style="width:150px;height:57px;display:flex;align-items:center;justify-content:flex-end;gap:7px;padding-right:8px;box-sizing:border-box;color:{INK}">
  {mark(INK, "#FFFFFF", INK, 42)}
  <div class="word" style="font-size:30px">LUDD</div>
</div>"""


def shoot(html: str, w: int, h: int, out: Path, work: Path) -> None:
    edge = next(p for p in EDGE if p.is_file())
    src = work / f"{out.stem}.html"
    src.write_text(html, encoding="utf-8")
    png = work / f"{out.stem}.png"
    subprocess.run([str(edge), "--headless=new", "--hide-scrollbars", "--force-device-scale-factor=1",
                    f"--window-size={w * SCALE},{h * SCALE}", f"--screenshot={png}", src.as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    im = Image.open(png).convert("RGB").crop((0, 0, w * SCALE, h * SCALE)).resize((w, h), Image.Resampling.LANCZOS)
    im.save(out, format="BMP")
    im.save(work / f"{out.stem}-check.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ludd-art-") as tmp:
        work = Path(tmp)
        shoot(page(SIDEBAR, 164, 314, INK), 164, 314, OUT / "sidebar.bmp", work)
        shoot(page(HEADER, 150, 57, "#FFFFFF"), 150, 57, OUT / "header.bmp", work)
        if len(sys.argv) > 1:  # optional: a folder to copy PNG previews into
            for f in work.glob("*-check.png"):
                (Path(sys.argv[1]) / f.name).write_bytes(f.read_bytes())
    for f in sorted(OUT.glob("*.bmp")):
        with Image.open(f) as im:
            print(f.name, im.size, im.mode)


if __name__ == "__main__":
    main()
