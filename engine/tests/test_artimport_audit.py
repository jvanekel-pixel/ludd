"""Artwork import reads the one chosen file and nothing else, and never uses the network: proved
with Python's audit hook in a process of its own, on files that point at other files and websites
every way each format can. PDFium is native code the hook can't see into, so the PDF also points
at a "secret" file whose drawing would show up in the answer if PDFium ever read it.

The PDF is read in a child process (artimport/child.py), the only process import may start. The
test runs that child under the same hook too: it gets the file's bytes on its stdin and opens
nothing at all but Python's own files."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from artimport_util import svg
from test_artimport_dxf import make, square
from test_artimport_pdf import PROOF, build_pdf, stream

ENGINE = Path(__file__).resolve().parents[1]

# The hook, in the importing process and in the child that reads the PDF.
HOOK = textwrap.dedent('''
    import json, os, sys

    events = []
    recording = [False]
    WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND

    def hook(event, args):
        if not recording[0]:
            return
        if event == "open":
            path, mode, flags = (list(args) + [None, None])[:3]
            if isinstance(path, int):
                return  # an already-open file given a new object
            writing = bool(mode and set("wax+") & set(mode)) or bool(isinstance(flags, int) and flags & WRITE_FLAGS)
            events.append(["open", os.fsdecode(path), writing])
        elif event == "subprocess.Popen":
            command = args[1]
            command = command if isinstance(command, str) else " ".join(map(os.fsdecode, command))
            events.append([event, command, False])
        elif event.startswith(("socket.", "urllib.", "http.client", "ftplib.", "smtplib.", "subprocess.",
                               "os.system", "os.exec", "os.spawn", "os.startfile", "webbrowser.", "ctypes.dlopen")):
            events.append([event, repr(args)[:300], False])

    sys.addaudithook(hook)
''')

# Run in its own process: import each file twice. Everything the first (cold) round does is
# recorded, then the second (warm) one, when every library has already been loaded.
SCRIPT = HOOK + textwrap.dedent('''
    import platform
    # Asked first: shapely asks too as it loads, and when Windows is slow to answer, Python runs
    # "cmd /c ver" for it. (The child must start nothing without this help: it sees to that itself.)
    platform.system()
    engine, watched_child, child_log = sys.argv[1:4]
    sys.path.insert(0, engine)
    out = {}
    for round_name in ("cold", "warm"):
        recording[0] = True
        events.clear()
        from threadline_engine import artimport
        from threadline_engine.artimport import child
        # The same child, started so that it runs under the hook as well.
        child.worker_command = lambda: [sys.executable, "-I", "-B", watched_child, engine, child_log]
        answers = []
        for path in sys.argv[4:]:
            try:
                answers.append(artimport.preview(path, {"closed_as_fills": True}))
            except artimport.ArtError as exc:
                answers.append({"refused": str(exc)})
        recording[0] = False
        out[round_name] = {"events": list(events), "answers": answers}
    out["prefixes"] = [sys.prefix, sys.base_prefix]
    print(json.dumps(out))
''')

CHILD_SCRIPT = HOOK + textwrap.dedent('''
    engine, log = sys.argv[1:3]
    sys.path.insert(0, engine)
    recording[0] = True
    from threadline_engine.artimport import child
    code = child.main()
    recording[0] = False
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(events) + "\\n")
    sys.exit(code)
''')

NETWORK = ("socket.__new__", "socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg", "socket.getaddrinfo",
           "socket.gethostbyname", "socket.gethostbyaddr", "socket.getnameinfo", "urllib.", "http.client", "ftplib.",
           "smtplib.", "subprocess.", "os.system", "os.exec", "os.spawn", "os.startfile", "webbrowser.")
FONTS = (".ttf", ".otf", ".ttc", ".shx", ".shp", ".lff", ".pfb", ".fon")


def _hostile_files(tmp_path: Path) -> tuple[list[Path], list[Path]]:
    """(the files to import, the files they point at that must never be read)."""
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    drawing = secrets / "drawing.svg"
    drawing.write_text(svg('<rect id="s" width="90" height="40" fill="#0000ff"/>'), encoding="utf-8")
    dtd = secrets / "secret.dtd"
    dtd.write_text('<!ENTITY leak "x">', encoding="utf-8")
    picture = secrets / "photo.png"
    picture.write_bytes(b"\x89PNG\r\n\x1a\n")
    outside = secrets / "outside.dxf"
    outside.write_text("0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n", encoding="utf-8")
    paint = secrets / "paint.txt"
    paint.write_text("0 0 1 rg 0 0 200 100 re f", encoding="latin-1")  # a blue square, if PDFium reads it

    here = tmp_path / "chosen"
    here.mkdir()
    linked = here / "linked.svg"
    linked.write_text(
        f'<?xml version="1.0"?><!DOCTYPE svg SYSTEM "{dtd.as_uri()}">' + svg(
            '<rect x="1" y="1" width="20" height="10" fill="#ff0000"/>'
            f'<use href="{drawing.as_uri()}#s"/><use xlink:href="../secrets/drawing.svg#s"/>'
            '<use href="http://example.invalid/a.svg#s"/>'
            f'<image href="{picture.as_uri()}" width="5" height="5"/><image xlink:href="../secrets/photo.png" '
            'width="5" height="5"/><image href="https://example.invalid/p.png" width="5" height="5"/>'
            '<image href="data:image/png;base64,iVBORw0KGgo=" width="5" height="5"/>'
            f'<style>@import url({drawing.as_uri()}); @font-face {{ src: url(secret.ttf) }} '
            'rect { fill: url(http://example.invalid/g.svg#g) }</style>'
            f'<a href="{drawing.as_uri()}"><circle cx="50" cy="20" r="6" fill="url(../secrets/drawing.svg#s)"/></a>'
            f'<script href="{drawing.as_uri()}"/><foreignObject><iframe src="{drawing.as_uri()}"/></foreignObject>'),
        encoding="utf-8")
    entity = here / "entity.svg"
    entity.write_text(f'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x SYSTEM "{drawing.as_uri()}">]>'
                      + svg("<text>&x;</text>"), encoding="utf-8")

    def build(doc, msp):
        square(msp)
        xref = doc.blocks.new("XR", dxfattribs={"flags": 4})
        xref.block.dxf.xref_path = str(outside)
        msp.add_blockref("XR", (0, 0))
        image = doc.add_image_def(filename=str(picture), size_in_pixel=(4, 4))
        msp.add_image(image, insert=(0, 0), size_in_units=(5, 5))
        msp.add_text("Hi", dxfattribs={"style": "Standard"})
        msp.add_mtext("There")
        underlay = doc.add_underlay_def(filename=str(drawing), fmt="pdf", name="1")
        msp.add_underlay(underlay, insert=(0, 0))
        doc.header["$PROJECTNAME"] = str(outside)

    dxf_file = make(here, build, name="refs.dxf")

    # A page whose content also names an external file for its data, an image kept in another file,
    # a form kept in another PDF, a script run on opening, and a link to a file and a website.
    objects = [
        "<< /Type /Catalog /Pages 2 0 R /OpenAction << /S /JavaScript /JS (app.launchURL('http://example.invalid')) "
        ">> >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 100] /Contents [4 0 R 5 0 R] /Annots [8 0 R] "
        "/Resources << /XObject << /Im 6 0 R /Ref 7 0 R >> >> >>",
        stream(PROOF + " q /Im Do /Ref Do Q"),
        f"<< /Length 0 /F ({paint.as_posix()}) >>\nstream\n\nendstream",
        stream("", f"/Type /XObject /Subtype /Image /Width 4 /Height 4 /ColorSpace /DeviceRGB /BitsPerComponent 8 "
                   f"/F ({picture.as_posix()})"),
        stream("", f"/Type /XObject /Subtype /Form /BBox [0 0 200 100] /Ref << /F ({outside.as_posix()}) /Page 0 >>"),
        f"<< /Type /Annot /Subtype /Link /Rect [0 0 9 9] /A << /S /Launch /F ({paint.as_posix()}) >> >>",
    ]
    pdf_file = here / "refs.pdf"
    pdf_file.write_bytes(build_pdf(objects))
    return [linked, entity, dxf_file, pdf_file], [drawing, dtd, picture, outside, paint]


@pytest.fixture(scope="module")
def audit(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("audit")
    chosen, secrets = _hostile_files(tmp_path)
    script, watched_child = tmp_path / "watch.py", tmp_path / "watched_child.py"
    script.write_text(SCRIPT, encoding="utf-8")
    watched_child.write_text(CHILD_SCRIPT, encoding="utf-8")
    child_log = tmp_path / "child-events.jsonl"
    home = tmp_path / "home"
    for folder in ("home", "cache", "config", "data", "cwd", "temp"):
        (tmp_path / folder).mkdir()
    env = {**os.environ, "THREADLINE_DATA_DIR": str(tmp_path / "data"), "HOME": str(home), "USERPROFILE": str(home),
           "XDG_CACHE_HOME": str(tmp_path / "cache"), "XDG_CONFIG_HOME": str(tmp_path / "config"),
           "TEMP": str(tmp_path / "temp"), "TMP": str(tmp_path / "temp"), "TMPDIR": str(tmp_path / "temp")}
    env.pop("EZDXF_CONFIG_FILE", None)
    done = subprocess.run([sys.executable, "-I", "-B", str(script), str(ENGINE), str(watched_child), str(child_log),
                           *map(str, chosen)],
                          capture_output=True, text=True, timeout=240, env=env, cwd=tmp_path / "cwd")
    assert done.returncode == 0, done.stderr[-3000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    out["children"] = [json.loads(line) for line in child_log.read_text(encoding="utf-8").splitlines()]
    return out, chosen, secrets, tmp_path


def _norm(path: str, base: Path) -> str:
    p = Path(path)
    return str((p if p.is_absolute() else base / p).resolve()).casefold()


def test_the_hostile_files_are_still_read(audit):
    out = audit[0]
    for round_name in ("cold", "warm"):
        linked, entity, dxf, pdf = out[round_name]["answers"]
        assert [(s["kind"], s["color"]) for s in linked["shapes"]] == [("fill", "#ff0000")], linked
        assert "entities" in entity["refused"]
        assert [s["kind"] for s in dxf["shapes"]] == ["fill"], dxf
        assert [(s["kind"], s["color"]) for s in pdf["shapes"]] == [("fill", "#ff0000"), ("satin", "#0000ff")], pdf


def _starts_the_child(event) -> bool:
    return event[0] == "subprocess.Popen" and "watched_child.py" in event[1] and "child-events.jsonl" in event[1]


def test_no_network_is_used(audit):
    out = audit[0]
    for round_name in ("cold", "warm"):
        used = [e for e in out[round_name]["events"] if e[0].startswith(NETWORK) and not _starts_the_child(e)]
        assert not used, used
    for events in out["children"]:
        used = [e for e in events if e[0].startswith(NETWORK)]
        assert not used, used


def test_only_the_pdf_starts_a_child_which_opens_nothing_but_pythons_own_files(audit):
    out, chosen, secrets, tmp_path = audit
    for round_name in ("cold", "warm"):
        assert len([e for e in out[round_name]["events"] if _starts_the_child(e)]) == 1  # the one PDF
    assert len(out["children"]) == 2
    python = tuple(_norm(p, tmp_path) for p in [*out["prefixes"], ENGINE / "threadline_engine"])
    ours = _norm(str(tmp_path), tmp_path)  # the chosen files, what they point at, and the user's folders
    assert all(_norm(str(p), tmp_path).startswith(ours) for p in [*chosen, *secrets])
    for events in out["children"]:
        opened = {_norm(e[1], tmp_path / "cwd") for e in events if e[0] == "open"}
        assert not [p for p in opened if p.startswith(ours)], opened
        assert not [p for p in opened if p.endswith(FONTS)]
        assert not [e for e in events if e[0] == "open" and e[2]]  # it writes no file
        if sys.platform == "win32":  # (elsewhere, loading a library may read the system's own files)
            others = sorted(p for p in opened if not p.startswith(python))
            assert not others, others


def test_only_the_chosen_files_are_opened(audit):
    out, chosen, _, tmp_path = audit
    python = [_norm(p, tmp_path) for p in [*out["prefixes"], ENGINE / "threadline_engine"]]
    opened = [e[1] for e in out["warm"]["events"] if e[0] == "open"]
    others = sorted({_norm(p, tmp_path / "cwd") for p in opened if not _norm(p, tmp_path / "cwd").startswith(tuple(python))})
    assert others == sorted(_norm(str(p), tmp_path) for p in chosen), others


def test_loading_the_libraries_reads_no_fonts_and_writes_only_a_passing_folder(audit):
    """The first import loads svgelements, ezdxf and PDFium: nothing they point at is read, no font
    on the computer is opened (ezdxf would open them all), and nothing is written but ezdxf's own
    short-lived font list in the temp folder, which is then removed."""
    out, _, secrets, tmp_path = audit
    cold = [e for e in out["cold"]["events"] if e[0] == "open"]
    opened = {_norm(e[1], tmp_path / "cwd") for e in cold}
    assert not opened & {_norm(str(s), tmp_path) for s in secrets}
    assert not [p for p in opened if p.endswith(FONTS)]
    temp = _norm(str(tmp_path / "temp"), tmp_path)
    written = sorted({_norm(e[1], tmp_path / "cwd") for e in cold if e[2]})
    # Only in the temp folder (Python's own check that it can write there, and ezdxf's list).
    assert written and all(p.startswith(temp) for p in written), written
    assert [p for p in written if "ludd-ezdxf-" in p]
    for folder in ("home", "cache", "config", "data", "cwd", "temp"):
        assert list((tmp_path / folder).iterdir()) == [], folder  # nothing is left behind
