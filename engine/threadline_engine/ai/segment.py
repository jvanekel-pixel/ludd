"""AI tracing (optional, off until you download it): MobileSAM, a small "click a thing, get its
outline" model, run on this computer with ONNX Runtime. No cloud and no account.

The model files (MobileSAM, Apache-2.0 license; converted copy from huggingface.co/Acly/MobileSAM) are only downloaded when you
press Download in Settings; nothing is fetched otherwise. Once downloaded, a picture is read by
the model once (about a second), then each click takes a fraction of a second.

How it is used: Auto-trace passes your click (plus Shift+clicks as "this too" and Alt+clicks as
"not this") and gets back up to four outlines, from a small part to the whole thing, each with
the model's own confidence.
"""

from __future__ import annotations

import functools

import hashlib
import http.client
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

from ..storage import data_dir

SOURCE = "https://huggingface.co/Acly/MobileSAM"
# Pinned: the files are fetched from this exact upstream revision (not "main", which can change), and
# each one is checked against its SHA-256 before it is kept. To move to a newer upstream version, look
# up the new revision and checksums on the model page, change both here, and try the download.
REVISION = "0d3b403339b4674a82493d5e97964dd78089ddc8"
FILES = {
    "encoder": (
        "mobile_sam_image_encoder.onnx",
        f"{SOURCE}/resolve/{REVISION}/mobile_sam_image_encoder.onnx",
        "580f5fb648ea1062c0aabc26217aed56921985f03f0cbbd852bba81d760cc749",
    ),
    "decoder": (
        "sam_mask_decoder_multi.onnx",
        f"{SOURCE}/resolve/{REVISION}/sam_mask_decoder_multi.onnx",
        "8976b90a87ba50a6a72217a5ff994f7d25ce16f2229fcc1ed259e1294c622ffe",
    ),
}
SIZE_MB = 45  # about: both files together
INPUT_SIDE = 1024  # the model reads pictures with their long side this big
MIN_MASK_SHARE = 0.0005  # ignore guesses smaller than this share of the picture


class SegmentError(Exception):
    rpc_code = -32000


def model_dir() -> Path:
    return data_dir() / "models" / "mobilesam"


def _runtime():
    try:
        import onnxruntime as ort  # noqa: PLC0415 - only needed when the model is used
    except (ImportError, OSError) as exc:  # pragma: no cover - not available on Intel Macs
        raise SegmentError("AI tracing isn't available on this computer (ONNX Runtime isn't included).") from exc
    return ort


@functools.cache
def runtime() -> bool:
    """ONNX Runtime is part of this build and really loads (it has no version for Intel Macs, so
    it's left out there). Importing it, not just finding the package, catches a build whose native
    library is missing or can't load: Settings then says so before a 45 MB download."""
    try:
        ort = _runtime()
    except SegmentError:
        return False
    return hasattr(ort, "InferenceSession")


def installed() -> bool:
    return all((model_dir() / name).is_file() for name, *_ in FILES.values())


def available() -> bool:
    """The model is downloaded and can run here."""
    return installed() and runtime()


def status() -> dict[str, Any]:
    d = model_dir()
    size = sum((d / n).stat().st_size for n, *_ in FILES.values() if (d / n).is_file())
    return {"installed": installed(), "runtime": runtime(), "size_mb": round(size / 1e6, 1) if size else SIZE_MB, "source": SOURCE, "license": "Apache-2.0"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _fetch(url: str, part: Path) -> str:
    """One file, all of it (a body shorter than the server announced is an error). Returns its SHA-256."""
    h = hashlib.sha256()
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "LUDD"}), timeout=60) as r, open(part, "wb") as f:
        expected = r.headers.get("Content-Length")
        got = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            h.update(chunk)
            got += len(chunk)
    if expected and expected.isdigit() and got != int(expected):
        raise http.client.IncompleteRead(b"", int(expected) - got)
    return h.hexdigest()


