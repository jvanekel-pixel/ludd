"""Turn docs/USER-MANUAL.md into a branded PDF: docs/LUDD-User-Manual.pdf.

Run from the repo root (Windows, with Microsoft Edge installed):
    uv run --with markdown --with websockets --with pypdf python scripts/make_manual_pdf.py

The manual is laid out as a web page in LUDD's brand (ink, bone and techno yellow; the hammer and
needle mark; Archivo and Space Mono, embedded), then printed to PDF by Edge in headless mode:
the cover full-bleed, the rest with page numbers. Links to other docs point at GitHub.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import markdown
import websockets
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "USER-MANUAL.md"
OUT = ROOT / "docs" / "LUDD-User-Manual.pdf"
REPO = "https://github.com/jvanekel-pixel/ludd/blob/main/docs/"
FONTS = ROOT / "node_modules" / ".pnpm"
EDGE = [
    Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
]

INK, BONE, LIME, MUTED = "#121114", "#EEE9DF", "#C8FF2E", "#5F5950"


def font(pattern: str) -> str:
    f = next(FONTS.rglob(pattern))
    return "data:font/woff2;base64," + base64.b64encode(f.read_bytes()).decode("ascii")


def mark(ink: str, gap: str, thread: str, size: int) -> str:
    """The LUDD mark (same drawing as apps/desktop/src/components/Logo.tsx)."""
    t = "M124 58 L142 74.5 C162 92 188 82 186 58 C184 38 166 34 172 16"
    return f'''<svg viewBox="0 0 200 200" width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">
<circle cx="100" cy="104" r="78" fill="none" stroke="{ink}" stroke-width="9"/>
<circle cx="100" cy="104" r="68" fill="none" stroke="{ink}" stroke-width="2.5"/>
<rect x="97.5" y="16" width="5" height="18" fill="{gap}"/>
<rect x="85" y="12" width="12" height="20" rx="2" fill="{ink}"/>
<rect x="103" y="12" width="12" height="20" rx="2" fill="{ink}"/>
<rect x="78" y="18" width="44" height="7" rx="3.5" fill="{ink}"/>
<g transform="rotate(-42 100 104)"><rect x="95.5" y="66" width="9" height="100" rx="4.5" fill="{ink}"/><rect x="70" y="46" width="60" height="24" rx="3" fill="{ink}"/></g>
<g transform="rotate(42 100 104)"><path d="M100 168 L95.5 74 L95.5 48 Q95.5 39 100 39 Q104.5 39 104.5 48 L104.5 74 Z" fill="{ink}" stroke="{gap}" stroke-width="6" stroke-linejoin="round" paint-order="stroke"/><rect x="98.2" y="46" width="3.6" height="16" rx="1.8" fill="{gap}"/></g>
<path d="{t}" fill="none" stroke="{gap}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>
<path d="{t}" fill="none" stroke="{thread}" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>'''


def fonts_css() -> str:
    return f"""
@font-face {{ font-family: "Archivo"; src: url({font("archivo-latin-wdth-normal.woff2")}) format("woff2");
  font-weight: 100 900; font-stretch: 62% 125%; }}
@font-face {{ font-family: "Space Mono"; src: url({font("space-mono-latin-400-normal.woff2")}) format("woff2"); font-weight: 400; }}
@font-face {{ font-family: "Space Mono"; src: url({font("space-mono-latin-700-normal.woff2")}) format("woff2"); font-weight: 700; }}
"""


def cover_html() -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{fonts_css()}
@page {{ size: 8.5in 11in; margin: 0; }}
html, body {{ margin: 0; height: 100%; }}
body {{ background: {INK}; color: {BONE}; -webkit-print-color-adjust: exact; print-color-adjust: exact;
  display: flex; flex-direction: column; align-items: center; justify-content: center; height: 11in; font-family: "Segoe UI", sans-serif; }}
.word {{ font-family: "Archivo"; font-weight: 900; font-stretch: 62%; font-size: 150pt; letter-spacing: 0.02em; line-height: 0.9; margin: 0.25in 0 0; }}
.sub {{ font-family: "Space Mono"; text-transform: uppercase; letter-spacing: 0.32em; font-size: 13pt; margin-top: 0.15in; }}
.rule {{ width: 1.1in; height: 4px; background: {LIME}; margin: 0.45in 0 0.35in; border-radius: 2px; }}
.tag {{ font-size: 15pt; color: #B5AEA3; }}
.foot {{ position: absolute; bottom: 0.6in; font-family: "Space Mono"; font-size: 9pt; letter-spacing: 0.18em; text-transform: uppercase; color: #8E877D; }}
.foot b {{ color: {LIME}; font-weight: 700; }}
</style></head><body>
{mark(BONE, INK, LIME, 230)}
<div class="word">LUDD</div>
<div class="sub">User manual · Version 1.0</div>
<div class="rule"></div>
<div class="tag">Break the machine. Free the stitch.</div>
<div class="foot">Free <b>+</b> open-source embroidery</div>
</body></html>"""


