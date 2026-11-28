"""Start a frozen engine (the sidecar the installed app runs) and check that it really works.

The tests run the engine from source; this runs what users get, so a library left out of the
bundle (OpenCV, GEOS, a hidden import) fails the build instead of shipping.

    python scripts/smoke_engine.py apps/desktop/src-tauri/binaries/threadline-engine-<triple>[.exe]

Standard library only. Uses a scratch data folder, never the user's own.
"""

from __future__ import annotations

import json
import os
import platform
import struct
import subprocess
import sys
import tempfile
import threading
import zlib
from pathlib import Path


def tiny_png(path: Path, size: int = 40) -> None:
    """A white square with a black disc in the middle (something for the tracer to find)."""
    rows = b""
    c, r2 = size / 2, (size / 4) ** 2
    for y in range(size):
        rows += b"\x00" + bytes(0 if (x - c) ** 2 + (y - c) ** 2 < r2 else 255 for x in range(size) for _ in range(3))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def tiny_svg(path: Path) -> None:
    """A 20 mm drawing with one filled 16 mm square."""
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="20mm" viewBox="0 0 20 20">'
                    '<rect x="2" y="2" width="16" height="16" fill="#cc0000"/></svg>', encoding="utf-8")


def tiny_dxf(path: Path) -> None:
    """A millimeter DXF with one 20 mm line, in the plain text form."""
    pairs = [(0, "SECTION"), (2, "HEADER"), (9, "$INSUNITS"), (70, 4), (0, "ENDSEC"),
             (0, "SECTION"), (2, "ENTITIES"), (0, "LINE"), (8, "0"), (10, 0.0), (20, 0.0), (11, 20.0), (21, 0.0),
             (0, "ENDSEC"), (0, "EOF")]
    path.write_text("".join(f"{code}\n{value}\n" for code, value in pairs), encoding="ascii")


def tiny_pdf(path: Path) -> None:
    """A one-page PDF with a filled square and a 4 pt stroked line."""
    content = b"0.8 0 0 rg 20 20 100 100 re f 0 0 0.8 RG 4 w 30 160 m 170 160 l S"
    objects = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
               b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R>>",
               b"<</Length %d>>\nstream\n%s\nendstream" % (len(content), content)]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (n, body)
    start = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, start)
    path.write_bytes(bytes(out))


def wide_svg(path: Path) -> None:
    """A 14 mm wide line of 450 points. The engine outlines a wide line of many points in a child
    process (a copy of itself), as it reads every PDF."""
    points = " ".join(f"{10 + i * 0.2:.1f},{20 + (i % 2) * 0.1:.1f}" for i in range(450))
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="120mm" height="40mm" viewBox="0 0 120 40">'
                    f'<polyline points="{points}" fill="none" stroke="#0000cc" stroke-width="14"/></svg>',
                    encoding="utf-8")


#: One file for each library that reads artwork, and the shapes it has to come out as.
ARTWORK = (("smoke.svg", tiny_svg, "svgelements", ["fill"]), ("smoke.dxf", tiny_dxf, "ezdxf", ["run"]),
           ("smoke.pdf", tiny_pdf, "pypdfium2", ["fill", "satin"]),
           ("smoke-wide.svg", wide_svg, "GEOS in the child process", ["fill"]))


def never_a_second_engine(command: list[str], data_dir: str) -> None:
    """The engine's child process mode (--ludd-artwork-worker), and any other option, must never
    answer the app's requests the way the engine does."""
    ping = b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n'
    for option in ("--ludd-artwork-worker", "--no-such-option"):
        done = subprocess.run([*command, option], input=ping, capture_output=True, timeout=180,
                              env=dict(os.environ, THREADLINE_DATA_DIR=data_dir))
        assert done.returncode == 2 and done.stdout == b"", (
            f"smoke: the engine started with {option} exited with {done.returncode} and wrote "
            f"{done.stdout[:200]!r}; its messages: {done.stderr[-500:]!r}")
    print("smoke: a copy started with an option never answers as a second engine")


