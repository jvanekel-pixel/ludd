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
            # Stops by itself (the packaged engine then deletes its unpacked files).
            assert eng.call("engine.shutdown") is True
            code = eng.p.wait(timeout=30)
            assert code == 0, f"engine exited with code {code} after engine.shutdown"
        finally:
            if eng.p.poll() is None:
                eng.p.kill()
            eng.err.close()  # Windows can't delete the scratch folder while this is open
    print("smoke: ok")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    exe = Path(sys.argv[1])
    # abspath, not resolve(): a virtual environment's python is a symlink on Linux and macOS, and following it
    # runs the real interpreter outside the environment (no OpenCV, no engine libraries).
    smoke([os.path.abspath(exe) if exe.exists() else sys.argv[1], *sys.argv[2:]])  # extra words: e.g. `python -m threadline_engine` to try it from source