def body_html() -> str:
    md = SRC.read_text(encoding="utf-8")
    # A list needs a blank line before it in this Markdown dialect (GitHub doesn't mind).
    md = re.sub(r"(?m)^(?!\s*(?:[-*] |\d+\. )|\s*$)(.+)\n(?=\s*(?:[-*] |\d+\. ))", r"\1\n\n", md)
    # Links to the other docs go to GitHub (a PDF has no docs folder next to it).
    md = re.sub(r"\]\(((?:[A-Z-]+|CHANGELOG)\.md[^)]*)\)", lambda m: f"]({REPO}{m.group(1)})", md)
    html = markdown.markdown(md, extensions=["tables", "toc", "sane_lists"], extension_configs={"toc": {"toc_depth": "2"}})
    # Drop the page title and the horizontal rules (each section starts its own page here).
    html = re.sub(r"<h1[^>]*>.*?</h1>", "", html, count=1, flags=re.S)
    html = html.replace("<hr />", "")
    # Keys look like keys.
    keys = r"(?:(?:Ctrl|Shift|Alt)\+[^<\s]{1,12}(?:\+[^<\s]{1,12})?|Esc|Enter|Tab|Space|Backspace|Delete|F1|Home|End)"
    html = re.sub(rf"<strong>({keys})</strong>", r'<kbd>\1</kbd>', html)
    # Contents page from the section headings.
    heads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', html)
    toc = "".join(f'<li><a href="#{i}">{re.sub(r"<[^>]+>", "", t)}</a></li>' for i, t in heads)
    intro_end = html.find("<h2")
    intro, rest = html[:intro_end], html[intro_end:]
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{fonts_css()}
@page {{ size: 8.5in 11in; margin: 0.75in 0.8in 0.85in; }}
* {{ box-sizing: border-box; }}
body {{ font-family: "Segoe UI", system-ui, sans-serif; font-size: 10.5pt; line-height: 1.5; color: {INK}; margin: 0;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
h2, h3, .toc-title {{ font-family: "Archivo"; font-stretch: 75%; color: {INK}; }}
h2 {{ break-before: page; font-size: 26pt; font-weight: 800; line-height: 1.05; margin: 0 0 0.25in; padding-top: 0.12in;
  border-top: 6px solid {LIME}; text-transform: uppercase; letter-spacing: 0.01em; }}
h3 {{ font-size: 14pt; font-weight: 700; margin: 0.28in 0 0.08in; break-after: avoid; }}
h3::before {{ content: ""; display: inline-block; width: 9px; height: 9px; background: {LIME}; border: 1.5px solid {INK};
  border-radius: 2px; margin-right: 8px; vertical-align: 2px; }}
p, li {{ orphans: 3; widows: 3; }}
ul, ol {{ padding-left: 1.3em; }}
li {{ margin: 0.12em 0; }}
a {{ color: {INK}; text-decoration-color: {LIME}; text-decoration-thickness: 2px; }}
strong {{ font-weight: 650; }}
code {{ font-family: "Space Mono"; font-size: 9pt; background: #F1EDE4; padding: 0.05em 0.3em; border-radius: 3px; }}
kbd {{ font-family: "Space Mono"; font-size: 8.5pt; font-weight: 700; background: #FBFAF6; border: 1px solid #CFC8BA;
  border-bottom-width: 2px; border-radius: 4px; padding: 0.02em 0.35em; white-space: nowrap; }}
table {{ width: 100%; border-collapse: collapse; margin: 0.12in 0 0.2in; font-size: 9.5pt; break-inside: auto; }}
tr {{ break-inside: avoid; }}
thead th {{ background: {INK}; color: {BONE}; font-family: "Archivo"; font-stretch: 80%; font-size: 8.5pt; text-transform: uppercase;
  letter-spacing: 0.08em; font-weight: 700; text-align: left; padding: 0.5em 0.7em; }}
td {{ padding: 0.45em 0.7em; border-bottom: 1px solid #E2DCD0; vertical-align: top; }}
tbody tr:nth-child(even) td {{ background: #F7F4EE; }}
td:last-child {{ white-space: normal; }}
.intro {{ font-size: 11.5pt; }}
.intro p:first-child {{ font-size: 12pt; }}
.toc-title {{ font-size: 30pt; font-weight: 900; font-stretch: 62%; text-transform: uppercase; margin: 0.25in 0 0.12in;
  border-top: 6px solid {LIME}; padding-top: 0.12in; }}
.toc {{ list-style: none; padding: 0; margin: 0; break-inside: avoid; }}
.toc li {{ border-bottom: 1px solid #E2DCD0; padding: 0.2em 0; font-size: 10.5pt; }}
.toc a {{ text-decoration: none; display: flex; justify-content: space-between; }}
.toc a::after {{ content: "→"; color: {MUTED}; }}
.brand {{ display: flex; align-items: center; gap: 0.12in; margin-bottom: 0.2in; }}
.brand .w {{ font-family: "Archivo"; font-weight: 900; font-stretch: 62%; font-size: 30pt; line-height: 1; }}
.brand .s {{ font-family: "Space Mono"; font-size: 8pt; letter-spacing: 0.2em; text-transform: uppercase; color: {MUTED}; }}
.note {{ background: {INK}; color: {BONE}; border-radius: 8px; padding: 0.16in 0.2in; margin-top: 0.15in; }}
.note b {{ color: {LIME}; }}
</style></head><body>
<div class="brand">{mark(INK, "#FFFFFF", INK, 54)}<div><div class="w">LUDD</div><div class="s">User manual · Version 1.0</div></div></div>
<div class="intro">{intro}</div>
<div class="note"><b>Esc</b> lets go of whatever you're in the middle of. <b>F1</b> opens Help, which searches this manual inside the app, offline.</div>
<div class="toc-title">Contents</div>
<ol class="toc">{toc}</ol>
{rest}
</body></html>"""


FOOTER = f"""<div style="width:100%; font-family:'Space Mono', monospace; font-size:7.5pt; color:{MUTED};
 padding:0 0.8in; display:flex; justify-content:space-between; letter-spacing:0.08em;">
<span>LUDD · USER MANUAL</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>"""


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def print_pdf(ws_url: str, html_path: Path, pdf_path: Path, footer: bool) -> None:
    async with websockets.connect(ws_url, max_size=2**28) as ws:
        n = 0

        async def call(method: str, params: dict | None = None) -> dict:
            nonlocal n
            n += 1
            await ws.send(json.dumps({"id": n, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == n:
                    if "error" in msg:
                        raise RuntimeError(msg["error"])
                    return msg["result"]

        await call("Page.enable")
        await call("Page.navigate", {"url": html_path.as_uri()})
        await asyncio.sleep(2.5)  # fonts are embedded; give layout a moment
        result = await call("Page.printToPDF", {
            "printBackground": True,
            "preferCSSPageSize": True,
            "displayHeaderFooter": footer,
            "headerTemplate": "<span></span>",
            "footerTemplate": FOOTER if footer else "<span></span>",
            "generateDocumentOutline": True,
        })
        pdf_path.write_bytes(base64.b64decode(result["data"]))


def main() -> None:
    edge = next((p for p in EDGE if p.is_file()), None)
    if not edge:
        raise SystemExit("Microsoft Edge wasn't found")
    work = Path(tempfile.mkdtemp(prefix="ludd-manual-"))
    try:
        (work / "cover.html").write_text(cover_html(), encoding="utf-8")
        (work / "body.html").write_text(body_html(), encoding="utf-8")
        port = free_port()
        proc = subprocess.Popen([str(edge), "--headless=new", f"--remote-debugging-port={port}",
                                 f"--user-data-dir={work / 'profile'}", "--no-first-run", "about:blank"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(60):
                try:
                    targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list"))
                    page = next(t for t in targets if t.get("type") == "page")
                    break
                except Exception:  # noqa: BLE001 - Edge still starting
                    time.sleep(0.5)
            else:
                raise SystemExit("Edge didn't start")
            for name, footer in (("cover", False), ("body", True)):
                asyncio.run(print_pdf(page["webSocketDebuggerUrl"], work / f"{name}.html", work / f"{name}.pdf", footer))
        finally:
            proc.terminate()
        out = PdfWriter()
        out.append(str(work / "cover.pdf"))
        out.append(str(work / "body.pdf"))
        out.add_metadata({"/Title": "LUDD user manual", "/Author": "LUDD", "/Subject": "Free, open-source embroidery software"})
        with OUT.open("wb") as f:
            out.write(f)
        print(f"{OUT} ({len(out.pages)} pages)")
    finally:
        time.sleep(0.5)
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