class Engine:
    def __init__(self, command: list[str], data_dir: str) -> None:
        env = dict(os.environ, THREADLINE_DATA_DIR=data_dir)
        # The engine's own messages go to a file so a failure can say why (they used to be thrown away).
        self.err_path = Path(data_dir) / "engine-stderr.txt"
        self.err = open(self.err_path, "wb")
        self.p = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err,
            env=env, text=True, encoding="utf-8",
        )
        self.next_id = 0

    def why(self) -> str:
        """What the engine said on its way out, and whether it is still running."""
        self.err.flush()
        text = self.err_path.read_text(encoding="utf-8", errors="replace").strip()
        state = "still running" if self.p.poll() is None else f"exited with code {self.p.returncode}"
        return f"engine {state}; its messages: {text[-1500:] or '(none)'}"

    def call(self, method: str, timeout: float = 120, **params):
        self.next_id += 1
        rid = self.next_id
        assert self.p.stdin and self.p.stdout
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}) + "\n")
        self.p.stdin.flush()
        reply: dict = {}

        stray: list[str] = []

        def read() -> None:
            while True:
                line = self.p.stdout.readline()
                if not line:
                    return
                try:
                    msg = json.loads(line)
                except ValueError:
                    stray.append(line.rstrip()[:200])  # not an answer: note it and keep reading
                    continue
                if msg.get("id") == rid:
                    reply.update(msg)
                    return

        t = threading.Thread(target=read, daemon=True)
        t.start()
        t.join(timeout)
        if not reply:
            gone = "the engine closed its output" if not t.is_alive() else f"nothing came back within {timeout:.0f} s"
            raise SystemExit(f"smoke: no answer to {method}: {gone}. {self.why()}. Stray output: {stray[:5] or 'none'}")
        if "error" in reply:
            raise SystemExit(f"smoke: {method} failed: {reply['error']}")
        return reply["result"]


def smoke(command: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        eng = Engine(command, tmp)
        try:
            # The first answer can be slow: the one-file engine unpacks itself first.
            assert eng.call("ping", timeout=180) == "pong"
            info = eng.call("engine.info")
            print(f"smoke: engine {info['version']} (Python {info['python']}, {info['platform']})")
            assert "pes" in json.dumps(eng.call("formats.list")).lower(), "formats.list has no PES"
            # OpenCV (auto-trace) and GEOS (shape tools) are the native libraries most likely to go missing.
            png = Path(tmp) / "smoke.png"
            tiny_png(png)
            place = {"x": 0, "y": 0, "width_mm": 20, "height_mm": 20, "rotate": 0}
            shapes = eng.call("trace.digitize_all", path=str(png), placement=place)["shapes"]
            assert shapes, "trace.digitize_all found nothing in a black disc"
            print(f"smoke: auto-trace ok ({len(shapes)} shape(s))")
            # ONNX Runtime (AI tracing) must really load, except on Intel Macs, which have no build of it.
            intel_mac = sys.platform == "darwin" and platform.machine() == "x86_64"
            ort = eng.call("ai.trace_model")["runtime"]
            assert ort or intel_mac, "ONNX Runtime doesn't load in this engine (AI tracing would be unavailable)"
            print(f"smoke: ONNX Runtime {'loads' if ort else 'left out (Intel Mac)'}")
            # The artwork libraries must be in the bundle and read a real file.
            for name, make, library, kinds in ARTWORK:
                art = Path(tmp) / name
                make(art)
                got = eng.call("art.preview", path=str(art), options={})
                found = sorted(s["kind"] for s in got["shapes"])
                assert found == kinds, f"art.preview ({library}) read {found} from {name}, not {kinds}"
                width, height = got["size_mm"]
                print(f"smoke: {library} ok ({name}: {', '.join(found)}, {width:.1f} x {height:.1f} mm)")
            # Stops by itself (the packaged engine then deletes its unpacked files).
            assert eng.call("engine.shutdown") is True
            code = eng.p.wait(timeout=30)
            assert code == 0, f"engine exited with code {code} after engine.shutdown"
        finally:
            if eng.p.poll() is None:
                eng.p.kill()
            eng.err.close()  # Windows can't delete the scratch folder while this is open
        never_a_second_engine(command, tmp)
    print("smoke: ok")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    exe = Path(sys.argv[1])
    # abspath, not resolve(): a virtual environment's python is a symlink on Linux and macOS, and following it
    # runs the real interpreter outside the environment (no OpenCV, no engine libraries).
    smoke([os.path.abspath(exe) if exe.exists() else sys.argv[1], *sys.argv[2:]])  # extra words: e.g. `python -m threadline_engine` to try it from source