def download() -> dict[str, Any]:
    """Fetch the model files (only ever called when the user presses Download)."""
    _runtime()  # no point fetching 45 MB that can't run here
    d = model_dir()
    d.mkdir(parents=True, exist_ok=True)
    for name, url, sha in FILES.values():
        dest = d / name
        if dest.is_file():
            if _sha256(dest) == sha:
                continue
            dest.unlink()  # an earlier download that isn't the pinned version: fetch it again
        part = d / (name + ".part")
        try:
            got = _fetch(url, part)
        except (OSError, http.client.HTTPException) as exc:
            part.unlink(missing_ok=True)
            if isinstance(exc, urllib.error.HTTPError):
                why = f"the server answered {exc.code}"
            elif isinstance(exc, urllib.error.URLError | TimeoutError | ConnectionError):
                why = "check the internet connection"
            else:
                why = "the download was cut off"
            raise SegmentError(f"Couldn't download the AI tracing model ({why}). Try again in a moment.") from exc
        if got != sha:
            part.unlink(missing_ok=True)
            raise SegmentError(
                f"The AI tracing model file {name} didn't match its expected checksum, so it was thrown away. "
                "Try again; if it keeps happening, the download source may have changed."
            )
        os.replace(part, dest)
    # Make sure it loads before saying it's ready.
    try:
        _sessions(force=True)
    except Exception as exc:
        remove()
        raise SegmentError(f"The downloaded AI tracing model wouldn't load ({exc}); it has been removed.") from exc
    return status()


def remove() -> dict[str, Any]:
    global _sess, _generation
    _sess = None
    _generation += 1
    for name, *_ in FILES.values():
        (model_dir() / name).unlink(missing_ok=True)
    return status()


_sess: tuple[Any, Any] | None = None
_generation = 0  # goes up when the model is loaded again or removed (old readings are stale)


def _sessions(force: bool = False):
    global _sess, _generation
    if _sess is None or force:
        _generation += 1
        ort = _runtime()
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        enc = ort.InferenceSession(str(model_dir() / FILES["encoder"][0]), opts, providers=["CPUExecutionProvider"])
        dec = ort.InferenceSession(str(model_dir() / FILES["decoder"][0]), opts, providers=["CPUExecutionProvider"])
        _sess = (enc, dec)
    return _sess


def _embedding(pic: Any) -> tuple[np.ndarray, float]:
    """The model's reading of a picture (the slow part). Kept on the analysed picture itself, so
    it goes when the picture does: an edited file is analysed again, and read again."""
    enc, _ = _sessions()
    hit = getattr(pic, "_ai_embedding", None)
    if hit and hit[0] == _generation:
        return hit[1], hit[2]
    import cv2  # noqa: PLC0415

    rgb = pic.rgb
    h, w = rgb.shape[:2]
    scale = INPUT_SIDE / max(h, w)
    img = cv2.resize(rgb, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA).astype(np.float32)
    inp = enc.get_inputs()[0]
    if len(inp.shape) == 4:  # an encoder that wants a batch, channels first, already normalised
        mean = np.array([123.675, 116.28, 103.53], np.float32)
        std = np.array([58.395, 57.12, 57.375], np.float32)
        x = (img - mean) / std
        pad = np.zeros((INPUT_SIDE, INPUT_SIDE, 3), np.float32)
        pad[: x.shape[0], : x.shape[1]] = x
        img = pad.transpose(2, 0, 1)[None]
    emb = enc.run(None, {inp.name: img})[0]
    pic._ai_embedding = (_generation, emb, scale)
    return emb, scale


def masks(pic: Any, positive: list[tuple[int, int]], negative: list[tuple[int, int]]) -> list[tuple[np.ndarray, float]]:
    """Outlines the model sees at these clicks (picture pixels), most confident first."""
    t0 = time.perf_counter()
    rgb = pic.rgb
    emb, scale = _embedding(pic)
    _, dec = _sessions()
    h, w = rgb.shape[:2]
    pts = [*positive, *negative]
    coords = np.array([[[x * scale, y * scale] for x, y in pts] + [[0.0, 0.0]]], np.float32)
    labels = np.array([[1] * len(positive) + [0] * len(negative) + [-1]], np.float32)
    feed = {
        "image_embeddings": emb.astype(np.float32),
        "point_coords": coords,
        "point_labels": labels,
        "mask_input": np.zeros((1, 1, 256, 256), np.float32),
        "has_mask_input": np.zeros(1, np.float32),
        "orig_im_size": np.array([h, w], np.float32),
    }
    names = {i.name for i in dec.get_inputs()}
    out = dec.run(None, {k: v for k, v in feed.items() if k in names})
    logits, scores = out[0][0], out[1][0]
    found = []
    for m, sc in sorted(zip(logits, scores), key=lambda t: -float(t[1])):
        mask = (m > 0).astype(np.uint8)
        if mask.shape != (h, w):
            import cv2  # noqa: PLC0415

            mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
        if mask.sum() >= MIN_MASK_SHARE * h * w:
            found.append((mask, float(sc)))
    _ = time.perf_counter() - t0
    return found
