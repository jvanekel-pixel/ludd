# LUDD QA/QC report

Prepared 2026-10-12 from the review run's saved results. Report-only: no source file in the repo was changed by the review (see the note at the end about one stray file).

## Summary

The review found **420 issues** across 22 review areas: **2 Critical, 37 High, 195 Medium, 186 Low**. These counts are before merging duplicates: the same root cause was often reported by several areas (for example 'One file per name' ignoring the machine profile was reported five times, and the hoop-split STOP bug three times). Merged by hand, the Critical and High items come down to about 26 distinct problems; the table below lists them.

**How sure are we?**

- 244 issues were reproduced by a second, independent agent (**Confirmed**).
- 174 were reported by a reviewer who usually reproduced them itself, but no second agent re-ran them (**Reviewer-reproduced / Suspected, not re-verified**). They are mostly from the docs, tests, packaging, installed-app and UI-behaviour reviews, which finished last.
- 1 is disputed, 1 is only suspected, and 2 reviewer claims were refuted and dropped (listed at the end).

**What was not done** (to stop the token spend): the three UI reviews for keyboard shortcuts, the feature walkthroughs (shape ops, auto-trace, guides, colorways, preview) and performance on 30k+ stitch designs were never run; there was no completeness-critic or follow-up round; about 170 findings were not independently re-verified. The installed Tauri app, macOS, and real stitch-outs on the machine were not exercised. Treat those areas as unchecked, not as clean.

**Baseline before the review:** engine 296 pytest passing, UI 85 vitest passing, typecheck clean.

## Top five fixes to make first

**1. Keep STOPs when splitting across hoopings (Critical, Confirmed, reported three times)**  
`split.py` drops every STOP command when it cuts a design into hoopings, so applique placement and tack-down pauses disappear and the machine sews straight through. Also in the same file: whole runs go to the earlier hooping, so a top layer straddling the seam gets stitched over by the next hooping (High, Confirmed). Fix: carry STOP through `_blocks`, and split runs at the seam.

**2. Make 'Fewer jumps & trims' safe, because it is on by default for new designs**  
One feature, three confirmed failures in `layout.py`: it crashes the render with a GEOS TopologyException on some shapes (including adding a whole-picture result), it takes seconds per render, and with Sort colors on, the cover is sewn before the travel it hides, leaving bare thread on top. Fix: guard `_cover`, plan hidden travel after the colour sort, and cache the geometry; consider shipping it off until the tests exist.

**3. Make 'One file per name' use the machine profile**  
It passes empty options, so none of the PE550D cut-stops, the hoop check or the warnings apply (reported five times, Confirmed). On your machine that means stray threads and no hoop warning on every file in a batch. Fix: build the options the same way the normal export does (`features.ts:322`). It also overwrites existing files silently.

**4. Stop losing work: recovery copy and unopenable projects**  
Saving any project deletes a crash-recovery copy that is still waiting for Recover or Discard (`actions.ts:341`, Confirmed). A project with lettering in a font that is not installed cannot be rendered or opened at all (`lettering.py:123`, Confirmed). Fix: only clear recovery after the user has decided, and fall back to a default font with a warning.

**5. Installed-app engine lifecycle**  
Every normal quit leaves ~180 MB behind (onefile sidecar killed, not stopped); if the engine dies the app stays dead with no restart; a second launch (double-clicking a .ludd) reports a false crash. All reviewer-reproduced, not re-verified. Fix: build the engine as onedir or stop it cleanly, restart on exit, add the single-instance plugin. Right behind these: the updater manifest 404s after publish and the Mac (Intel) release leg cannot build (no onnxruntime wheel), both release blockers.

## Critical and High: distinct problems

| # | Problem | Severity | Status | Found by |
|---|---|---|---|---|
| C1 | Splitting a design across hoopings throws away every STOP, so applique placement and tack-down pauses vanish | Critical | Confirmed | docs-c, export, layout-order |
| C2 | 'Fewer jumps & trims' (on by default) crashes the render with a GEOS TopologyException on some shapes | High | Confirmed | autotrace, fuzz-rpc |
| C3 | Fewer jumps & trims (on by default for new designs) makes every render, check and export preview take seconds | High | Confirmed | layout-ops |
| C4 | Deleting every stitch of a colour leaves an empty colour block in the output. Emptying the FIRST colour shifts the PES/JEF thread table by one, so ... | High | Confirmed | layout-ops |
| C5 | Split assigns whole runs to the earlier hooping, so a top layer straddling the seam is stitched over by the later hooping's base | High | Confirmed | layout-order |
| C6 | Sort colors defeats 'Fewer jumps & trims': the travel is hidden under a cover that is then sewn first, leaving bare travel stitches on top | High | Confirmed | docs-c, export, layout-ops, layout-order |
| C7 | A project with lettering in a font that isn't installed cannot be rendered or opened at all | High | Confirmed | lettering |
| C8 | Applique silently drops holes: stitches and SVG cut file treat the piece as solid, although the UI offers "Add a hole (O)" and keeps holes on convert | High | Confirmed | patterns |
| C9 | Saving any project deletes a crash-recovery copy that is still waiting for Recover or Discard | High | Confirmed | project |
| C10 | Stitch Advisor crashes on any design that contains a satin ribbon | High | Confirmed | docs-b, satin |
| C11 | Updater manifest (latest.json) is built from draft-release URLs that 404 after publishing | High | Confirmed | packaging, security |
| C12 | 'One file per name' export ignores the machine profile: no cut-stops, no hoop check, warnings discarded | High | Confirmed | compat, docs-a, docs-b, lettering, security |
| C13 | Knife and merge ignore a drawn object's transform; Ctrl+D copies of drawn shapes carry one | High | Confirmed | shapeops |
| C14 | Outline/offset around a whole dense design takes 9-21 s, past the installed app's 10 s RPC timeout, and blocks the engine for the whole time | High | Confirmed | shapeops |
| C15 | Wave fill: rows are sampled at different phases and cross each other, leaving bare gaps and double thread | High | Confirmed | visual |
| C16 | Measuring tool (M) never shows a distance, and has no menu entry | High | Suspected | docs-a |
| C17 | A design re-render during a drag throws and silently drops the drag | High | Reviewer-reproduced | live-esc |
| C18 | Every key repeat queues a full engine render and only the last is shown: holding an arrow key freezes the canvas, then times out and rolls the whole ... | High | Reviewer-reproduced | live-state |
| C19 | An edit made while a project is still opening supersedes the open, leaving projectPath on the OLD project: the next Ctrl+S overwrites it with the new ... | High | Reviewer-reproduced | live-state |
| C20 | Text tool: the new text box is never focused, so typing runs shortcuts and Backspace deletes the text | High | Reviewer-reproduced | live-state |
| C21 | Mac (Intel) release leg cannot build: onnxruntime is a hard dependency and has no macOS x86_64 wheel | High | Reviewer-reproduced | packaging |
| C22 | Print template and thread list print unstyled in the installed app (black square, no centre cross, no swatches): Tauri injects a style nonce that ... | High | Reviewer-reproduced | tauri |
| C23 | Installed app leaves a ~180 MB PyInstaller temp folder behind on every quit | High | Reviewer-reproduced | packaging, tauri |
| C24 | Double-clicking a .ludd while LUDD is open starts a second app that reports a false crash, does not open the file, and Discard destroys the first ... | High | Reviewer-reproduced | tauri |
| C25 | If the engine process dies the app stays dead: no restart, saving impossible, startup failure leaves the child running | High | Reviewer-reproduced | tauri |
| C26 | A clean checkout fails the engine suite: test_library.py needs the gitignored personal fixtures and does not skip | High | Reviewer-reproduced | tests |

## Critical and High: details

### C1 · Critical · Confirmed: Splitting a design across hoopings throws away every STOP, so applique placement and tack-down pauses vanish

**Where:** `engine/threadline_engine/split.py:77-94 (_blocks, STOP handled only by end_run in the else branch at 88-91)`, `engine/threadline_engine/split.py:133-158 (_cut) and 219-221 (_tied) build fresh lists, so any flag on the run must be copied`, `engine/threadline_engine/split.py:224-256 (section_pattern emits no STOP)`, `engine/threadline_engine/layout.py:796-815 (export_split)`  
**Found by:** docs-c, export, layout-order (also reported as docs-c#1, layout-order#1)  
**Status:** Confirmed (a second agent reproduced it)

**What happens:** Any design that has STOPs (an applique's placement and tack-down stops, or a user-inserted "stop here") loses all of them when exported with "Split it across hoopings". Each hooping file sews the placement line, tack-down and cover satin back to back with no pause. The user never lays or trims the fabric, so the satin border sews over bare garment. No warning is shown, and `stops_added` is 0.

**What should happen:** Each hooping file keeps a STOP wherever the original sequence has one between that hooping's runs. PES then writes the same-colour colour change that pauses the machine.

**Repro:**

```
import pyembroidery as pe, tempfile, os
from threadline_engine import layout
sq = lambda x0,y0,x1,y1: [[x0,y0,'c'],[x1,y0,'c'],[x1,y1,'c'],[x0,y1,'c']]
n = lambda pat,k: sum(1 for *_,c in pat.stitches if c&255==k)
lay = {'items':[{'id':'a','kind':'applique','geometry':{'outline':sq(-90,-30,90,30)},'params':{}}]}
print('stops in the whole design:', n(layout.render(lay).pattern, pe.STOP))
r = layout.export_split(lay, os.path.join(tempfile.mkdtemp(),'app.pes'), {'width_mm':100,'height_mm':100})
for p in r['paths']: print(os.path.basename(p), 'stops:', n(pe.read(p), pe.STOP))
# run from engine/: uv run --frozen --no-sync python repro.py
# observed (ran):
# stops in the whole design: 2
# app 1 of 2.pes stops: 0
# app 2 of 2.pes stops: 0
```

**Observed:** [reproduce/confirmed/ran] Ran the reviewer's repro from engine/ with `uv run --frozen --no-sync python`. Output: `stops in the whole design: 2`, `app 1 of 2.pes stops: 0 colour changes: 1 stitches 2070`, `app 2 of 2.pes stops: 0 colour changes: 1 stitches 2051`. The one colour change per file is the pink alignment-mark thread, not a stop. The whole design round-trips with its stops. `prepare()` plus `design.write` to PES, then `pe.read`, gives 2 stops, so only the split path loses them. In the whole design the stops sit at stitch records 197 and 1161 (placement line, then tack-down, then satin). `split.plan` on that design returns one colour block of 3 runs (placement, tack-down, satin). ...

**Suggested fix:** In `_blocks`, record on each run how many STOPs came before it. Carry that count onto every cut piece (`_cut`) and onto the tied copy (`_tied`), then emit `pe.STOP` in `section_pattern` between consecutive runs of one colour group whenever the count rises. A single per-run `stop_after` flag, as the reviewer suggests, is lost when a run is cut into pieces, so it needs to be a sequence number or be copied to every piece. Add a split test asserting per-section stop counts for an applique larger than the hoop.

**Caveats:** The bug is real, and the severity is Critical for the designs it affects: the applique satin border sews onto the garment with no fabric laid, and that spoils a stitch-out. The scope is narrow. It needs both a design bigger than the hoop (about 98 mm or more in one direction on a 100 mm hoop, which triggers the default split) and at least one STOP, meaning an applique piece or a user-inserted stop. Ordinary designs without stops split correctly in this respect. If the team grades by how often ...

### C2 · High · Confirmed: 'Fewer jumps & trims' (on by default) crashes the render with a GEOS TopologyException on some shapes

**Where:** `engine/threadline_engine/layout.py:530-533 (_cover: area.buffer(-0.3) returns an invalid MultiPolygon from a valid polygon; this is the root cause)`, `engine/threadline_engine/layout.py:545-547 (unary_union(later) raises GEOSException; nothing catches it)`, `engine/threadline_engine/layout.py:539 (covers are computed for every digitized block, including different-colour ones)`, `engine/threadline_engine/layout.py:695 (call site; the reviewer cited 696)`  
**Found by:** autotrace, fuzz-rpc (also reported as autotrace#1)  
**Status:** Confirmed (a second agent reproduced it)

**What happens:** layout.render, layout.check, layout.preview_export, layout.optimize_order and layout.export all fail with RPC error -32603 'TopologyException: side location conflict at ...' for a valid design with travel_under on. That is the default for new designs. Trigger: at least one consecutive same-thread pair of drawn objects, plus an invalid _cover at or after the second of them. The cover can belong to a later shape of any colour. Running stitches are the main trigger, because their cover is an almost-zero-width sliver. About 3% of random 2-4 same-colour running-stitch layouts failed in my fuzz, and about 0.5% of mixed layouts. The user sees a raw GEOS error and the shape they just drew is not added. Export is blocked until they find and untick 'Fewer jumps & trims' (Ctrl+Alt+T).

**What should happen:** A valid design always renders. If a cover can't be built or is invalid, that one move falls back to a normal jump/trim, as it does with the feature off.

**Repro:**

```
import sys; sys.path.insert(0, r"C:\Users\Copper Felix\HTML Stuffs\threadline\engine")
from threadline_engine import layout
Y = {"color": "#f1c40f", "name": "y", "catalog": "", "brand": ""}
def run(id, nodes, tr=None):
    return {"id": id, "kind": "run", "thread": Y, "threads": [], "ops": [], "transform": tr or {},
            "geometry": {"nodes": [[x, y, "s"] for x, y in nodes], "closed": False},
            "params": {"style": "single", "stitch_mm": 7.06}}
tr = {"x": -21.53, "y": -6.47, "rotate": 363.7, "scale_x": 0.6286, "scale_y": 0.6286, "flip_x": True, "flip_y": False}
dot = run("a", [(0, 0), (3, 0)])
bad = run("b", [(1.912, 1.553), (-1.575, 6.743), (-8.657, 17.875), (-18.096, 24.422), (-6.892, 23.839)], tr)
for tu in (False, True):
    try:
        layout.render({"items": [dot, bad], "travel_under": tu}); print("travel_under", tu, "ok")
    except Exception as e:
        print("travel_under", tu, "->", type(e).__name__, str(e)[:90])
# diagnose: the cover is invalid even though the stitched area is valid
from shapely.validation import explain_validity
cap = {}; orig = layout._join_same_thread_objects
layout._join_same_thread_objects = lambda b, t=False: (cap.setdefault("b", b), orig(b, t))[1]
layout.render({"items": [dot, bad], "travel_under": False})
a = layout._stitched_area([cap["b"][1]]); c = layout._cover(cap["b"][1])
print("area valid:", a.is_valid, "| cover:", c.geom_type, explain_validity(c))
# observed (shapely 2.2.0, GEOS 3.14.1):
# travel_under False ok
# travel_under True -> GEOSException TopologyException: side location conflict at -32.473362279275896 4.3521099574736
# area valid: True | cover: MultiPolygon Self-intersection[-32.4733622792759 4.35210995747367]
```

**Observed:** [reproduce/confirmed/ran] 1) The reviewer's snippet, run unchanged from engine/ with `uv run --frozen --no-sync python`: 'travel_under False ok' and 'travel_under True -> GEOSException TopologyException: side location conflict at -32.473362279275896 4.3521099574736732...'. Shapely 2.2.0 with GEOS 3.14.1. 2) Root cause (diagnosed by capturing the blocks): for the second object (the run), `_stitched_area` returns a valid Polygon, but `layout._cover(block)` (`area.buffer(-0.3)`, layout.py:533) returns a MultiPolygon that is NOT valid: 'Self-intersection[-32.4733622792759 4.35210995747367]'. One part has is_valid False (area 0.004 mm2). `unary_union([cover])` then raises the same ...

**Suggested fix:** In `_cover` return `make_valid(c)` (or `c.buffer(0)`) when `not c.is_valid`, dropping empty and zero-length parts. In `_join_same_thread_objects` wrap `unary_union(later)` in try/except GEOSException (and skip any cover that is still invalid), setting hidden=None so the move becomes an ordinary jump/trim. I tried make_valid in `_cover` by monkeypatching: 0 failures in 1200 fuzz layouts, down from 17. Also add a regression test using a thin running-stitch pair; the existing tests use only square fills. Consider also skipping covers for 'run' objects, since their cover is essentially empty.

**Caveats:** The reviewer's diagnosis holds, with these corrections. (a) The root cause is `_cover`'s `buffer(-0.3)` (layout.py:533), not `_stitched_area` (311-327): the stitched area is valid and only the extra shrink makes it invalid. (b) The applique is not required: two same-colour running stitches reproduce it. (c) The conditions are narrower than 'any valid design'. The design needs a consecutive same-colour pair of drawn objects, and the invalid cover has to be at or after the second of the pair, ...

### C3 · High · Confirmed: Fewer jumps & trims (on by default for new designs) makes every render, check and export preview take seconds

**Where:** `engine/threadline_engine/layout.py:536-547`, `engine/threadline_engine/layout.py:530-533`, `engine/threadline_engine/layout.py:311-327`, `engine/threadline_engine/layout.py:696`  
**Found by:** layout-ops  
**Status:** Confirmed (a second agent reproduced it)

**What happens:** With travel_under on (the default for every new design), render() builds a shapely cover for every digitized block (_stitched_area: a buffer per line, a union, then buffer(-0.5), then buffer(-0.3)), whether or not any same-thread join exists. For each join it also unions every later cover again. Nothing is cached. Measured here: Banner render 0.02 s off versus 3.96 s on, and check 1.64 s versus 5.39 s. One 80x80 mm fill with nothing to join: 0.01 s versus 2.07 s. 100 small same-thread squares: 0.39 s versus 8.78 s. layout.render, layout.check and layout.preview_export run serially on the engine's main loop, so a check started after an edit holds up the next edit's render (check answered at 6.4 s and the next render at 10.2 s in the simulation). The UI awaits layout.render before it shows or records an edit, so every edit lags by seconds. In the five shipped samples the flag changes no ...

**What should happen:** Turning on a feature that only hides a move when the straight path is already under later stitching should cost milliseconds when nothing can be hidden, and never seconds per edit. It should not scale worse than linearly with the number of same-thread objects.

**Repro:**

```
import sys, time; sys.path.insert(0, r"C:\Users\Copper Felix\HTML Stuffs\threadline\engine")
from threadline_engine import layout as L, project
def timed(fn, *a):
    t = time.time(); fn(*a); return time.time() - t
lay = project.open_project(r"C:\Users\Copper Felix\HTML Stuffs\threadline\samples\Banner (two hoopings).ludd")["layout"]
for tu in (False, True):
    l = dict(lay, travel_under=tu); L.render(l)
    print(f"Banner travel_under={tu}: render {timed(L.render, l):.2f}s check {timed(L.check, l):.2f}s")
I = {"x":0,"y":0,"rotate":0,"scale_x":1,"scale_y":1,"flip_x":False,"flip_y":False}
def sq(i, x, y, s):
    return {"id":f"f{i}","kind":"fill","geometry":{"outline":[[x,y,"c"],[x+s,y,"c"],[x+s,y+s,"c"],[x,y+s,"c"]]},
            "params":{},"thread":{"color":"#cc2222","name":"Red"},"transform":I,"threads":[],"ops":[]}
for tu in (False, True):   # a single block: nothing to join at all
    l = {"items":[sq(0,0,0,80)], "travel_under": tu}; L.render(l)
    print(f"one 80x80 fill travel_under={tu}: render {timed(L.render, l):.2f}s")
items = [sq(i, (i % 10) * 12, (i // 10) * 12, 8) for i in range(100)]
for tu in (False, True):
    print(f"100 same-thread squares travel_under={tu}: render {timed(L.render, {'items': items, 'travel_under': tu}):.2f}s")
# Run from engine/:  uv run --frozen --no-sync python repro.py
# Observed (machine under load): Banner False 0.02s/1.64s, True 3.96s/5.39s; 80x80 fill False 0.01s, True 2.07s; 100 squares False 0.39s, True 8.78s
```

**Observed:** [reproduce/confirmed/ran] Re-ran the reviewer's repro and extra probes in scratch (nothing touched in the repo). Timings below were taken while other reviewers were running on the same machine, so absolute numbers may be pessimistic by up to about 2x, but the ratios are 50x to 400x. 1) Banner sample (5 shapes), render / check: travel_under=False render 0.02 s check 1.64 s travel_under=True render 3.96 s check 5.39 s 2) One fill, nothing to join (a single block): 40x40 mm: 0.00 s off, 0.56 s on 80x80 mm: 0.01 s off, 2.07 s on 3) Profile of Banner render with the flag on: 4.22 s total. 4.19 s is _join_same_thread_objects, of which 4.18 s is _cover (5 calls, one per digitized block) and 4.03 s ...

**Suggested fix:** In _join_same_thread_objects, skip all cover work unless at least one adjacent same-thread digitized pair exists. Compute covers lazily, only for blocks at or after the first joinable pair, and build the "later" union once as a running suffix union walked from the end instead of calling unary_union(covers[i:]) per join. Cache each block's cover by a hash of its stitches, as _generate_cached does. Make _stitched_area cheaper for this use (union the simplified lines first, use a larger simplify tolerance and quad_segs=1, or derive the cover from the object geometry) because the buffer calls ...

**Caveats:** Reproduced fully; the reviewer's numbers match mine within load noise (Banner on: they saw 4.8-5.8 s, I saw 4.0-4.2 s; 80x80 fill: 2.7-3.4 s versus my 2.1 s). Narrowness and caveats: - This is a performance problem only. Stitch output is identical with the flag on or off in all five samples and in the square tests, so no stitch-out is spoiled. High is justified because it hits the default path for every new design and makes each edit lag by seconds. It is not Critical. I would not go below ...

### C4 · High · Confirmed: Deleting every stitch of a colour leaves an empty colour block in the output. Emptying the FIRST colour shifts the PES/JEF thread table by one, so every later colour is labelled with the wrong thread

**Where:** `engine/threadline_engine/layout.py:647`, `engine/threadline_engine/layout.py:664`, `engine/threadline_engine/layout.py:693`, `engine/threadline_engine/layout.py:160-174`  
**Found by:** layout-ops  
**Status:** Confirmed (a second agent reproduced it)

**What happens:** delete_stitches removes only STITCH records. render() keeps any block that still has a JUMP/TRIM, so an emptied colour stays in the sewing order as "C T J". Summary reports colors N-1 but color_changes N and N+1 threads. The PES gets an extra colour-change prompt, plus a writer-inserted stray stitch if the empty block is in the middle. A trailing empty block gives a final change that sews nothing. When the first colour is emptied, the stream starts with a leading C that the PES/JEF writers drop while keeping the deleted thread, so the thread table is shifted: the blue stitches are labelled red and the last colour is missing. Deleting every stitch still exports without a warning (PES writes a 0-stitch file; a single-colour JEF fails with "list index out of range").

**What should happen:** A colour with no stitches disappears from the sewing order, the threads list and the exported file (as delete_block already does). color_changes = colors - 1. Thread table entry k is the colour of stitch block k. Exporting a design with no stitches is refused with a clear message.

**Repro:**

```
import sys, os, tempfile
import pyembroidery as pe
from threadline_engine import layout as L   # run via: cd engine && uv run --frozen --no-sync python this.py

p = pe.EmbPattern()
for n, c in (("Red","#ff0000"),("Blue","#0000ff"),("Green","#00ff00")): p.add_thread(pe.EmbThread(c, n, "1", brand="T"))
for blk in range(3):
    if blk: p.color_change()
    p.move_abs(0, blk*100)
    for x in range(0, 201, 25): p.stitch_abs(x, blk*100)
p.end()
d = tempfile.mkdtemp(); f = os.path.join(d, "three.pes"); pe.write(p, f, {"version": 6})
N = {pe.STITCH:"S", pe.JUMP:"J", pe.TRIM:"T", pe.COLOR_CHANGE:"C", pe.END:"E"}
seq = lambda b: "".join(N.get(c & 0xFF, "?") for *_, c in b.stitches)

def run(label, idx):
    lay = {"items": [{"id": "a", "path": f, "ops": [{"op": "delete_stitches", "indices": idx}]}]}
    s = L.render_summary(lay)
    out = os.path.join(d, label + ".pes"); L.export(lay, out, {"machine": "brother-pe550d"})
    b = pe.read(out)
    print(label, "| summary colors", s["info"]["colors"], "color_changes", s["info"]["color_changes"],
          "threads", len(s["threads"]), "| PES", [t.hex_color() for t in b.threadlist], seq(b))

run("middle", list(range(13, 22)))   # all stitches of Blue
run("first", list(range(1, 10)))     # all stitches of Red
run("all", list(range(0, 40)))       # everything

# observed:
# middle | summary colors 2 color_changes 2 threads 3 | PES ['#ff0000','#0000ff','#00ff00'] JSSSSSSSSSCTJSCTJSSSSSSSSSE
# first  | summary colors 2 color_changes 2 threads 3 | PES ['#ff0000','#0000ff'] JTJSSSSSSSSSCTJSSSSSSSSSE
#          (Blue and Green stitches, but the table says Red then Blue: shifted by one, Green missing)
# all    | summary colors 0 color_changes 2 threads 3 | PES 2 threads  JTJSCTJE  (0 stitches, no warning)
```

**Observed:** [reproduce/confirmed/ran] All run from engine/ with `uv run --frozen --no-sync python <script>`. Scratch scripts are in .../scratchpad/v_delete/. 1. The reviewer's repro reproduces exactly, on a synthetic 3-colour PES (S=stitch, J=jump, T=trim, C=colour change) with the middle colour's stitches deleted: summary: colors 2 color_changes 2 threads listed 3 PES: 3 threads; JSSSSSSSSSCTJSCTJSSSSSSSSSE The layout record stream before the writer is JSSSSSSSSSCTJCTJSSSSSSSSSE: blue is an empty "C T J" block. The lone S in the PES is added by pyembroidery's PES writer at the jump target (0,100), not by LUDD. `delete_block` on the same block gives colors 2, color_changes 1, 2 threads, so the ...

**Suggested fix:** In render(), drop blocks with no STITCH record once, right after the per-item loop (or at lines 647, 664, 693): `all_blocks = [b for b in all_blocks if any(r[2] == pe.STITCH for r in b.recs)]`. That removes the empty colour changes and the shifted-thread-table case (verified in a scratch copy: 132 related tests still pass). Also strip JUMP/TRIM records left orphaned at a block's start or end in _apply_ops. Make export()/preview_export() raise LayoutError("There are no stitches to save") when the rendered pattern has no STITCH.

**Caveats:** I agree with the reviewer's core finding and fix, but I raise severity from Medium to High. Mid-design and last-colour deletions are Medium: an extra thread-change prompt and one stray stitch. The reviewer missed the first-colour case, which silently mislabels every thread in the PES/JEF, so the machine's thread chart disagrees with LUDD's preview. That is verified on Key.PES and Heart.thin.PES (names and counts only). Narrowness: it needs stitch-edit mode on a placed stitch file, with every ...

### C5 · High · Confirmed: Split assigns whole runs to the earlier hooping, so a top layer straddling the seam is stitched over by the later hooping's base

**Where:** `engine/threadline_engine/split.py:196-207 (plan: whole-run assignment ignores layer order against runs in other hoopings)`, `engine/threadline_engine/split.py:231-236 (section_pattern: block order is only enforced inside one hooping)`, `engine/threadline_engine/split.py:8-9 and 20-21 (docstring: 'in the design's colour order' implies an order that is not kept across files)`, `engine/tests/test_m8.py:104-130 (existing split test checks coverage and marks only, no layer-order assertion)`  
**Found by:** layout-order  
**Status:** Confirmed (a second agent reproduced it)

**What happens:** A run that fits any window goes whole to one hooping, even when a lower-layer run it overlaps was assigned to a later hooping. The later hooping then sews the base over the earlier hooping's top layer. This needs no cut run: in Case B2 both the base and the top are whole runs and the base still buries the top. The affected area is the band where the two hooping windows overlap, about 23 mm wide in the example and wider for designs only slightly bigger than the hoop.

**What should happen:** Layer order is preserved across hoopings: nothing sewn in a later hooping may cover a higher layer sewn in an earlier one. Equivalently, for any two overlapping runs A (lower block) and B (higher block), A's hooping index must be at or before B's. Runs that would violate this need to be cut at the seam so each hooping sews only its own side.

**Repro:**

```
import sys; sys.path.insert(0, ".")   # run from engine/: uv run --frozen --no-sync python repro.py
from threadline_engine import layout, split
def sq(a,b,c,d): return [[a,b,"c"],[c,b,"c"],[c,d,"c"],[a,d,"c"]]
def fill(i, ol, col): return {"id": i, "kind": "fill", "name": i, "geometry": {"outline": ol}, "params": {}, "thread": {"color": col, "name": col}}
# Variant B2: no run is cut. Red base (bottom layer) fits hooping 2 only, blue top fits hooping 1 only.
lay = {"items": [fill("dotL", sq(0,0,4,4), "#00ff00"), fill("dotR", sq(146,0,150,4), "#00ff00"),
                 fill("base", sq(64,10,145,50), "#ff0000"), fill("top", sq(60,20,80,40), "#0000ff")]}
blocks, sections, grid, bounds = split.plan(layout.render(lay).pattern, 100, 100, 10)
for s in sections:
    print("hooping", s.index+1, [(blocks[bi][0]["color"], "cut" if c else "whole") for bi, _, c in s.runs if blocks[bi][0]["color"] in ("#ff0000","#0000ff")][:3])
n = sum(1 for bi, run, cut in sections[1].runs if blocks[bi][0]["color"].lower()=="#ff0000" for x,y in run if 64<=x<=80 and 20<=y<=40)
print("red stitches in hooping 2 over blue patch:", n)
# actual: hooping 1 [('#0000ff','whole')]; hooping 2 [('#ff0000','whole')]; 294
# Reviewer's original (base 0..150, top 66..80 straddling the seam) prints 126 with the same check (x 75..80).
```

**Observed:** [reproduce/confirmed/ran] split.py is unmodified in the working tree (git status is clean for it, last change was the 1.0.0 commit). I ran the reviewer's repro from engine/ with `uv run --frozen --no-sync python`. It printed `grid (2, 1)`, hooping 1 colours ['#0000ff','#ff0000'], hooping 2 colours ['#ff0000'], and `red stitches sewn in hooping 2 over the blue patch: 126`. So the claim reproduces as stated. I then went through the real export path (`layout.export_split` to .pes, read back with pyembroidery, mapped to design coordinates). Stitches landing inside the blue patch rectangle, in sew order: - Case A (reviewer's, patch x 66..80): file 1 gives red 284 then blue 299. File 2 gives red ...

**Suggested fix:** In plan(), after the first assignment, detect any run assigned whole to hooping h that overlaps (bounding box, then real geometry if needed) a lower-block run assigned to a hooping later than h. Cut that run with `_cut`, or simply cut every run at cell seams, so the part in the later cell is sewn in the later hooping after the base. Keep per-hooping colour-block ordering. Add a test that, for the design in the repro, no lower-block stitch in a later hooping falls inside a higher-block run's footprint. Also reword the docstring item 4.

**Caveats:** Severity: I kept High. The defect is silent and real, because top layers in the window-overlap band get partly or fully buried, and any layered design that crosses a seam can hit it (lettering over a big background, for example). That can ruin a stitch-out, but it only affects objects in the overlap band, and the other parts of the split output are correct. It would be Critical for a design whose focal object sits on the seam. The reviewer's description is accurate but narrower than the real ...

### C6 · High · Confirmed: Sort colors defeats 'Fewer jumps & trims': the travel is hidden under a cover that is then sewn first, leaving bare travel stitches on top

**Where:** `engine/threadline_engine/layout.py:696-702 (travel_under join runs before _color_sort reorders)`, `engine/threadline_engine/layout.py:536-551 (_join_same_thread_objects takes covers[i:] from the pre-sort order, line 546)`, `engine/threadline_engine/layout.py:265-281 and 245-252 (_color_sort joins with _join, which returns a Block without digitized=True and adds a TRIM with no hidden check)`, `apps/desktop/src/actions.ts:219 (travel_under is on for every new design, so the combination is easy to reach)`  
**Found by:** docs-c, export, layout-ops, layout-order (also reported as layout-ops#1, export#2, docs-c#2)  
**Status:** Confirmed (a second agent reproduced it)

**What happens:** With Fewer jumps & trims on (the default for new designs) and Sort colors on, a same-thread move that was judged to be "covered later" is turned into a row of 2.5 mm running stitches. The sort then moves the covering block of another thread ahead of it. The final PES has 8 plain STITCH records lying across the finished blue field, with no TRIM or JUMP. The Brother PE550D only cuts at colour changes, so the owner gets a visible line of red running stitches across a blue area and can only fix it by unpicking.

**What should happen:** Hidden-travel decisions should be made on the final sewing order. After the sort the red block has no cover sewn after it, so the move should fall back to the normal TRIM+JUMP (or short jump), as it does with travel_under off. The manual says the travel is "covered by stitching sewn later".

**Repro:**

```
import sys; sys.path.insert(0, ".")   # run from engine/
import pyembroidery as pe
from threadline_engine import layout
def sq(a,b,c,d): return [[a,b,"c"],[c,b,"c"],[c,d,"c"],[a,d,"c"]]
def sqf(i,x,y,s,col): return {"id":i,"kind":"fill","name":i,"geometry":{"outline":sq(x,y,x+s,y+s)},"params":{},"thread":{"color":col,"name":col}}
B, R = "#0000ff", "#ff0000"
def run(ts, cs):
    lay = {"travel_under": ts, "color_sort": cs, "items": [sqf("x",-30,-30,5,B), sqf("a",0,0,6,R), sqf("b",30,0,6,R), sqf("c",-2,-2,40,B)]}
    r = layout.render(lay)
    red = next(b for b in r.blocks if b.thread["color"] == R)
    print(ts, cs, [b.thread["color"] for b in r.blocks],
          "gap stitches:", len([p for p in red.recs if p[2]==pe.STITCH and 8 < p[0]/10 < 28]),
          "trims/jumps:", sum(1 for p in red.recs if p[2] in (pe.TRIM, pe.JUMP)))
run(True, True)    # BUG: ['#0000ff','#ff0000'] gap stitches: 8 trims/jumps: 0   (blue sewn first, travel on top)
run(True, False)   # ok: blue,red,blue; 8; 0  (blue c covers the travel)
run(False, True)   # ok: blue,red; 0; 2       (trim + jump)
```

**Observed:** [reproduce/confirmed/ran] Ran the reviewer's repro unchanged from engine/ (uv run --frozen --no-sync python). Output for travel_under + color_sort: ['#0000ff', '#ff0000'] (blue first, red second) red travel stitches in the gap: 8 trims/jumps: 0 Control runs, same design: travel_under=True, color_sort=False -> order [blue, red, blue], 8 gap stitches, 0 trims/jumps. Correct: the last blue square c is sewn after red and covers the travel. travel_under=False, color_sort=True -> order [blue, red], 0 gap stitches, 2 trims/jumps. Correct: the move is trimmed and jumped. travel_under=True, merge_colors=True (no sort) -> same as the unsorted case (merge never reorders, so it is not affected). Wrote ...

**Suggested fix:** Split _color_sort into two steps. First do a stable reorder by thread (first-appearance order) with no joining. Then run _join_same_thread_objects on the reordered list, so covers[i:] means "sewn later in the final order". Let the existing _join / _merge_same handle only non-digitized (stitch-file) blocks afterwards. Add a regression test (travel_under + color_sort, assert no STITCH records across the gap and a TRIM/JUMP present). The simpler option is to skip travel_under whenever color_sort is on. The reviewer's wording "run _color_sort before _join_same_thread_objects" would not work as ...

**Caveats:** Narrower than a general travel_under failure. Both options must be on: Sort colors is off by default, and travel_under is on for new designs. The order must also change so that a covering thread ends up before the thread whose move it hides. That happens when the covering thread's first appearance is earlier than the traveller's (here the small blue x is first, so blue is sewn first). If the covering thread first appears after the traveller, the sort keeps the cover later and the output is ...

### C7 · High · Confirmed: A project with lettering in a font that isn't installed cannot be rendered or opened at all

**Where:** `engine/threadline_engine/lettering.py:123-134 (resolve_font raises)`, `engine/threadline_engine/lettering.py:396 (layout_text calls resolve_font)`, `engine/threadline_engine/layout.py:459-469 (_text_block turns it into LayoutError; layout.py:634 caller aborts whole render)`, `apps/desktop/src/actions.ts:166-189 (showHistory returns false, nothing applied)`  
**Found by:** lettering  
**Status:** Confirmed (a second agent reproduced it)

**What happens:** A project containing lettering in a font that isn't installed (its file path is gone and no installed font has the same family) cannot be opened. project.open succeeds in the engine, but the first layout.render raises LayoutError for the whole layout. In the UI, showHistory returns false, replaceDoc/openProject do not load the document, and the user gets only an error toast ("...choose another") with no document and no Font picker. Any other item in the same project is blocked too. The same applies to a missing .luddfont stitch font. Fonts are never embedded in the .ludd, unlike stitch files and pictures.

**What should happen:** The project opens. The text item uses a substitute (the default everyday font) and shows a clear warning such as "Font Fancy Script isn't installed, showing Arial", so the user can pick another font. Other items render normally. Better still, embed the stitch fonts (small JSON), and ideally the glyph outlines or font files used, in the .ludd as is done for pictures and stitch files, so that "opening the project on another PC can't lose them" (project.py docstring) holds for fonts too.

**Repro:**

```
cd engine; uv run --frozen --no-sync python repro.py

from threadline_engine import layout
F = lambda p, fam: {'path': p, 'index': 0, 'family': fam, 'style': 'Regular'}
def text(i, f, y): return {'id': i, 'kind': 'text', 'text': 'Hello', 'font': f, 'size_mm': 12, 'spacing_mm': 0, 'style': 'satin',
  'shape': {'type': 'line'}, 'monogram': False, 'thread': {'color': '#cc0000', 'name': 'Red'}, 'transform': {'y': y}, 'threads': [], 'ops': []}
missing = F('C:/Users/someone/AppData/Local/Microsoft/Windows/Fonts/Fancy.ttf', 'Fancy Script')
cfg = {'merge_colors': False, 'color_sort': False, 'basting': {'enabled': False}}
layout.render({'items': [text('b', F('C:/Windows/Fonts/arial.ttf', 'Arial'), 40)], **cfg})   # OK
layout.render({'items': [text('a', missing, 0), text('b', F('C:/Windows/Fonts/arial.ttf', 'Arial'), 40)], **cfg})

Actual (run): LayoutError: Text: The font Fancy Script isn't installed on this computer; choose another
(the first call succeeds; the second fails and item 'b' is not rendered either).
Whole-flow variant: methods.project_save(path, {'layout': lay, 'images': []}) -> zip contains only project.json; methods.project_open(path) succeeds; methods.layout_render(opened['layout']) raises the same LayoutError.
```

**Observed:** [reproduce/confirmed/ran] 1) Reviewer's repro, run from engine/ with `uv run --frozen --no-sync python repro.py`. The good arial-only layout renders fine ("good only OK: Rendered"). Adding the item with a missing font gives: `LayoutError Text: The font Fancy Script isn't installed on this computer; choose another`. The good item 'b' is not rendered either, so the whole layout fails. 2) Engine end-to-end (THREADLINE_DATA_DIR pointed at scratch): project.save with a text item whose font path and family are not installed. The zip holds only `['project.json']`, so no font is embedded. project.open then returns the project fine ("project.open OK, items: 2"). layout.render on that layout raises ...

**Suggested fix:** In layout._text_block (and/or lettering.layout_text), catch the font-not-found case, fall back to a default installed text font (first of list_fonts() with kind outline, or Arial), and add a warning on the item instead of raising LayoutError. Show that warning in the Text panel. Longer term, embed .luddfont files in the project zip and extract them to the cache on open, as is done for designs.

**Caveats:** Reproduced as filed; I agree with High. Reasons it is not Critical: no data is destroyed in the normal open case (installing the font, or copying the .luddfont back, makes the project open again), and the same-family fallback already covers the common case of a font reinstalled in a different folder. Narrowness: it needs the font family to be absent altogether. Realistic triggers are moving a .ludd to another PC, uninstalling a font, deleting a user stitch font from the data fonts folder, or ...

### C8 · High · Confirmed: Applique silently drops holes: stitches and SVG cut file treat the piece as solid, although the UI offers "Add a hole (O)" and keeps holes on convert

**Where:** `engine/threadline_engine/digitize/stitches.py:686-690`, `engine/threadline_engine/digitize/applique.py:64-77,107-135,138-140`, `engine/threadline_engine/layout.py:360-390 (373 reads only geometry.outline)`, `apps/desktop/src/components/InfoPanel.tsx:599`  
**Found by:** patterns  
**Status:** Confirmed (a second agent reproduced it)

**What happens:** An applique that has a hole sews exactly the same stitches as one without. The placement line, tack-down and satin cover go round the outer outline only. The SVG cut file has one path, so a cutting machine cuts a solid patch. Nothing is placed, tacked or covered around the hole's edge, and no warning is shown. The same happens when a fill with holes is converted to an applique, for example a lettering letter such as O or an Auto-trace ring.

**What should happen:** Either the hole gets its own placement, tack and satin edge and its own path in the cut file, or the UI does not offer holes on applique and convertObject drops them (or warns) when a fill with holes becomes an applique.

**Repro:**

```
cd engine; uv run --frozen --no-sync python snippet.py
from threadline_engine.digitize.stitches import generate
from threadline_engine import layout as L
n = lambda pts: [[x, y, 'c'] for x, y in pts]
sq = n([(0,0),(40,0),(40,40),(0,40)]); hole = n([(15,15),(25,15),(25,25),(15,25)])
a,_ = generate({'kind':'applique','geometry':{'outline':sq},'params':{}})
b,_ = generate({'kind':'applique','geometry':{'outline':sq,'holes':[hole]},'params':{}})
print('identical with and without hole:', a == b)          # True (1361 == 1361 records)
f1,_ = generate({'kind':'fill','geometry':{'outline':sq,'holes':[hole]},'params':{}})
f0,_ = generate({'kind':'fill','geometry':{'outline':sq},'params':{}})
print('a fill honours the hole:', f1 != f0)                # True
svg,_ = L.applique_svg({'items':[{'id':'a','kind':'applique','geometry':{'outline':sq,'holes':[hole]},'params':{}}]})
print('cut-file paths:', svg.count('<path'))              # 1 (hole missing)
import pyembroidery as pe
print('stitches inside hole:', len([1 for x,y,k in b if k==pe.STITCH and 14<x<26 and 14<y<26]))  # 0
# Output seen: True / True / 1 / 0
```

**Observed:** [reproduce/confirmed/ran] Ran the reviewer's snippet from engine/ with `uv run --frozen --no-sync python`. Output: - identical with and without hole: True (1361 stitch records each) - a fill honours the hole: True (fill 1813 records without the hole, 1823 with it) - cut-file paths: 1 Extra checks I added: - Applique stitch points inside the hole's bounding region (14<x<26, 14<y<26): 0. The inner edge is never placed, tacked or covered. - Whole render path: layout.render_summary of a 40x40 applique gives stitches 1357, stops 2, jumps 2 both without and with a 10x10 hole. The hole is dropped in the real export path too, not only in generate(). Code read in the working tree: - ...

**Suggested fix:** Preferred: build the applique polygon with fill_polygon(outline, holes). Run outline_ring plus the placement, tack and cover sections for each interior ring (offset the rails the other way for holes), and make cut_path/applique_svg emit one path per ring. Cheaper: hide Add a hole (O) for applique, drop holes in convertObject when `to === "applique"`, and add a warning to generate() if an applique arrives with holes.

**Caveats:** Reproduces exactly as filed; the severity stays High under the project definitions (a feature is broken or misleading), with these limits: - Narrow: only applique pieces that actually have a hole. Solid applique is correct. There is no crash and no stray thread. The outer edge sews properly, so the stitch-out is not ruined. The cost is one wasted fabric piece or stitch-out, and a user who cuts the hole by hand ends up with a raw, unsewn inner edge. - Misleading UX: the hole is drawn on screen ...

### C9 · High · Confirmed: Saving any project deletes a crash-recovery copy that is still waiting for Recover or Discard

**Where:** `apps/desktop/src/actions.ts:341`, `apps/desktop/src/actions.ts:356-358`, `apps/desktop/src/actions.ts:1614-1615`, `apps/desktop/src/App.tsx:214-231`  
**Found by:** project  
**Status:** Confirmed (a second agent reproduced it)

**What happens:** After a crash and relaunch, with the 'LUDD closed without saving your work... Get it back?' banner left unanswered, any successful Save or Save As (of a project opened or started in the meantime) calls project.discard_recovery. This unlinks the crash copy while the banner stays on screen. Clicking Recover afterwards shows the error 'There's nothing to recover'. The crashed session's unsaved work is lost for good, with no warning.

**What should happen:** While recoveryWaiting is true, nothing may delete or overwrite the pending crash copy (per the comment at actions.ts:356 and the changelog at docs/CHANGELOG.md:105). Save should write the user's project and leave the recovery file alone until the user clicks Recover or Discard.

**Repro:**

```
// Temporary vitest in apps/desktop/src (mocks: @tauri-apps/plugin-dialog {save: async () => "C:/x/other.ludd"}, @tauri-apps/api/path).
// Fake engine: holds one recovery record; project.discard_recovery clears it; project.restore throws "There's nothing to recover" when it is gone.
it("save must not delete a recovery that is still waiting", async () => {
  await actions.checkRecovery();                       // banner up, recoveryWaiting = true
  useStore.setState({ history: { past: [], present: newDoc(), future: [] }, savedDoc: null }); // user opens/starts something else
  await actions.saveProject(true);                     // Ctrl+Shift+S
  expect(f.calls).not.toContain("project.discard_recovery");
});
it("Recover after that Save", async () => {
  await actions.checkRecovery();
  useStore.setState({ history: { past: [], present: newDoc(), future: [] }, savedDoc: null });
  await actions.saveProject(true);
  await actions.restoreRecovery();                     // click Recover on the still-visible banner
  expect(useStore.getState().notice?.kind).not.toBe("error");
});
// Output seen:
// CALLS ["project.recovery","project.save","project.discard_recovery"] waiting= true
// AssertionError: expected [ 'project.recovery', ...(2) ] to not include 'project.discard_recovery'
// NOTICE {"kind":"error","text":"There's nothing to recover"} waiting= true
// Real-engine check: project.autosave(...) -> project.recovery() shows it; project.discard_recovery() -> recovery() is None; project.restore() raises ProjectError: There's nothing to recover
```

**Observed:** [reproduce/confirmed/ran] Code read (current working tree): apps/desktop/src/actions.ts:341 `if (!isDirty(useStore.getState())) void engine().call("project.discard_recovery").catch(() => {});` has no isRecoveryWaiting() guard. Every other discard is guarded: startAutosave line 366 returns early on `recoveryWaiting` before the clean-state discard at 368; App.tsx:179 only discards on close when `!isRecoveryWaiting()`; the only unguarded callers are the user's own Discard click (App.tsx:228) and saveProject. Save is enabled whenever an engine and a document exist (actions.ts:1614, not tied to dirty), and RecoveryPrompt is non-modal and only cleared by its own buttons (App.tsx:357), so the ...

**Suggested fix:** In saveProject (actions.ts:341) only call project.discard_recovery when !isRecoveryWaiting(), i.e. `if (!recoveryWaiting && !isDirty(...)) ...`. Better: while a recovery is pending, autosave to a second slot (or have the engine refuse to unlink the file until Recover or Discard), so the new session is also protected, which also addresses H2 in docs/QA-REPORT-2026-10-11.md. Add a unit test like the one above to the UI suite.

**Caveats:** Reviewer's finding holds as written; the locations and repro are right. Calibration: I kept High rather than Critical. The lost data is a crash-recovery copy, and it takes a crash, then ignoring the banner, then a Save in the new session. But it is silent data loss on a feature advertised as safe, and the still-visible Recover button then errors, which is misleading. Critical could be argued, since the definition includes 'loses user work'. The trigger is easy to hit: Save is enabled even for ...

### C10 · High · Confirmed: Stitch Advisor crashes on any design that contains a satin ribbon

**Where:** `engine/threadline_engine/ai/advisor.py:52-61 (_ring ignores ribbon geometry)`, `engine/threadline_engine/ai/advisor.py:65-91 (summarize; line 76 reads rail_a/rail_b)`, `engine/threadline_engine/ai/advisor.py:128-147 (render_crop; max() of an empty ring)`, `engine/threadline_engine/ai/advisor.py:150-165 (build_request; objs[:MAX_OBJECTS] then summarize/render_crop)`  
**Found by:** docs-b, satin (also reported as docs-b#1)  
**Status:** Confirmed (a second agent reproduced it)

**What happens:** With the AI add-on on, clicking the Stitch Advisor (button, menu or Ctrl+Shift+I) fails with the raw error "max() iterable argument is empty" in two cases. One is when the satin ribbon is the selected shape. The other is when nothing is selected and a ribbon is among the first 12 drawn shapes (MAX_OBJECTS slices before summarising). So a design that contains a ribbon cannot be advised on as a whole, and a ribbon cannot be advised on by itself. Fills and lines alone work. After the engine is fixed, proposals that change a ribbon's type, or turn a fill or line into a satin, still show a disabled Accept with 'draw the shape again with the satin tool; it can't be switched over'.

**What should happen:** A ribbon is summarised (column width from width_mm, length from the centre line), drawn in the crop, and proposals to or from satin can be applied the way Stitch as does it.

**Repro:**

```
# cd engine; uv run --frozen --no-sync python repro.py
from threadline_engine.ai import advisor
c = lambda x, y: [x, y, 'c']
layout = {'fabric': 'woven', 'items': [
  {'id': 'f1', 'kind': 'fill', 'geometry': {'outline': [c(0,0), c(20,0), c(20,20), c(0,20)]}, 'params': {}},
  {'id': 'r1', 'kind': 'satin', 'geometry': {'nodes': [c(0,0), c(30,0)], 'width_mm': 3}, 'params': {}}]}
for ids in (None, ['f1'], ['r1']):
    try: advisor.build_request(layout, [], ids); print(ids, 'OK')
    except Exception as e: print(ids, 'FAILS:', type(e).__name__, e)
# actual output:
# None FAILS: ValueError max() iterable argument is empty
# ['f1'] OK
# ['r1'] FAILS: ValueError max() iterable argument is empty
# Through the dispatcher (provider stubbed) both ai.advisor_preview and ai.advise return
# {'error': {'code': -32603, 'message': 'max() iterable argument is empty'}}
```

**Observed:** [reproduce/confirmed/ran] 1) Reviewer's repro, run from engine/ with `uv run --frozen --no-sync python repro.py`: None FAILS: ValueError max() iterable argument is empty ['f1'] OK ['r1'] FAILS: ValueError max() iterable argument is empty An open 2-point ribbon (nodes [0,0]-[30,0], width_mm 3, no `closed`) fails the same way, so it is not specific to closed ribbons. 2) Through the real RPC dispatcher (methods.dispatcher.handle_line), with providers.require stubbed so no network or key is needed. Both methods the UI calls return an error, and ai.advisor_preview fails first, so the user hits it the moment they click the sparkle button, before the "what will be sent" confirmation: ...

**Suggested fix:** In advisor.py add a helper `_pairs(g)` that returns dz.ribbon_pairs(g["nodes"], g["width_mm"], 1.0, bool(g.get("closed"))) when "nodes" is in the geometry, and dz.satin_pairs(rail_a, rail_b, 1.0) otherwise. Build _ring from those pairs (a + b[::-1] + a[:1]), and take column_width_mm and length_mm in summarize from the same pairs. In ai.ts make applicable()/withChange convert a ribbon the way convertObject does (nodes to outline for fill, nodes for run, nodes plus width_mm for satin), and update ai.test.ts:24-28. Add a ribbon case (selected, and mixed with a fill and ids=None) to ...

**Caveats:** Narrower or different from the report: (a) The Advisor is opt-in (AI add-on, off by default; canAdvise needs aiOn('advisor')), so this only bites users who turned it on. It never touches stitch output. High is right because the feature fails on the app's default satin type, but it is not Critical. (b) The report says withChange builds an empty outline for a satin. In practice it does not, because the branch at ai.ts:146 is gated by applicable(), which returns false for any change to or from ...

### C11 · High · Confirmed: Updater manifest (latest.json) is built from draft-release URLs that 404 after publishing

**Where:** `.github/workflows/release.yml:156`, `.github/workflows/release.yml:179`, `.github/workflows/release.yml:25-40`, `apps/desktop/src/updates.ts:42-53`  
**Found by:** packaging, security (also reported as packaging#3)  
**Status:** Confirmed (a second agent reproduced it)

**What happens:** updater-manifest writes `platforms.*.url = a.browser_download_url` from a draft release. For a draft, GitHub reports /releases/download/untagged-<hash>/<file>. After Publish those paths 404 (observed on the identical pattern in the published v1.0.0 manifest). Installed copies read releases/latest/download/latest.json, see version 1.0.1, offer the update, then downloadAndInstall fails with a 404 error. The manifest would be wrong for all five platform keys.

**What should happen:** latest.json urls must be the permanent tag form https://github.com/jvanekel-pixel/ludd/releases/download/v1.0.1/<asset name>, which resolve after Publish (the v1.0.0 tag URLs return 302 as shown).

**Repro:**

```
Offline check of the code (no GitHub needed):
  grep -n "browser_download_url" .github/workflows/release.yml     # line 179
Live proof of the failure mode on the already-published v1.0.0 release (read-only):
  gh api -H "Accept: application/octet-stream" repos/jvanekel-pixel/ludd/releases/assets/632008680 | grep '"url"'
  # every url contains /releases/download/untagged-db359eb759b1d39a26c9/
PowerShell header probe (nothing downloaded):
  foreach ($u in @(
    "https://github.com/jvanekel-pixel/ludd/releases/download/untagged-db359eb759b1d39a26c9/LUDD_1.0.0_x64-setup.exe",
    "https://github.com/jvanekel-pixel/ludd/releases/download/v1.0.0/LUDD_1.0.0_x64-setup.exe")) {
    (Invoke-WebRequest -Uri $u -Method Head -MaximumRedirection 0 -SkipHttpErrorCheck).StatusCode }
  # actual output: 404 then 302
To see it for 1.0.1 before publishing: after the Release run finishes (still a draft), `gh api repos/jvanekel-pixel/ludd/releases --jq '.[0].assets[].browser_download_url'` or open the attached latest.json and look for 'untagged-'.
```

**Observed:** [reproduce/confirmed/ran] 1) Read .github/workflows/release.yml in the working tree (unmodified vs HEAD): updater-manifest lists assets of the DRAFT release (line 156) and writes `url: a.browser_download_url` (line 179). The draft is created at lines 29-38 (draft: true); the manifest job runs before anyone presses Publish. 2) Real precedent in this repo. The live v1.0.0 release (built by the older tauri-action includeUpdaterJson path from the same kind of draft) has a published latest.json. `gh api repos/jvanekel-pixel/ludd/releases` (metadata only) shows v1.0.0 draft:false, tag v1.0.0. `gh api -H "Accept: application/octet-stream" repos/jvanekel-pixel/ludd/releases/assets/632008680` ...

**Suggested fix:** In .github/workflows/release.yml line 179 build the URL from the tag instead of the draft URL: `const url = \`https://github.com/${owner}/${repo}/releases/download/v${version}/${encodeURIComponent(a.name)}\`;` (the tag is `v${version}` per line 32), then `platforms[k] = { url, signature }`. Equivalent: `a.browser_download_url.replace(/\/download\/untagged-[^/]+\//, \`/download/v${version}/\`)`. Add a note to docs/RELEASING.md step 5 to confirm no 'untagged-' appears in latest.json and test the 1.0.0 -> 1.0.1 update once from an installed 1.0.0.

**Caveats:** The reviewer's suspicion is right, and the evidence is stronger than hoped: this repo's own published v1.0.0 latest.json already contains 'untagged-db359eb759b1d39a26c9' URLs (written by tauri-action from the draft) and those URLs 404 today. Remaining narrowness and caveats: (a) the new updater-manifest job has not been run (no v1.0.1 tag yet), so I inferred that listReleaseAssets on a draft returns the same untagged form; it is the same browser_download_url field tauri-action used for v1.0.0, ...

### C12 · High · Confirmed: 'One file per name' export ignores the machine profile: no cut-stops, no hoop check, warnings discarded

**Where:** `apps/desktop/src/features.ts:310-330 (call at :322)`, `apps/desktop/src/components/FeatureDialogs.tsx:188-233`, `apps/desktop/src/actions.ts:1336-1339`, `apps/desktop/src/design/machine.ts:29-34`  
**Found by:** compat, docs-a, docs-b, lettering, security (also reported as compat#2, lettering#2, docs-b#2, docs-a#2)  
**Status:** Confirmed (a second agent reproduced it)

**What happens:** exportNames calls layout.export with options: {}. Options.from_dict({}) gives no machine, no hoop and cut-stops disabled. With a single-colour name like "Emma", every gap between letters is written as TRIM+JUMP with no STOP (3 stray threads for 4 letters). The PE550D only cuts at colour changes, so each gap leaves a thread to snip by hand. Save for machine, with the same design, writes 3 STOPs. No hoop-fit, max-stitch or "trims_ignored" warning is produced, and the report is discarded anyway. A name wider than the 4x4 hoop (for example "Olivia Grace Marie" at 20 mm) is written silently, where Save for machine reports hoop_too_big. The user only sees "Saved N files (one per name)".

**What should happen:** Each name file is prepared exactly as Save for machine would prepare it: the selected machine and hoop, and cut-stops at the machine's recommended default (on for the PE550D when the design has trims). Per-file warnings (hoop too big, long stitches) are shown, or at least a summary such as "2 of 5 names don't fit your hoop".

**Repro:**

```
# engine dir: uv run --frozen --no-sync python t2.py   (run from a scratch dir)
import pyembroidery as pe
from threadline_engine import layout as L
def counts(p):
    c={}
    for x,y,cmd in pe.read(p).stitches:
        k={pe.JUMP:'JUMP',pe.TRIM:'TRIM',pe.STOP:'STOP'}.get(cmd&pe.COMMAND_MASK)
        if k:c[k]=c.get(k,0)+1
    return c
item=lambda name,size:{"id":"t","kind":"text","text":name,"font":{"path":"C:/Windows/Fonts/arial.ttf","index":0},
  "size_mm":size,"style":"satin","thread":{"color":"#ff0000","name":"Red"},"transform":{},"threads":[],"ops":[]}
FULL={'machine':'brother-pe550d','hoop':'4x4','threads':[],
      'cut_stops':{'enabled':True,'min_jump_mm':3.0,'include_untrimmed':False,'tie':True}}
for name in ("Emma","Olivia Grace Marie"):
    lay={"items":[item(name,20)],"merge_colors":False,"color_sort":False,"basting":{"enabled":False}}
    a=L.export(lay,'a.pes',{})      # what exportNames sends (features.ts:322)
    b=L.export(lay,'b.pes',FULL)    # what Save for machine sends (exportOptions)
    print(name,'names-export',counts('a.pes'),a['stops_added'],[w['code'] for w in a['warnings']])
    print(name,'save-for-machine',counts('b.pes'),b['stops_added'],[w['code'] for w in b['warnings']])
# Output:
# Emma names-export {'JUMP': 4, 'TRIM': 3} 0 []
# Emma save-for-machine {'JUMP': 4, 'STOP': 3, 'TRIM': 3} 3 ['stops_added']
# Olivia Grace Marie names-export {'JUMP': 19, 'TRIM': 18} 0 []
# Olivia Grace Marie save-for-machine {'JUMP': 19, 'STOP': 18, 'TRIM': 18} 18 ['hoop_too_big', 'stops_added']
```

**Observed:** [reproduce/confirmed/ran] Ran the reviewer's repro from the engine dir (uv run --frozen --no-sync python): exportNames-style options {} -> {'TRIM': 1, 'JUMP': 1}, stops_added 0, warnings [] Save-for-machine-style options -> {'STOP': 1, 'TRIM': 1, 'JUMP': 1}, stops_added 1, warnings ['stops_added'] I then reproduced it with realistic lettering, the case "One file per name" is built for. One red text item in Arial, size 20 mm, written with {} versus the Save-for-machine options (machine brother-pe550d, hoop 4x4, cut-stops enabled): "Emma" {}: {'JUMP': 4, 'TRIM': 3}, 0 stops, warnings [] full: {'JUMP': 4, 'STOP': 3, 'TRIM': 3}, 3 stops "Olivia Grace Marie" {}: {'JUMP': 19, 'TRIM': 18}, 0 ...

**Suggested fix:** In exportNames, build the options with exportOptions(defaultCutStops(selectMachine(state), design)), using the same helpers the Save dialog uses, instead of `{}`. Collect each call's returned `warnings` and `stops_added` and show them, for example "Saved 5 files; 2 are bigger than your hoop: Olivia, Marie". Optionally add a "Have the machine cut jump threads" tick to NamesDialog, as the Save dialog has. Add a test for exportNames' options.

**Caveats:** Narrower than "ruins a stitch-out": the stray threads are jump threads that can be snipped, and the file still sews. They are not misplaced stitches. High is kept because the feature advertises "machine files", the PE550D profile and the manual present cut-stops as the fix for exactly this, and the names path is the one export that silently skips them. It would be Medium if only the cosmetic threads counted. Scope: only exportNames (features.ts:322) uses empty options; every other export path ...

### C13 · High · Confirmed: Knife and merge ignore a drawn object's transform; Ctrl+D copies of drawn shapes carry one

**Where:** `engine/threadline_engine/shapeops.py:168-170 (_fill_poly)`, `engine/threadline_engine/shapeops.py:173-178 (_path)`, `engine/threadline_engine/shapeops.py:181-211 (split)`, `engine/threadline_engine/shapeops.py:214-227 (merge)`  
**Found by:** shapeops  
**Status:** Confirmed (a second agent reproduced it)

**What happens:** Ctrl+D on a drawn shape (fill, applique, run or satin) leaves the copy with transform.x/y = +10 and unchanged local points. The engine sews it at +10 mm. split() and merge() work on the untransformed local geometry, while the knife line comes from screen/world mm. The results are as follows. A knife through the middle of the copy on screen reports "The cut doesn't cross the shape". A cut that does cross lands 10 mm off. The pieces are re-added with an identity transform, so they jump back 10 mm onto the original. Merge of original plus copy returns just the original's 0..20 outline (area 400 instead of 700), so the copy's area is lost. If the copy is the first item, its transform is applied to the whole merged geometry and the result is sewn in the wrong place. A copy dragged away afterwards (moveBy changes only the points) keeps the stale transform, so the problem persists, and copies ...

**What should happen:** Knife and merge act on what is on the canvas (the geometry with its transform applied), and the results sit where the shapes were. Alternatively every drawn object has an identity transform, as the layout.ts comment says: duplicateItem should bake the 10 mm offset into the points, as paste already does with moveBy.

**Repro:**

```
# Python, from engine dir:  uv run --frozen --no-sync python repro.py
from threadline_engine import shapeops, layout as L
I = {"x":0,"y":0,"rotate":0,"scale_x":1,"scale_y":1,"flip_x":False,"flip_y":False}
sq = lambda x,y,w: [[x,y,"c"],[x+w,y,"c"],[x+w,y+w,"c"],[x,y+w,"c"]]
def fill(i, tr=I):
    return {"id":i,"kind":"fill","geometry":{"outline":sq(0,0,20)},"params":{"underlay":[]},"thread":{"color":"#cc2222"},"transform":tr,"threads":[],"ops":[]}
a, dup = fill("a"), fill("b", dict(I, x=10, y=10))   # dup = what duplicateItem produces
r = L.render({"version":1,"items":[a, dup]})
xs = [x/10 for (x,y,c),it in zip(r.pattern.stitches, r.item_of) if it==1 and c&0xFF==0]
print("copy sews at x", round(min(xs)), round(max(xs)))                      # 10 30
try: shapeops.split(dup, (20,0), (20,40))                                     # screen-middle of the copy
except Exception as e: print("knife at x=20:", e)                              # The cut doesn't cross the shape
print([(min(n[0] for n in p["outline"]), max(n[0] for n in p["outline"])) for p in shapeops.split(dup,(15,0),(15,40))["geometries"]])  # [(0,15),(15,20)]; expected world (10,15),(15,30)
m = shapeops.merge([a, dup])["geometry"]["outline"]
print("merge x range", min(n[0] for n in m), max(n[0] for n in m))           # 0 20; expected 0 30
# vitest (apps/desktop, vi.mock("./actions")): addObject a drawn fill, duplicateItem(layout,id).items[1].transform.x === 10
```

**Observed:** [reproduce/confirmed/ran] 1) Python repro (engine dir, uv run --frozen --no-sync): the reviewer's snippet reproduces exactly. copy sews at x 10 30 y 10 30 knife at x=20: The cut doesn't cross the shape [(0.0, 15.0), (15.0, 20.0)] (pieces in local coordinates; on screen the copy spans 10..30) merge x range 0.0 20.0 y 0.0 20.0 (the union of what is sewn is 0..30) 2) TypeScript: a temporary vitest (mocking ./actions; deleted afterwards, git status shows no stray file) built a drawn fill via addObject and ran duplicateItem. The copy's transform.x came out as 10, with outline nodes still at their original local coordinates. So Ctrl+D on a drawn shape leaves a non-identity transform, unlike ...

**Suggested fix:** Two parts. (1) In duplicateItem (layout.ts:245), for drawn objects clone the item and then call moveBy(..., ADD_OFFSET_MM, ADD_OFFSET_MM), as pasteClipboard does; keep the transform offset only for file items. (2) Make the engine safe for any existing or saved project: at the start of shapeops.split() and merge(), convert each object to world coordinates with t = layout.Transform.from_dict(obj.get('transform')); if not t.is_identity(): obj = dz.transform_geometry(obj, t, bounds centre of dz.geometry_points(obj)). This is the same recipe as layout._object_blocks and was checked in scratch. ...

**Caveats:** The Python repro, the vitest check and the fix recipe were all run. The reviewer's severity of High holds. The trigger is the normal way to get a second shape (Ctrl+D, then knife or merge). It is a broken feature and a silent wrong merge, not a ruined stitch-out, and the wrong result is visible on the canvas straight away and can be undone. Narrowness: only drawn objects with a non-identity transform are hit. That means Ctrl+D copies, copies of those (Repeat clones the transform), and any saved ...

### C14 · High · Confirmed: Outline/offset around a whole dense design takes 9-21 s, past the installed app's 10 s RPC timeout, and blocks the engine for the whole time

**Where:** `engine/threadline_engine/shapeops.py:152`, `apps/desktop/src/features.ts:135`, `apps/desktop/src/engine/sidecar.ts:37`, `apps/desktop/src/engine/rpc.ts:29,35,42`  
**Found by:** shapeops  
**Status:** Confirmed (a second agent reproduced it)

**What happens:** In the installed app, selecting a whole dense design (5 of 11 owner fixtures, about 13k-27k stitches) and running Outline / offset (Ctrl+Shift+K) takes 10-21 s in the engine. The UI gives up at 10 s with "Engine did not answer shape.offset within 10000 ms" and no outline is added. The sidecar keeps computing for another 0-11 s because the method is not a background method. Every other request queued behind it (a ping sent 1 s in came back at 21.5 s) waits for the same time and, with the default 10 s timeout, can show a timeout error too. Retrying hits the same wall.

**What should happen:** An outline around a normal design finishes in about 1-2 s. If it can be slow, the UI uses a long timeout (LONG_MS) and the engine stays responsive (background method).

**Repro:**

```
# run from engine/:  uv run --frozen --no-sync python repro.py   (~10 s CPU)
import math, time
from threadline_engine import shapeops, layout as L
I = {"x":0,"y":0,"rotate":0,"scale_x":1,"scale_y":1,"flip_x":False,"flip_y":False}
n = 24*12
nodes = [[round((5+2.5*i/24)*math.cos(2*math.pi*i/24),2), round((5+2.5*i/24)*math.sin(2*math.pi*i/24),2), "s"] for i in range(n+1)]
sat = {"id":"s","kind":"satin","geometry":{"nodes":nodes,"width_mm":2.5},"params":{},"thread":{"color":"#cc2222"},"transform":I,"threads":[],"ops":[]}
lay = {"version":1,"items":[sat]}
print(len(L.render(lay).pattern.stitches), "stitches")   # 8754
t = time.process_time(); shapeops.offset(lay, ["s"], 2.0)
print("offset CPU seconds:", round(time.process_time()-t, 1))   # 9.4 observed

# More realistic, on the owner's file (read in place):
# lay = {"version":1,"items":[{"id":"f","kind":"file","path":"<repo>/fixtures/Heart.thin.PES","name":"x","transform":I,"threads":[],"ops":[]}]}
# shapeops.offset(lay, ["f"], 2.0)   -> 20.6 s CPU, 27248 stitches
```

**Observed:** [reproduce/confirmed/ran] I reproduced it three ways. 1. Reviewer's synthetic satin spiral, run from engine/ with `uv run --frozen --no-sync python repro1.py`: ``` 8754 stitches 0.08 s render offset CPU seconds: 9.4 wall 9.5 rings 1 ``` Turn scaling: 4 turns / 1466 stitches took 1.3 s, 8 turns / 4381 stitches 1.8 s, 12 turns / 8754 stitches 9.5 s. 2. Whole-design outline (2 mm, one `file` item) on each owner PES fixture, CPU seconds on this machine under other reviewers' load: | Fixture | Stitches | CPU | |---|---|---| | Heart.thin | 27248 | 20.6 s | | NewFrog | 19221 | 19.2 s | | Frieren.Cut | 25143 | 15.3 s | | BMOFACE | 16986 | 12.8 s | | Inclusive Pride.Border | 14934 | 10.3 s | | ...

**Suggested fix:** In `shapeops.offset` (line 152), split each `ln.simplify(0.1)` into about 40-vertex pieces, buffer them all in one vectorised `shapely.buffer(array, 0.6, quad_segs=3)` call, and `unary_union` the results (measured 1.2-1.6 s versus 14-22 s, same shape within about 0.03 mm2). Also pass `LONG_MS` as the third argument to `engine().call` in `addOffset`, and consider `background=True` on `shape.offset` (check that `L.render` is thread-safe first).

**Caveats:** Mostly confirmed as filed. Differences and caveats: - The synthetic spiral is artificial: 12 turns packed into a 2.5 mm band, so the stitching overlaps about 12 times. The 4- and 8-turn versions are fast (1.3 s and 1.8 s). The owner's real fixtures are the stronger evidence, and the fixture numbers are what justify High. - Scope: affects the installed Tauri app. The browser-preview dev bridge uses a 60 s timeout, so there the call succeeds but is slow. Selecting a small part of a design (a few ...

### C15 · High · Confirmed: Wave fill: rows are sampled at different phases and cross each other, leaving bare gaps and double thread

**Where:** `engine/threadline_engine/digitize/stitches.py:563 (per-row brick stagger (r%3)*stitch/3 passed to _row_stitches)`, `engine/threadline_engine/digitize/stitches.py:564-572 (wave_offset applied only at those per-row penetrations; inner points only, and only where inside the shape)`, `engine/threadline_engine/digitize/patterns.py:180-181 (wave_offset)`, `engine/threadline_engine/digitize/stitches.py:656 (wave only reached via pattern == 'wave'; the default 1.5 mm / 8 mm and 3.5 mm stitch are set at stitches.py:409-410 and 397-399)`  
**Found by:** visual  
**Status:** Confirmed (a second agent reproduced it)

**What happens:** With the default Wave settings (height 1.5 mm, length 8 mm, stitch 3.5 mm, spacing 0.4 mm) a 24 mm circle has 296 to 330 stitches (66 to 74% of all stitches) crossing another stitch at angle 0 and 45 (tatami: 0). About 25% of 0.4 mm cells get under 0.15 mm of thread (bare fabric shows through) and about 23 to 25% get over 0.7 mm (nearly double thread, pucker and thread-break risk). The image is a woven-looking mesh of chevrons, not rows that ripple like water. Worse for taller waves (642 crossings at 3 mm); milder for long waves (22 to 38 crossings at 20 mm).

**What should happen:** Neighbouring rows stay parallel offset copies of each other, giving even coverage like tatami (the ripple should change the direction of the rows, not make them cross). USER-MANUAL.md:383 says only 'Rows that ripple like water'.

**Repro:**

```
# cd engine; uv run --frozen --no-sync python r2_wave.py
import math
from shapely.geometry import LineString
from shapely.strtree import STRtree
from threadline_engine.digitize.stitches import generate, STITCH
c = lambda x, y: [x, y, 'c']
circle = [c(15+12*math.cos(2*math.pi*i/48), 15+12*math.sin(2*math.pi*i/48)) for i in range(48)]
for pat in ("tatami", "wave"):          # public path, default angle 45, default wave 1.5/8
    recs, _ = generate({"kind": "fill", "geometry": {"outline": circle},
                        "params": {"pattern": pat, "underlay": []}})
    segs, prev = [], None
    for x, y, k in recs:
        if prev and k == STITCH and math.dist(prev, (x, y)) > 0.05:
            segs.append(LineString([prev, (x, y)]))
        prev = (x, y)
    t = STRtree(segs)
    n = sum(1 for i, s in enumerate(segs) for j in t.query(s)
            if j > i + 1 and s.crosses(segs[j]))
    print(pat, n, "crossings in", len(segs), "stitches")
# Output (actual run):
# tatami 0 crossings in 451 stitches
# wave 330 crossings in 451 stitches
```

**Observed:** [reproduce/confirmed/ran] Reproduced independently. (1) The reviewer's script (r2_wave.py, run from engine/ with uv run --frozen --no-sync) gives: tatami 0 crossings in 448 stitches; wave 1.5/8 (default) 296 crossings in 448; wave 3/8 642 crossings; wave 0.8/8 12 crossings. (2) Through the public path generate({kind:'fill', pattern:'wave', underlay:[]}) on the same 24 mm circle at the default 45 degree angle: tatami 0 crossings in 451 stitches, wave 330 crossings in 451 stitches. So it is not an artefact of calling tatami() directly at angle 0. (3) Coverage per 0.4 mm cell, interior cells only (2056 cells, thread length per cell, tatami = 0.400 mm exactly). At angle 0, wave 1.5/8: 25.9% of ...

**Suggested fix:** In wave mode give every row the same penetration grid (no per-row (r%3)*stitch/3 stagger, or add shared fixed-x points every wave_length/8 to all rows) so rows are vertical translates of one another. In scratch, the no-stagger variant takes crossings from 296 to 14 and bare/double cells from 25% to 0%. Also ripple the end points near the rim so they do not break the pattern, and add a crossing and density test (for example 'no stitch crosses a non-adjacent stitch' and 'per-cell density within +/-30% of spacing') to test_patterns.py, then regenerate the fill_wave snapshot.

**Caveats:** Reproduces exactly as reported. The reviewer's numbers match my runs (296 / 448 at angle 0; density 25.9% bare and 25.4% double against the claimed 25% / 25.6%). Severity: I keep High. This is optional-pattern, not the default fill, and it does not make stitches unsewable (max stitch 3.8 mm, all stay inside the shape), so it is not Critical. But it is the stitch output the owner cares most about: it puts bare gaps and double-thread zones in the same few mm and produces a mesh, not a ripple. ...

### C16 · High · Suspected: Measuring tool (M) never shows a distance, and has no menu entry

**Where:** `apps/desktop/src/components/StitchCanvas.tsx:534-541`, `apps/desktop/src/components/StitchCanvas.tsx:1415-1418`, `apps/desktop/src/components/ToolRail.tsx:85-134`, `apps/desktop/src/actions.ts:1207-1213`  
**Found by:** docs-a  
**Status:** Suspected (not re-verified)

**What happens:** M turns on `store.ruler`; each click adds a point and the canvas draws a line with two dots (StitchCanvas.tsx:534-541). Nothing anywhere turns the two points into a number: the only `new Text` calls in StitchCanvas are the ruler tick labels (:296) and the hooping numbers (:428), DrawHint handles `measure` (picture sizing) but not `ruler` and returns null for the Select tool (ToolRail.tsx:120), StatusBar prints no distance. Also `view.measure` is in no menu (Toolbar ... and the panel ... lists do not include it), so the manual's '(or ...)' is false (already QA-REPORT M17). Same code at HEAD, so it is not a recent regression.

**What should happen:** Manual: 'M (or ...) turns on the measuring tool: click two points to see the distance'. A readout (in the current units) should appear beside the line or in the hint bar, and the command should be in the ... menu.

**Repro:**

```
Static check (run from the repo root):
  grep -n "new Text" apps/desktop/src/components/StitchCanvas.tsx      # :296 ruler labels, :428 hooping numbers only
  grep -rn "\.ruler\b" apps/desktop/src --include=*.tsx              # only StitchCanvas.tsx:534,538,1415,1417,952 and actions.ts
  grep -rn "view.measure" apps/desktop/src --include=*.tsx           # no results (not in any Menu)
To confirm in the app: open any design, press M, click two points, look for any number (none expected).
```

**Suggested fix:** Draw a label (Pixi Text at the line's midpoint, formatted with fmtLen in the current units) in drawOverlay when st.ruler has two points, and add { id: "view.measure" } to the Toolbar ... menu (or drop '(or ...)' from the manual).

### C17 · High · Reviewer-reproduced: A design re-render during a drag throws and silently drops the drag

**Where:** `apps/desktop/src/components/StitchCanvas.tsx:1034-1046`, `apps/desktop/src/components/StitchCanvas.tsx:1613-1619`, `apps/desktop/src/components/StitchCanvas.tsx:1725-1730`  
**Found by:** live-esc  
**Status:** Reviewer-reproduced (not independently re-verified)

**What happens:** The scene is rebuilt (buildScene) every time `design` changes. A move/scale/rotate drag keeps its ghost in the old scene. If a render lands while the mouse is down (the previous drag's commit is still being computed by the engine, an undo, etc.), the ghost is destroyed: every pointermove throws 'Cannot read properties of null (reading set)' and pointerup throws 'Cannot read properties of null (reading x)' before commit, so the shape does not move, no history entry is added, and nothing tells the user. Nothing blocks new drags while a render is pending (loading only shows status text).

**What should happen:** The drag survives a re-render (recreate the ghost on the new scene) or is cancelled cleanly with the shape back where it was; no uncaught exceptions.

**Repro:**

```
// shape selected, tool = select
const r=el.getBoundingClientRect(); /* (x,y) = a point on the shape */
el.dispatchEvent(pe('pointerdown',x,y)); el.dispatchEvent(pe('pointermove',x+50,y+30));
S.setState({design:{...S.getState().design}});     // what an engine render finishing does
await new Promise(r=>setTimeout(r,300));
el.dispatchEvent(pe('pointermove',x+90,y+50));
window.dispatchEvent(pe('pointerup',x+90,y+50));
// history.past.length unchanged (11 -> 11); console: Uncaught TypeError ... reading 'set' at onMove, reading 'x' at onUp (twice)
```

**Suggested fix:** In onMove, if `drag.ghost?.destroyed` (or its scene differs from sceneRef.current) recreate it with startGhost on the current scene; in onUp guard the same way. Alternatively cancel the active drag when the scene is rebuilt.

### C18 · High · Reviewer-reproduced: Every key repeat queues a full engine render and only the last is shown: holding an arrow key freezes the canvas, then times out and rolls the whole move back

**Where:** `apps/desktop/src/actions.ts:166-196 (showHistory/commitDoc: one render per edit, older replies discarded at :180)`, `apps/desktop/src/actions.ts:1512-1520,1734-1741 (nudge commands)`, `apps/desktop/src/commands.ts:44-49 and App.tsx:109 (no e.repeat handling)`, `apps/desktop/src/actions.ts:87 (OPEN_TIMEOUT 60 s)`  
**Found by:** live-state  
**Status:** Reviewer-reproduced (not independently re-verified)

**What happens:** Each repeat of an arrow key (or R, Ctrl+D, Ctrl+Z...) calls commit(), which sends a layout.render and adds an undo step. The engine runs every queued render (drawn fills render at about 3,200 stitches/s: 2 fills 1.3 s, 6 fills 4 s, 10 fills 16-23 s) but the UI applies only the newest reply. Measured in the preview with a 14.7k-stitch design (6 fills, about 3.4 s per render): real Right-key x12 left the canvas unchanged for 41.8 s and added 12 undo steps; Right x22 made the last renders hit the 60 s timeout: notice 'Engine did not answer layout.render within 60000 ms', all 22 nudges rolled back (x unchanged, history unchanged) and the engine stayed busy about 75 s. Even on a 2-fill doc, 12 quick presses froze the canvas for 13.8 s. Holding a key about 3 s also pushes 100 steps and evicts the whole earlier undo history.

**What should happen:** Holding an arrow key moves the shape visibly and smoothly, one Ctrl+Z undoes the gesture, and a burst of edits never times out or rolls back. At most one render is in flight plus one trailing render; consecutive nudges merge into one undo step.

**Repro:**

```
Vitest (fake engine whose layout.render resolves after renderDelay ms; harness in the scratch file):
  setDoc(obj('a')); useStore.getState().select('a');
  let renders = 0; // counting engine: increments on 'layout.render'
  for (let k = 0; k < 30; k++) A.COMMANDS.find(c => c.id === 'arrange.right')!.run();
  await sleep(100);
  expect(renders).toBeLessThan(5);                              // fails: 30
  expect(useStore.getState().history.past.length).toBeLessThan(5); // fails: 30
Live (preview, real engine): build 6 circles/stars (about 14.7k stitches), select one, press Right x22 with the real keyboard: canvas frozen, after about 60 s the timeout notice appears and nothing moved.
```

**Suggested fix:** Keep at most one layout.render in flight and render only the newest pending history when it returns (latest-wins queue); ignore e.repeat or coalesce arrow nudges within about 500 ms into one undo step (pushHistory with a merge flag).

### C19 · High · Reviewer-reproduced: An edit made while a project is still opening supersedes the open, leaving projectPath on the OLD project: the next Ctrl+S overwrites it with the new project's content

**Where:** `apps/desktop/src/actions.ts:224-236 (replaceDoc only runs select/markSaved when showHistory returned true)`, `apps/desktop/src/actions.ts:166-191 (showHistory returns false when a newer render supersedes)`, `apps/desktop/src/actions.ts:294-306 (openProject)`, `apps/desktop/src/actions.ts:309-351 (saveProject reads s.projectPath at :313)`  
**Found by:** live-state  
**Status:** Reviewer-reproduced (not independently re-verified)

**What happens:** Open B.ludd while A.ludd is open. After project.open answers, B's render is in flight and 'Opening B…' shows only in the small status bar; the old design is still on screen. Any commit-based command run in that window (Fewer jumps, a recolour, a picture drop, a fabric change) builds on the pending B doc and supersedes the open's render. replaceDoc then sees ok=false and never calls markSaved(B), so the end state is B's content, dirty, with projectPath still A.ludd. The title says 'B' (layout.title was set from B's path), but Ctrl+S calls project.save with A's path and title: A.ludd is silently overwritten with B's design. Reproduced live with Star badge.ludd then Wreath.ludd: final projectPath was Star badge.ludd, 15 items, dirty. (I did not save: save was never invoked.)

**What should happen:** The window title, projectPath and saved baseline always describe the document that is on screen. Edits while opening are blocked or applied after the open completes.

**Repro:**

```
Vitest (fake engine; render delayed 80 ms):
  setDoc(obj('old')); useStore.setState({ projectPath: 'A.ludd' });
  projectOpen = { layout: layoutOf(obj('new')), images: [], path: 'B.ludd' };
  renderDelay = 80;
  const opening = A.openDesign('B.ludd', true);
  await sleep(30);                       // project.open answered, render in flight
  A.COMMANDS.find(c => c.id === 'layout.travelUnder')!.run();
  await opening; await sleep(300);
  expect(useStore.getState().projectPath).toBe('B.ludd'); // fails: 'A.ludd'
```

**Suggested fix:** Apply path, savedDoc and selection reset together with the history in the render that wins (pass them into showHistory), or disable commits and commands while `loading` is set.

### C20 · High · Reviewer-reproduced: Text tool: the new text box is never focused, so typing runs shortcuts and Backspace deletes the text

**Where:** `apps/desktop/src/actions.ts:873-877 (select(item.id) then immediate window.dispatchEvent('ludd:edit-text'))`, `apps/desktop/src/components/TextPanel.tsx:88-97 (listener registered in an effect of SelectedText, which mounts only on the next render)`, `apps/desktop/src/actions.ts:1717-1718 (Delete and Backspace bound to Remove)`, `docs/USER-MANUAL.md:168 ('click where it goes, then type')`  
**Found by:** live-state  
**Status:** Reviewer-reproduced (not independently re-verified)

**What happens:** Shift+T, click on the canvas: text 'Text' is added and selected, but document.activeElement is BODY because the focus event fires before SelectedText exists to hear it. Typing the real keys h e l l o then runs commands: hoop hidden, crosshair on, Line tool selected and the text deselected; the letters never reach the text. A real Backspace (fixing a typo) removed the freshly placed text item (items 1 -> 0, one undo step).

**What should happen:** After placing text the box is focused with the placeholder selected, so typing replaces it.

**Repro:**

```
Preview with real input: press Shift+T, click on the canvas, then press keys h e l l o (showHoop false, crosshair true, tool 'run', selection lost). Or after placing text press BackSpace: layout.items becomes []. Check document.activeElement right after the click: BODY.
```

**Suggested fix:** Focus after render: dispatch the event in requestAnimationFrame/after a store-flushed tick, or keep a pendingFocusId in the store that SelectedText consumes in a mount effect.

### C21 · High · Reviewer-reproduced: Mac (Intel) release leg cannot build: onnxruntime is a hard dependency and has no macOS x86_64 wheel

**Where:** `engine/pyproject.toml:10`, `engine/uv.lock:89-105`, `engine/uv.lock:303`, `engine/uv.lock:107-121`  
**Found by:** packaging  
**Status:** Reviewer-reproduced (not independently re-verified)

**What happens:** The uncommitted change added `onnxruntime>=1.31.0` to the unconditional dependencies. uv.lock lists only these wheels for it, with no sdist: macosx_14_0_arm64, manylinux_2_28_aarch64, manylinux_2_28_x86_64, win_amd64, win_arm64. The Intel leg (`macos-15-intel`) runs `uv run pytest` first, which fails at the environment sync, so the Intel installer is never built. v1.0.0 predates the onnxruntime change, so the Intel leg is untested with it. ci.yml only covers windows-latest and macos-latest (arm64), so CI cannot catch it. The cv2 wheel for Intel Mac is also only macosx_14_0_x86_64.

**What should happen:** Every platform in the release matrix can install the engine environment, or the optional AI-tracing runtime is optional. CLAUDE.md already calls onnxruntime optional, and segment.py already turns a missing import into a friendly SegmentError.

**Repro:**

```
cd <any scratch dir>   # uv 0.12.23, offline, no network needed
echo "onnxruntime==1.31.0" | uv pip compile - --no-config --python-platform x86_64-apple-darwin --python-version 3.12 --offline --only-binary :all: --no-deps
# actual output:
# error: No solution found when resolving dependencies
#   cause: Because onnxruntime==1.31.0 has no wheels with a matching platform tag (e.g., `macosx_13_0_x86_64`) and you require onnxruntime==1.31.0, we can conclude that your requirements are unsatisfiable.
# hint: Wheels are available for `onnxruntime` (v1.31.0) on the following platforms: `manylinux_2_28_aarch64`, `manylinux_2_28_x86_64`, `macosx_14_0_arm64`, `win_amd64`, `win_arm64`
# The same command with --python-platform x86_64-unknown-linux-gnu or x86_64-pc-windows-msvc prints "Resolved 1 package".
```

**Suggested fix:** Make onnxruntime conditional or optional: `"onnxruntime>=1.31.0; sys_platform != 'darwin' or platform_machine != 'x86_64'"`, or move it to an extra, then re-lock. Have `ai.trace_model` report `runtime: false` so Settings hides the Download button when it is absent. Add an Intel Mac and a Linux job to ci.yml, or at least a `uv lock --check` plus a `uv sync --frozen --dry-run` step per matrix target.

### C22 · High · Reviewer-reproduced: Print template and thread list print unstyled in the installed app (black square, no centre cross, no swatches): Tauri injects a style nonce that cancels 'unsafe-inline'

**Where:** `apps/desktop/src/print.ts:66,94,98-114,140-145`, `apps/desktop/src-tauri/tauri.conf.json:24`, `apps/desktop/index.html:9-12`, `C:/Users/Copper Felix/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/tauri-2.12.3/src/manager/mod.rs:96-103`  
**Found by:** tauri  
**Status:** Reviewer-reproduced (not independently re-verified)

**What happens:** The release build serves: style-src 'self' 'unsafe-inline' 'nonce-1113...' (Tauri adds a nonce because index.html has an inline <style>). Per CSP, 'unsafe-inline' is ignored when a nonce is present, and the print iframe (srcdoc) inherits the page CSP. Console: "Applying inline style violates ... 'unsafe-inline' is ignored if either a hash or nonce value is present". Rendering the real printHtml() output in the installed app: the SVG hoop rectangle is filled solid black (SVG default fill), the red centre-cross lines are invisible (their stroke comes from CSS), thread swatches are transparent, the table is unstyled. Screenshot: <scratch>/tauri/print_as_shipped.png vs print_csp_bypassed.png. The browser preview and dev server have no nonce, so it works there and print.test.ts (string-only) cannot catch it.

**What should happen:** A real-size template with dashed hoop, red centre lines, coloured stitches, and a styled thread list with colour swatches, as the manual promises.

**Repro:**

```
Start the release LUDD.exe with: set WEBVIEW2_USER_DATA_FOLDER=%TEMP%\wv2qa & set WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9333 & set THREADLINE_DATA_DIR=%TEMP%\ludd-qa. Attach a CDP client to http://127.0.0.1:9333 (stdlib one: <scratch>/tauri/cdp.py) and evaluate in the page:
const f=document.createElement('iframe');
f.srcdoc='<style>.a{background:#0f0;width:9px;height:9px}</style><div class=a id=a></div><svg><style>path{fill:none}</style><path id=p d="M0 0L9 9"/></svg>';
f.onload=()=>console.log(getComputedStyle(f.contentDocument.getElementById('a')).backgroundColor, getComputedStyle(f.contentDocument.getElementById('p')).fill);
document.body.appendChild(f)
Installed app prints: rgba(0, 0, 0, 0) rgb(0, 0, 0)   Expected: rgb(0, 255, 0) none.
Header: fetch('/').then(r=>r.headers.get('content-security-policy')) shows style-src ... 'nonce-...'.
Full page: <scratch>/tauri/run_app5.py (renders printHtml() output; AS SHIPPED swatchBg rgba(0,0,0,0), hoopFill rgb(0,0,0), crossStroke none; with Page.setBypassCSP the correct values).
```

**Suggested fix:** In tauri.conf.json app.security add "dangerousDisableAssetCspModification": ["style-src"] so no style nonce is injected and 'unsafe-inline' works (or move the inline <style> out of index.html so Tauri has nothing to nonce, or give print.ts presentation attributes and an external stylesheet). Then add a check that the effective style-src has no nonce, and a smoke test of the print page in the built app.

### C23 · High · Reviewer-reproduced: Installed app leaves a ~180 MB PyInstaller temp folder behind on every quit

**Where:** `scripts/build_engine.py:44-50`, `apps/desktop/src/engine/sidecar.ts:49-53`, `C:/Users/Copper Felix/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/tauri-plugin-shell-2.4.1/src/lib.rs:163-173`, `apps/desktop/src/App.tsx:172-183`  
**Found by:** packaging, tauri (also reported as packaging#2)  
**Status:** Reviewer-reproduced (not independently re-verified)

**What happens:** The engine is a PyInstaller --onefile exe: a bootloader parent that extracts ~180 MB to %TEMP%\_MEIxxxx and runs a Python child, then deletes the folder when the child exits. On quit the shell plugin kills only the parent (TerminateProcess); the child exits later on pipe EOF, but nobody deletes the folder. Real app: window close -> LUDD exit code 0, 0 engine processes, and the run's _MEI folder is still on disk. This PC has 171 _MEI* folders in %LOCALAPPDATA%\Temp, 112 of them LUDD engine copies, about 6.9 GB. The same happens on macOS/Linux (SIGKILL of the parent). Every launch also re-extracts 180 MB (see the startup finding).

**What should happen:** No residue after quit; a graceful stop (engine exits by itself) or an onedir bundle.

**Repro:**

```
<scratch>/tauri/closetest.py (launches the built app copy, closes the window with WM_CLOSE) prints: LUDD exit code: 0 | engine processes after quit: 0 | _MEI dirs from this run still on disk after a normal quit: [True].
No-app version, <scratch>/tauri/lifecycle.py: start engine.exe, ping, then p.kill() (what the plugin does):
run1 after graceful exit (stdin closed): _MEI still present: [False]
run2 after kill(): _MEI still present: [True] procs still alive: 1
run2 after the app's pipe closed: procs still alive: 0 _MEI still present: [True]
Count on any machine that used LUDD: (Get-ChildItem $env:LOCALAPPDATA\Temp -Directory -Filter _MEI*).Count
```

**Suggested fix:** Best: build the sidecar --onedir (no per-launch extraction, no leak) and ship it via Tauri resources. Otherwise add an engine 'shutdown' RPC, call it and wait for the 'close' event in onCloseRequested (and before relaunch), and only kill as a fallback; optionally sweep stale _MEI* folders containing threadline modules at startup.

### C24 · High · Reviewer-reproduced: Double-clicking a .ludd while LUDD is open starts a second app that reports a false crash, does not open the file, and Discard destroys the first window's recovery copy

**Where:** `apps/desktop/src-tauri/src/lib.rs:12-22`, `apps/desktop/src-tauri/Cargo.toml:16-22`, `apps/desktop/src/App.tsx:324-333`, `apps/desktop/src/App.tsx:205-235`  
**Found by:** tauri  
**Status:** Reviewer-reproduced (not independently re-verified)

**What happens:** No single-instance handling. The installer registers .ludd as LUDD.exe "%1", so a double-click starts a second process (second window, second engine). Recovery is one global file (%APPDATA%\Ludd\recovery\autosave.ludd) written by whichever instance has unsaved work. The second instance finds the first one's autosave and shows 'LUDD closed without saving your work from ... Get it back?'; because a recovery exists, the argv file is never opened (App.tsx only opens it when there is no recovery, once). Discard (or the second window closing) deletes the first window's only crash-protection; Recover pulls the first window's work into the second.

**What should happen:** The file opens in the running window (or a new window without touching the other's recovery data); no false crash prompt.

**Repro:**

```
Simulation of the double-click against the built app, <scratch>/tauri/run_app7.py: seed an autosave through the sidecar (what window 1 writes 3 s after any edit), then run LUDD.exe "proj.ludd" with the same data dir. Output:
window title: 'LUDD'
banner: LUDD closed without saving your work from 10/12/2026, 1:27:18 AM (“My unsaved work”, 1 design part). Get it back? Recover Discard
body mentions the project's design/hoop (design opened)? False
By hand: edit something in LUDD, wait 4 s, double-click any .ludd in Explorer.
```

**Suggested fix:** Add tauri-plugin-single-instance; in its callback forward argv to the running window (emit an event the UI turns into openDesign) and focus it. Also open the argv file after the Recover/Discard choice, and key the recovery file by process (or lock it) so a second instance never reads or deletes another's.

### C25 · High · Reviewer-reproduced: If the engine process dies the app stays dead: no restart, saving impossible, startup failure leaves the child running

**Where:** `apps/desktop/src/engine/sidecar.ts:43-47,55-65`, `apps/desktop/src/App.tsx:52-74`, `apps/desktop/src/components/StatusBar.tsx:6-9`, `apps/desktop/src/engine/rpc.ts:29,65-72`  
**Found by:** tauri  
**Status:** Reviewer-reproduced (not independently re-verified)

**What happens:** startEngine is called once (App.tsx:57 is the only caller). When the child exits, in-flight calls are rejected (good) and the status bar shows 'Engine disconnected' plus the raw reason, but nothing restarts the engine and there is no button. Every save, export and autosave goes through the engine, so the user cannot save or export what is on screen; only the last autosave (at most 3 s old) survives, offered back after a manual restart. A failed first connection (ping timeout, spawn error) returns client=null and also does not kill the spawned child.

**What should happen:** Automatic restart (at least once) or a visible 'Restart engine' action; unsaved work still savable.

**Repro:**

```
<scratch>/tauri/run_app6.py: launch the built app with a design open, kill only its threadline-engine.exe (taskkill /PID <engine> /T /F). Output every 2.5 s for 15 s: 'Engine disconnected | Engine exited (code 1)'; notice text: None; buttons matching restart/retry/reconnect: []. grep -rn startEngine apps/desktop/src shows only App.tsx.
```

**Suggested fix:** Make the engine a restartable singleton: on 'close' or a failed start, retry once automatically, then show a banner with 'Restart engine'; re-run formats/machines/charts loading after a restart; kill the child when the first ping fails. Give the first ping a 60 s timeout.

### C26 · High · Reviewer-reproduced: A clean checkout fails the engine suite: test_library.py needs the gitignored personal fixtures and does not skip

**Where:** `engine/tests/test_library.py:7`, `engine/tests/test_library.py:13`, `fixtures/README.md`, `engine/tests/test_golden.py:17`  
**Found by:** tests  
**Status:** Reviewer-reproduced (not independently re-verified)

**What happens:** test_library.py (untracked, new) scans the repo's fixtures/ folder and asserts that PES designs are found. In CI, fixtures/ contains only README.md (everything else is gitignored), so the list is empty and `assert pes and all(...)` fails. test_scan_filters_by_name passes vacuously (all() over an empty list). The suite is green here only because the owner's designs are on disk. Pushing this turns both CI jobs red and blocks the release workflow. library.py has 0% coverage in a clean checkout.

**What should happen:** Tests that need private designs skip (as test_golden.py does) or build their own designs in tmp_path; CI stays green and library.scan keeps real coverage.

**Repro:**

```
# Simulate a CI checkout: fixtures/ has README.md only
mkdir -p S/ci/engine S/ci/fixtures
cp -r engine/threadline_engine engine/tests S/ci/engine/ ; cp fixtures/README.md S/ci/fixtures/
cd S/ci/engine && PYTHONPATH=. uv run --frozen --no-sync python -m pytest -q
# actual: FAILED tests/test_library.py::test_scan_lists_designs_with_thumbnails_and_skips_other_files
#         assert ([])      ->  1 failed, 251 passed, 4 skipped
# (my copy: C:/Users/COPPER~1/AppData/Local/Temp/claude/C--Users-Copper-Felix-HTML-Stuffs-threadline/182de744-a28c-4a68-96f5-d0545ff7ce29/scratchpad/tests/ci/engine)
```

**Suggested fix:** Write two or three small designs with pyembroidery into tmp_path (or point the test at the committed samples/ folder) and assert on those; make the filter test assert that the result is non-empty.

## Medium findings (192 after merging look-alikes)

Each entry: status, title, where, suggested fix. Area in headings. Full detail and repro snippets are in the per-area reports (see Appendix).

### autotrace

- **Confirmed**: Busy pictures take 20 to 90 s (one click on connected line art 3 to 16 s) with no progress, no real cancel, and a 'few seconds' label  
  Where: `engine/threadline_engine/autotrace.py:378-399 (thin)`, `engine/threadline_engine/autotrace.py:405-456 (_neighbours, _one_pixel, _prune)`  
  Fix: Thin only a window around the click (or cache the skeleton per picture keyed on the Pic), replace _one_pixel/_prune/_segments with vectorised code or cv2.ximgproc/skimage-style thinning, crop the ...
- **Confirmed**: With "fewer jumps" on (the default for new designs), layout render time grows steeply with object count (about 9 s at 1,000 objects, 120 s at 3,199); past the UI's 60 s timeout, "Add all" silently adds nothing and then reports "Added N shapes"  
  Where: `engine/threadline_engine/layout.py:530-533 (_cover leaves ~1e-14 mm^2 sliver polygons for running stitches)`, `engine/threadline_engine/layout.py:536-549 (_join_same_thread_objects: not c.is_empty at 546 keeps slivers; unary_union(later) at 547 for every join)`  
  Fix: 1) layout.py:539-547: ignore degenerate covers (for example `c.area > 0.01` in addition to `not c.is_empty`), and build the "hidden" union once in a sweep from the last block backwards instead of ...
- **Confirmed**: Auto-trace offers nothing (or only a capped 10 mm ribbon) when you click inside a solid black or very dark shape  
  Where: `engine/threadline_engine/autotrace.py:624-625`, `engine/threadline_engine/autotrace.py:484-531`  
  Fix: In region(), when the seed is ink, also build a fill candidate for the seed's solid core. Reuse the digitize_all solid branch (core = ink & ink_dt >= solid_r, dilated by solid_r, connected component ...
- **Confirmed**: 16-bit greyscale PNGs are read as near-pure black and white, so every mid-tone vanishes in Auto-trace and Trace Assist  
  Where: `engine/threadline_engine/autotrace.py:62`, `engine/threadline_engine/trace.py:74`  
  Fix: Add one shared helper used by both analyse() functions (and advisor.py:106). If img.mode starts with "I" (I;16, I;16L, I;16B, I), convert through numpy with np.asarray(img).astype(np.int64) // 257, ...
- **Confirmed**: AI embedding cache is keyed by file path and picture size only, so an in-place edit of the same size gets AI guesses for the old picture  
  Where: `engine/threadline_engine/ai/segment.py:97`, `engine/threadline_engine/ai/segment.py:112-135`  
  Fix: Key the cache on (path, st_mtime_ns, st_size). The simplest way is to keep the embedding on the cached Pic object (e.g. pic.embed) so it is dropped when autotrace._cache reloads or evicts the ...
- **Confirmed**: Whole-picture digitize samples a separate colour for every outline and dark fill, so anti-aliased or JPEG logos get many near-identical threads  
  Where: `engine/threadline_engine/autotrace.py:776 (each outline segment coloured by the median of its own skeleton pixels, which are anti-aliased)`, `engine/threadline_engine/autotrace.py:762 (solid-dark fill colour is the median of its own pixels)`  
  Fix: In `digitize_all`, after choosing all shape colours, snap each to the nearest `pic.centres` colour (converted from Lab to RGB) and merge palette entries within about ΔE 10. Give all `pic.ink` ...
- **Confirmed**: "Leave out the background" has no effect when the background is dark and neutral (black, charcoal, dark navy or brown): it is stitched as one picture-sized fill  
  Where: `engine/threadline_engine/autotrace.py:72-75 (ink = gray<70 and chroma<70)`, `engine/threadline_engine/autotrace.py:711-715 (solid dark areas built from ink)`  
  Fix: Decide the background once, from the dominant colour of the 1-px frame of the picture (or the large region touching the border), and apply that test to both the colour-patch loop and the solid-dark ...
- **Confirmed**: "Leave out the background" in whole-picture digitize drops real shapes: any colour area touching the picture edge that is pale or covers more than 45% of the picture is discarded  
  Where: `engine/threadline_engine/autotrace.py:740-742`, `engine/threadline_engine/autotrace.py:63 (transparent PNGs become white paper, so trimmed transparent logos hit the rule)`  
  Fix: In digitize_all (autotrace.py:740-742), decide background per colour group from pic.groups, not per patch from "touches and (light or big)". Compute the share of border pixels in each group. Treat a ...
- **Confirmed**: Strokes 3 to 4.4 mm wide (bold lettering) come out as a patchwork of small fills and satin pieces  
  Where: `engine/threadline_engine/autotrace.py:711-716`, `engine/threadline_engine/autotrace.py:752-762`  
  Fix: In digitize_all, decide fill versus satin per connected ink component (or per skeleton branch) from the median stroke width, and add hysteresis (e.g. core at 1.25 mm and keep as fill when the ...
- **Confirmed**: Whole-picture digitize: paper enclosed by a shape (letter counters, rings) is sewn as a white fill even with "Leave out the background" ticked  
  Where: `engine/threadline_engine/autotrace.py:740-743`, `engine/threadline_engine/autotrace.py:729-734`  
  Fix: In digitize_all keep a set of colour groups already skipped as background (add g where the `continue` at line 743 fires, and skip any later patch whose group is in the set when skip_background is ...
- **Confirmed**: Whole-picture digitize turns soft or anti-aliased edges into hairline ring fills (many colours, junk stitches); JPEG q50 also fragments 1 px outlines  
  Where: `engine/threadline_engine/autotrace.py:722-750 (patch loop: filters by pixel area only, `st[c, CC_STAT_AREA] >= min_px` at 727 and `np.count_nonzero(r) < min_px` at 737; no width test on the finished fill, unlike `_part` at 346-347 which checks MIN_HOLE_WIDTH_MM for holes)`, `engine/threadline_engine/autotrace.py:92-112 (simplify_colors: k-means into 12 groups gives edge-blend colours their own group, so each soft edge becomes a ring-shaped patch of one group)`  
  Fix: In digitize_all, after the patch loop builds each fill (around line 745), drop it or fold it into the neighbouring colour when mean width 2*area/perimeter is under about 1 mm, the same test _part ...
- **Confirmed**: Whole-picture satin ribbons stop about half a line width short at every free line end (single-click ribbons reach the tip)  
  Where: `engine/threadline_engine/autotrace.py:766-780 (digitize_all ribbon/run loop; no tip extension)`, `engine/threadline_engine/autotrace.py:770 (speck test applied to the shortened skeleton, so short dashes vanish)`  
  Fix: Factor the tip-extension block at autotrace.py:513-522 into a helper, e.g. `_reach_tips(px, width_px)`. Call it in `digitize_all` for open segments, extending only the ends whose skeleton pixel has ...

### compat

- **Confirmed**: Default-on 'Fewer jumps & trims' adds a per-render cost on every drawn object, and it grows quadratically with same-thread objects  
  Where: `engine/threadline_engine/layout.py:529-533 (_cover, uses _stitched_area at 311-327)`, `engine/threadline_engine/layout.py:536-551 (_join_same_thread_objects: covers for every digitized block, then unary_union(covers[i:]) per join)`  
  Fix: Compute _cover only for blocks adjacent to a same-thread digitized block, cache each cover by the same kind/geometry/params key as _generate_cached, and replace the per-join unary_union(covers[i:]) ...
- **Confirmed**: Fewer jumps & trims plus "Sort colors": hidden travel stitches are sewn after (on top of) the shape meant to hide them  
  Where: `engine/threadline_engine/layout.py:696-698 (_join_same_thread_objects runs on the pre-sort order, then _color_sort)`, `engine/threadline_engine/layout.py:536-551 (hidden = union of covers[i:] in the pre-sort order)`  
  Fix: Simplest: at layout.py:696 pass `bool(layout.get("travel_under")) and not layout.get("color_sort")`, so a colour-sorted design uses honest jump and trim joins. Better, but more work: sort first, then ...
- **Confirmed**: Text on a line longer than the line: surplus letters stack at the two ends with no warning (code comment promises one)  
  Where: `engine/threadline_engine/lettering.py:481 (s_mid clamped to [0, length])`, `engine/threadline_engine/lettering.py:495-496 (dead 'objects = objects' branch; comment says 'the warning below says so' but there is none)`  
  Fix: In _along_path (or in layout_text's path branch) append "The text is {total-length:.0f} mm longer than the line; shorten it, make the letters smaller or draw a longer line" to warnings when total > ...
- **Confirmed**: 'Put the text on the line' ignores the text's rotation, scale and flip, so turned, resized or mirrored lettering lands off the line (also: shapeops)  
  Where: `apps/desktop/src/features.ts:290-306 (textOnLine; local = node - (t.x, t.y) only, line 297)`, `engine/threadline_engine/layout.py:459-482 (_text_block applies the full text transform to the generated letters)`  
  Fix: In textOnLine, map each line node through the inverse of the text's transform before storing it as shape.nodes: subtract x,y, rotate by -rotate, divide by scale_x/scale_y, undo flip_x/flip_y. I ...
- **Confirmed**: Stitch-edit moves (move_stitch) are stored and applied as world-space offsets, so they no longer match the design if it is rotated, flipped or resized after the edit  
  Where: `engine/threadline_engine/layout.py:177-194 (_move_stitches; docstring at 178-179 promises 'relative to the design')`, `engine/threadline_engine/layout.py:673-676 (_transform, then _move_stitches)`  
  Fix: Apply `_move_stitches` before `_transform` in layout.py (move the call from line 676 to before line 675). In `moveSelectedStitches` (features.ts:278), first convert the world drag (dx, dy) into the ...
- **Confirmed**: A stop or trim inserted after a stitch silently disappears when that same stitch is deleted in stitch-edit  
  Where: `engine/threadline_engine/layout.py:165-172 (_apply_ops: `continue` at 166 skips the `inserts.get(r[4])` loop at 169)`, `apps/desktop/src/design/layout.ts:385-394 (insertAt anchors the op to a stitch's source index)`  
  Fix: In _apply_ops, when a STITCH record is in `gone`, still emit its `inserts` (stop or trim) before the `continue`. Use the previous kept record's x/y (`recs[-1]`, else the deleted record's own x/y) so ...
- **Confirmed**: Stipple fill sews only the largest connected region; other parts of the shape are silently left unstitched (and thin-armed shapes with a hole error out as "too small")  
  Where: `engine/threadline_engine/digitize/patterns.py:77-123 (stipple_path; line 115 `biggest = max(shapes, key=lambda g: g.area)` drops all other tree components)`, `engine/threadline_engine/digitize/patterns.py:84-92 (cells only where the inset shape contains the cell centre, so a narrow neck or a lone-cell arm gives no cell or no line)`  
  Fix: In stipple_path, link the separate tree components with an in-shape connecting path (travel inside poly.buffer(0.3), as contour/cross do via _open_pattern) so every region is sewn, for example by ...
- **Confirmed**: Mac (Intel) release job cannot install the engine: onnxruntime 1.31.0 has no macOS x86_64 wheel and no sdist in uv.lock  
  Where: `engine/pyproject.toml:10`, `engine/uv.lock:89-104 (wheels macosx_14_0_arm64, manylinux aarch64/x86_64, win_amd64, win_arm64; no sdist)`  
  Fix: Make onnxruntime an optional extra (for example `[project.optional-dependencies] ai = ["onnxruntime>=1.31.0; sys_platform != 'darwin' or platform_machine == 'arm64'"]`), with the release job syncing ...

### docs-a

- **Reviewer-reproduced**: In-app Help is not 'this same material': missing topics and two wrong statements  
  Where: `engine/threadline_engine/ai/helpdocs.py:29 (Shape tab)`, `engine/threadline_engine/ai/helpdocs.py:48 (Text tool (T))`  
  Fix: Add the missing sections (or build GUIDE from the manual's headings), correct the two statements, and add a pytest that checks every '(Key)' in GUIDE against the COMMANDS registry.
- **Reviewer-reproduced**: Shift+comma ('machine speed') can never fire  
  Where: `apps/desktop/src/actions.ts:1845`, `apps/desktop/src/commands.ts:19-32`  
  Fix: Match punctuation on e.code (Comma) when Shift is part of the shortcut, or choose another key (for example a letter) and update manual and Help.
- **Reviewer-reproduced**: Stitch-edit moves are stored in world space and drift when the design is turned, mirrored or resized afterwards  
  Where: `engine/threadline_engine/layout.py:177-193`, `engine/threadline_engine/layout.py:674-676`  
  Fix: Convert the dragged delta into the file's own frame when it is stored (inverse of the item's transform) and apply it before _transform, or rotate/scale stored deltas whenever transform ops run.
- **Reviewer-reproduced**: A project whose lettering uses a font that is not installed will not open at all  
  Where: `engine/threadline_engine/layout.py:459-469`, `engine/threadline_engine/lettering.py:123-134`  
  Fix: In _text_block catch the font error, fall back to the first installed outline font, and add a warning naming the missing font; optionally embed the font file (when its licence allows) like pictures.
- **Reviewer-reproduced**: Knife pieces lose a colour changed in Threads, the group and the pin  
  Where: `apps/desktop/src/features.ts:175-200`, `apps/desktop/src/features.ts:35-54`  
  Fix: Build the pieces with ...rest of the original (threads, group, locked) in insertObjects/finishKnife, or pass them through to addObject.
- **Reviewer-reproduced**: Browse designs: typing a name cannot find designs past the first 600, though the message says it can  
  Where: `apps/desktop/src/components/FeatureDialogs.tsx:94-96`, `apps/desktop/src/components/FeatureDialogs.tsx:115-118`  
  Fix: Debounce the search box and call library.scan with query=<text>, or filter in the engine; keep the 600 cap only for the unfiltered view.
- **Reviewer-reproduced**: Text on a drawn line: letters beyond the line's ends pile up on each other, with no warning  
  Where: `engine/threadline_engine/lettering.py:465-497 (s_mid clamp at :481, dead no-op at :495-496)`, `engine/threadline_engine/lettering.py:456-462 (warning only for circles)`  
  Fix: In layout_text, when kind == 'path' and total > the line length, append a warning ('The text is longer than the line: shorten it, make the letters smaller or draw a longer line'); better, extend the ...
- **Reviewer-reproduced**: Manual overstates cut-stops: only jumps the design marks as trims become stops; the dialog then says 'no jump threads long enough to cut'  
  Where: `docs/USER-MANUAL.md:82-85`, `apps/desktop/src/components/ExportDialog.tsx:208-212`  
  Fix: Reword the manual (and Help) to 'jumps marked for trimming (and, with the extra option, other long jumps)'; in the dialog show 'N long jumps are not marked for trimming: cut them too?' when such ...

### docs-b

- **Reviewer-reproduced**: Insert a stop/trim at the needle cannot target lettering and silently inserts in the wrong place  
  Where: `engine/threadline_engine/layout.py:484, 502 (every text stitch is emitted with source index -1)`, `apps/desktop/src/design/layout.ts:385-394 (insertAt walks back to the nearest earlier real stitch)`  
  Fix: Give text stitches real source indices (so ops can address them) or make insertAt refuse when the nearest real stitch belongs to another item, with a clear message.
- **Reviewer-reproduced**: Stitch Advisor's 'make it a satin' suggestions can never be accepted, and the message is stale  
  Where: `apps/desktop/src/ai.ts:137-141 (applicable() says a fill or line can't become a satin)`, `apps/desktop/src/components/AIPanels.tsx:97`  
  Fix: Make applicable() true for satin and use convertObject's ribbon conversion in withChange; update the test and the AIPanels hint.
- **Reviewer-reproduced**: 'Save this font as a stitch font' leads nowhere: the file is not found by the font list, and the manual doesn't say where it goes  
  Where: `apps/desktop/src/actions.ts:893-905 (no default folder; message says 'Put it in LUDD's fonts folder')`, `engine/threadline_engine/lettering.py:46-57, 78-83 (stitch fonts are only found in the data dir's fonts folder, which does not exist by default)`  
  Fix: Default the save dialog to the fonts folder (create it), refresh the font list after saving, and add 'where it goes and how to edit it' to the manual.
- **Reviewer-reproduced**: Key matching uses e.key: Machine speed (Shift+comma) can never fire, and Alt shortcuts are likely dead on a Mac  
  Where: `apps/desktop/src/commands.ts:19-32 (matchesShortcut compares e.key)`, `apps/desktop/src/actions.ts:1845 (player.machineSpeed Shift+,)`  
  Fix: Match punctuation and Alt combinations on e.code (Comma, BracketLeft, KeyH, Digit1...) as well as e.key, or normalise shifted symbols; add a table-driven test for every manual shortcut.
- **Reviewer-reproduced**: Put the text on the line ignores the lettering's own rotation and size handles  
  Where: `apps/desktop/src/features.ts:290-307 (line 297 subtracts only transform.x/y)`, `engine/threadline_engine/layout.py:474-478 (text objects are then transformed by the full transform)`  
  Fix: When putting text on a line, first bake the text's scale/rotate/flip into size_mm and a plain translation (or invert the full transform when computing the local path points).
- **Reviewer-reproduced**: Text longer than its line piles up at the ends with no warning; a line drawn right to left gives upside-down text  
  Where: `engine/threadline_engine/lettering.py:465-497 (s_mid clamped to 0..length; comment says 'the warning below says so' but there is none)`, `apps/desktop/src/features.ts:290-307`  
  Fix: Add a warning like the circle one when total > path length (and maybe offer to shrink), and reverse the path automatically when it runs mostly right to left.
- **Reviewer-reproduced**: Fabric: 'anything you set by hand wins' is false for density, and lettering ignores the fabric completely  
  Where: `engine/threadline_engine/fabrics.py:63-81 (line 72 always divides spacing_mm by the fabric density)`, `engine/threadline_engine/layout.py:442 (objects go through fabrics.apply) vs 459-502 (_text_block does not)`  
  Fix: Mark density as user-set (e.g. only scale spacing when it was never touched) or reword the manual to 'density is scaled by the fabric'; decide whether lettering should get the fabric underlay/density ...
- **Reviewer-reproduced**: Sew in the shortest order does far less than documented and then says the order is already short  
  Where: `engine/threadline_engine/layout.py:554-608 (optimize_order: run needs >2 shapes, same kind and thread, and NO pair with overlapping bounding boxes)`, `apps/desktop/src/features.ts:229-242 (line 235 message)`  
  Fix: Reorder per group of mutually non-overlapping shapes using real geometry overlap, ignore stitch type when threads match, and change the 'already short' message to say why nothing moved.
- **Reviewer-reproduced**: Knockdown 'set its thread to match the fabric' is impossible: its colour block has no edit button  
  Where: `apps/desktop/src/components/InfoPanel.tsx:983-1008 (edit/remove buttons hidden when a block has no sources)`, `engine/threadline_engine/layout.py:307, 704-714 (knockdown and basting blocks are created with sources=[])`  
  Fix: Store knockdown.thread (and basting thread) in the layout, show the pencil for those two blocks and pass the choice to the engine, or delete the sentence from the manual and in-app help.
- **Reviewer-reproduced**: Trim jumps longer than 3 mm only covers designs that existed when it was ticked, yet stays ticked  
  Where: `apps/desktop/src/design/layout.ts:397-413 (op added to each current item; setting read from the first item with it)`, `apps/desktop/src/actions.ts:1315-1318`  
  Fix: Keep the setting once at layout level (e.g. layout.jumps_to_trims_mm) and have the engine apply it to every item at render time.

### docs-c

- **Reviewer-reproduced**: In-app Help (F1) text has wrong keys and stale UI names, and leaves out whole features; the manual says Help 'searches this same material'  
  Where: `engine/threadline_engine/ai/helpdocs.py:48 ('The Text tool (T)': Text is Shift+T, T is realistic thread)`, `engine/threadline_engine/ai/helpdocs.py:29 ('Pin in place on the Shape tab': the tabs were replaced by folding sections; Pin is in the header and Ctrl+L)`  
  Fix: Correct the three lines, add Batch convert / stop+trim at the needle / trim jumps / hand tool sections and the missing shortcuts, and add a pytest that extracts shortcuts from the guide and checks ...
- **Reviewer-reproduced**: Text on a drawn line that is longer than the line piles its extra letters at the line ends with no warning; the code comment claims a warning exists  
  Where: `engine/threadline_engine/lettering.py:481 (s_mid clamped to the line's ends)`, `engine/threadline_engine/lettering.py:495-496 (no-op 'objects = objects  # ... the warning below says so'; no warning is emitted)`  
  Fix: In _along_path (or layout_text) append a warning when total > line length ('The text is longer than the line; make the letters smaller or the line longer'), and drop the misleading comment and no-op.
- **Reviewer-reproduced**: Stitch-edit moves are stored as world-space deltas applied after the design's transform, so rotating, resizing or mirroring the design afterwards displaces the edited stitches; the code comment says the opposite  
  Where: `engine/threadline_engine/layout.py:177-194 (_move_stitches; docstring says they 'stay where you put them relative to the design')`, `engine/threadline_engine/layout.py:673-676 (called after _transform)`  
  Fix: Store the delta in the design's own frame (apply _move_stitches before _transform, or inverse-transform dx/dy when recording the op).
- **Reviewer-reproduced**: 'Sew in the shortest order' does nothing if any two shapes in a run overlap, and then says the order is 'already about as short as it gets'; docs imply per-shape handling  
  Where: `engine/threadline_engine/layout.py:590 (all-or-nothing: len(run) > 2 and not any(overlap(...)))`, `engine/threadline_engine/layout.py:568-572 (run key includes the object kind, so a red fill and a red satin are never reordered together)`  
  Fix: Split each run into groups that overlap and reorder only the non-overlapping ones (or reorder around fixed overlapping shapes); change the kind from the run key to the thread key; make the ...

### export

- **Confirmed**: Deleting all stitches of a colour leaves an empty colour block, so export keeps a pointless colour change (previously QA M3, still open)  
  Where: `engine/threadline_engine/layout.py:164-174`, `engine/threadline_engine/layout.py:647`  
  Fix: In render() (engine/threadline_engine/layout.py), replace the three `if blk.recs` filters at 647, 664 and 693 with `any(r[2] == pe.STITCH for r in blk.recs)`. A single pass over all_blocks just ...
- **Confirmed**: Text on a drawn line (open or closed) that is much longer than the line stacks the extra letters on the line's ends, and nothing warns: render, Check-before-stitching and the export preview are all clear  
  Where: `engine/threadline_engine/lettering.py:480-481 (s_mid clamp that stacks letters)`, `engine/threadline_engine/lettering.py:495-497 (no-op placeholder whose comment says a warning follows; none does)`  
  Fix: Have _along_path also return a warning (or return the clamp count): when total > length (or any s_mid was clamped), append 'The text is longer than the line; shorten it, make the letters smaller or ...
- **Confirmed**: JEF header extents and hoop code assume the design is centred on the origin; designs converted from the owner's PES files are not  
  Where: `engine/.venv/Lib/site-packages/pyembroidery/JefWriter.py:94-110 (extents = half the bbox on both sides; hoop code from bbox size, line 97)`, `engine/.venv/Lib/site-packages/pyembroidery/JefWriter.py:107-125 (hoop-edge distances derived from the same half-widths)`  
  Fix: In design.write (design.py:169), the single funnel that export, convert_folder, layout.export and export_split all call, for ext == 'jef' copy the pattern and call move_center_to_origin() before ...
- **Confirmed**: JEF export turns every stitch longer than 12.7 mm (per axis) into a jump plus a half-length stitch  
  Where: `engine/threadline_engine/design.py:30-35`, `engine/threadline_engine/design.py:171-174`  
  Fix: In design.write() (design.py:171-174), start the settings dict with 'long_stitch_contingency': pe.CONTINGENCY_LONG_STITCH_SEW_TO for every format, not only JEF, so DST, EXP and the others are covered ...
- **Confirmed**: PES export fails above 255 colour steps (cut-stops make one per trim), the PE550D profile has no limit, so no warning is shown  
  Where: `engine/threadline_engine/profiles.py:34 (also :55 and :76, all built-ins have max_colors None)`, `engine/threadline_engine/prepare.py:170-171 (early return when no machine, so no format-level check can exist)`  
  Fix: 1) Add a format-level check in `prepare.check` for `ext == 'pes'` that raises the existing `max_colors` error when `steps > 255`. Place it before the `if not opts.machine: return` at line 170, so it ...
- **Confirmed**: Export is not atomic: any writer error leaves a truncated or corrupt file at the destination and destroys the previous file  
  Where: `engine/threadline_engine/design.py:169-176 (write: the root cause)`, `engine/threadline_engine/design.py:191 (design.export)`  
  Fix: In `design.write()`, write to a temp file in the same folder, call `os.replace(tmp, dest)` on success, and unlink the temp file in the `except` branch. The temp name must keep the real extension ...
- **Confirmed**: A non-ASCII character in a thread name corrupts the whole PES v6 thread table  
  Where: `engine/.venv/Lib/site-packages/pyembroidery/PESWriter.py:218-225 (write_pes_string_8, root cause)`, `engine/.venv/Lib/site-packages/pyembroidery/PESWriter.py:228-233 (write_pes_string_16, same bug; used for block names, not threads)`  
  Fix: LUDD cannot edit the vendored library, so fix it in `design.write` (design.py:169-176), the single choke point for every PES export. For ext == 'pes', copy the threadlist with description, ...
- **Confirmed**: 'One file per name' bypasses the machine settings, silently overwrites, and writes to device names (also: fuzz-rpc)  
  Where: `apps/desktop/src/features.ts:316-329 (exportNames; options {} at :322, sanitiser at :321, report ignored)`, `apps/desktop/src/components/FeatureDialogs.tsx:197,216-230 (list not de-duplicated; folder picker, so no replace prompt)`  
  Fix: In exportNames, pass `exportOptions(defaultCutStops(machine, design))` (machine, hoop, cut_stops) instead of `{}`, and collect each result's `warnings` (hoop_too_big, max_stitches) into one summary ...
- **Confirmed**: Stitch-edit moves are stored as world-space deltas, so they are wrong after the design is later rotated, flipped, resized, duplicated-then-turned or mirror-repeated  
  Where: `engine/threadline_engine/layout.py:177-193`, `engine/threadline_engine/layout.py:675-676`  
  Fix: Store move_stitch in source-file space. In features.ts moveSelectedStitches, convert the world drag delta with the inverse of the item's current transform (undo rotate, then divide by scale_x and ...

### fill

- **Confirmed**: Wave fill: rows drift apart and bunch up (gaps to ~0.9 mm and rows touching at default 0.4 mm spacing)  
  Where: `engine/threadline_engine/digitize/stitches.py:557-574 (region_points; ripple at 564-571 is evaluated only at needle points)`, `engine/threadline_engine/digitize/stitches.py:563 (per-row brick offset (r % 3) * stitch / 3 means rows sample the sine at different phases)`  
  Fix: In region_points, when `wave` is set, sample each row at no more than wave_length/4 to /6 (about 1.3-2 mm at the default wave length) so every row follows the sine closely. Alternatively give wave ...
- **Confirmed**: Stipple fill sews only the largest grid-connected patch; any other part of the shape is silently left unfilled (no warning)  
  Where: `engine/threadline_engine/digitize/patterns.py:80-88 (cells kept only where the cell centre lies inside poly.buffer(-0.45*size))`, `engine/threadline_engine/digitize/patterns.py:112-115 (shapes = _polys(tree); biggest = max(shapes, key=area) discards the other patches)`  
  Fix: In stipple_path, build a line for every patch in `shapes` instead of only `biggest`. Return a list of rings and have _open_pattern (stitches.py:605-608) join them with travel(). Add a warning (or a ...
- **Confirmed**: fill and applique silently stitch only one part of a shape that crosses itself or is split by a hole (buffer(0) / max(geoms))  
  Where: `engine/threadline_engine/digitize/stitches.py:459 (buffer(0) already discards a bow-tie lobe)`, `engine/threadline_engine/digitize/stitches.py:462-463 (max(poly.geoms) drops the other parts of a split shape)`  
  Fix: In fill_polygon and outline_ring, replace `.buffer(0)` with `shapely.make_valid(...)` and keep every Polygon part (drop only slivers under the area threshold). Return the parts, stitch each (tatami ...
- **Confirmed**: Fill underlay ignores every part but the largest: a lobe behind a narrow neck gets none, any split-off nub drops the edge run for the whole shape, and hole edges never get an edge run  
  Where: `engine/threadline_engine/digitize/stitches.py:631-635 (edge run only if poly.buffer(-0.5) is a single Polygon, and only its exterior ring)`, `engine/threadline_engine/digitize/stitches.py:637-648 (cross-hatch keeps only the largest part of poly.buffer(-0.6), at 641-642)`  
  Fix: In fill() (stitches.py:631-648), loop the edge run over every geometry in poly.buffer(-0.5) and over each ring in (part.exterior, *part.interiors), joining the rings with travel(..., poly). Pass the ...
- **Confirmed**: Fill generation is very slow for concave outlines or shapes with many holes (travel re-buffers the polygon on every region join)  
  Where: `engine/threadline_engine/digitize/stitches.py:80 (inside.buffer(-0.3) per _edge_route call)`, `engine/threadline_engine/digitize/stitches.py:101 (inside.buffer(1e-6) per candidate route)`  
  Fix: In tatami(), compute `cover = inside.buffer(1e-6)` once (call shapely.prepare on it) and `zone = inside.buffer(-0.3)` once. Pass both into travel() and _edge_route() instead of rebuilding them on ...
- **Confirmed**: Default Satin-look lettering sews 7.0 mm stitches, so the 'long loose stitches (up to 7.0 mm)' warning fires on ordinary names  
  Where: `engine/threadline_engine/quality.py:27 (LONG_MM = 7.0)`, `engine/threadline_engine/quality.py:186 (long_ = lengths > LONG_MM: strict compare, no tolerance)`  
  Fix: Preferred: give the comparison a tolerance in quality.py:186, e.g. `long_ = lengths > LONG_MM + 0.05`. That absorbs float noise and the 0.1 mm export rounding (the saved files reach 7.033 mm), it ...

### fuzz-rpc

- **Confirmed**: Text on a drawn line that is shorter than the text piles the extra letters up at the ends with no warning  
  Where: `engine/threadline_engine/lettering.py:495-496 (no-op `objects = objects`; the warning the comment promises is never created)`, `engine/threadline_engine/lettering.py:434 (path branch returns `warnings` that never contains a path warning; compare the arc/circle warning at 460-461)`  
  Fix: Make `_along_path` return a warning (or return `(objects, warnings)`) when `total > length + 1e-6`, for example "The text is longer than the line by N mm; letters at the ends overlap. Draw a longer ...
- **Confirmed**: "Fewer jumps" is uncached and quadratic: every render and every quality check takes 10-80 s with 100-200 same-colour shapes  
  Where: `engine/threadline_engine/layout.py:536-551 (covers built for every digitized block even when none join; unary_union(covers[i:]) per join is quadratic)`, `engine/threadline_engine/layout.py:311-327 (_stitched_area and _cover: simplify, buffer and union per block, uncached)`  
  Fix: Cache each shape's cover next to its stitches in `_object_cache`. Compute the "later covers" union once in a backwards pass (suffix unions), or test the path against only the covers whose bounds ...
- **Confirmed**: travel_under combined with "sort by colour" sews the hidden travel stitches on top of the finished covering shape  
  Where: `engine/threadline_engine/layout.py:696-698 (join with 'hidden' judged against the pre-sort order, then _color_sort reorders)`, `engine/threadline_engine/layout.py:536-551 (_join_same_thread_objects: covers[i:] is the pre-sort 'later')`  
  Fix: Group the blocks by thread (stable, first-appearance order, without merging) before calling `_join_same_thread_objects`, so that `covers[i:]` is the final sewing order. I prototyped this by ...
- **Confirmed**: One bad input line (or one non-serialisable result) kills the engine for the whole session, and the UI never restarts it  
  Where: `engine/threadline_engine/rpc.py:40-45 (is_background json.loads catches only JSONDecodeError, so ValueError/RecursionError escape from the main loop)`, `engine/threadline_engine/rpc.py:47-52 (handle_line json.loads: same narrow except)`  
  Fix: In rpc.py, wrap the whole per-line body of serve()/answer() in try/except Exception and reply with a -32700 or -32603 error (also catch ValueError/RecursionError in is_background and handle_line). ...
- **Confirmed**: JEF export turns stitches over 12.7 mm into jump+stitch pairs (profile max_stitch is a no-op); preview and quality checks describe stitches the file does not contain  
  Where: `engine/threadline_engine/prepare.py:226-231 (write_settings passes only max_stitch, which equals JefWriter's own default of 127)`, `engine/threadline_engine/design.py:169-176 (write() calls pe.write with no long_stitch_contingency; WRITE_SETTINGS at design.py:30-35)`  
  Fix: In write_settings (prepare.py:226) always return "long_stitch_contingency": pe.CONTINGENCY_LONG_STITCH_SEW_TO, plus the profile's max_stitch. Better, split over-length stitches inside prepare() ...
- **Confirmed**: Stitch-edit moves are stored as world-space deltas: they do not follow the design when it is later rotated, scaled or flipped  
  Where: `engine/threadline_engine/layout.py:177-193 (_move_stitches adds dx*10, dy*10 to placed coordinates; docstring is misleading)`, `engine/threadline_engine/layout.py:675-676 (_transform, then _move_stitches)`  
  Fix: In features.ts moveSelectedStitches, convert the canvas delta to the design's own frame using the item's current transform (rotate by -rotate, divide by scale_x / scale_y, apply the flip signs). In ...
- **Confirmed**: A stop/trim inserted into a drawn shape is stored by stitch index and moves (or silently vanishes) when the shape is edited  
  Where: `engine/threadline_engine/layout.py:148-175 (_apply_ops: insert matched on r[4])`, `engine/threadline_engine/layout.py:448 (for drawn objects r[4] is the list position of the freshly generated stitch)`  
  Fix: For drawn shapes (kind in OBJECT_KINDS), do not key an insert by stitch index. Either store the insertion as a position (x/y in mm in the shape's own frame, snapped at apply time to the nearest ...

### layout-ops

- **Confirmed**: Cover test treats gaps and holes under 1.6 mm as solid, so travel is 'hidden' where the thread is plainly visible  
  Where: `engine/threadline_engine/layout.py:327`, `engine/threadline_engine/layout.py:530-533`  
  Fix: Give _cover its own tighter closing radius instead of the knockdown-tuned values. For example build the cover from the stitch lines with buffer(0.35, quad_segs=2).buffer(-0.35, quad_segs=2) and then ...
- **Confirmed**: Stitch-edit moves (move_stitch) are page-space offsets applied after the item transform, so a later rotate, flip, scale, or Repeat (circle with turn, or mirror x4) leaves the moved stitch displaced from where the user put it in the design  
  Where: `engine/threadline_engine/layout.py:177-193`, `engine/threadline_engine/layout.py:673-676`  
  Fix: Store the delta in file space and apply it before the transform. In features.ts moveSelectedStitches, convert the page-space drag with the inverse of the item's flip, scale and rotate (v = F^-1 S^-1 ...
- **Confirmed**: In Edit-stitches mode, Delete/Backspace with nothing selected removes the whole design  
  Where: `apps/desktop/src/actions.ts:1538-1551`, `apps/desktop/src/actions.ts:1717-1718`  
  Fix: Make stitch.deleteSelected and stitch.deleteSelectedAlt enabled whenever stitchEdit is non-null; deleteSelectedStitches already no-ops on an empty selection, so the key is swallowed and never reaches ...
- **Confirmed**: A user-inserted stop or trim is silently dropped when the stitch it follows is deleted, and its record stays behind when that stitch is moved  
  Where: `engine/threadline_engine/layout.py:165-170`, `engine/threadline_engine/layout.py:189-193`  
  Fix: In `_apply_ops` (layout.py:165-170), when a stitch is in `gone`, still append its inserts, positioned at the last kept record, or at the deleted stitch's own x/y if none was kept, before the ...
- **Confirmed**: 'Sew in the shortest order' is defeated when Fewer jumps is on: hidden travel stitches are tagged with the next item, so its start point is wrong  
  Where: `engine/threadline_engine/layout.py:564-566 (ends() takes the first STITCH of the item, which can be a hidden-travel stitch)`, `engine/threadline_engine/layout.py:520 (hidden travel stitches get item = sb[3], src = -1)`  
  Fix: In optimize_order.ends() (layout.py:565) skip hidden-travel stitches by also requiring `src_of[i] >= 0`: zip r.pattern.stitches, r.item_of and r.src_of, and add `and sr >= 0`. Applied in a scratch ...
- **Confirmed**: 'Sew in the shortest order' does nothing for mixed fills and lines, and one overlapping pair (judged by bounding box) disables it for every other shape in the run  
  Where: `engine/threadline_engine/layout.py:572 (kind in key())`, `engine/threadline_engine/layout.py:574-578 (overlap() uses bounding boxes only)`  
  Fix: Drop it.get('kind') from key(), so a run is any consecutive drawn shapes in one thread. Replace the whole-run veto at line 590 with a constrained nearest-neighbour pass: a shape may be picked next ...

### layout-order

- **Confirmed**: The "Overlap between hoopings" slider does not set any overlap: it only nudges the hoop count, and the number shown is not the real overlap  
  Where: `engine/threadline_engine/split.py:107-123 (overlap only feeds the cols/rows count; window overlap is w - cw regardless of the setting)`, `engine/threadline_engine/split.py:144-156 and 206-207 (runs cut exactly on the cell seam, zero sewn overlap)`  
  Fix: Make the number true. Pick the hoop count as `cols = ceil(W / (w - ov))` (and the same for rows), so every neighbouring window overlap `w - cw` is at least `ov`; verified by reasoning, not run. If a ...
- **Confirmed**: Dense and needle-hit checks flag every one of the 11 reference PES designs, so Save for machine always warns "needles can break"  
  Where: `engine/threadline_engine/quality.py:22-29 (DENSE_MM_PER_MM2 = 7.0, HITS_PER_MM2 = 20, module header 5-10 admits they are unconfirmed)`, `engine/threadline_engine/quality.py:161-175 (dense and needle_hits checks)`  
  Fix: Recalibrate the limits against the fixtures: dense near 15 to 20 mm/mm2 and hits near 40 to 80. Add a snapshot or test that opens a fixture and expects no dense warning. For items with kind ...
- **Confirmed**: Default satin lettering trips "long loose stitches (up to 7.0 mm)" because of float noise at exactly the 7 mm limit  
  Where: `engine/threadline_engine/quality.py:27 (LONG_MM = 7.0)`, `engine/threadline_engine/quality.py:186 (long_ = lengths > LONG_MM, no tolerance)`  
  Fix: In quality.py:186 use `lengths > LONG_MM + 0.05` (or round lengths to 0.01 mm first). 0.05 also absorbs the up to about 0.07 mm added by 0.1 mm export quantisation, since written PES and JEF files ...
- **Confirmed**: Gap check silently switches off above 80 drawn shapes; panel and Save-for-machine then report "Nothing to fix"  
  Where: `engine/threadline_engine/quality.py:29 (GAP_MAX_OBJECTS = 80)`, `engine/threadline_engine/quality.py:117 (early return [] when len(lines) > GAP_MAX_OBJECTS)`  
  Fix: In quality._gaps, drop the len(lines) > GAP_MAX_OBJECTS early return and use a shapely STRtree over the buffered per-item shapes (query with each shape's envelope grown by GAP_MM) so only neighbours ...
- **Confirmed**: "One file per name" ignores the machine profile: no cut-stops, no hoop check, and its report is discarded (also: shapeops)  
  Where: `apps/desktop/src/features.ts:322 (layout.export called with options: {}; the returned report/warnings are discarded)`, `apps/desktop/src/features.ts:310-331 (exportNames: no machine, hoop or cut-stop options, no per-name warning handling)`  
  Fix: In exportNames, build options with exportOptions(defaultCutStops(machine, design)), taking the machine from the store and the design from the store (or from layout.preview_export). Collect each ...
- **Confirmed**: shortestOrder commits a stale copy of the layout, dropping edits (or swapping in the old design) made while the engine is working  
  Where: `apps/desktop/src/features.ts:230-242 (stale `l` read at :231, reused at :236-237)`, `apps/desktop/src/actions.ts:199-202 (commit has no staleness check)`  
  Fix: In shortestOrder, remember `const before = currentDoc()` and, after the await, return if `currentDoc() !== before` (or only if the document identity changed; reusing the latest layout is enough for ...
- **Confirmed**: Design slightly over the hoop (e.g. 0.4 mm) defaults to a recommended multi-hooping split, with no shrink-to-fit offer  
  Where: `apps/desktop/src/components/ExportDialog.tsx:73 (split defaults to true)`, `apps/desktop/src/components/ExportDialog.tsx:109-110,170-171,185-193 (tooBig, splitting, 'sews in N hoopings', '(recommended)')`  
  Fix: In ExportDialog (and the Design panel fit line), when 0 < over% <= about 5% compute s = min(hoop.w / w, hoop.h / h) * 0.995 and show "Make it {100*(1-s)}% smaller to fit in one hooping" as the first ...
- **Confirmed**: Alignment crosses are placed on stitched area; hooping 2's start crosses are sewn first and then buried under its own fill  
  Where: `engine/threadline_engine/split.py:161-184 (_marks: 20%/80% of the seam, clipped to design bounds only, never checks stitching)`, `engine/threadline_engine/split.py:229-230 and 237-238 (marks_start sewn before the design, marks_end after it)`  
  Fix: In `_marks`, generate candidate positions along the seam across the whole overlap of both windows, not just the design bounds, and keep those whose 3 mm cross box is clear of `layout._stitched_area` ...
- **Confirmed**: Sort colors can bury top layers under another colour, and the engine's "check the order" note is never shown in the UI  
  Where: `engine/threadline_engine/layout.py:265-281 (_color_sort groups by first appearance with no overlap test)`, `engine/threadline_engine/layout.py:697-700 (only an info-level color_sort warning)`  
  Fix: In _color_sort, do not pull a block ahead of an intervening different-thread block whose stitched area overlaps it (or run quality's overlap test and fall back to the original order for those ...
- **Confirmed**: "Sew in the shortest order" misses its saving (can report "already as short as it gets") when moves between same-thread shapes are hidden under later stitching (Fewer jumps & trims, the new-design default)  
  Where: `engine/threadline_engine/layout.py:520 (hidden-travel stitches written with item=sb[3], src=-1, so they count as the next shape's stitches)`, `engine/threadline_engine/layout.py:564-566 (ends() takes the first and last STITCH with item_of == idx, travel stitches included)`  
  Fix: In optimize_order's ends(), use only a shape's own stitches: filter on `r.src_of[i] >= 0`, since every stitch a drawn shape produces has src >= 0 and the travel stitches have src -1. Or call ...
- **Confirmed**: optimize_order is all-or-nothing and only for 3+ consecutive same-kind shapes; one overlapping pair disables it, yet the UI says the order is already short  
  Where: `engine/threadline_engine/layout.py:590 (`len(run) > 2 and not any(overlap(a, b) ...)` over all pairs in the run: the all-or-nothing gate)`, `engine/threadline_engine/layout.py:574-578 (overlap() is bounding-box only; touching counts; missing bounds counts as overlap)`  
  Fix: In optimize_order, treat truly overlapping pairs (shapely intersection of the stitched area or outline, not bounding boxes) as precedence constraints and run the nearest-neighbour pass over only the ...
- **Confirmed**: Fewer jumps & trims (default on for new designs) makes every render, check and export 40-100x slower: about 3-6 s per edit at 100 shapes  
  Where: `engine/threadline_engine/layout.py:538-539 (_cover computed for every digitized block on every render, uncached, even when there is nothing to join)`, `engine/threadline_engine/layout.py:530-533 and 311-327 (_cover -> _stitched_area: line buffer plus union plus negative buffer, about 25 ms per shape)`  
  Fix: Cache each block's cover keyed by its object hash (as _object_cache does) so unchanged shapes cost nothing on later edits. Replace the per-join unary_union(covers[i:]) with a cheaper test: build an ...
- **Confirmed**: Basting box counts toward hoop fit: a 90 mm design on the 4x4 hoop becomes "too big" and defaults to a 2-hooping split; margin has no UI  
  Where: `engine/threadline_engine/layout.py:284-302 (_basting expands bounds by margin_mm*10) and 710-714 (box inserted before the summary is computed)`, `engine/threadline_engine/layout.py:790-795 (split_plan) and 798-815 (export_split) both split the pattern that includes the box`  
  Fix: In layout.render (the basting step at layout.py:710-714), take the hoop and clamp margin_mm to (hoop size minus the design extent) / 2, with a floor of about 2 mm. If even the minimum does not fit, ...
- **Suspected**: Knockdown thread cannot be set from the UI although the manual says to set it to match the fabric  
  Where: `docs/USER-MANUAL.md:505-506`, `apps/desktop/src/actions.ts:1160-1163 (toggle only)`  
  Fix: Show the thread picker for the knockdown row (writing layout.knockdown.thread) and tell basting/knockdown apart from each other in InfoPanel rather than lumping all sourceless blocks together.

### lettering

- **Confirmed**: Characters the font can't draw are silently swapped for '?' or dropped; text with nothing drawable gives an empty design and an empty PES with no message  
  Where: `engine/threadline_engine/lettering.py:289-293 (outline font: missing glyph becomes '?', or is skipped if no '?')`, `engine/threadline_engine/lettering.py:340-343 (stitch font: unknown character skipped)`  
  Fix: In _outline_glyphs and _stitch_font_glyphs, collect the characters with no real glyph (include the '?' substitution case when the typed character wasn't '?'), and return them through a new warning in ...
- **Confirmed**: Stitch fonts: Save-as-stitch-font exports only 69 characters, no case/accent fallback, Satin/Fill toggle does nothing, and the file isn't saved where LUDD looks  
  Where: `apps/desktop/src/actions.ts:892-908 (save dialog 894-898 passes only a file name; chars string line 901; toast line 904 gives no path)`, `apps/desktop/src/components/TextPanel.tsx:166-173 (Satin/Fill buttons shown for stitch fonts), 247-248 (Save button not guarded against a stitch-font source)`  
  Fix: In export_stitch_font, loop over every cmap character that has outlines. Add a 'kern' map (or bake kerning into the advances) to the .luddfont. In _stitch_font_glyphs, try the other case for a ...
- **Confirmed**: Damaged or odd stitch fonts give raw Python errors, and one wrong-typed field breaks the font list for every font  
  Where: `engine/threadline_engine/lettering.py:96-98 (stitch-font entry takes meta.get('name') unchecked; meta may be a non-dict, name may be a non-string)`, `engine/threadline_engine/lettering.py:117-119 (the sort calls e['family'].lower(); the AttributeError is raised here, after the index is written at 112-116)`  
  Fix: In `list_fonts`, require `isinstance(meta, dict)` and use `family = str(meta.get("name") or f.stem)`; sort on `str(e["family"]).lower()`. In `_load_stitch_font`, check the parsed value is a dict with ...
- **Confirmed**: Edited or replaced font file (stitch font or TTF at the same path) isn't picked up until the engine restarts: text layout cache key ignores the file  
  Where: `engine/threadline_engine/layout.py:456-472 (_text_cache keyed by the spec JSON only; font is just path/index/family/style)`, `engine/threadline_engine/lettering.py:192-222 (_fonts keyed by (path, index), no mtime; TTF/OTF only, stitch fonts are re-read each call at lettering.py:264-271)`  
  Fix: After resolve_font, add (st_mtime_ns, st_size) of font["path"] to the spec used to build the _text_cache key in layout._text_block (resolve the font there, or have lettering expose a ...
- **Confirmed**: The Fabric setting has no effect on lettering (identical stitches for knit, towel and stretch)  
  Where: `engine/threadline_engine/layout.py:459-502 (_text_block takes no fabric and never calls fabrics.apply)`, `engine/threadline_engine/layout.py:633-634 vs 650 (render passes layout.get('fabric') only to _object_blocks; fabrics.apply at 442)`  
  Fix: Pass layout['fabric'] into _text_block and run each letter object through fabrics.apply before _generate_cached (include the fabric in the stitch cache key). Also set pull_comp_mm and underlay to ...
- **Confirmed**: 'Letter height (capitals)' is wrong (up to +18%/-10%) for Segoe Script/Print, MS Gothic, Yu Gothic UI and Mongolian Baiti: the engine trusts OS/2 sCapHeight over the real H  
  Where: `engine/threadline_engine/lettering.py:207-214 (_load: the measured H is used only when sCapHeight is 0)`, `engine/threadline_engine/lettering.py:285 (scale = size_mm / lf.cap)`  
  Fix: In _load (lettering.py:206-214), when 'H' is in the cmap, always set cap to the H's measured max y. Fall back to sCapHeight, then upm*0.7, only when there is no H or its outline is empty. Add a test ...
- **Confirmed**: One file per name overwrites existing files and silently merges colliding names, then reports the wrong count  
  Where: `apps/desktop/src/features.ts:316-331 (exportNames: clean list, safe name at 324, done++ and 'Saved N files' at 326-328)`, `apps/desktop/src/components/FeatureDialogs.tsx:204-227 (NamesDialog: pickFolder then exportNames with no confirmation or preview of file names)`  
  Fix: In exportNames, build the list of destination file names first: sanitise, avoid Windows reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9, prefix with an underscore), de-duplicate case-insensitively ...
- **Confirmed**: Text on a line longer than the line: extra letters pile up on the two ends, with no warning  
  Where: `engine/threadline_engine/lettering.py:481 (s_mid clamped to [0, length])`, `engine/threadline_engine/lettering.py:495-496 (no-op `objects = objects`; comment promises a warning that does not exist)`  
  Fix: In _along_path compute overflow = total - length. If it is above about 0.5 mm, return a warning ('The text is N mm longer than the line; draw a longer line or make the letters smaller') through ...
- **Confirmed**: Put the text on the line ignores the text's rotate/flip, and turning, resizing or mirroring text on a line pivots about the anchor so it leaves the line  
  Where: `apps/desktop/src/features.ts:290-307 (textOnLine: nodes = world - (t.x,t.y) only; rotate/scale/flip kept)`, `apps/desktop/src/design/layout.ts:184-188 (rotateBy, text branch), 203-213 (mirror), 225-229 (scaleBy, text branch), 311-335 (transformTogether assumes each item turns about its own centre)`  
  Fix: In textOnLine, reset the text transform to identity (rotate 0, scale 1, no flips) and put x,y at the line's middle point (the point at half its length, where _along_path centres the letters). Express ...
- **Confirmed**: Satin angle is chosen on the upright letter and never turned with it: arcs, circles, paths and rotated text lose the satin look  
  Where: `engine/threadline_engine/lettering.py:313 (angle_deg set from the upright glyph)`, `engine/threadline_engine/lettering.py:318-331 (_satin_angle)`  
  Fix: Make the angle follow the geometry. The cleanest place is dz.transform_geometry (stitches.py:708): for kind == 'fill' with params.angle_deg, add t.rotate and negate the angle on each of flip_x / ...
- **Confirmed**: Glyph winding rule is approximate: filled islands inside holes and separate parts wound the other way are dropped  
  Where: `engine/threadline_engine/lettering.py:230-258 (_glyph_shapes; lines 242-254 classify contours as adds or cuts by comparing direction to the largest contour, then union(adds) minus union(cuts))`, `docs/CHANGELOG.md:121 (claim that letters follow the font's winding rule; true for ordinary text only)`  
  Fix: In _glyph_shapes, replace the add/cut classification with a non-zero winding fill. Polygonize unary_union of all contour LinearRings, give each face a winding sum from every contour that contains its ...
- **Confirmed**: 'Circle' text shape is the same code path as 'Arch' (arc_up): it does not spread letters round the ring, contrary to its tooltip  
  Where: `engine/threadline_engine/lettering.py:446 (else branch shared by arc_up and circle)`, `engine/threadline_engine/lettering.py:460 (the only other kind check; the 'longer than the circle' warning is the same for all curved shapes)`  
  Fix: In lettering.py, give kind == "circle" its own branch. Compute extra = (2*pi*radius - total) / len(glyphs) and add it to each glyph's pitch (clamped at 0 when the text is already longer than the ...
- **Confirmed**: Smile (arc_down) text and text on a V-shaped line: neighbouring letters overlap, at default settings for common words, with no warning  
  Where: `engine/threadline_engine/lettering.py:443-444 (arc_down: r = radius + size, then phi = pi/2 - centre / r, so the pitch is measured on the baseline radius)`, `engine/threadline_engine/lettering.py:479-493 (_along_path: rigid letters placed by tangent at their centre, so the inside of a corner overlaps)`  
  Fix: In layout_text arc_down, use the inner radius for the angle: `phi = math.pi/2 - centre/radius`, keeping r = radius + size only for placement. I checked on a scratch copy that this gives 0.0 overlap ...
- **Suspected**: Text box can lose characters typed while a render is in flight (draft reset by an effect)  
  Where: `apps/desktop/src/components/TextPanel.tsx:87 (useEffect(() => setDraft(item.text), [item.text]))`, `apps/desktop/src/components/TextPanel.tsx:99-102 and 113-121 (debounced commit, 450 ms)`  
  Fix: Only setDraft when document.activeElement !== input.current or when item.id changes; and skip the reset while a commit is pending (compare the draft to the last committed value).

### live-esc

- **Reviewer-reproduced**: Window blur during a drag leaves a stale Esc hold: the next Esc press does nothing  
  Where: `apps/desktop/src/components/StitchCanvas.tsx:1188-1204`, `apps/desktop/src/components/StitchCanvas.tsx:1758`  
  Fix: In cancelDrag call the release before nulling it: `const rel = releaseEsc; releaseEsc = null; rel?.();` (harmless when Esc already popped it). Add a vitest/Playwright check that blur mid-drag leaves ...
- **Reviewer-reproduced**: 'One file per name' dialog defaults to PES even when the machine is a JEF machine  
  Where: `apps/desktop/src/components/FeatureDialogs.tsx:188-196`  
  Fix: Reset ext from defaultFormat(machine) in an effect when `open` becomes true, as in ExportDialog.
- **Reviewer-reproduced**: Knife armed then tool change or New/Open leaves a stale Esc hold (first Esc is swallowed)  
  Where: `apps/desktop/src/features.ts:162-171`, `apps/desktop/src/store.ts:414-424`  
  Fix: Mirror the other modes: subscribe to the store in features.ts and release releaseKnife when `knife` becomes null (or call releaseKnife in setTool / replaceDoc).
- **Reviewer-reproduced**: Modal dialog open + focus on the page body: Esc cannot close the dialog and runs the Esc commands behind it  
  Where: `apps/desktop/src/App.tsx:81-95`, `apps/desktop/src/App.tsx:109`  
  Fix: At the top of onKey add `if (document.querySelector('dialog[open]')) return;` (keep the existing closest check), so focus-on-body cannot leak keys or block the dialog's own Esc.
- **Reviewer-reproduced**: Stitch-edit mode (and its Esc hold) survives New / Open and deleting the file  
  Where: `apps/desktop/src/actions.ts:224-236`, `apps/desktop/src/features.ts:248-262`  
  Fix: Call endStitchEdit() (and clear knife/autoAll) in replaceDoc, and end stitch edit from a store subscription when the item id is no longer in the layout.
- **Reviewer-reproduced**: Panel-edge separator focused by keyboard: arrow keys resize the panel AND nudge the selected design  
  Where: `apps/desktop/src/components/PanelResizer.tsx:67-71`, `apps/desktop/src/App.tsx:98-109`  
  Fix: In the separator's onKeyDown call e.preventDefault() and e.stopPropagation() for handled keys, and/or make useShortcuts skip targets matching [role=separator].
- **Reviewer-reproduced**: Wheel zoom (or zoom/pan keys) during a move/scale/rotate drag puts the shape in the wrong place  
  Where: `apps/desktop/src/components/StitchCanvas.tsx:1327-1337`, `apps/desktop/src/components/StitchCanvas.tsx:1611-1631`  
  Fix: Store the grabbed world point at pointerdown and position the ghost from toWorld(current pointer) minus that point; or ignore wheel and zoom requests while `drag` is a ghost drag.
- **Reviewer-reproduced**: No pointer identity on the canvas: a second pointer leaves a phantom ghost, any pointerup ends the drag, pointercancel commits it  
  Where: `apps/desktop/src/components/StitchCanvas.tsx:1339-1348`, `apps/desktop/src/components/StitchCanvas.tsx:1634-1643`  
  Fix: Remember dragPointer and ignore pointermove/up/cancel from other ids; on pointercancel and on the stale-drop path call cancelDrag() (endGhost, overlay.visible = true) instead of committing.

### live-state

- **Reviewer-reproduced**: Duplicate (Ctrl+D / the panel's duplicate button) copies only the primary item when several are selected  
  Where: `apps/desktop/src/actions.ts:596-602 (uses targetId() only)`, `apps/desktop/src/actions.ts:1703`  
  Fix: Loop duplicateItem over selectionIds() in one layout and select all the copies.
- **Reviewer-reproduced**: Stitch-edit mode and the knife leak: stitchEdit survives Open/New with a dead id and a live Delete, and a cancelled knife leaves a phantom Esc hold  
  Where: `apps/desktop/src/actions.ts:224-236 (replaceDoc), apps/desktop/src/store.ts:403-413 (setHistory) never clear stitchEdit`, `apps/desktop/src/features.ts:159-172 (releaseKnife), 246-262 (releaseEdit)`  
  Fix: Use the subscribe-and-release pattern already used for autoTrace/autoAll for knife and stitchEdit, and clear stitchEdit in replaceDoc/setHistory when its item is gone.
- **Reviewer-reproduced**: Stitch-edit moves are stored as world-space offsets, so rotating, mirroring or resizing the design later shifts the moved stitches  
  Where: `engine/threadline_engine/layout.py:673-676 (ops applied, then _transform, then _move_stitches in world space), 177-193`, `apps/desktop/src/features.ts:278-285`  
  Fix: Apply move_stitch before _transform (in file coordinates, converting the drag delta through the inverse transform at edit time) so moves rotate and scale with the design.
- **Reviewer-reproduced**: Stitch-edit stores one move_stitch op per stitch per drag, so layouts, autosave and renders grow without bound  
  Where: `apps/desktop/src/features.ts:278-285 (one op per selected index)`, `apps/desktop/src/features.ts:265-269 (ops array copied each commit)`  
  Fix: Add a {op:'move_stitches', indices:[...], dx_mm, dy_mm} op and merge it with the previous move of the same indices.
- **Reviewer-reproduced**: Stitch-edit overlay redraws every needle point on each pointer move: about 200-350 ms per frame, 1 s stall on release, at 27k stitches  
  Where: `apps/desktop/src/components/StitchCanvas.tsx:732-756 (two full passes over all records per redraw)`, `apps/desktop/src/components/StitchCanvas.tsx:1560-1566 (redraw per pointer move while dragging a box or moving)`  
  Fix: Draw needle points only inside the viewport and above a zoom threshold, and cache the unselected-points Graphics between redraws.
- **Reviewer-reproduced**: The quality check runs on the same serial engine after every edit, is never cancelled, and costs about 2x a render, so each edit queues behind the previous edit's check  
  Where: `apps/desktop/src/actions.ts:393-419 (startChecks: 500 ms after each design change; seq only drops the reply)`, `engine/threadline_engine/rpc.py:92-100 (non-background methods run inline, one at a time)`  
  Fix: Run layout.check in a background thread (background=True) or skip it when another request is queued; reuse the render's result instead of rendering again.
- **Suspected**: If the engine process dies there is no restart, no clear message, and Save cannot work  
  Where: `apps/desktop/src/engine/sidecar.ts:43-47 (close/error handlers only set a status)`, `apps/desktop/src/App.tsx:52-74 (engine started once)`  
  Fix: Add a restart (re-run startEngine) on 'close', surface it in the status bar and as an error notice, and disable engine-dependent commands while disconnected.
- **Reviewer-reproduced**: Lettering text box reverts keystrokes typed while a slower update lands  
  Where: `apps/desktop/src/components/TextPanel.tsx:87 (useEffect(() => setDraft(item.text), [item.text]))`, `apps/desktop/src/components/TextPanel.tsx:99-120 (450 ms debounce commit)`  
  Fix: Only sync the draft from item.text when the input is not focused or the item id changes; coalesce consecutive text commits.
- **Reviewer-reproduced**: Clearing a number box and leaving it commits 0 (moves the design to 0,0, sets rotation 0)  
  Where: `apps/desktop/src/components/InfoPanel.tsx:78-87 (Number('') is 0 and passes Number.isFinite)`, `apps/desktop/src/components/InfoPanel.tsx:164-194 (Across, Down, Rotate commit the raw value)`  
  Fix: Treat text.trim() === '' as a revert (setText(value.toFixed(digits))) before onCommit.
- **Reviewer-reproduced**: Design browser: a slower earlier folder scan overwrites the newer folder's results and the saved folder  
  Where: `apps/desktop/src/components/FeatureDialogs.tsx:89-104 (scan has no request id; setDesigns/setBusy/savePrefs run for every reply)`, `apps/desktop/src/components/FeatureDialogs.tsx:129-138`  
  Fix: Keep a scan counter in a ref and ignore replies (and busy/pref updates) from older scans.
- **Reviewer-reproduced**: Autosave is off for the whole session while the crash-recovery banner is unanswered  
  Where: `apps/desktop/src/actions.ts:366,374 (return while recoveryWaiting)`, `apps/desktop/src/App.tsx:206-235 (non-modal banner)`  
  Fix: Write autosave to a second recovery slot while the first is pending.
- **Reviewer-reproduced**: Edits computed from a stale snapshot silently discard a concurrent edit: Delete, the Sewing-order arrows and 'Sew in the shortest order'  
  Where: `apps/desktop/src/actions.ts:581-594 (removeSelected reads s.history.present at :583 instead of currentDoc())`, `apps/desktop/src/components/InfoPanel.tsx:746,749 (reorder(layout, ...) uses the displayed layout)`  
  Fix: Use currentDoc()/currentLayout() in removeSelected and the reorder buttons; in shortestOrder apply the returned order to currentLayout() after the await.
- **Reviewer-reproduced**: A failed newest render throws away the earlier edit that rendered fine, and a superseded commit skips its follow-up (selection, tool)  
  Where: `apps/desktop/src/actions.ts:178-190 (older reply dropped at :180 even if it succeeded; failure of the newest only clears pending at :187)`, `apps/desktop/src/actions.ts:477-479, 601, 791, 822-825 (follow-ups guarded by `if (await commit(...))`)`  
  Fix: Track the last applied history; when the newest render fails, re-render the newest older history that has not failed (or apply the last successful reply), and make follow-ups depend on the final ...
- **Reviewer-reproduced**: Recover says 'Recovered your unsaved work' even when the recovered design cannot be shown, and then the recovery copy is deleted when the app closes  
  Where: `apps/desktop/src/actions.ts:440-457 (recoveryWaiting=false at :443, showHistory result ignored at :445, info at :453)`, `apps/desktop/src/App.tsx:216-224 (banner dismissed before restore runs)`  
  Fix: Use the boolean from showHistory: only set recoveryWaiting=false and show the success note when it is true; otherwise leave the banner and recovery file alone.
- **Reviewer-reproduced**: Success messages are shown (and replace the error) when the edit actually failed  
  Where: `apps/desktop/src/features.ts:109-123 (acceptWholePicture: 'Added N shapes' at :122; the preview is dismissed at :112 before the commit)`, `apps/desktop/src/features.ts:203-220 (mergeSelected :216), 130-155 (addOffset :151), 175-200 (finishKnife :196), 341-349 (saveColorway :348), 230-242 (shortestOrder :238)`  
  Fix: Gate each info() on the commit result, and dismiss the preview/guess only after the commit succeeds.
- **Reviewer-reproduced**: Quick repeated Rotate/Mirror/Scale of several selected things uses the last rendered bounds, so the group scatters  
  Where: `apps/desktop/src/actions.ts:516-529 (selectionGeometry reads s.design.items[i].bounds_mm)`, `apps/desktop/src/actions.ts:532-543 (editSelection)`  
  Fix: Compute centres from the pending layout (the engine bounds are only needed for stitch files) or wait for the in-flight render before applying a multi-item transform.
- **Reviewer-reproduced**: Switching tool with several things selected leaves hidden selected ids: the panel says 'N selected' with nothing highlighted, clicking one of them does nothing, Esc does nothing  
  Where: `apps/desktop/src/store.ts:414-425 (setTool clears selectedId but not extraIds)`, `apps/desktop/src/actions.ts:505-513 (selectionIds still counts extraIds), 546-561 (pickItem returns early at :559 for an id in the stale set), 1726 (Deselect enabled only when selectedId !== null)`  
  Fix: In setTool (non-select) also set extraIds: [] and selectedNode: null.

### packaging

- **Suspected**: If any build leg fails, the updater-manifest job is skipped and no latest.json is produced for anyone  
  Where: `C:/Users/Copper Felix/HTML Stuffs/threadline/.github/workflows/release.yml:44-46`, `C:/Users/Copper Felix/HTML Stuffs/threadline/.github/workflows/release.yml:144-145`  
  Fix: Add `if: ${{ !cancelled() && needs.create-release.result == 'success' }}` to updater-manifest. Add one RELEASING.md line: re-run failed jobs only, never Re-run all.
- **Suspected**: The packaged engine needs macOS 13/14 or newer (and Intel needs 14) but the app declares macOS 10.13; no OS minimums documented  
  Where: `apps/desktop/src-tauri/tauri.conf.json:27-76 (no bundle.macOS.minimumSystemVersion)`, `engine/uv.lock (onnxruntime macosx_14_0_arm64; opencv macosx_13_0_arm64 / macosx_14_0_x86_64; numpy macosx_14_0_*)`  
  Fix: Set `bundle.macOS.minimumSystemVersion` to "14.0" (or to "13.0" for Apple Silicon only, after fixing the onnxruntime marker). State the minimum macOS and Linux versions in USER-GUIDE and the release ...
- **Reviewer-reproduced**: Nothing ever runs the frozen engine: no smoke test in build_engine.py, ci.yml or release.yml, and the FFmpeg drop is not verified  
  Where: `C:/Users/Copper Felix/HTML Stuffs/threadline/.github/workflows/ci.yml:34-62`, `C:/Users/Copper Felix/HTML Stuffs/threadline/.github/workflows/release.yml:82-88`  
  Fix: Add a `--smoke` mode or a short scripts/smoke_engine.py that does the above. Call it at the end of build_engine.py (assert the spec edit applied) and as a CI step after `pnpm build:engine` on each ...
- **Suspected**: No single-instance handling and no macOS open-file event: double-clicking a .ludd either does nothing (Mac) or starts a second app that shares one recovery file  
  Where: `apps/desktop/src-tauri/src/lib.rs:1-19`, `apps/desktop/src-tauri/Cargo.toml:17-22 (no tauri-plugin-single-instance)`  
  Fix: Add `tauri-plugin-single-instance` that emits the file argument to the existing window, and handle `RunEvent::Opened` for macOS. Optionally key the autosave file by process id and sweep stale ones.
- **Reviewer-reproduced**: No third-party licence notices ship with the installer or app (OpenCV, ONNX Runtime, GEOS, NumPy, fonts under the SIL OFL)  
  Where: `apps/desktop/src-tauri/tauri.conf.json:51-55 (resources: samples only)`, `apps/desktop/src-tauri/tauri.conf.json:50 (licenseFile: LUDD's GPL only)`  
  Fix: Generate a notices file (`pnpm licenses list --json` plus `uv pip` licence metadata, with the OFL text for the two fonts). Add it to `bundle.resources` and link it from Settings.

### patterns

- **Confirmed**: Gradient with the default cross-hatch underlay never fades out  
  Where: `engine/threadline_engine/digitize/stitches.py:636-648`, `engine/threadline_engine/digitize/stitches.py:417-420`  
  Fix: In fill(), treat gradient like the open patterns for the tatami underlay: add "gradient" to the skip list at stitches.py:637 (keeping the edge run), or build the underlay only over the dense part of ...
- **Confirmed**: A self-crossing outline silently loses all but one loop (fills and applique)  
  Where: `engine/threadline_engine/digitize/stitches.py:454-464`, `engine/threadline_engine/digitize/applique.py:64-77`  
  Fix: In `fill_polygon`/`outline_ring`, compare the repaired area with `make_valid(raw).area` (or a union of the lobes) and, when more than a small fraction (say >2% or >1 mm2, so a stray 1-2 mm kink does ...
- **Confirmed**: Stipple silently leaves unconnected or thin parts of a shape unfilled (only the largest tree is stitched)  
  Where: `engine/threadline_engine/digitize/patterns.py:80-86 (cells kept only if centre inside shape shrunk by 0.45*loop, on a bbox-anchored grid)`, `engine/threadline_engine/digitize/patterns.py:91-109 (one DFS tree per connected component is built)`  
  Fix: In stipple_path, return one smoothed ring per polygon in `_polys(tree)` (largest first) instead of only the biggest, and make `_open_pattern` use `paths = lines`. Its existing `travel(here, path[0], ...
- **Confirmed**: Contour fill on shapes with a hole or several lobes sews long travel lines and a stacked radial thread ridge that quality.check misses  
  Where: `engine/threadline_engine/digitize/patterns.py:53-71`, `engine/threadline_engine/digitize/stitches.py:601-621`  
  Fix: In contour_paths, group rings by containment (a tree), sew each branch depth-first, and stagger each ring's start angle so joins do not line up. Or connect consecutive rings as a spiral. Separately, ...
- **Confirmed**: Cross-stitch sews a vertical connector on every cell boundary (190 for 200 diagonals, 90 of them twice), so Xs read as a barred lattice  
  Where: `engine/threadline_engine/digitize/patterns.py:150-159`, `engine/threadline_engine/digitize/stitches.py:601-621`  
  Fix: In cross_paths, sew each row run as two zigzag passes: out along (x0+k*s, y + (s if k odd else 0)), back along the complementary zigzag, joined by one short connector at the run end. Every cell still ...
- **Confirmed**: Cross-stitch fill sews runs in row order and returns each run to its start end, so shapes with holes or notches get long travel stitches over finished crosses  
  Where: `engine/threadline_engine/digitize/patterns.py:129-160 (cross_paths: row-major run order at line 150, there+back path at line 158 ends where it began)`, `engine/threadline_engine/digitize/stitches.py:601-621 (_open_pattern: joins consecutive paths with travel(), whose stitches nothing later covers for a cross fill)`  
  Fix: In cross_paths (or _open_pattern), collect all runs first, then sew them nearest-neighbour: pick the closest run, start it from its nearer end (use the mirrored there/back pair when starting from the ...
- **Confirmed**: Default Wave fill: per-row brick offset samples the ripple at a different phase on each row (8 mm ripple vs 3.5 mm stitch), so rows cross and the pattern looks like a zigzag  
  Where: `engine/threadline_engine/digitize/stitches.py:563 (per-row brick offset (r % 3) * stitch / 3 is the cause)`, `engine/threadline_engine/digitize/stitches.py:557-575 (region_points: ripple applied to stitch-grid points only)`  
  Fix: In the wave pattern, make every row sample the ripple on the same x grid (for wave, pass offset 0 instead of (r % 3) * stitch / 3 at stitches.py:563; this removed all mid-field crossings at no extra ...
- **Confirmed**: Applique border spacing is quantised to 1/n mm: the default 0.4 sews at 0.33, 0.5-0.8 all sew at 0.5, 1.0-1.5 all sew at 1.0  
  Where: `engine/threadline_engine/digitize/stitches.py:252-266 (satin_pairs: n = ceil(mid_len/spacing) per section)`, `engine/threadline_engine/digitize/applique.py:77 (outline_ring resample 1.0 mm)`  
  Fix: In applique(), build the cover pairs the way ribbon_pairs() does. Resample each rail by arc length at the requested spacing, or call satin_ribbon() on the ring with the cover width. Alternatively ...

### project

- **Confirmed**: A project with lettering will not open at all on a PC that lacks the text's font, because fonts are not embedded in the .ludd  
  Where: `engine/threadline_engine/project.py:99-121 (_pack: only designs/ and images/ are embedded)`, `engine/threadline_engine/project.py:169-190 (open_project: nothing to extract for fonts)`  
  Fix: In `_pack`, read each text item's `font.path` and store the file as fonts/<sha>.<ext>. Set `font.embedded` and `font.original_name`, and extract on open into the cache, rewriting `font.path`. ...
- **Confirmed**: One global recovery slot and no single-instance guard: a second window shows, steals or deletes the first window's recovery copy  
  Where: `engine/threadline_engine/project.py:55-58`, `engine/threadline_engine/project.py:206-212`  
  Fix: Add tauri-plugin-single-instance (forward the .ludd argument to the running window), and/or have the engine key the recovery file by its own process id (autosave-<pid>.ludd), delete only its own, and ...
- **Confirmed**: A failed Recover leaves autosave off for the whole session, and an undrawable recovery is reported as 'Recovered' (and the file is then deleted)  
  Where: `apps/desktop/src/actions.ts:440-457`, `apps/desktop/src/actions.ts:362-381`  
  Fix: In restoreRecovery(): `const ok = await showHistory(...)`. Only when ok, clear recoveryWaiting, set projectPath and savedDoc, and show the success text. In the catch block and in the `!ok` case, ...
- **Confirmed**: Reopened projects name placed designs by their cache hash, and re-saving destroys the original file name  
  Where: `engine/threadline_engine/project.py:111`, `engine/threadline_engine/project.py:196`  
  Fix: In `_pack` (project.py:111), keep an existing `original_name` when the item's path is inside the project-files cache: `it["original_name"] = it.get("original_name") if _in_cache(it["path"]) and ...
- **Confirmed**: Project format version is never bumped, so older LUDD versions silently sew new projects wrong  
  Where: `C:/Users/Copper Felix/HTML Stuffs/threadline/engine/threadline_engine/project.py:33`, `C:/Users/Copper Felix/HTML Stuffs/threadline/engine/threadline_engine/project.py:103`  
  Fix: Make `_pack` stamp the lowest version that can read the project (for example `version = 2` only when a layout uses a post-1.0.1 feature such as a fill pattern other than tatami/gradient, a ribbon ...
- **Confirmed**: Stitch-edit moves are stored as world-space deltas: turning, scaling or mirroring an edited stitch file afterwards puts the moved stitches in the wrong place  
  Where: `engine/threadline_engine/layout.py:177-194`, `engine/threadline_engine/layout.py:672-676`  
  Fix: Convert the dragged delta into the file's own frame when it is recorded (invert the item's rotate, scale and flip in moveSelectedStitches), then apply move_stitch before _transform in layout.render. ...
- **Confirmed**: Machine files (PES/JEF), split exports and the SVG/font writers are written in place: a failed write truncates and destroys the previous good file  
  Where: `engine/threadline_engine/design.py:169-176 (write: pe.write straight onto dest)`, `engine/threadline_engine/design.py:185-192 (design.export, same path)`  
  Fix: In design.write, write to a temp file in dest.parent (tempfile.mkstemp(prefix='.ludd-', suffix='.tmp', dir=dest.parent)), call pe.write on the temp path (give it an extension-aware name, or pass an ...
- **Confirmed**: One bad user JSON file (My threads, imported chart, machine profile) breaks chart list, machine list and export; user files are written non-atomically  
  Where: `engine/threadline_engine/threads.py:150-163 (list_charts catches only OSError/JSONDecodeError)`, `engine/threadline_engine/threads.py:258 and 310 (non-atomic write_text)`  
  Fix: Add one atomic `write_json(path, obj)` helper (temp file in the same folder plus `os.replace`, as in project.py:125-135) and use it in threads.py (`_save_my`, `import_csv`) and ai/settings.py. In ...
- **Confirmed**: open_project has no structured error handling: raw Python/zip error text in the UI, a good-but-locked or missing file reported as "damaged", wrong-shaped files that "open" and then fail in the UI, and NaN/Infinity that hangs the open for 60 s  
  Where: `engine/threadline_engine/project.py:166-202 (open_project; 168-171 OSError lumped with BadZipFile; 173-176 only KeyError/JSONDecodeError; 177-180 no type check on project/format/version; 181 and 49-52 _cache_dir() mkdir unguarded; 183-200 extract(), z.read, tmp.write_bytes, it.pop('embedded'), img.pop('embedded') unguarded)`, `engine/threadline_engine/rpc.py:73-77 (any non-opted-in exception becomes -32603 with str(exc) shown verbatim)`  
  Fix: In open_project, open the zip, read project.json and extract members in separate try blocks (OSError -> "Couldn't read X: it may be missing, in use by another program, or not allowed"; ...

### satin

- **Confirmed**: Batch convert into the same folder converts nothing and says nothing  
  Where: `engine/threadline_engine/design.py:216-228`, `apps/desktop/src/components/BatchDialog.tsx:114-125`  
  Fix: In convert_folder, change the guard at design.py:227 to skip a file only when dest is a strict subfolder of src and the file is under dest. In design.py:216-219, either raise DesignError when ...
- **Confirmed**: Fewer jumps & trims (travel_under) is decided on the pre-sort order, so Sort colors can sew the cover first and leave the travel stitches visible on top  
  Where: `engine/threadline_engine/layout.py:695-698 (join with hidden travel runs before color sort)`, `engine/threadline_engine/layout.py:536-551 (covers[i:] = later in the pre-sort order)`  
  Fix: When layout.color_sort is on, put the blocks into their final colour-sorted order (stable, by first appearance of each thread) BEFORE calling `_join_same_thread_objects`, so the covers come from the ...
- **Confirmed**: JEF (and DST) export does not sew satin stitches longer than the format limit: pyembroidery's default JUMP_NEEDLE contingency writes needle-up jump + half stitch, so the long stitch is never laid and the file reads back as one trim per stitch  
  Where: `engine/threadline_engine/design.py:30-35`, `engine/threadline_engine/design.py:169-176`  
  Fix: In design.write (or write_settings in prepare.py) add `long_stitch_contingency: pe.CONTINGENCY_LONG_STITCH_SEW_TO` whenever a max_stitch applies, so over-long stitches become sewn stitches with a ...
- **Confirmed**: 'Split long stitches' ignores edge and zigzag underlay, so the 'long loose stitches' check still fires on satins about 7.8 mm and wider, with advice that cannot fix it  
  Where: `engine/threadline_engine/digitize/stitches.py:364-376 (edge and zigzag underlay, never split)`, `engine/threadline_engine/digitize/stitches.py:384-392 (the only place split_mm is applied)`  
  Fix: Make the split helper shared and apply it to the edge-turn and zigzag legs in `satin_from_pairs` (`stitches.py:368-376`), or have the satin return which records are underlay so `quality.check` can ...
- **Confirmed**: Knife on a closed satin ribbon or closed line cuts it into 3 pieces, not 2 (also QA-REPORT M6)  
  Where: `C:/Users/Copper Felix/HTML Stuffs/threadline/engine/threadline_engine/shapeops.py:173-178`, `C:/Users/Copper Felix/HTML Stuffs/threadline/engine/threadline_engine/shapeops.py:198-210`  
  Fix: In `split`, when `g.get("closed")` is true and there are at least 2 pieces, whose first piece starts at the ring start and whose last piece ends there, replace them with one LineString: last piece ...

### security

- **Confirmed**: No single-instance guard: all LUDD windows share one recovery slot, so one window overwrites or deletes another's crash-recovery copy (and a second launch ignores the double-clicked file)  
  Where: `apps/desktop/src-tauri/src/lib.rs:14-19`, `apps/desktop/src-tauri/Cargo.toml:17-22`  
  Fix: Add tauri-plugin-single-instance in lib.rs, registered first, with a callback that focuses the main window and emits the argv file path so the first window opens it. Also allow the capability and ...
- **Confirmed**: 'One file per name' overwrites existing files, silently drops duplicate or case-different names while counting them as saved, writes nothing for Windows device names, and stops at the first failing name  
  Where: `apps/desktop/src/features.ts:316-329 (no existence check, weak sanitiser at 321, single try/catch aborts loop, done++ counts overwrites)`, `apps/desktop/src/components/FeatureDialogs.tsx:197 and 221-226 (names are not de-duplicated or validated before saving)`  
  Fix: In exportNames: (1) build the target names first: sanitise, strip control characters, cap length, prefix an underscore on reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9, any extension), ...
- **Confirmed**: Dev engine bridge (/__engine) executes any engine method for any web page or rebinding host while `pnpm dev` / `pnpm tauri dev` runs  
  Where: `apps/desktop/vite-engine-bridge.ts:52-79`, `apps/desktop/vite-engine-bridge.ts:63`  
  Fix: 1) In vite-engine-bridge.ts, have `configureServer` return a function that does the `server.middlewares.use("/__engine", ...)`. The route is then installed after Vite's allowedHosts and CORS ...
- **Confirmed**: API key is only base64 on macOS/Linux, but the toast and manual say it is encrypted for your Windows account  
  Where: `engine/threadline_engine/ai/settings.py:92-101`, `engine/threadline_engine/ai/settings.py:136-147`  
  Fix: Make `ai.set_key` also return `{"storage": "dpapi" | "file"}` (or a `key_protection` field in public()) and have ai.ts show "encrypted for your Windows account" only for dpapi, otherwise "saved in a ...
- **Confirmed**: A .ludd project is trusted for local file paths: re-saving it embeds any file it names (UNC paths possible)  
  Where: `engine/threadline_engine/project.py:99-115 (_pack: no kind/extension/UNC check, line 106-107)`, `engine/threadline_engine/project.py:166-205 (open_project keeps non-embedded item paths; line 195-196 only handles embedded; line 198 KeyError for images)`  
  Fix: In open_project, delete `path` from every layout item (and `font.path` unless it resolves to an installed font) that did not come from a valid `embedded` member, so the only paths in memory are cache ...

### shapeops

- **Confirmed**: Outline of one shape follows hidden travel stitches when "Fewer jumps & trims" is on (the default for new designs)  
  Where: `engine/threadline_engine/layout.py:520 (_join_objects tags the bridge stitches with sb[3] and kind STITCH)`, `engine/threadline_engine/shapeops.py:133 (offset renders with the layout's travel_under)`  
  Fix: In shapeops.offset, render with the hidden travel switched off: r = L.render({**layout, "travel_under": False}). That is the safest fix because the item tag on bridge stitches may be used elsewhere ...
- **Confirmed**: Knife pieces lose the Threads-list colour override, ops, pin and group; Knife/Merge/Offset show a success message even when the commit failed  
  Where: `apps/desktop/src/features.ts:185-195 (finishKnife builds pieces from kind/name/geometry/params/thread only)`, `apps/desktop/src/features.ts:35-54 and apps/desktop/src/design/layout.ts:48-51 (insertObjects -> addObject hard-codes threads: [], ops: [], identity transform; no locked/group)`  
  Fix: In finishKnife build each piece from a copy of the original: `{...structuredClone(o), id: newId(), name, geometry}` (so threads, locked, group and ops carry over; drop only ops tied to source stitch ...
- **Confirmed**: Knife on a closed line or closed satin ribbon gives one extra piece (3 instead of 2)  
  Where: `engine/threadline_engine/shapeops.py:173-178`, `engine/threadline_engine/shapeops.py:198-210`  
  Fix: In shapeops.split, for closed paths, after splitting, if there are more than 2 pieces and pieces[0].coords[0] == pieces[-1].coords[-1], replace the first and last piece with one ...
- **Confirmed**: Design browser hint "type part of a name to find older ones" is false: the search box only filters the 600 newest designs already loaded  
  Where: `apps/desktop/src/components/FeatureDialogs.tsx:94-96`, `apps/desktop/src/components/FeatureDialogs.tsx:105-118`  
  Fix: In BrowseDialog, debounce `query` (about 300 ms) and call library.scan with `{ folder, recursive: true, query }` whenever it changes (the cached thumbnails make this cheap), dropping the client-side ...

### tauri

- **Suspected**: macOS: double-clicking a .ludd in Finder does not open it, and Cmd+Q bypasses the 'Save your changes first?' prompt  
  Where: `apps/desktop/src-tauri/src/lib.rs:4-10,13-21`, `apps/desktop/src-tauri/tauri.conf.json:56-66`  
  Fix: Handle RunEvent::Opened in lib.rs (emit an 'open-file' event to the window; also use it for the single-instance forward) and handle RunEvent::ExitRequested by prevent_exit + asking the UI to confirm.
- **Reviewer-reproduced**: The update check still contacts GitHub 8 s after launch even when the user unticks 'Tell me when a new version is out'  
  Where: `apps/desktop/src/updates.ts:56-61`, `apps/desktop/src/App.tsx:263-295,334`  
  Fix: In the timer callback re-read loadPrefs() and require welcomed === true and checkUpdates !== false; on Welcome 'Continue' with the box ticked, schedule the check then.
- **Reviewer-reproduced**: F5 and the default WebView2 context menu are live in the installed app: reload wipes the open design without a prompt and leaves an extra engine process  
  Where: `apps/desktop/src-tauri/src/lib.rs:13-21`, `C:/Users/Copper Felix/.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/wry-0.57.0/src/lib.rs:1768-1769`  
  Fix: In useShortcuts (capture phase) preventDefault F5, Ctrl+R, Ctrl+Shift+R, Ctrl+F, Ctrl+P regardless of command enabled state; preventDefault 'contextmenu' outside text inputs; add a beforeunload guard ...
- **Suspected**: Engine start depends on a 10 s ping after a 180 MB onefile extraction on every launch; one slow start leaves the app dead  
  Where: `apps/desktop/src/engine/rpc.ts:29`, `apps/desktop/src/engine/sidecar.ts:55-65`  
  Fix: Use an onedir sidecar (fixes the leak too), raise the first ping timeout to 60 s, and retry once before reporting 'disconnected'.
- **Reviewer-reproduced**: 'One file per name' silently overwrites existing files and merges names that collapse to one file, but reports 'Saved N files'  
  Where: `apps/desktop/src/features.ts:309-330`, `apps/desktop/src/components/FeatureDialogs.tsx:260-267`  
  Fix: In exportNames build the list of target paths first, make them unique case-insensitively (Emma, Emma 2), ask once if any exists (a message() with Overwrite/Skip/Cancel) and report the count of ...
- **Reviewer-reproduced**: Zooming a 40,000-stitch design is slow in the installed app (one 170-220 ms frame per wheel step; 450-700 ms in stitch-edit mode)  
  Where: `apps/desktop/src/components/StitchCanvas.tsx:1327-1337`, `apps/desktop/src/components/StitchCanvas.tsx:843-851`  
  Fix: Cache the stitch-edit points in a Graphics (or a particle/sprite batch) and only update it when the design, selection or edit set changes, scaling with the view; cull to the viewport; avoid ...

### tests

- **Reviewer-reproduced**: Stitch editing: repeated moves of one stitch are untested, and moves do not follow a rotated, scaled or flipped design  
  Where: `engine/threadline_engine/layout.py:177`, `engine/threadline_engine/layout.py:676`  
  Fix: Apply moves before _transform (in source coordinates) or inverse-transform the delta; add a test with rotate=90 and with two ops on one stitch.
- **Reviewer-reproduced**: CLAUDE.md says every stitch type gets snapshot tests; applique, lettering, knockdown, basting and several variants have none  
  Where: `engine/tests/test_digitize.py:269`, `engine/tests/test_m8.py:26`  
  Fix: Add snapshot cases for the listed types (record once, review, commit) and tighten the applique tolerance.
- **Reviewer-reproduced**: Stops, seam lock stitches and the do-not-overwrite guard of split export are untested  
  Where: `engine/threadline_engine/layout.py:114`, `engine/threadline_engine/layout.py:809`  
  Fix: Add those three tests.
- **Reviewer-reproduced**: RPC method wiring is untested: 52 of the engine's ~63 methods are never called through the dispatcher (methods.py 64% covered)  
  Where: `engine/threadline_engine/methods.py:30`, `engine/tests/test_rpc.py`  
  Fix: Add a parametrised test that calls each method through dispatcher.handle_line with sample params (and one asserting set(dispatcher._methods) equals the names the UI uses).
- **Reviewer-reproduced**: The new UI (actions.ts, features.ts, store.ts, App.tsx) has almost no tests, and vitest runs without a DOM  
  Where: `apps/desktop/src/actions.ts`, `apps/desktop/src/features.ts`  
  Fix: Add a small test helper that installs a fake `engine.call` in the store, then test commit/undo, colorways, guides, stitch-edit ops and exportNames; add jsdom for App's key handler.
- **Reviewer-reproduced**: All PES/JEF golden round-trip tests skip in CI, so the formats the owner uses have no real-design coverage there  
  Where: `engine/tests/test_golden.py:17`, `engine/tests/test_golden.py:12`  
  Fix: Build FILES from fixtures/ plus samples/ (or move a few small purchased-free designs into a committed folder), keeping the personal folder as an optional extra.
- **Suspected**: Alt-based shortcuts probably cannot match on macOS: matchesShortcut compares only event.key, and the unit tests fabricate the key  
  Where: `apps/desktop/src/commands.ts:24`, `apps/desktop/src/commands.ts:34`  
  Fix: Add `code` to KeyLike and, when the shortcut has Alt and a single-letter/digit key, compare against `Key${K}` / `Digit${n}`; add a test with real macOS key values.
- **Reviewer-reproduced**: "One file per name" overwrites duplicate names and names that clean to the same file, then reports success for all of them  
  Where: `apps/desktop/src/features.ts:310`, `apps/desktop/src/features.ts:324`  
  Fix: De-duplicate destinations (append (2), (3)), rename reserved device names, and count unique paths; add a unit test.
- **Suspected**: CI never runs or smoke-tests the frozen sidecar that users actually run  
  Where: `.github/workflows/ci.yml:36`, `.github/workflows/ci.yml:51`  
  Fix: Add a CI step after `pnpm build:engine` that pipes a few JSON-RPC lines into the built sidecar and checks the replies.
- **Reviewer-reproduced**: Snapshot tests record a missing entry and pass, also in CI; a new case without its committed entry has no protection  
  Where: `engine/tests/test_digitize.py:314`, `engine/tests/test_digitize.py:317`  
  Fix: Only write when UPDATE_SNAPSHOTS is set; otherwise `pytest.fail('no snapshot recorded for NAME: run with UPDATE_SNAPSHOTS=1 and review the diff')`.
- **Reviewer-reproduced**: The cuts that cut-stops depend on can vanish with no test failing (joined colour blocks, text letters, travel fallback)  
  Where: `engine/threadline_engine/layout.py:245`, `engine/threadline_engine/layout.py:491`  
  Fix: Add the tests in test_qa_gaps.py (sorting cut, far letters trimmed, travel fallback) and replace the key-membership assertion with `stops_added >= 1` on a design that has a long same-colour jump.
- **Reviewer-reproduced**: Export settings for JEF/PES are barely tested: short trims, the Janome max-stitch setting, and machine limits  
  Where: `engine/threadline_engine/design.py:30`, `engine/threadline_engine/prepare.py:226`  
  Fix: Add those three tests; assert exact stops_added in the layout path.
- **Reviewer-reproduced**: A self-crossing fill outline silently loses half its shape, and the test that should catch it only checks 'some stitches exist'  
  Where: `engine/threadline_engine/digitize/stitches.py:462`, `engine/tests/test_digitize.py:245`  
  Fix: In fill_polygon keep every piece of a MultiPolygon (or warn 'this shape crosses itself: part of it was left out'), and make the test assert stitches exist on both sides of x=5.
- **Reviewer-reproduced**: Text on a drawn line piles extra letters on top of each other at the line's ends, with no warning and a comment that says there is one  
  Where: `engine/threadline_engine/lettering.py:495`, `engine/threadline_engine/lettering.py:496`  
  Fix: Return a warning from _along_path when total > length (and include it in layout_text's warnings), and add an overflow test.
- **Reviewer-reproduced**: Glyph curve flattening, kerning and the cap-height fallback have no test: the lettering test font is made only of straight rectangles  
  Where: `engine/tests/test_lettering.py:25`, `engine/threadline_engine/lettering.py:155`  
  Fix: Add the curved-glyph test (and a CFF/cubic variant); add a kern table to the test font.
- **Reviewer-reproduced**: travel_under (fewer jumps) is tested with one scenario; partly covered paths and the cover margin are not pinned  
  Where: `engine/threadline_engine/layout.py:516`, `engine/threadline_engine/layout.py:526`  
  Fix: Add the partial-cover and margin tests to test_connectors.py.

### visual

- **Confirmed**: Stitch-edit moves are world-space deltas added after the transform, so rotating, scaling or mirroring the design later (or copying it turned or mirrored) displaces the edited stitches  
  Where: `engine/threadline_engine/layout.py:177-193`, `engine/threadline_engine/layout.py:673-676`  
  Fix: Store and apply the delta in the source file's frame. In render(), call _move_stitches before _transform so the delta rotates, scales and flips with the design. When the op is created in features.ts ...
- **Confirmed**: 'Fewer jumps & trims' (on by default for new designs) re-computes every block's cover and a growing union on each render: about 6.5 to 8.7 s per render at 100 shapes, and layout.check repeats it  
  Where: `engine/threadline_engine/layout.py:536-551 (_join_same_thread_objects: covers computed for every digitized block, and unary_union(covers[i:]) rebuilt per join)`, `engine/threadline_engine/layout.py:530-533 (_cover) and :311-327 (_stitched_area: buffer + unary_union per block, no caching)`  
  Fix: Cache each block's cover by a hash of its recs (like _object_cache). Compute covers only when the option is on and the block can join. For each candidate join, query an STRtree of the covers for ...
- **Confirmed**: 'Split long stitches' cannot clear the 'long loose stitches' warning on satins wider than about 7.8 mm: zigzag and edge underlay stitches are never split  
  Where: `engine/threadline_engine/digitize/stitches.py:364-376 (underlay emitted with no split_mm handling)`, `engine/threadline_engine/digitize/stitches.py:384-390 (split applies to top stitches only)`  
  Fix: In satin_from_pairs, run the zigzag points and the edge-underlay end crossings through the same split_mm subdivision as the top stitches. Alternatively, mark underlay stitches (or compute the ...
- **Confirmed**: Stipple stitches only the largest connected group: other lobes, and most thin rings and bands, are left bare with no warning  
  Where: `engine/threadline_engine/digitize/patterns.py:111-116 (biggest = max(shapes, key=area); the other shapes are discarded)`, `engine/threadline_engine/digitize/patterns.py:77-123 (stipple_path returns a single path)`  
  Fix: Make stipple_path return a list of paths, one smoothed and resampled ring per polygon in _polys(tree), instead of only the biggest. Let _open_pattern use that list (it already joins paths with travel ...
- **Confirmed**: Stipple and cross-stitch fills leave sewn travel threads visible on top of the open pattern (long straight chord from the edge underlay; cross-stitch row connectors)  
  Where: `engine/threadline_engine/digitize/stitches.py:631-636 (edge ring sewn before an open pattern, ending at its own start vertex)`, `engine/threadline_engine/digitize/stitches.py:657-660 (straight chord to the pattern start via travel())`  
  Fix: In fill(), for open patterns compute the pattern's first point first and rotate the closed edge ring to start at the vertex nearest to it (re-using patterns._nearest_rotation). I checked this cuts ...
- **Confirmed**: Cross-stitch fill sews a vertical bar down every column boundary (39% of the thread), so the fill looks like Xs in ladder rails, not "little Xs"  
  Where: `engine/threadline_engine/digitize/patterns.py:150-159`, `engine/threadline_engine/digitize/patterns.py:152-157`  
  Fix: In cross_paths(), sew each run as an out-and-back zigzag. Out: the alternating diagonals "/ \ / \ ..." across the run. Back: the complementary diagonals of each cell from right to left, with one ...
- **Confirmed**: Rotated lettering keeps the stitch angle chosen for upright letters (text turned, on an arc, circle or path)  
  Where: `engine/threadline_engine/lettering.py:306-315`, `engine/threadline_engine/lettering.py:318-331`  
  Fix: In transform_geometry (stitches.py:708), when the object is a fill, add t.rotate to params.angle_deg (mod 180, and negate it for a mirror), as layout.ts withFillAngle does. In lettering.layout_text, ...
- **Confirmed**: Text on a drawn line longer than the line: letters stack on the end points with no warning (dead warning code)  
  Where: `engine/threadline_engine/lettering.py:481`, `engine/threadline_engine/lettering.py:495-496`  
  Fix: Have `_along_path` return `(objects, warnings)` (or take the `warnings` list), and when `total > length + 1e-6` append "The text is longer than the line; draw a longer line or make the letters ...
- **Confirmed**: Satin-look lettering from about 18 mm up triggers a false "long loose stitches ... (up to 7.0 mm)" warning  
  Where: `engine/threadline_engine/quality.py:27`, `engine/threadline_engine/quality.py:186-193`  
  Fix: In quality.check use `long_ = lengths > LONG_MM + 0.05` (about 0.15 would also cover 0.1 mm export rounding). Or set SATIN_MAX_STITCH_MM to 6.9 in lettering.py. Test 'Hello Ag' at 25 mm in Arial ...
- **Confirmed**: Self-crossing fill/applique outline: part of the shape is silently dropped (no warning)  
  Where: `engine/threadline_engine/digitize/stitches.py:454-464 (fill_polygon: buffer(0) at line 459 drops a lobe itself; the max-of-parts branch at 462-463 drops the rest when buffer(0) returns several parts)`, `engine/threadline_engine/digitize/applique.py:64-77 (outline_ring, same pattern)`  
  Fix: In fill_polygon and outline_ring, test Polygon(shell, holes).is_valid before buffer(0). If it is invalid, use shapely.make_valid(...) instead of buffer(0), keep every Polygon part (or at least append ...
- **Disputed**: Spacing under 0.3 mm: stitch_run() drops the first penetration of each satin column and fill row, thinning satin rail edges and fill side edges  
  Where: `engine/threadline_engine/digitize/stitches.py:26`, `engine/threadline_engine/digitize/stitches.py:43-50`  
  Fix: Give stitch_run() a `min_mm` argument. Call it with about 0.05 to 0.1 mm for the satin top stitching (stitches.py:392) and tatami rows (stitches.py:596). Keep 0.3 mm for running stitches and ...

## Low findings (185 after merging look-alikes)

Each entry: status, title, where, suggested fix. Area in headings. Full detail and repro snippets are in the per-area reports (see Appendix).

### autotrace

- **Confirmed**: Very large pictures: 144 MP peaks at 2.9 GB; over 179 MP fails with a raw 'decompression bomb' error  
  Where: `engine/threadline_engine/autotrace.py:61-66 (analyse: full-size RGBA convert, second RGBA, composite, RGB convert before the resize)`, `engine/threadline_engine/autotrace.py:125-127 (prepare: except OSError does not catch DecompressionBombError)`
- **Confirmed**: Installed-but-unloadable AI tracing model makes every Auto-trace click fail (no fallback to classical guesses, raw ONNX error shown as "couldn't read that picture")  
  Where: `engine/threadline_engine/autotrace.py:616-622`, `engine/threadline_engine/ai/segment.py:51-58`
- **Confirmed**: AI model download: no size/hash check, unpinned 'main' URLs, short bodies accepted, IncompleteRead escapes, a truncated first file survives a retry  
  Where: `engine/threadline_engine/ai/segment.py:26-29`, `engine/threadline_engine/ai/segment.py:67`
- **Confirmed**: The engine traces the live original file, not the copy the canvas shows, so an externally edited picture is traced against the wrong content  
  Where: `engine/threadline_engine/kept.py:36-40`, `engine/threadline_engine/autotrace.py:115-132`
- **Confirmed**: Whole-picture preview goes stale: spacing/spread keys and picture changes do not refresh it, and an older (or out-of-order) engine answer can overwrite a newer run  
  Where: `apps/desktop/src/features.ts:75-106`, `apps/desktop/src/autoTrace.ts:139-157`
- **Confirmed**: A picture with no light pixel at all makes a click on it crash with 'cannot convert float NaN to integer'  
  Where: `engine/threadline_engine/autotrace.py:85 (dt = cv2.distanceTransform(ink, ...) returns FLT_MAX when ink has no zero pixel)`, `engine/threadline_engine/autotrace.py:513-521 (_ribbon_candidates: width_px, reach, tip become inf/NaN)`
- **Confirmed**: Analysis time grows steeply with picture detail per mm: one click 0.3 s becomes 5.7 s, a photo 5 s becomes 20 s  
  Where: `engine/threadline_engine/autotrace.py:300-301 (big elliptical kernel and dilate in _to_line_middle: the main cost)`, `engine/threadline_engine/autotrace.py:593 and :707 (reach = max(2, round(3*ppm)) grows with px/mm)`

### compat

- **Confirmed**: Project format VERSION stays 1 although new projects use geometry and params that the released (HEAD, 1.0.1) engine cannot read, so the "saved by a newer LUDD; update to open it" guard never fires  
  Where: `engine/threadline_engine/project.py:33 (VERSION = 1)`, `engine/threadline_engine/project.py:103 (_pack always writes VERSION)`
- **Confirmed**: Stray apps/desktop/tsconfig.tsbuildinfo (stale tsc build cache) is untracked and not git-ignored  
  Where: `C:/Users/Copper Felix/HTML Stuffs/threadline/.gitignore (missing *.tsbuildinfo)`, `C:/Users/Copper Felix/HTML Stuffs/threadline/apps/desktop/tsconfig.tsbuildinfo (untracked, stale, 1804 bytes, Oct 11 18:11)`

### docs-a

- **Reviewer-reproduced**: Manual: 'PES, JEF, DST, EXP, VP3, XXX and 40 more' - LUDD reads 40 formats in total  
  Where: `docs/USER-MANUAL.md:60`, `README.md:6`
- **Reviewer-reproduced**: Duplicate command ids player.faster / player.slower; undocumented always-on [ and ] change playback speed  
  Where: `apps/desktop/src/actions.ts:1838-1844`, `apps/desktop/src/actions.ts:1848-1865`
- **Reviewer-reproduced**: Manual wording that does not match the UI (tool rail, Repeat button, Forget guesses, Whole picture, which ... menu)  
  Where: `docs/USER-MANUAL.md:20 (rail omits Auto-trace; apps/desktop/src/components/ToolRail.tsx:10-17 has it)`, `docs/USER-MANUAL.md:313 ('or the Repeat button'; there is only the menu item: Toolbar.tsx:113, InfoPanel.tsx:1144-1157/1197-1211)`
- **Reviewer-reproduced**: USER-GUIDE.md is stale after the 1.0.1 panel rework (already QA-REPORT M18) (also: docs-c)  
  Where: `docs/USER-GUIDE.md:14-17`, `docs/USER-GUIDE.md:38`
- **Reviewer-reproduced**: Shapes menu (rectangle, circle, star) ignores 'your settings carry over'  
  Where: `apps/desktop/src/actions.ts:819`, `apps/desktop/src/actions.ts:675-677`
- **Reviewer-reproduced**: Adding a picture tells the user to 'lock it (lock icon)'; the control is the Pin (pin icon)  
  Where: `apps/desktop/src/actions.ts:652`, `apps/desktop/src/components/InfoPanel.tsx:1172-1174`
- **Reviewer-reproduced**: Backspace with a point selected deletes the whole shape (Delete deletes only the point)  
  Where: `apps/desktop/src/actions.ts:1704-1718`, `docs/USER-MANUAL.md:200`
- **Reviewer-reproduced**: Pinned shapes and designs still move, turn, mirror and scale from the keyboard; pinned pictures do not  
  Where: `apps/desktop/src/actions.ts:1512-1520 (picture lock honoured at :1516, items not)`, `apps/desktop/src/actions.ts:1696-1703`
- **Suspected**: With B (pictures hidden) a hidden picture can still be clicked and dragged  
  Where: `apps/desktop/src/components/StitchCanvas.tsx:1310-1325`, `apps/desktop/src/components/StitchCanvas.tsx:846`
- **Reviewer-reproduced**: Whole-picture preview says Spread and point spacing 'apply here too' but cannot change or refresh them  
  Where: `apps/desktop/src/components/ToolRail.tsx:293`, `apps/desktop/src/features.ts:75-106`
- **Reviewer-reproduced**: CLAUDE.md and the machine schema describe things that no longer exist or changed  
  Where: `CLAUDE.md:27 ('The canvas fabric stays light in both')`, `apps/desktop/src/store.ts:296`
- **Reviewer-reproduced**: User-visible features the manual does not mention  
  Where: `apps/desktop/src/dragDialogs.ts:1-12`, `apps/desktop/src/actions.ts:1848-1865`
- **Reviewer-reproduced**: Browse designs 'opens faster next time' only within one session, and the list never refreshes  
  Where: `engine/threadline_engine/library.py:1-6`, `engine/threadline_engine/library.py:41`

### docs-b

- **Reviewer-reproduced**: Applique shows 'Lock stitches' tick boxes that do nothing  
  Where: `apps/desktop/src/components/InfoPanel.tsx:588-589 (shown for every kind)`, `engine/threadline_engine/digitize/stitches.py:686-690 (applique returns before tie_in/tie_off flags are read)`
- **Reviewer-reproduced**: Font list shows only the first 200 fonts with no hint  
  Where: `apps/desktop/src/components/TextPanel.tsx:43 (.slice(0, 200))`, `docs/USER-MANUAL.md:425`
- **Reviewer-reproduced**: Manual vs panel: names, numbers and one claim in the setting table are off  
  Where: `docs/USER-MANUAL.md:364 (Type; Stitch as is the UI label, Satin button missing from the row)`, `docs/USER-MANUAL.md:366 (Density: the mm value is 'Spacing' under Advanced)`
- **Reviewer-reproduced**: In-app Help guide (helpdocs.py) has stale or wrong lines  
  Where: `engine/threadline_engine/ai/helpdocs.py:48 ('The Text tool (T)': T is realistic thread, text is Shift+T)`, `engine/threadline_engine/ai/helpdocs.py:29 ('Pin in place on the Shape tab': there are no tabs)`
- **Reviewer-reproduced**: AI section wording: key 'encrypted for your Windows account' toast on every OS, and 'exactly what will go' leaves out the system prompt  
  Where: `apps/desktop/src/ai.ts:68-69 (toast text is fixed)`, `engine/threadline_engine/ai/settings.py:122-132 (non-Windows: base64 'PLAIN' blob, chmod 600 applied after the write)`
- **Reviewer-reproduced**: player.slower/player.faster are registered twice (undocumented [ ] aliases)  
  Where: `apps/desktop/src/actions.ts:1838-1865 (ids player.slower and player.faster used for ',' '.' and again for '[' ']')`, `docs/USER-MANUAL.md:709`

### docs-c

- **Reviewer-reproduced**: schemas/machine.schema.json still says Threadline and the old data folder; the other schemas CLAUDE.md and the plan promise do not exist  
  Where: `schemas/machine.schema.json:3-5 ($id threadline.app, title 'Threadline machine profile', 'Windows: %APPDATA%\Threadline\machines')`, `engine/threadline_engine/profiles.py:86 (reads <data dir>/machines, which is %APPDATA%\Ludd)`
- **Reviewer-reproduced**: CHANGELOG 1.0.1 contradicts itself on the Sewing order pencil, and files unrelated items under 'Features from comparing LUDD with Hatch'  
  Where: `docs/CHANGELOG.md:26 ('Rename anything (the pencil in Sewing order, ...)')`, `docs/CHANGELOG.md:35 ('the pencil now changes that step's thread ... double-click a name to rename it')`
- **Reviewer-reproduced**: CLAUDE.md definition-of-done rules were not fully followed for the uncommitted 1.0.1 stitch output  
  Where: `docs/stitchout-log.md:7-36 (added rows cover ribbons, fill+border, patterns, motifs, hidden travel, whole picture)`, `engine/threadline_engine/lettering.py:465-497 (text on a line: new stitch output, no row)`
- **Reviewer-reproduced**: CLAUDE.md and PLAN.md describe a different stack and status than the code  
  Where: `CLAUDE.md Layout ('networkx'; 'onnxruntime optional') versus engine/pyproject.toml:6-15 (no networkx; onnxruntime is a required dependency)`, `docs/PLAN.md:130 ('Zustand + Immer': immer is not a dependency, apps/desktop/package.json)`
- **Reviewer-reproduced**: Dead anchor in the manual: link to #auto-trace-shift-a  
  Where: `docs/USER-MANUAL.md:537 (link)`, `docs/USER-MANUAL.md:213 (heading '### Auto-trace (Shift+A)' slugs to #auto-trace-shifta on GitHub and in python-markdown, which scripts/make_manual_pdf.py uses)`
- **Reviewer-reproduced**: Release housekeeping: PDF manual not part of RELEASING.md, a stale root-level PDF copy, version-bump list incomplete, untracked build artefact  
  Where: `docs/RELEASING.md:31-44 (no step to regenerate docs/LUDD-User-Manual.pdf; scripts/make_manual_pdf.py reads the version from package.json and stamps it on the cover)`, `LUDD-User-Manual.pdf at the repo root (git-ignored, Oct 11 17:31, 'Version 1.0', 643 text lines, none of the 1.0.1 sections)`
- **Suspected**: MobileSAM is called MIT-licensed in the UI, docs and code; upstream MobileSAM is, as far as I know, Apache-2.0  
  Where: `engine/threadline_engine/ai/segment.py:4 and 58`, `apps/desktop/src/components/AISettings.tsx:165`
- **Reviewer-reproduced**: No third-party notices anywhere (OFL fonts, MIT/BSD/Apache libraries bundled in the installer)  
  Where: `repository root (no NOTICE / THIRD-PARTY file; git ls-files shows none)`, `apps/desktop/src-tauri/tauri.conf.json:49-50 (licenseFile is the GPL only)`
- **Suspected**: 'One file per name' silently overwrites: duplicate names, names that collapse to the same file name, and existing files in the folder  
  Where: `apps/desktop/src/features.ts:310-330 (exportNames: no de-duplication, safe-name collisions or overwrite check; 'Saved N files' counts writes, not distinct files)`, `docs/CHANGELOG.md:13 and docs/USER-MANUAL.md:441-445 (promise one file per name)`
- **Reviewer-reproduced**: Mixed US/UK spelling in user-visible text  
  Where: `apps/desktop/src/components/InfoPanel.tsx:371 ('Centre' underlay button)`, `apps/desktop/src/components/SettingsDialog.tsx:64 ('Millimetres')`
- **Reviewer-reproduced**: README and release notes still lead with Trace Assist and its Tab key, which is now off by default; Auto-trace and the 1.0.1 features are absent  
  Where: `README.md:14 and 74 (table row 'Trace Assist: take the suggested point | Tab / Shift+Tab')`, `docs/release-notes.md:23 (this file is the body of every GitHub release draft, release.yml create-release step)`
- **Reviewer-reproduced**: README says LUDD can save for your machine in '40+ formats'; only 9 formats are writable (40 are read)  
  Where: `README.md:6`

### export

- **Confirmed**: Split export loses isolated single stitches and silently overwrites its numbered files  
  Where: `engine/threadline_engine/split.py:71-75`, `engine/threadline_engine/layout.py:807-814`
- **Confirmed**: PE550D export: long untrimmed jumps get no cut and no warning (dialog says "no jump threads long enough"); PES writes every jump after the first as a trim  
  Where: `engine/threadline_engine/prepare.py:110`, `engine/threadline_engine/prepare.py:155-156`
- **Confirmed**: PES v6 CSewSeg point count is 16-bit, so an unbroken run of more than 65,535 stitches declares a truncated count  
  Where: `engine/.venv/Lib/site-packages/pyembroidery/PESWriter.py:371 (third-party code, ignored by git: engine/.venv/ is in .gitignore)`, `engine/.venv/Lib/site-packages/pyembroidery/WriteHelper.py:27 (write_int_16le masks to 16 bits)`
- **Confirmed**: Unclear or raw errors for odd destinations; batch convert silently does nothing when the destination contains the source  
  Where: `engine/threadline_engine/design.py:171-172`, `engine/threadline_engine/design.py:173-176`
- **Confirmed**: A design with no stitches exports silently (PES/JEF), or fails with a raw Python error and leaves a 0-byte or partial file  
  Where: `engine/threadline_engine/prepare.py:167-176 (check never looks for an empty design)`, `engine/threadline_engine/prepare.py:217-223 (prepare)`
- **Suspected**: JEF header hoop code ignores the chosen hoop, and STOPs are written as colour-table index 0 (pyembroidery 1.5.1 behaviour, unverified on a Janome)  
  Where: `engine/threadline_engine/design.py:30-35`, `engine/threadline_engine/design.py:169-176`

### fill

- **Confirmed**: UI ranges for fill Length (8), cross Square (8) and applique Border (8) allow stitches the Checks panel calls loose; cross and applique have no split  
  Where: `apps/desktop/src/components/InfoPanel.tsx:548-552 (fill Length max 8; the line Length max is 12)`, `apps/desktop/src/components/InfoPanel.tsx:341 (cross Square max 8; the finding cited 366-368, which is wrong)`
- **Confirmed**: Fill 'Auto' underlay uses only light vs. not-light: width is ignored and heavy fabrics get the same as cotton, though the manual and tooltip say Auto follows the fabric and the width  
  Where: `engine/threadline_engine/digitize/stitches.py:417-420 (fill Auto reads only underlay_level == 'light')`, `engine/threadline_engine/digitize/stitches.py:644 (cross-hatch spacing hard-coded to 2.0 mm, so a heavy fill base would need a new parameter)`
- **Confirmed**: No upper limit on fill size: absurd sizes run for minutes and never return  
  Where: `engine/threadline_engine/digitize/stitches.py:454-464 (fill_polygon: best place for the guard)`, `engine/threadline_engine/digitize/stitches.py:520-598 (tatami: row loop and region building)`
- **Confirmed**: travel() and contour rings are resampled without keeping route corners, so thread paths clip notch/hole corners up to about 0.5 mm outside the outline (0.6 mm for Contour fill)  
  Where: `engine/threadline_engine/digitize/stitches.py:115 (travel(): resample(route, TRAVEL_STITCH_MM) with no keep, no min-stitch filter)`, `engine/threadline_engine/digitize/stitches.py:77-103 (_edge_route builds the ring route that gets cut)`
- **Confirmed**: Fill and applique settings outside the UI's range are not validated, so a hand-edited or damaged project fails the whole render with a raw library error  
  Where: `engine/threadline_engine/digitize/stitches.py:422 (angle_deg: float() only, no finite or range check)`, `engine/threadline_engine/digitize/stitches.py:425 (pull_comp_mm not range-checked; SatinParams checks 0..2 at :213 and FillParams has no equivalent)`
- **Confirmed**: Fill row spacing under 0.3 mm drops the first stitch of every second row (rows stop up to one stitch short of the edge); reachable with Dense on Towel  
  Where: `engine/threadline_engine/digitize/stitches.py:43-50 (stitch_run drops points closer than MIN_STITCH_MM = 0.3, defined at :26, to the previous record)`, `engine/threadline_engine/digitize/stitches.py:596 (tatami passes each whole region, with row turns inside it, through stitch_run)`

### fuzz-rpc

- **Confirmed**: Lettering ignores the "Stitching on" fabric (documented as "Lettering doesn't follow the fabric yet"), and USER-GUIDE.md:59 promises more than that  
  Where: `engine/threadline_engine/layout.py:459-502 (_text_block has no fabric argument; line 480 calls _generate_cached without fabrics.apply, unlike line 442)`, `engine/threadline_engine/layout.py:634 (call site does not pass layout.get('fabric'))`
- **Confirmed**: Engine start-up has a 10 s ping timeout, no retry, and leaves the process running when it gives up  
  Where: `apps/desktop/src/engine/sidecar.ts:55-65 (single ping with 10 s limit; catch returns client:null with no retry and no child.kill())`, `apps/desktop/src/engine/rpc.ts:29 (default timeoutMs 10_000)`
- **Confirmed**: Unexpected engine failures show raw Python messages in the UI, and TypeErrors are mislabelled "invalid params" and never logged  
  Where: `engine/threadline_engine/rpc.py:71-72 (any TypeError becomes -32602 with str(exc), unlogged, silently dropped for notifications)`, `engine/threadline_engine/rpc.py:73-77 (str(exc) of KeyError/IndexError/ValueError sent as the message; stderr gets only repr, no traceback)`
- **Confirmed**: AI-trace embedding cache keyed on path + pixel size only: a retouched picture of the same size gets the old picture's AI masks  
  Where: `engine/threadline_engine/ai/segment.py:112-116 (cache hit check compares only h*100000+w)`, `engine/threadline_engine/ai/segment.py:134 (entry stored with the same size-only token)`
- **Confirmed**: Source-file cache trusts the modified time alone and is never evicted  
  Where: `engine/threadline_engine/layout.py:52 (_cache unbounded dict)`, `engine/threadline_engine/layout.py:55-73 (_load: validity is `hit[0] == mtime` only)`
- **Confirmed**: A design with every stitch removed exports a blank PES with no warning (and JEF/PES sometimes fail with a cryptic error)  
  Where: `engine/threadline_engine/layout.py:716-734 (render builds a pattern holding only END; the only empty guard is the items-list check at :626-627)`, `engine/threadline_engine/layout.py:818-824 (preview_export) and :827-835 (export): no zero-stitch check`
- **Confirmed**: Object cache is capped at 512 entries: designs with more than 512 objects regenerate every stitch on every edit  
  Where: `engine/threadline_engine/layout.py:415-416 (_object_cache dict, _OBJECT_CACHE_MAX = 512)`, `engine/threadline_engine/layout.py:419-428 (_generate_cached: FIFO eviction via pop(next(iter(...))), no move on hit)`
- **Confirmed**: Text stays stale when a stitch font (.luddfont) is edited on disk: the text cache is keyed by path only  
  Where: `engine/threadline_engine/layout.py:456-472 (_text_cache; key built at 462-463 from the spec only, no font file stat; this is the only stale layer)`, `engine/threadline_engine/layout.py:634 (sole caller of _text_block)`
- **Suspected**: Every autosave and save re-sends the full base64 of every reference picture over the engine's stdin  
  Where: `apps/desktop/src/actions.ts:372-377 (project_data includes images with data_url)`, `engine/threadline_engine/project.py:100-103 (the engine pops data_url and re-reads the file)`

### layout-ops

- **Confirmed**: 'Trim jumps longer than 3 mm' adds a second TRIM in front of jumps that were already trimmed (TRIM then JUMP), inflating the Trims figure  
  Where: `engine/threadline_engine/layout.py:203-213 (JUMP-only run start; TRIM before the run is copied at 219 and never inspected)`, `engine/threadline_engine/layout.py:209 (trimmed check ignores out[-1])`
- **Confirmed**: Stitch-edit ops are not validated: malformed delete_stitches/move_stitch/insert/delete_block fields abort the whole render with raw Python errors, and index -1 on a text or drawn-shape item deletes every stitch  
  Where: `engine/threadline_engine/layout.py:149-151`, `engine/threadline_engine/layout.py:154-157`
- **Confirmed**: New ops are not versioned: an older LUDD silently ignores delete_stitches/move_stitch and exports the stitches the user deleted  
  Where: `engine/threadline_engine/project.py:33 (VERSION = 1)`, `engine/threadline_engine/project.py:103 (_pack stamps VERSION on save)`
- **Confirmed**: Moving N selected stitches stores N move_stitch ops: a full-design drag is 1.8 MB, ten drags 18 MB, resent on every render and autosave  
  Where: `apps/desktop/src/features.ts:278-285`, `apps/desktop/src/features.ts:265-269`

### layout-order

- **Confirmed**: Fabric preset does not reach lettering (text); only the CHANGELOG says so  
  Where: `engine/threadline_engine/layout.py:459-502 (_text_block has no fabric argument; line 480 calls _generate_cached on unadjusted letters)`, `engine/threadline_engine/layout.py:442 (_object_blocks applies fabrics.apply; the text call site passes no fabric)`
- **Confirmed**: Empty hoopings are exported and listed (files with only pink crosses)  
  Where: `engine/threadline_engine/split.py:107-123 (_grid: one Section per cell)`, `engine/threadline_engine/split.py:153-181 (_marks: crosses on every neighbouring seam, sewn or not)`
- **Confirmed**: Every cut run piece gets its own lock stitches and a jump: split fills carry about 9% more stitches and 130 jumps, with 3x the needle hits at the seam  
  Where: `engine/threadline_engine/split.py:219-221 (_tied)`, `engine/threadline_engine/split.py:232-234 (tie on every cut piece; the comment's unravel reasoning does not hold for same-colour joins on a machine that cuts only at colour changes)`
- **Confirmed**: profiles._validate does not enforce the machine schema: bad user profiles surface raw Python TypeErrors in Save  
  Where: `engine/threadline_engine/profiles.py:63-80 (_validate)`, `engine/threadline_engine/profiles.py:88-92 (list_machines except clause too narrow)`
- **Confirmed**: fabrics.apply silently clamps stitch spacing to 0.2-3.0 mm on every fabric, including plain woven  
  Where: `engine/threadline_engine/fabrics.py:71-72`, `engine/threadline_engine/digitize/stitches.py:211 (satin range 0.15-3)`
- **Confirmed**: No pytest covers optimize_order, travel_under, color sort/merge of drawn shapes, or split with applique/stops; the defects above sit in exactly those paths  
  Where: `engine/tests/test_connectors.py:23-55 (optimize_order and travel_under ARE tested here; the file is untracked)`, `engine/tests/test_layout.py:105-123 (colour sort and merge tested on stitch-file items only)`
- **Confirmed**: Fabric presets never suggest knockdown for towel, fleece and the other napped fabrics, although PLAN.md lists a knockdown default per fabric  
  Where: `engine/threadline_engine/fabrics.py:35-44`, `engine/threadline_engine/fabrics.py:84-89`

### lettering

- **Confirmed**: Kerning is read only from the legacy 'kern' table, so fonts that kern in GPOS (Roboto, Bahnschrift, Segoe Print/Script, Lato partly) get little or none  
  Where: `engine/threadline_engine/lettering.py:215-218 (only font['kern'] format-0 subtables are read; GPOS is ignored)`, `engine/threadline_engine/lettering.py:295-296 (applies lf.kern only)`
- **Confirmed**: Text is centred on its ink, so adding a descender letter moves the baseline (bad for One file per name)  
  Where: `engine/threadline_engine/lettering.py:500-507 (_centre re-centres ink bounds in Y as well as X)`, `engine/threadline_engine/lettering.py:462 (line and arc return _centre(objects))`
- **Confirmed**: Unicode text handling: decomposed accents land beside the letter; newline and tab become a '?'-wide gap; no multi-line text  
  Where: `engine/threadline_engine/lettering.py:283-303 (_outline_glyphs: raw code points, '?' fallback at 289-293, isspace suppression at 298)`, `engine/threadline_engine/lettering.py:334-349 (_stitch_font_glyphs: single-character glyph keys, missing combining mark silently dropped)`
- **Confirmed**: Small-text warning is coarse: dots vanish at exactly 5 mm with only the separate 'tiny parts' note, thin-stroke fonts get no width warning, monogram side letters are not checked  
  Where: `engine/threadline_engine/lettering.py:35 (SMALL_TEXT_MM = 5.0) and :400-401 (size < SMALL_TEXT_MM)`, `engine/threadline_engine/lettering.py:413 (monogram side letters = size * 0.7, never checked)`
- **Confirmed**: Text on a drawn line has no way to choose side or direction; a line drawn right to left gives upside-down text, closed paths start opposite the first point  
  Where: `engine/threadline_engine/lettering.py:475-493 (reads left to right in drawing direction, centred at length/2, letters on the left of travel)`, `apps/desktop/src/features.ts:295-305 (stores only nodes and closed, deletes the line)`
- **Confirmed**: Put the text on the line destroys the line when the lettering is a monogram  
  Where: `apps/desktop/src/features.ts:290-307 (textOnLine has no monogram check; line filtered out at ~302, shape written at ~303, success message at 306)`, `engine/threadline_engine/lettering.py:409-427 (monogram branch returns before `shape` is read; path branch is at 433-434)`
- **Confirmed**: In-app help "Lettering and monograms" section says the Text tool is T (it is Shift+T; T toggles realistic thread)  
  Where: `engine/threadline_engine/ai/helpdocs.py:48 (the bug)`, `engine/threadline_engine/ai/helpdocs.py:23 and the Keyboard shortcuts section (correct, show the contradiction)`
- **Confirmed**: Moving or nudging lettering regenerates every letter; a held arrow key queues serial renders (0.35 s per step for a 43-char line)  
  Where: `engine/threadline_engine/layout.py:477-480 (_text_block: transform_geometry bakes t.x/t.y into each letter before _generate_cached)`, `engine/threadline_engine/layout.py:419-428 (_generate_cached key is the translated geometry)`
- **Suspected**: Lettering panel polish: font list capped at 200 without a hint, emptied text box keeps old design, letter-height errors keep the bad number  
  Where: `apps/desktop/src/components/TextPanel.tsx:43 (slice(0, 200))`, `apps/desktop/src/components/TextPanel.tsx:99-102,122-125 (empty text never committed, draft not restored)`

### live-esc

- **Reviewer-reproduced**: Esc auto-repeat releases several things in one press  
  Where: `apps/desktop/src/App.tsx:83-96`
- **Reviewer-reproduced**: Space on the focused sewing-order name (role=button span) also starts or stops playback  
  Where: `apps/desktop/src/App.tsx:102-108`, `apps/desktop/src/components/InfoPanel.tsx:1062-1073`
- **Reviewer-reproduced**: Esc in the lettering text box does not bring the old text back once the 450 ms typing pause has passed  
  Where: `apps/desktop/src/components/TextPanel.tsx:112-132`, `docs/USER-MANUAL.md:28-32`
- **Suspected**: Esc in an AI-settings text box closes the dialog and saves the half-typed value  
  Where: `apps/desktop/src/components/AISettings.tsx:14-29`
- **Reviewer-reproduced**: The click that dismisses a menu or font list also acts on the canvas  
  Where: `apps/desktop/src/components/Menu.tsx:21-28`, `apps/desktop/src/components/TextPanel.tsx:28-37`
- **Reviewer-reproduced**: Auto-pan keeps scrolling the view after the window loses focus  
  Where: `apps/desktop/src/components/StitchCanvas.tsx:1156-1184`, `apps/desktop/src/components/StitchCanvas.tsx:1745-1750`
- **Reviewer-reproduced**: One Esc can revert a focused field and also drop a held mode  
  Where: `apps/desktop/src/App.tsx:83-95`, `apps/desktop/src/components/InfoPanel.tsx:99-105`
- **Reviewer-reproduced**: Snap-to-grid makes points ignore guides  
  Where: `apps/desktop/src/components/StitchCanvas.tsx:1229-1243`, `docs/USER-MANUAL.md:140`
- **Reviewer-reproduced**: Dialog dragging does not match its description: Esc closes the dialog instead of putting it back; the thread-charts dialog cannot be dragged  
  Where: `apps/desktop/src/dragDialogs.ts:1-6`, `apps/desktop/src/dragDialogs.ts:36-40`
- **Suspected**: onCancel guard on Export and Batch dialogs is defeated by a second Esc  
  Where: `apps/desktop/src/components/ExportDialog.tsx:163`, `apps/desktop/src/components/BatchDialog.tsx:69`
- **Reviewer-reproduced**: Panel resizer and dialog drags keep following the mouse after blur / pointercancel / lost mouse-up  
  Where: `apps/desktop/src/components/PanelResizer.tsx:53-66`, `apps/desktop/src/dragDialogs.ts:36-43`

### live-state

- **Reviewer-reproduced**: No-op edits add undo steps and mark the document modified (tabbing onto the picture opacity slider, clearing then reselecting a value, stale ids)  
  Where: `apps/desktop/src/design/layout.ts:440-444 (pushHistory only dedupes by reference)`, `apps/desktop/src/components/InfoPanel.tsx:632-633 (onKeyUp also commits on Tab)`
- **Reviewer-reproduced**: Closing, New or Open ignore an edit that is still rendering  
  Where: `apps/desktop/src/actions.ts:239-249 (confirmDiscard tests the displayed history)`, `apps/desktop/src/App.tsx:176-181 (close handler)`
- **Reviewer-reproduced**: After Save the window title and panel header keep the old name  
  Where: `apps/desktop/src/actions.ts:326-340 (the saved file gets title stem(path) but the in-memory layout.title is not updated)`, `apps/desktop/src/App.tsx:164`
- **Reviewer-reproduced**: Choosing a drawing tool before any document exists is silently reset to Select  
  Where: `apps/desktop/src/actions.ts:1521-1529 (tool(): setTool then replaceDoc)`, `apps/desktop/src/actions.ts:224-236 (replaceDoc calls s.setTool('select') at :229)`
- **Reviewer-reproduced**: Per-document UI state outlives its document: auto-trace reply for a deleted picture, Stitch Advisor proposals after Open, and pen points dropped when the render fails  
  Where: `apps/desktop/src/autoTrace.ts:59-106 (no check that the picture still exists after the await; setHistory does not clear autoTrace)`, `apps/desktop/src/actions.ts:224-236 (replaceDoc does not clear advice)`
- **Reviewer-reproduced**: A missing project file is reported as 'isn't a LUDD project or is damaged'  
  Where: `engine/threadline_engine/project.py:168-171 (OSError and BadZipFile get one message)`
- **Suspected**: One file per name overwrites files when two names map to the same file name  
  Where: `apps/desktop/src/features.ts:310-330 (no de-duplication of names after sanitising or ignoring case)`
- **Reviewer-reproduced**: Duplicate command ids: player.faster and player.slower are each registered twice  
  Where: `apps/desktop/src/actions.ts:1838-1845 and 1849-1865`, `already docs/QA-REPORT-2026-10-11.md M11`
- **Reviewer-reproduced**: After deleting every stitch of a colour in stitch-edit, the preview counts an extra colour change (export is right)  
  Where: `engine/threadline_engine/layout.py:166-174 (delete_stitches keeps JUMP/TRIM records)`, `engine/threadline_engine/layout.py:693 (blocks kept if they have any record)`

### packaging

- **Reviewer-reproduced**: Release workflow hardening: actions pinned only to mutable tags, checkout keeps the write token, ci.yml has no permissions block, and no tag/version guard  
  Where: `C:/Users/Copper Felix/HTML Stuffs/threadline/.github/workflows/release.yml:22,62,63,64,71,72,131,149`, `C:/Users/Copper Felix/HTML Stuffs/threadline/.github/workflows/release.yml:12-13,28-32`
- **Suspected**: CI and release builds are not locked: `uv run` and the tauri/cargo build can silently re-resolve dependencies  
  Where: `C:/Users/Copper Felix/HTML Stuffs/threadline/.github/workflows/ci.yml:22`, `C:/Users/Copper Felix/HTML Stuffs/threadline/.github/workflows/release.yml:83`
- **Reviewer-reproduced**: Cargo.toml rust-version = "1.77" is wrong: every Tauri dependency requires Rust 1.90  
  Where: `apps/desktop/src-tauri/Cargo.toml:7`
- **Reviewer-reproduced**: .gitignore gaps: untracked apps/desktop/tsconfig.tsbuildinfo is not ignored, and *.pfx / *.p12 certificates are not blocked  
  Where: `.gitignore:28-30`, `apps/desktop/tsconfig.tsbuildinfo`
- **Reviewer-reproduced**: Docs out of step with the build: USER-GUIDE download names say 1.0.0, CLAUDE.md dependency list is wrong, RELEASING.md step 1 omits lockfiles  
  Where: `docs/USER-GUIDE.md:14-17`, `CLAUDE.md:10`
- **Suspected**: Dev-only: the Vite engine bridge accepts POSTs from any origin and runs any engine RPC  
  Where: `apps/desktop/vite-engine-bridge.ts:50-80`
- **Reviewer-reproduced**: CI never runs the golden PES/JEF tests, and the snapshot test records a missing entry instead of failing  
  Where: `engine/tests/test_golden.py:17`, `engine/tests/test_digitize.py:314-321`
- **Reviewer-reproduced**: Documented command for scripts/make_installer_art.py fails: it imports make_manual_pdf, which needs markdown, websockets and pypdf  
  Where: `scripts/make_installer_art.py:4`, `scripts/make_installer_art.py:24`

### patterns

- **Confirmed**: Zero-length (repeated) stitches at every join in contour, cross and tatami regions, kept in the PES  
  Where: `engine/threadline_engine/digitize/stitches.py:43-50 (stitch_run only de-dupes inside one call)`, `engine/threadline_engine/digitize/stitches.py:106-120 (travel returns [] for d < MIN_STITCH_MM, else stitches ending on the target)`
- **Confirmed**: Edge underlay (and cross-hatch underlay) only covers one polygon's outer ring: shapes whose inset splits lose the edge run, holes never get one  
  Where: `engine/threadline_engine/digitize/stitches.py:631-635`, `engine/threadline_engine/digitize/stitches.py:638-648`
- **Confirmed**: Applique ignores the 'Lock stitches at the start/end' checkboxes the panel shows for it  
  Where: `apps/desktop/src/components/InfoPanel.tsx:588-589`, `engine/threadline_engine/digitize/stitches.py:686-690`
- **Confirmed**: Contour rings cut corners by about 1.2 mm, so square and pointed shapes are not filled to their corners  
  Where: `engine/threadline_engine/digitize/patterns.py:66`, `engine/threadline_engine/digitize/paths.py:115`
- **Confirmed**: Cross-stitch 'Square' sizes above about 4.95 mm sew diagonals over the app's own 7 mm limit; the warning's advice (shorter stitch length) does nothing for cross-stitch  
  Where: `engine/threadline_engine/digitize/stitches.py:440-441`, `engine/threadline_engine/digitize/stitches.py:43-50`
- **Confirmed**: Panel shows settings that do nothing for open patterns (Density, Random, Edge pad, Cross-hatch underlay, Length)  
  Where: `apps/desktop/src/components/InfoPanel.tsx:485-493`, `apps/desktop/src/components/InfoPanel.tsx:496`
- **Confirmed**: Fabric preset silently clamps fill spacing to [0.2, 3.0], so the FillParams 0.2-5 range and its validation never apply on the render path  
  Where: `engine/threadline_engine/fabrics.py:72`, `engine/threadline_engine/layout.py:442`
- **Confirmed**: Motif lines (blanket, scallop) sit on one side of the drawn line and swap sides with drawing direction or mirroring; no side control  
  Where: `engine/threadline_engine/digitize/patterns.py:195-196 (blanket unit: base at -0.5, tooth at +0.5)`, `engine/threadline_engine/digitize/patterns.py:222-225 (left-hand normal from travel direction, no winding normalisation)`
- **Confirmed**: Contour fill re-buffers the full outline for every ring, so dense or wobbly outlines take seconds to a minute to render  
  Where: `engine/threadline_engine/digitize/patterns.py:58-60`, `engine/threadline_engine/digitize/stitches.py:604`
- **Confirmed**: Applique satin border is never split: borders of about 6.8 mm or more (and sharp-cornered shapes from 3.5 mm) sew stitches over the 7 mm loose-stitch limit  
  Where: `engine/threadline_engine/digitize/applique.py:131-132`, `apps/desktop/src/components/InfoPanel.tsx:516`
- **Confirmed**: Stipple seed comes from the shape's centroid, so any move or point edit regenerates a different stipple pattern  
  Where: `engine/threadline_engine/digitize/stitches.py:606`, `engine/threadline_engine/layout.py:441`

### project

- **Confirmed**: Save is brittle on Windows: no retry when the destination is briefly locked, stale .ludd-*.tmp files are never swept (project folder and recovery folder), and paths whose temp name exceeds 259 characters fail with a misleading message  
  Where: `engine/threadline_engine/project.py:127`, `engine/threadline_engine/project.py:135`
- **Confirmed**: Double-clicked .ludd file is silently dropped when a crash recovery is pending (never opened, even after Discard)  
  Where: `apps/desktop/src/App.tsx:324-332`, `apps/desktop/src/App.tsx:206-235`
- **Confirmed**: Recovery copy can be deleted by a startup race (and, unverified, by closing too fast)  
  Where: `apps/desktop/src/App.tsx:57-65`, `apps/desktop/src/App.tsx:324-326`
- **Confirmed**: Autosave is all-or-nothing on unreadable pictures and recovery() only tolerates damaged zips (hardening gaps; both preconditions are unreachable through normal UI use)  
  Where: `engine/threadline_engine/project.py:65-69`, `engine/threadline_engine/project.py:99-121`
- **Confirmed**: Opening a hostile or corrupt .ludd reads unbounded data into memory, and an oversize image member is also written to the disk cache (zip bomb)  
  Where: `engine/threadline_engine/project.py:174`, `engine/threadline_engine/project.py:186-191`
- **Confirmed**: Private copy cache (project-files) is never pruned and is trusted by file name without a hash check  
  Where: `engine/threadline_engine/kept.py:25-33`, `engine/threadline_engine/project.py:183-192`
- **Confirmed**: Data-folder migration from Threadline never merges: if %APPDATA%\Ludd already exists, the old folder's data is ignored silently  
  Where: `engine/threadline_engine/storage.py:14-27`, `engine/threadline_engine/kept.py:13,35-36,40-43`
- **Confirmed**: No project schema exists, and the machine schema is stale and unused; CLAUDE.md's schema-first rule is not followed  
  Where: `CLAUDE.md:11`, `docs/PLAN.md:113`
- **Confirmed**: Thread chart ids are used unchecked as file names (get_chart / delete_chart accept '../' ids), and delete_chart('my-threads') deletes My threads: hardening only  
  Where: `engine/threadline_engine/threads.py:165-173`, `engine/threadline_engine/threads.py:262-267`
- **Confirmed**: Opening a project overwrites the user's saved machine and hoop preference (persists across restarts, no notice)  
  Where: `apps/desktop/src/actions.ts:300-304`, `apps/desktop/src/store.ts:494-503`
- **Confirmed**: 'One file per name' can silently lose or overwrite files: Windows device names, duplicate and case-only-duplicate names, existing files  
  Where: `apps/desktop/src/features.ts:314-329`, `apps/desktop/src/components/FeatureDialogs.tsx:197-226`

### satin

- **Confirmed**: A ribbon wider than the local curve radius folds its inner edge (rungs cross, thread piles up) with no warning  
  Where: `engine/threadline_engine/digitize/stitches.py:315-322 (rung offset uses the full half-width regardless of local curvature)`, `engine/threadline_engine/digitize/stitches.py:334-352 (satin_from_pairs only warns on width: auto-widen, over SATIN_MAX_WIDTH_MM, under SATIN_MIN_WIDTH_MM)`
- **Confirmed**: Reversed or twisted legacy rail columns sew as a bow-tie of long stitches; the warning is only 'too wide' and short columns get no warning at all (QA-REPORT L5)  
  Where: `engine/threadline_engine/digitize/stitches.py:252-266 (satin_pairs: no direction or crossing check; docstring 'stitches never cross' is only true for same-direction rails)`, `engine/threadline_engine/digitize/stitches.py:347-349 (width warning is the only signal)`
- **Confirmed**: Running stitches and rail columns shorter than the 0.3 mm minimum stitch produce one lone, unlocked needle drop and no message  
  Where: `engine/threadline_engine/digitize/stitches.py:43-50 (stitch_run drops points under MIN_STITCH_MM)`, `engine/threadline_engine/digitize/stitches.py:53-77 (tie_in/tie_off return early when fewer than 2 stitches)`
- **Confirmed**: Closed motif line does not close at a corner start: first and last needle points differ by about 0.7 x motif width  
  Where: `engine/threadline_engine/digitize/patterns.py:200-226`, `engine/threadline_engine/digitize/stitches.py:160-164`
- **Confirmed**: Test gaps in the satin and running-stitch lane; the split test and snapshot mechanism hide regressions  
  Where: `engine/tests/test_digitize.py:317`, `engine/tests/test_digitize.py:368-372`
- **Confirmed**: "Split long stitches" lets pieces run up to 33% longer than the "Longest" setting (8 mm satin at Longest 4 still has 5.33 mm stitches)  
  Where: `engine/threadline_engine/digitize/stitches.py:384-391`, `engine/threadline_engine/quality.py:27`
- **Confirmed**: Wide satins: no automatic split, and the satin's own warning only starts at 10 mm while the manual and design check say 7 mm (also QA-REPORT L4)  
  Where: `engine/threadline_engine/digitize/stitches.py:221`, `engine/threadline_engine/digitize/stitches.py:347-349`
- **Confirmed**: Pen-tool curves hook past a node when neighbouring segments differ in length by about 8:1 or more (uniform Catmull-Rom tangents)  
  Where: `engine/threadline_engine/digitize/paths.py:49-57`, `engine/threadline_engine/digitize/paths.py:65-79`
- **Confirmed**: Ribbon widths 0.5 to 0.99 mm are accepted by the Width control but always sew at 1.0 mm  
  Where: `engine/threadline_engine/fabrics.py:80`, `engine/threadline_engine/digitize/stitches.py:223`

### security

- **Confirmed**: Huge-pixel pictures: tracing allocates 1.4-2.9 GB at full size before downscaling, and over 179 MP the user gets a raw Pillow "decompression bomb" message  
  Where: `engine/threadline_engine/project.py:79-90 (load_image caps file bytes only)`, `engine/threadline_engine/trace.py:66-84 (analyse: convert('RGBA'), Image.new, alpha_composite at full size before the resize)`
- **Confirmed**: Crafted .vp3 or .hus (tens to ~1,000 bytes) makes the stitch-file reader allocate 2-4 GB for under a second  
  Where: `engine/threadline_engine/design.py:87 (pe.read on a real file handle, in load() at :79)`, `engine/threadline_engine/library.py:86 (entry() -> design.load, reached by scan() at :100 for every file in a browsed folder)`
- **Confirmed**: No upper bound on shape size or stitch count: a huge fill ties up the single engine thread for minutes  
  Where: `engine/threadline_engine/digitize/stitches.py:445`, `engine/threadline_engine/digitize/stitches.py:454-466`
- **Confirmed**: Chart id used as a file name without validation (read/delete any .json outside the charts folder), and fonts.export_stitch_font writes JSON to any path with any extension  
  Where: `engine/threadline_engine/threads.py:165-173`, `engine/threadline_engine/threads.py:262-267`
- **Confirmed**: Project cache trusts member names as content hashes: opening one .ludd can plant wrong bytes that later projects reuse  
  Where: `engine/threadline_engine/project.py:183-192 (extract: exists-check, no hash verification)`, `engine/threadline_engine/project.py:197-199 (image path: poisoned file is also loaded as the data_url)`
- **Confirmed**: Update check reads the preference once at mount; GitHub request fires 8 s later even if the user declines or has not yet answered the welcome card  
  Where: `apps/desktop/src/updates.ts:57-61`, `apps/desktop/src/App.tsx:263-290`
- **Confirmed**: Release workflow hardening gaps: all actions pinned to moving tags (incl. tauri-action, which gets the updater signing key), checkout leaves a write token on disk, `uv run` not `--locked`  
  Where: `.github/workflows/release.yml:22,24,62-64,71-72,131,148-149 (tag-pinned `uses:`; tauri-action at :131 is the step that receives TAURI_SIGNING_PRIVATE_KEY at :135-136 and GITHUB_TOKEN at :133)`, `.github/workflows/release.yml:12-13 (workflow-wide contents: write)`
- **Confirmed**: Updater signing key and its password sit side by side in plaintext on the dev PC, and RELEASING.md never says to delete the password file  
  Where: `docs/RELEASING.md:13-29`, `docs/RELEASING.md:21-23`
- **Confirmed**: Saved .ludd projects embed the Windows account name in the text font's absolute path  
  Where: `engine/threadline_engine/project.py:99-121`, `engine/threadline_engine/lettering.py:46-57`
- **Confirmed**: Copies of every picture and design you add are kept forever in %APPDATA%\Ludd\project-files (no cleanup, no mention in the docs)  
  Where: `engine/threadline_engine/kept.py:25-33`, `engine/threadline_engine/project.py:49-52`
- **Confirmed**: AI settings accept wrong types (scalar replaces a section) and then break every AI call (first reported as M13, still present)  
  Where: `engine/threadline_engine/ai/settings.py:49-56 (_merge: the `elif k in out: out[k] = v` branch lets a scalar replace a default dict)`, `engine/threadline_engine/ai/settings.py:74-86 (save: validates only mode, provider and URLs, not types of features or prices)`
- **Confirmed**: Print template builds HTML strings with an unescaped colour and runs them in a same-origin iframe (safe today only by luck of engine normalisation)  
  Where: `apps/desktop/src/print.ts:9 (esc covers & < > " but is not applied to colour)`, `apps/desktop/src/print.ts:25 (colour fallback and passthrough in stitchPaths)`
- **Confirmed**: AI "On this computer" mode accepts any address and skips the "before you send" preview; cloud address may be plain http; the send dialog never names the host  
  Where: `apps/desktop/src/ai.ts:88-90`, `apps/desktop/src/ai.ts:117`
- **Confirmed**: AI tracing model download is not pinned or hash-checked (moving /resolve/main/ URL, redirects to http followed)  
  Where: `engine/threadline_engine/ai/segment.py:25-30`, `engine/threadline_engine/ai/segment.py:61-84`
- **Confirmed**: Project zip members are read with no size limit: a 0.3 MB .ludd expands to 300+ MB in memory (and embedded members to disk)  
  Where: `engine/threadline_engine/project.py:174`, `engine/threadline_engine/project.py:188`
- **Reviewer-reproduced**: Design browser and batch convert follow Windows junction loops: 600 duplicate entries for one real file in 26 s, and convert aborts with a raw OS error  
  Where: `engine/threadline_engine/library.py:100-120`, `engine/threadline_engine/design.py:205-241`

### shapeops

- **Confirmed**: "Also around the inside of holes" silently skips small holes (stitched gap under about 4.2 mm); only matters for outline distances under about 1 mm  
  Where: `engine/threadline_engine/shapeops.py:151-152 (0.6 mm thickening plus buffer(1.5).buffer(-1.5) closing fills any hole with a gap under 4.2 mm)`, `engine/threadline_engine/shapeops.py:160-161 (hole rings read from the already closed area, with an area >= 4 filter)`
- **Confirmed**: Outline ring can sit up to about 0.6 mm inside the requested distance at tight turns, and nothing in the Outline dialog controls the point spacing that causes it  
  Where: `engine/threadline_engine/shapeops.py:47-105 (to_nodes: uniform 'spacing' mm picks, smooth between corners)`, `engine/threadline_engine/shapeops.py:213-217 (offset ring built with to_nodes at caller spacing)`
- **Confirmed**: Shape-operation messages are misleading or raw: empty negative offset says "try a bigger one", mm limit text shown in inch mode, knife disarmed before the engine answers, raw shapely errors, success shown after a failed commit  
  Where: `engine/threadline_engine/shapeops.py:131-132 (mm limit text)`, `engine/threadline_engine/shapeops.py:198-205 (shapely_split on run/satin not wrapped; no >=2-node guard)`
- **Confirmed**: Merge: "first" means earliest in the layout (not first clicked), the merged shape takes that slot, and a corner-only touch is accepted as one shape  
  Where: `apps/desktop/src/features.ts:28-32 (selectedItems() returns layout order, not selection order)`, `apps/desktop/src/features.ts:202-220 (mergeSelected: items[0] is the earliest in layout; others removed, merged shape placed at that slot)`
- **Confirmed**: Knife/merge silently drop holes under 2 mm2; test file has a vacuous assertion and no coverage of the failure cases above  
  Where: `engine/threadline_engine/shapeops.py:110 (`if Polygon(r).area >= 2.0` in _poly_nodes; used by split at :197 and merge at :227)`, `engine/threadline_engine/shapeops.py:18 and :231 (unused MultiPolygon import and `_ = MultiPolygon`)`
- **Confirmed**: Text longer than its drawn line piles up at the ends; the length warning is a dead statement (circle shape does warn)  
  Where: `engine/threadline_engine/lettering.py:495-496`, `engine/threadline_engine/lettering.py:434`
- **Suspected**: Knife clicks do not snap to guides, grid or existing points  
  Where: `apps/desktop/src/components/StitchCanvas.tsx:1383-1388`, `apps/desktop/src/components/StitchCanvas.tsx:1545-1548`
- **Suspected**: One-file-per-name can silently overwrite files (duplicate or case-different names, existing files)  
  Where: `apps/desktop/src/features.ts:310-330`, `apps/desktop/src/components/FeatureDialogs.tsx:197,228`

### tauri

- **Reviewer-reproduced**: The CSP has no connect-src, so Tauri's fast IPC is blocked; every session logs a CSP error and falls back to postMessage  
  Where: `apps/desktop/src-tauri/tauri.conf.json:24`
- **Reviewer-reproduced**: Offline 'Check for updates' shows a raw networking error  
  Where: `apps/desktop/src/updates.ts:35-38`
- **Suspected**: launch_file uses std::env::args(), which panics on a non-Unicode argument  
  Where: `apps/desktop/src-tauri/src/lib.rs:6-10`
- **Suspected**: Private copies of every added picture/design are never pruned, and autosave resends whole pictures  
  Where: `engine/threadline_engine/kept.py:25-33`, `engine/threadline_engine/project.py:182-194,208-214`
- **Reviewer-reproduced**: apps/desktop/tsconfig.tsbuildinfo is an untracked build artifact that is not git-ignored  
  Where: `.gitignore`, `apps/desktop/tsconfig.tsbuildinfo`

### tests

- **Reviewer-reproduced**: Layout caches: nothing detects a field dropped from the text-cache key (size, shape)  
  Where: `engine/threadline_engine/layout.py:462`, `engine/threadline_engine/layout.py:421`
- **Reviewer-reproduced**: Several tests pass even when the behaviour they name is broken (ribbon miter limit, motif shape, shortest-order overlap guard)  
  Where: `engine/tests/test_digitize.py:387`, `engine/tests/test_patterns.py:66`
- **Reviewer-reproduced**: Assertions that cannot fail: `or True`, key-membership, `or` in a stipple check, registered-name lists  
  Where: `engine/tests/test_shapeops.py:35`, `engine/tests/test_layout.py:197`
- **Reviewer-reproduced**: Any TypeError inside an engine method is reported as 'invalid params' (-32602) and is not logged  
  Where: `engine/threadline_engine/rpc.py:71`, `engine/tests/test_rpc.py:32`
- **Reviewer-reproduced**: No registry invariant test; two command ids are defined twice (player.slower and player.faster)  
  Where: `apps/desktop/src/actions.ts:1838`, `apps/desktop/src/actions.ts:1849`
- **Suspected**: Test collection reads (and may migrate) the real user data folder, and the AI-model test results depend on the machine  
  Where: `engine/tests/test_autotrace.py:223`, `engine/tests/test_autotrace.py:230`
- **Suspected**: Wall-clock assertions in engine tests can flake on slow or busy runners  
  Where: `engine/tests/test_autotrace.py:112`, `engine/tests/test_autotrace.py:117`

### visual

- **Confirmed**: Cross-hatch underlay leaks stitches outside the shape when an inset arm collapses to a zero-width spike (arms exactly 1.2 mm wide)  
  Where: `engine/threadline_engine/digitize/stitches.py:638-648 (fill: poly.buffer(-0.6) feeds tatami with zero-width spikes)`, `engine/threadline_engine/digitize/stitches.py:527-529 (tatami: rotate, then _rows on the degenerate polygon)`
- **Confirmed**: Lettering ignores the fabric preset (identical stitches on all seven fabrics); the UI gives no hint  
  Where: `engine/threadline_engine/layout.py:459-502 (_text_block takes no fabric and never calls fabrics.apply)`, `engine/threadline_engine/layout.py:442 and :650 (drawn objects do get fabrics.apply and layout.get('fabric'))`
- **Confirmed**: Characters missing from the font are silently swapped for '?' (outline fonts) or silently dropped (stitch fonts), with no warning  
  Where: `engine/threadline_engine/lettering.py:288-292`, `engine/threadline_engine/lettering.py:338-343`
- **Confirmed**: Fill underlay is skipped for part of a shape when a neck is narrower than about 1.0 mm (edge run) or 1.2 mm (cross-hatch), with no warning  
  Where: `engine/threadline_engine/digitize/stitches.py:632-635`, `engine/threadline_engine/digitize/stitches.py:641-642`
- **Confirmed**: Fill region joins and underlay-to-top joins pierce the same hole twice (zero-length stitch)  
  Where: `engine/threadline_engine/digitize/stitches.py:106-120 (travel returns b as its last stitch)`, `engine/threadline_engine/digitize/stitches.py:595-596 (tatami region join)`
- **Confirmed**: Satin ribbon round a curve tighter than half its width folds on the inside with no warning (rungs cross, needle points bunch)  
  Where: `engine/threadline_engine/digitize/stitches.py:284-323 (ribbon_pairs: no radius-of-curvature check)`, `engine/threadline_engine/digitize/stitches.py:330-352 (satin_ribbon/satin_from_pairs: warning logic only looks at rung length)`
- **Confirmed**: Satin width thresholds disagree: manual and Checks say about 7 mm, satin warning says 10 mm  
  Where: `engine/threadline_engine/digitize/stitches.py:221`, `engine/threadline_engine/digitize/stitches.py:347-349`
- **Suspected**: Guides do not snap while snap-to-grid is on (grid rounding returns before the guide test)  
  Where: `apps/desktop/src/components/StitchCanvas.tsx:1229-1244`, `docs/USER-MANUAL.md:140`
- **Suspected**: One file per name: duplicate names (or names that map to the same file name) silently overwrite each other  
  Where: `apps/desktop/src/features.ts:309-329`, `engine/threadline_engine/layout.py:827-835`

## Known soft spots: outcome

| Soft spot | Area | Outcome | Detail |
|---|---|---|---|
| "Fewer jumps" (travel_under) only hides a move when the straight path ... | autotrace | problem-confirmed | Confirmed by reading layout._join_objects (path.within(hidden), hidden = union of later covers shrunk 0.3 mm): only the straight start-to-start path is tested. As a limitation this matches the changelog. In the same ... |
| Guides snap placed and dragged points only, not whole-shape drags | autotrace | could-not-check | Outside the auto-trace lane; not examined. |
| Text on a drawn line: if the text is longer than the line, the extra ... | autotrace | could-not-check | Outside the auto-trace lane; not examined. |
| Stitch-edit moves are stored as world-space deltas, which drift if ... | autotrace | could-not-check | Outside the auto-trace lane; not examined. |
| "One file per name" export and the design-browser folder picker were ... | autotrace | could-not-check | Outside the auto-trace lane; no installed-app run was possible. |
| Stitch-edit canvas draws every needle point: check performance on ... | autotrace | could-not-check | Outside the auto-trace lane. Related data point from my lane: whole-picture results of 8,500 to 19,000 stitches render fine in the engine; the slow part is object count (finding on 3,199 objects), not stitch count. |
| Little or no test coverage: whole-picture digitize (one test) | autotrace | problem-confirmed | test_whole_picture_becomes_fills_then_satin_outlines is the only digitize_all test and uses one clean synthetic PNG; none of the failures found here (JPEG colours, dark or cropped backgrounds, counters, soft edges, ... |
| "Fewer jumps" (travel_under) only hides a move when the straight path ... | compat | problem-confirmed | Confirmed as stated and conservative: only a dense fill (0.4 mm rows) counts as cover; 1.2/1.6/2.5 mm tatami, cross-stitch, stipple and contour covers all fall back to jump+trim. The shipped samples gain nothing ... |
| Guides snap placed and dragged points only, not whole-shape drags | compat | not-a-problem | By code (StitchCanvas.tsx snapped(), called at the point-placing, cursor and point-drag sites, not in the shape-move drag or moveBy) this is as described, and the manual (line 140) says only 'points you place or drag' ... |
| Text on a drawn line: if the text is longer than the line, the extra ... | compat | problem-confirmed | Confirmed: ten W's on a 20 mm line put four letters on top of each other at each end, with no warning from the engine (a code comment says one exists, the branch is a no-op). A second, related defect: textOnLine ignores ... |
| Stitch-edit moves are stored as world-space deltas, which drift if ... | compat | problem-confirmed | Confirmed for rotation and scale: a 1.5 mm move stays (1.5, 0) after a 90 degree turn and after 200% enlargement. A second defect in the same ops list: an inserted stop is lost if its anchor stitch is deleted. |
| "One file per name" export and the design-browser folder picker were ... | compat | problem-confirmed | One file per name has a real defect: it calls layout.export with options {}, so none of the PE550D cut-stops or machine checks are applied (0 stops vs 7 for Save for machine on the same text). The folder picker looks ... |
| Stitch-edit canvas draws every needle point: check performance on ... | compat | could-not-check | Needs the browser. By code, drawStitchEdit (StitchCanvas.tsx ~732) loops over all design records twice per redraw and adds one Graphics rect per unselected stitch of the edited item (about 30k rects for a 30k-stitch ... |
| Little or no test coverage: whole-picture digitize, ... | compat | problem-confirmed | Confirmed: no UI test touches colorways, garment preview, guides, exportNames, shortestOrder, textOnLine or the stitch-edit actions; engine tests exist for travel_under/optimize_order (test_connectors.py) but only with ... |
| Fewer jumps (travel_under) only hides a move when the straight path ... | docs-b | not-a-problem | Confirmed by code (layout.py:516 path.within(hidden)) and a run: A,B navy then red cover gives 0 jumps/0 trims, same without the cover or with the cover sewn earlier gives 1 jump + 1 trim. The manual states exactly this ... |
| Guides snap placed and dragged points only, not whole-shape drags | docs-b | problem-confirmed | StitchCanvas.tsx:1618-1619 moves a whole shape by raw pointer delta with no snapping to guides or grid. Also snapped() (1218-1260) returns at the grid step before checking guides and other shapes' points, so with ... |
| Text on a drawn line: if the text is longer than the line, the extra ... | docs-b | problem-confirmed | 12 letters on a 30 mm line overlap 70 percent with no warning (lettering.py:495-496 has an empty 'if' and a comment promising a warning). See the text-on-a-line findings, which also show the line is ignored when the ... |
| Stitch-edit moves are stored as world-space deltas, which drift if ... | docs-b | problem-confirmed | Ran: own 26-stitch PES, stitch #3 moved 3 mm down, then item rotated 90 degrees: the moved stitch is still offset (0,+3) in world space relative to the rotated design instead of rotating with it (layout.py:177-193 ... |
| One file per name export and the design-browser folder picker were ... | docs-b | problem-confirmed | Names export has a real defect independent of the installed app: it ignores machine options (no cut-stops, no hoop check, silent overwrite) - see the finding. Folder picker: capabilities/default.json grants ... |
| Stitch-edit canvas draws every needle point: check performance on ... | docs-b | could-not-check | No browser access. Static read: drawStitchEdit (StitchCanvas.tsx:732-756) builds one rect per stitch (two passes over all records) on every overlay redraw, including each pointer move while dragging or box-selecting, ... |
| Little or no test coverage: whole-picture digitize, ... | docs-b | problem-confirmed | The UI layer has no tests for shortest order, jumps-to-trims state, insert-at-needle on lettering, colour sets or guides, and the findings on shortest order, Trim jumps and Insert a stop all live in exactly those ... |
| 'Fewer jumps' (travel_under) only hides a move when the straight path ... | docs-c | problem-confirmed | Confirmed by test: with a blue patch covering the whole way from red A to red B, 0 jumps and 0 trims; shrinking the patch so about 4 mm of the 40 mm path is uncovered gives 1 jump + 1 trim again (same as travel_under ... |
| Guides snap placed and dragged points only, not whole-shape drags | docs-c | not-a-problem | The limitation is real (snapped() in StitchCanvas.tsx is called only for pen placement at 1453, the cursor preview at 1568 and node drags at 1606; moves, resizes and rotation do not snap) but the manual says exactly ... |
| Text on a drawn line: if the text is longer than the line, the extra ... | docs-c | problem-confirmed | Confirmed: 16 characters at 10 mm on a 20 mm line give 14 letters, about 7 stacked at each end, and no warning; the code comment claims a warning exists. The manual does not mention the limit. See finding 4. |
| Stitch-edit moves are stored as world-space deltas, which drift if ... | docs-c | problem-confirmed | Confirmed with layout.render: the same move_stitch op displaces the stitch by the same world (5, 0) mm at 0 and at 90 degrees of design rotation; scale and mirror are not applied either. The code comment says the ... |
| 'One file per name' export and the design-browser folder picker were ... | docs-c | could-not-check | The installed app was not run. Statically: the capability file has dialog:allow-open (covers the directory picker) and the engine receives plain paths, so the picker should work; in the preview the picker is ... |
| Stitch-edit canvas draws every needle point: check performance on ... | docs-c | problem-suspected | Confirmed by reading: drawStitchEdit (StitchCanvas.tsx:732-756) loops over all records twice and adds one rect or circle per needle point on every overlay redraw, with a new Set of the selection each time; nothing is ... |
| Little or no test coverage: whole-picture digitize, ... | docs-c | problem-confirmed | digitize_all is called by one test (test_autotrace.py:262); offset/knife/merge have 7 engine tests (test_shapeops.py) and no UI tests; grep finds no test file mentioning colorways, guides or garments (the only hit is ... |
| "Fewer jumps" (travel_under) only hides a move when the straight path ... | fill | not-a-problem | Behaves as the manual describes ('the way there will be covered by stitching sewn later'). Rendering two same-thread fills: a 30x30 square sewn after a 20x20 one inside it gives 0 jumps/trims with travel_under on (1 ... |
| Little or no test coverage (whole-picture digitize, ... | fill | problem-confirmed | For my area the new pattern tests (engine/tests/test_patterns.py) and the new snapshots use only a plain 30 mm square. None of the Medium findings (wave gaps, stipple on multi-lobe shapes, MultiPolygon drop, lobe/hole ... |
| Stitch-edit moves stored as world-space deltas; stitch-edit canvas ... | fill | could-not-check | Outside the fill lane and needing the UI or installed app; not examined. |
| "Fewer jumps" (travel_under) only hides a move when the straight path ... | fuzz-rpc | problem-confirmed | The documented limitation itself works as described (a half-covered gap falls back to one trim and one jump, which the PE550D will not cut without cut-stops). Around it I found real defects: GEOSException on valid ... |
| Guides snap placed and dragged points only, not whole-shape drags | fuzz-rpc | could-not-check | Pure UI behaviour with no engine or RPC part; needs the browser preview. |
| Text on a drawn line: extra letters pile up at the ends when the text ... | fuzz-rpc | problem-confirmed | Confirmed (11 letters on a 30 mm line: same stitch count, width 38.9 mm). The code at lettering.py:493-496 is a no-op whose comment promises a warning; no warning or check is produced and the manual does not mention it. |
| Stitch-edit moves are stored as world-space deltas, which drift if ... | fuzz-rpc | problem-confirmed | Confirmed: a 3 mm drag stays (+3, 0) after rotate 90 and after scale 200%. Also found the related index drift of stops/deletes on drawn shapes. |
| "One file per name" export and the design-browser folder picker were ... | fuzz-rpc | problem-suspected | Read the code: exportNames uses empty export options, does not de-duplicate names and overwrites existing files; engine-side overwrite and the CON.pes failure were reproduced. The folder picker could not be checked. |
| Stitch-edit canvas draws every needle point: check performance on ... | fuzz-rpc | could-not-check | Canvas code needs the app. Engine side is fine: the 27k-stitch Heart.thin fixture renders in 0.25 s and the layout response is a few MB. |
| Little or no test coverage: whole-picture digitize, ... | fuzz-rpc | not-a-problem | Fuzzing trace.digitize_all/region/suggest, shape.offset/split/merge, optimize_order and preview_export (about 400 calls, synthetic pictures including 900-dot and noise images) gave no internal errors and strict-JSON ... |
| Text on a drawn line: if the text is longer than the line, the extra ... | lettering | problem-confirmed | Confirmed and measured. 15 letters at 10 mm on a 40 mm line: the first five centres sit at x=-20..-21 and the last five at x=+19.6..+20, 40% of letter area is stitched twice, 19 needle hits per mm2 against 8 when it ... |
| "One file per name" export and the design-browser folder picker were ... | lettering | problem-confirmed | The logic has real faults regardless of the dialogs: it exports with options {} (no machine, hoop or cut-stops), ignores returned warnings, and overwrites colliding names silently (vitest with mocked actions: 5 names, 2 ... |
| "Fewer jumps" (travel_under) only hides a move when the straight path ... | lettering | not-a-problem | For lettering this simply never applies: letters are one block and the move from letter to letter is never covered by later stitching. With travel_under on, 'Emma' still has 3 trims and 'Hello World' 9; with PE550D ... |
| Little or no test coverage (whole-picture digitize, ... | lettering | problem-confirmed | For my area test_lettering.py has 12 tests but none for old .tlfont files, damaged stitch fonts, missing glyphs, case handling, text longer than the line, closed paths, per-letter rotation vs satin angle, Smile ... |
| Guides snap placed and dragged points only, not whole-shape drags | lettering | could-not-check | Outside the lettering lane; not examined. |
| Stitch-edit moves are stored as world-space deltas, which drift if ... | lettering | could-not-check | Outside the lettering lane; the earlier report docs/QA-REPORT-2026-10-11.md says it was checked at 90 degrees and does not drift. |
| Stitch-edit canvas draws every needle point: performance on 30k+ ... | lettering | could-not-check | Needs the live app; not in my lane. For lettering, the largest text I produced was 126k stitches (200 mm wide W's) and the sidecar returned it in 6.5 s with a 3.3 MB reply. |
| Fewer jumps (travel_under) only hides a move when the path is ... | live-esc | could-not-check | Engine/stitch output, outside the Esc and pointer area; not examined. |
| Guides snap placed and dragged points only, not whole-shape drags | live-esc | problem-confirmed | That limit matches the manual (line 140 says points). Whole-shape drags never use guides. Separate finding: with Snap to grid on, points ignore guides entirely (x 6.35 instead of 7.3). |
| Text on a drawn line: extra letters pile up at the ends | live-esc | could-not-check | Lettering engine, outside my area. |
| Stitch-edit moves are stored as world-space deltas and drift if the ... | live-esc | problem-confirmed | Engine check with a scratch PES: layout._move_stitches runs after _transform, so a 5 mm move of stitch #3 is (5.0, 0.0) unrotated and still (5.0, 0.0) after rotating the item 90 degrees (it should become (0, 5)). The ... |
| One file per name export and the design-browser folder picker were ... | live-esc | problem-confirmed | Names dialog uses a stale default file type (PES for a JEF machine), found in the preview. The folder pickers and the installed app were not exercised. |
| Stitch-edit canvas draws every needle point: performance on 30k+ ... | live-esc | could-not-check | 40,200-stitch PES in the preview: entering stitch-edit took about 1.5 s and each box-drag frame about 1.1 s, but a plain pan of the same design also costs about 1.1 s/frame in this software-rendered pane, so stitch-edit ... |
| Little or no test coverage (whole-picture digitize, ... | live-esc | problem-confirmed | escape.test.ts only covers the stack and command order. Nothing tests canvas drag holds, blur, features.ts holds, or dialogs; the stale-hold bugs found (blur, knife) are exactly those gaps. |
| 'Fewer jumps' (travel_under) only hides a move when the straight path ... | live-state | could-not-check | Engine routing and travel logic are outside the live-state lane; I only saw that the toggle is one commit and one undo step. QA-REPORT-2026-10-11.md C1 covers a related travel_under/colour-sort problem. |
| Guides snap placed and dragged points only, not whole-shape drags | live-state | not-a-problem | By code (StitchCanvas.tsx onMove): snapped() is used for pen points and node drags; the 'move' branch sets the ghost position without snapping. The manual (USER-MANUAL.md:140) says 'Points you place or drag near a guide ... |
| Text on a drawn line: text longer than the line piles up at the ends | live-state | could-not-check | Lettering geometry is another reviewer's lane. In my lane textOnLine is one commit and one undo step and the layout still renders. |
| Stitch-edit moves are stored as world-space deltas, which drift if ... | live-state | problem-confirmed | Engine render of Flower.pes: a stitch moved 5 mm in x is still displaced (5.00, 0.00) at rotate 90 (should be (0, 5)); layout.py applies _move_stitches after _transform. See finding 'Stitch-edit moves are stored as ... |
| One file per name export and the design-browser folder picker were ... | live-state | problem-confirmed | In the preview I found a stale-reply race in BrowseDialog.scan (slow earlier scan overwrites the newer folder and the saved pref) and, by code, file-name collisions in exportNames. The native folder dialog and the ... |
| Stitch-edit canvas draws every needle point: performance on 30k+ ... | live-state | problem-confirmed | Heart.thin.PES (27,248 stitches): box-select of 12,251 stitches gave rAF gaps of 348/194/1,021 ms and long tasks of 65-271 ms; each pointer move redraws all points. Moving 12,251 stitches also creates 12,251 move_stitch ... |
| Little or no test coverage (whole-picture digitize, ... | live-state | problem-confirmed | No UI test touches the pending/superseded-render paths in actions.ts or the selection, Esc-hold or recovery flows. I wrote 10 scratch vitest cases (fake engine) that all fail today; kept outside the repo in the scratch ... |
| "One file per name" export and the design-browser folder picker were ... | packaging | could-not-check | I could not run the installed app. From the packaging side nothing blocks them: the folder picker calls `open({directory:true})` (features.ts:335), which `dialog:allow-open` in capabilities/default.json covers. The ... |
| Little or no test coverage (whole-picture digitize, ... | packaging | not-a-problem | CI does run all engine and UI tests and the typecheck on Windows and macOS (arm64), so any tests that exist do run. The coverage gap itself is outside packaging. The CI gaps I found are different: no Intel Mac or Linux ... |
| Fewer jumps (travel_under) only hides a move when the straight path ... | patterns | not-a-problem | For these patterns the code (layout._join_objects: path.within(hidden), covers from later blocks only) behaves as stated and errs on the safe side. Test: red squares A and B 38 mm apart with a later red 54 mm fill. ... |
| Little or no test coverage (whole-picture digitize, ... | patterns | problem-confirmed | In my area tests/test_patterns.py (14 tests, all passing) covers containment, ring count, stipple simplicity and motif extents, but nothing for holes or necks in stipple, applique holes, cross connectors (only diagonals ... |
| Fewer jumps (travel_under) only hides a move when the straight path ... | satin | problem-confirmed | Works as documented with satin covers: a whole-path cover gives 8 hidden travel stitches and no jump or trim; a partial cover and a ring cover with a hole fall back to one jump plus one trim. The real defect is that the ... |
| Little or no test coverage (whole-picture digitize, ... | satin | problem-confirmed | In the satin/running lane: triple, three of four motifs, split, comp_by_width, auto_widen, auto underlay on ribbons, hairpins, seam, advisor-with-ribbon and an old-rails golden have no test, and the split test tolerance ... |
| Stitch-edit moves are stored as world-space deltas, which drift if ... | satin | could-not-check | Not in the satin/running lane; layout._move_stitches is applied after the transform and only on stitch files, so objects are unaffected. |
| Stitch-edit canvas draws every needle point (30k+ stitches) | satin | could-not-check | UI only; not exercised in this lane. |
| "One file per name" export and the design-browser folder picker were ... | security | problem-confirmed | Permissions are fine for the installed app: pickFolder uses open({directory:true}), covered by dialog:allow-open, and the path then goes to the engine, so no fs scope is needed. I could not run the installed app. ... |
| Little or no test coverage: whole-picture digitize (one test), ... | security | could-not-check | Only the security-relevant parts of those features were read (library.scan, shapeops file handling, features.ts export). No coverage measurement. No security issue found in whole-picture digitize beyond the shared ... |
| "Fewer jumps" (travel_under) only hides a move when the straight path ... | shapeops | problem-confirmed | Confirmed by code: layout.py:513-523 bridges only when path.within(hidden), otherwise a jump (and a trim past TRIM_TRAVEL_MM). The bridge stitches are real STITCH records tagged with the next object's item, and this ... |
| Guides snap placed and dragged points only, not whole-shape drags | shapeops | problem-suspected | In my area: the knife's two clicks do not call snapped() at all (StitchCanvas.tsx:1383-1388, 1545-1548), so they do not snap to guides, grid or nodes. Whole-shape drags were not checked. |
| Text on a drawn line: if the text is longer than the line, the extra ... | shapeops | problem-confirmed | Confirmed, and worse than described: lettering.py:495-496 has a no-op where the warning should be, so there is no warning at all. 16 letters on a 20 mm line gave no warning. Separately, textOnLine ignores the ... |
| Stitch-edit moves are stored as world-space deltas, which drift if ... | shapeops | problem-confirmed | Confirmed with a generated PES: stitch 20 moved by dx=5 mm shifts by (5, 0) at rotate 0 and still by (5, 0) at rotate 90, instead of turning with the design (layout.py:177-193, _move_stitches runs after _transform in ... |
| "One file per name" export and the design-browser folder picker were ... | shapeops | problem-confirmed | Reading the code for the names export found the options {} problem (no cut-stops, no hoop check), which is independent of the preview-versus-installed question and reproduced in Python. The design browser's >600 designs ... |
| Stitch-edit canvas draws every needle point: check performance on ... | shapeops | could-not-check | Rendering performance needs the live app; not in my brief. The engine side of shape ops on 27k-stitch files was measured: render 0.1 s, offset 19 s (see the performance finding). |
| Little or no test coverage: offset/knife/merge (engine tests only, no ... | shapeops | problem-confirmed | engine/tests/test_shapeops.py has 7 passing tests (one with a vacuous `or True`), none for transforms, travel_under, closed lines, non-fill inputs, negative offsets or 3+ merges. features.ts has no test file. A vitest ... |

## Things checked that are solid

**autotrace**
- Placement mapping is exact: digitize_all centroids matched to 0.00 mm over 56 combinations of rotation (0, 17, 30, -45, 90, 135, 180, 270, 12.5), offset and non-square sizes, and region() fills to ...
- EXIF orientation 2, 3 and 6 JPEGs trace in the displayed orientation (bounding boxes rotate as expected); transparent PNGs (alpha 0 over white or black RGB, semi-transparent, hard edges) give ...
- Corrupt input is handled: 900 byte-fuzzed or truncated PNG/JPEG/GIF/BMP/WebP/TIFF files, an empty file and a non-image named .png all give a plain TraceError (-32000); only DecompressionBombError ...
- Output is deterministic: identical hashes of digitize_all and region results across two separate processes for five pictures.
- Click guesses are accurate: IoU 0.99 against the true disc for flat, JPEG q10/50/90, palette, gray and soft-alpha pictures (0.87 for the noisy one); points about the requested spacing; corners kept; ...
- Network: the only outbound calls in the engine are ai/providers.py (AI add-on) and segment.download(); download is reachable only through ai.trace_model_download <- downloadTraceModel <- the Download ...

**compat**
- Old-to-new stitch equivalence: 196 inputs (5 shipped samples; 20 old-style single objects with rail satins, no travel_under and no newer fields; 40 random objects with a random mix of old parameters ...
- HEAD vs the first 1.0.0 commit (a5b44eb): the only differences are the Random/Reverse/Split-satin parameters when used; old 'c'/'s' node projects keep their shape (the new 'l' node kind does not ...
- Snapshot update (engine/tests/snapshots/digitize.json) is additive only: 11 new entries; the 5 existing hashes (fill_donut, fill_square_45, run_bean, run_single, satin_curved) are unchanged, and the ...
- Engine test files were only added to (+72, +15, +18 lines, no deletions); the two UI test edits (layout.test.ts casts, traceAssist.test.ts) follow the satin-rails-to-ribbon change.
- Rename compatibility: a project made by the first-1.0.0 engine opens in the working tree as both .ludd and a hand-relabelled .thl ('threadline-project'); the layout renders to the same hash, the ...
- Threadline data folder: a lone Threadline folder is renamed to Ludd (also when only an OSError retry is needed); unchanged since 1.0.0. (If a Ludd folder already exists, even empty, the old data is ...

**docs-a**
- Esc order matches the manual: holdEscape LIFO (drag, menu/list, autotrace guess, whole picture, knife, stitch-edit) then a focused field restores its value, then COMMANDS order pen.cancel, ...
- Every shortcut named in lines 1-360 is registered with the documented key (checked all of S2-S5 against COMMANDS), except Shift+comma.
- Panel: section order and default-open rules, per-kind open memory, Ctrl+click only-this, Alt+click open/close subs, panel width 260 px to 60% of the window, default 300 px, double-click reset ...
- Toolbar, tool rail, status bar and notice strip contents and labels; Save for machine is the accent (yellow #c8ff2e) button; info notices auto-close after 5 s, errors stay.
- Save: .ludd embeds designs and pictures; save, delete originals, reopen returns identical data (tests/test_project.py plus my round trip); guides, colour sets and names survive a save/open round ...
- Autosave delay 3 s with Recover/Discard banner; window title dot and close prompt; five .ludd samples render (Banner is 164 x 48 mm, too big for the 100 mm hoop as Help says); PES/JEF twins of three ...

**docs-b**
- Programmatic cross-check: every one of the ~125 shortcut rows in the manual's tables (lines 569-723) exists in COMMANDS with the identical key; ordering of shared keys (Esc, Tab, Enter, [ ], 1, C, K, ...
- Satin ribbon drawing: Ctrl+click straight, Shift+click corner, Alt 15 degree steps, Enter/right-click/double-click finish, Ctrl+right-click closes, pale band equals the width, width limits 0.5-12 and ...
- Fill patterns and motifs: all six patterns and their settings/labels match the manual; contour/stipple/cross skip the cross-hatch underlay and hide Angle; no jumps or oversize stitches in 18 pattern ...
- Applique: placement line, STOP, tack-down (zigzag or straight), STOP, satin cover; PES read-back keeps both stops; SVG cut file is in real millimetres; 'Sew a placement line first' label matches.
- Checks: dense, needle hits, very short stitches, long stitches over 7 mm and almost-touching shapes all exist with thresholds as documented, each with why/fix and Show me; the same checks are ...
- Fewer jumps & trims: tested A,B navy then red cover - 0 jump/0 trim with it on vs 1/1 off, and 1/1 when the cover is sewn earlier; on for new designs (freshDoc) and off for older projects as ...

**docs-c**
- Every shortcut written in helpdocs, USER-GUIDE, README, release-notes, USER-MANUAL and CHANGELOG exists in the COMMANDS registry (parsed with a script), including all new 1.0.1 ones (Shift+A, Alt+A, ...
- Version 1.0.1 agrees across tauri.conf.json, package.json, Cargo.toml, Cargo.lock, pyproject.toml, uv.lock and __init__.py; only tag v1.0.0 exists; commit dates match the CHANGELOG headings; ...
- The 11 cut-stop counts in the CHANGELOG (Evangelion 20, Key 18, Test 9, Frieren 8, Gunter 8, Heart.thin 6, PuppyPrideFlag 4, NewFrog 2, BMOFACE 1, both Inclusive Pride 0) all reproduce with the ...
- CHANGELOG 1.0.1 claims checked against code and found true: Auto-digitize Alt+A and the Whole picture button, Outline/offset dialog and holes option, Knife and Merge commands, travel_under on for new ...
- git diff HEAD has no user-visible feature missing from the CHANGELOG (scanned actions.ts, StitchCanvas, ToolRail, InfoPanel, TextPanel, App, store, types).
- The shipped samples regenerate with identical PES/JEF stitch coordinates, all five .ludd files pass layout.check with no warnings, they match the user-guide steps (Flower.ludd exists, 'Or try one of ...

**export**
- Units and rounding: model mm are multiplied by 10 once in render; the writers round absolute coordinates, so there is no cumulative drift. 11 fixture PES x (identity, and rotate 33.3 / scale 0.93 / ...
- Boundary lengths: 1500 random PES/JEF patterns with stitch and jump lengths at 62-64, 126-129, 254-256, 381-382, 2046-2049 units (both signs, x and y, diagonals) decode to the exact source positions; ...
- Large designs: 120k and 400k stitches write in 1.6 s / 5.2 s (PES) and 0.9 s / 3.6 s (JEF) with identical positions; JEF header point count equals the real count; PEC block length is right.
- Command encoding: colour change (FE B0 xx), END, JUMP/TRIM (PES uses the 0x20 flagged long form; JEF 80 02, trims as three 80 02 00 00), STOP (PES = duplicate palette colour, JEF = colour change) all ...
- Cut-stops: Key.PES gives 18 stops (matches stitchout-log.md), Test 9, Frieren 8, Gunter 8, Heart.thin 6, Puppy 4, NewFrog 2, BMO 1, both Inclusive Pride 0 (matches CHANGELOG); PEC palette repeats the ...
- Colour table: PES v6 with 1 to 255 colour blocks writes and reads back; JEF handles 300 colours; names, catalogs and brands survive for ASCII; PES header hoop word (01 00) matches Embrilliance's own ...

**fill**
- Plain tatami row completeness: over 120 random polygons (some with holes) and 6806 row segments at spacing >= 0.4, every row segment is stitched end to end (0 missing ends); region ordering never ...
- Pull compensation is applied as documented: top-layer row stitches never go beyond poly + pull_comp/2 (max excess 0.000 mm); the pull edge also narrows holes by the same amount (hole intrusion 0.1 ...
- Stitch lengths: top rows <= configured length + pull comp (at most +0.2 mm at length 8); cross-hatch <= 3.73 mm; edge run and travel <= 2.5 mm. About 1000 fixed and random shapes with holes (0.2-2.0 ...
- Raster coverage of tatami at 0.4-2.0 mm spacing: the share of the shape farther than half-spacing from any stitch is 0.0-0.7% (only acute star tips, max distance 0.45-0.73 mm at 0.4 spacing); tatami ...
- Determinism: sha1 of 7 shapes x 9 pattern/option combinations (tatami, gradient, wave, contour, stipple, cross, random 30, reverse, no underlay) is byte-identical across four processes with ...
- Degenerate geometry returns a clear DigitizeError or sane stitches: empty, 1 point, 2 points, collinear, all-duplicate, area under 0.5 mm2, hole larger than or equal to the shell. Duplicate ...

**fuzz-rpc**
- Protocol basics hold: parse errors, invalid requests, unknown methods, notifications (no reply), duplicate ids, string/number/null ids, CRLF/CR-only/BOM/NUL lines, a partial last line at EOF, an ...
- 50 MB params line, 69 MB autosave line, a 1 MB method name and 20,000 pings in 1.6 s: no problem; background requests (library.scan) are answered out of order correctly while foreground calls keep ...
- Lone surrogates, non-ASCII paths/names/ids and emoji work under a cp1252 locale with PYTHONIOENCODING unset: stdout carries ASCII-escaped JSON, stderr uses backslashreplace; ...
- stdout carries only protocol lines: no print() in engine or pyembroidery, fontTools 'kern' warnings and engine error logs go to stderr; error messages contain no tracebacks.
- rpc.ts: pending map cleaned on resolve/timeout/send failure/close; late responses to timed-out calls are dropped; chunk reassembly and out-of-order replies are tested; the shell plugin delivers one ...
- Cache key for drawn objects (kind, geometry, params after transform and fabric) contains every input of dz.generate: all 36 param mutations, 14 text-field mutations and ~30 item/layout-level ...

**layout-ops**
- delete_stitches indices are source-file record indices (r[4]), so they never go stale after earlier deletes; duplicates, out-of-range, negative and JUMP/TRIM/COLOR-CHANGE indices are ignored for file ...
- Undo restores exactly: features.ts addOps builds a new layout with ops appended immutably and goes through commit/showHistory (render first, then history), so Ctrl+Z returns the previous layout ...
- move_stitch deltas add up per stitch; translating the design moves edited stitches with it (delta stays 5.00 for x=7); the rotation/scale centre is computed from the original bounds, so deleting ...
- Old projects: with travel_under absent, the else-branch of _join_objects is identical to the previous code; rendering the 5 sample projects with the last committed layout.py and the working tree ...
- travel_under hides a move only when the straight path lies entirely inside the union of LATER digitized covers: crossing an 8 mm gap between two later patches, a cover sewn earlier, a 1.8-6 mm hole, ...
- Hidden travel stitches: n = ceil(d/2.5), so every step is at most 2.5 mm (and at least 1.25 mm for d over 2.5); well under any machine max_stitch. A 120-design random fuzz found 15 hidden-travel ...

**layout-order**
- optimize_order never changed the relative order of overlapping shapes: 0 of 859 overlapping pairs reordered in a random mixed-thread test, and repeated calls return identical results (deterministic); ...
- Combine same colors (merge_colors) only joins adjacent blocks, so it cannot change which shape is on top; the order of shapes is unchanged
- Basting: box is exactly the stitch bounds plus the margin, closed rectangle, stitches never longer than 4 mm, sewn before the knockdown and everything else, and counted in render, export, preview, ...
- Knockdown: always the first block (after basting), covers every stitch plus 2.3 mm, leaves holes in rings, grid at +-45 degrees with 2 mm row spacing and 4 mm stitches, trims between disjoint parts, ...
- Split: no stitch lost or duplicated for synthetic designs and three real designs; section files stay inside the 98 mm window and read back at the right size in both PES and JEF; cuts land exactly on ...
- Hidden-travel rule is conservative: only straight paths fully inside later covers, steps at most 2.5 mm, everything else falls back to trim plus jump; consecutive same-thread objects join without a ...

**lettering**
- engine/tests/test_lettering.py: 12 tests pass (holes, overlaps merged, satin angle, spacing, arcs, monogram, validation, export round trip, stitch-font round trip, font list, missing-file family ...
- All 206 installed outline fonts (incl. .ttc, .otf and the user's fonts in %LOCALAPPDATA%) lay out a sample string at 15 mm without any exception or slow case (every one under 3 s); only 6 symbol ...
- Outline fidelity: glyph areas compared with FreeType for 2,182 glyph samples; only 3 differ by more than 12 percent; holes in O, A, B, 8 correct in 187 of 206 fonts (the rest are solid or ...
- Stitch output of letters: 4,480 letter objects across Arial, Times, Georgia, Comic, Segoe Script, Ink Free, Gabriola at 6 to 40 mm in satin and fill: satin stitch never exceeds 7.0 mm, fill 3.6 mm; ...
- Determinism: three different layouts produce identical md5 of the stitch list across separate processes and after clearing caches; cache hit renders in 0.01 s.
- Old .tlfont files with format 'threadline-font' load and lay out (checked with a converted copy; no genuine old file was available); truncated stitch font gives a friendly message; fonts.list cold ...

**live-esc**
- escape.ts stack semantics are right (newest first, one per call, release is idempotent); escape.test.ts passes and matches the COMMANDS Escape order in actions.ts:1597-1730 and the manual's list.
- Real Esc cancels a canvas move drag (shape back, no history entry, hold released), a ruler-guide drag (no guide created) and a panel-resizer drag (width restored, later moves ignored, preference ...
- Real mouse drag of a shape and of the panel edge work and leave heldCount at 0.
- Mixed stack ordering is correct live: stitch-edit hold then an open toolbar menu: first Esc closes the menu, second ends stitch-edit, selection untouched.
- Menu and FontPicker release their hold in the effect cleanup on close, outside click and unmount; font-list Esc (focus in its search box) closes the list only.
- autoTrace and autoAll holds are driven by store subscriptions, so every exit (Esc, tool change via setTool, accept, engine error, early return) releases them; digitize/knife early returns happen ...

**live-state**
- Every multi-step edit command I ran is exactly one undo step with a clean undo/redo round trip (compared whole-document JSON): rotate, mirror and nudge on 3 selected items, group, ungroup, delete of ...
- Redo is cleared by any new edit (pushHistory sets future to []); undo across save is correct: clean open, edit makes dirty, save (mocked) with a second edit during the save stays dirty, undo back to ...
- Undo memory with embedded pictures: with a 12 MB PNG (16 MB data URL) and 66+ history entries every snapshot shares the images array/strings (1 unique data URL), heap about 73 MB; no byte copies. ...
- Overlapping successful renders coalesce correctly (slow A then fast B: both edits present, two undo steps, stale reply does not overwrite). Opening a design while an edit renders drops the stale ...
- Failed open (missing file, PNG as design, missing project): old document kept, loading cleared, readable text except the missing-project wording. Failed edit: pending reset, document unchanged, ...
- Auto-trace/trace-assist replies after Esc, tool switch or project switch are guarded by seq or by the cleared state; whole-picture preview that is dismissed while working is not applied. Mixed file + ...

**packaging**
- Versions agree at 1.0.1 in apps/desktop/package.json, tauri.conf.json, Cargo.toml and Cargo.lock's own entry, engine/pyproject.toml, engine/threadline_engine/__init__.py, uv.lock's threadline-engine ...
- Frozen sidecar on disk (engine/build/dist and src-tauri/binaries are byte-identical, built 21:19, newer than all engine sources): `threadline-engine-x86_64-pc-windows-msvc.exe` has the right triple ...
- The frozen engine actually runs: ping, engine.info (1.0.1), ai.trace_model, trace.digitize_all and trace.region (cv2), shape.offset (shapely/GEOS), library.scan, help.search, fonts.list. Output is ...
- All recent engine modules (autotrace, shapeops, ai.segment, library, digitize.patterns) are in the frozen PYZ archive; the lazy `import onnxruntime` and `from . import shapeops` imports were picked ...
- The built installer LUDD_1.0.1_x64-setup.exe (79.8 MB, was 34.9 MB for 1.0.0, consistent with the CHANGELOG's +30 MB OpenCV and +14 MB onnxruntime) contains LUDD.exe, threadline-engine.exe (no triple ...
- Updater public key in tauri.conf.json is byte-identical to `%USERPROFILE%\.tauri\ludd-updater.key.pub`; the endpoint equals the one in RELEASING.md. No private keys, tokens, personal paths or e-mail ...

**patterns**
- Stitch length and containment at default settings: tatami, gradient, wave, contour, stipple and cross on about 17 shapes (square, circle, star, L, C with a thin notch, H, donut, comb, B with 2 holes, ...
- Extreme parameters (spacing 0.2 to 5, stitch 1 to 8, wave 2 to 40 mm and height 6, loop 1 to 10 mm, square 1 to 8 mm) never crash, never leave the shape, never produce a jump or trim. Only stitch 8 ...
- Validation: bad pattern, motif, spacing, size and random values are refused with readable messages (test_patterns and my own checks); an empty or unknown motif is refused; a motif longer than a short ...
- Performance at 90x90 mm with default settings: tatami 0.07 s, gradient 0.06 s, wave 0.24 s, contour 0.03 s, stipple 0.14 s, cross 0.06 s. Worst realistic: stipple at 1 mm 1.2 s, cross at 1 mm 0.34 s ...
- Stipple core guarantees hold: 40 seeds x 4 shapes x 3 loop sizes gave a simple (non-self-crossing) closed line, always inside the shape, at least loop/2 apart, with every stitch at most 2.5 mm. It is ...
- Applique structure on a 30 mm square: placement line, STOP, tack-down, STOP, cover; lock stitches before and after every stop; one hop (JUMP) after each stop only; no trims; all three parts centred ...

**project**
- Round trip: save, delete every original, reopen, deep-compare every field for a project with a file item carrying all five op kinds, a motif run, rail satin, ribbon satin, fill with hole and gradient ...
- Unknown future fields are kept at top level, layout, item and picture level and survive a second save.
- Old projects: samples/*.ludd (rail satins) render identically (hash of every stitch) under the 1.0.0 release engine, HEAD and the working tree; a 38-case old-format corpus (runs, rail satins, fills ...
- Compatibility rules in CLAUDE.md hold: the .thl format string opens, .thl saves go to .ludd, a .tlfont (format threadline-font) is listed and renders, the Threadline data folder is renamed to Ludd ...
- Damaged project files never touch the original: zero-byte, truncated, random bytes, a PES renamed .ludd, wrong format, newer version (refused with a clear message), zip-slip and absolute member names ...
- Atomic save: a write that fails part way keeps the previous project and leaves no temp file; read-only and locked destinations fail cleanly with the original intact; a killed save never corrupts the ...

**satin**
- Ribbon geometry is accurate: the union of rung quads vs a shapely mitred offset gives IoU 0.998 to 1.000 on line, right angle, 60-degree zigzag, S curve, wave, closed square/triangle/blob/heart at ...
- Fuzz of 1500 random ribbons (open/closed, c/s/l nodes, width 0.5 to 12, underlay none/center/edge+zigzag): no exception, no NaN, every needle point within 2 x half-width of the centre line (max 6.12 ...
- Old-format objects: 1200 random rails-satin and run objects (c/s and l nodes, plain/underlay/auto/comp_by_width/auto_widen/triple/bean) give identical records from the working tree and HEAD; 400 c/s ...
- Running stitch: stitch length longer than the path, closed path shorter than the stitch, triple/bean on 3 mm paths, all four motifs at repeat 1.5 to 20 and width 0.5 to 10, a 0.1 mm path: no crash, ...
- Performance is linear: a 3000-node closed ribbon at 0.2 mm spacing in 0.25 s, 100 000 mm ribbon in 3 s, bean line with 600k records in 1.2 s.
- TS design/paths.ts flatten matches the engine's flatten on 60 random node lists (max difference 1.5e-14), including closed paths and line nodes.

**security**
- Network inventory: the only network code in engine/threadline_engine is ai/providers.py (urllib POST) and ai/segment.py (model download); no requests/httpx/socket/http.client/ftplib. UI has no ...
- The AI add-on is off by default (DEFAULTS mode 'off'); with mode off, current() returns Off and neither Advisor nor Help sends anything; help.ask returns only local guide matches. Model download ...
- What the Advisor sends (executed advisor.build_request with a layout carrying names, a title and an image path under the user profile): fabric name, shape id, kind, size/area/widest/column widths, ...
- Key handling: ai.json never contains the key; public() exposes only has_key; on Windows the key file is DPAPI-protected (verified no plaintext, no base64); errors and logs contain URLs and codes but ...
- Tauri hardening: no assetProtocol, no withGlobalTauri, no dangerous* flags, no devtools feature, no remote capability URLs; one capability file limited to the main window; the shell plugin scope ...
- Updater: HTTPS GitHub endpoint, minisign pubkey in tauri.conf.json matches the .pub on the dev PC, updates are signature-checked by the plugin; installMode currentUser; no private key or token in the ...

**shapeops**
- Offset distances: d=0, 0.3, 1, 2, 5, 30, -1, -3 behave on a 20 mm square (ring bounds within about 0.2 mm of the stitch edge plus d). -10 and 30 are accepted. -11, 31, NaN and inf give a clean ...
- Offset works for fills, fills with holes, text (IOX, with letter holes), satin ribbon, run line, applique, a generated PES stitch file, and several items at once. Items closer than about 3 mm get one ...
- Rings from offset sew cleanly as closed satin (widths 2, 3 and 5) and as triple line for star, heart, text, circle and square at d=1 and 2: no exceptions, no jumps, no warnings. Round joins only, so ...
- Fuzz of 120 random multi-item offsets (random distance, spacing 2-4, holes on or off): no exceptions, no self-intersecting rings, output deterministic.
- Knife on fills: 275 random cuts on random star-shaped polygons, some with holes. Area conserved within 2%, no overlapping pieces, 2 to 5 pieces, no crashes. Edge cases give clean ShapeErrors or ...
- Knife on open run and satin ribbon keeps width_mm and splits exactly at node positions. A satin column (rails), text and non-shape kinds are refused with a clear message. A bowtie behaves the same as ...

**tauri**
- CSP vs PixiJS 8: main.tsx imports pixi.js/unsafe-eval first; the built bundle contains the polyfills (_unsafeEvalCheck(){}, _systemCheck(){}, _generateShaderSync replaced); the 5 remaining new ...
- Capabilities probed in the live app: set_title, set_theme, destroy (reaches 'window not found' for a bogus label), dialog open/save/message and event listen are allowed; minimize, dialog ask, shell ...
- Frozen engine (not stale: built Oct 11 21:19, last engine source edit 21:17; all 28 current threadline_engine modules are in the PYZ incl. autotrace, shapeops, library, ai.segment, digitize.patterns; ...
- Windows paths over JSON-RPC: non-ASCII and CJK paths, spaces, forward slashes, UNC (\\localhost\C$\...) and \\?\ long paths all work; non-ASCII/CJK install dir, TEMP and data dir each start the ...
- No console window flash: CREATE_NO_WINDOW is set in tauri-plugin-shell and no visible engine/console windows appeared across 7 s of 20 ms sampling at startup.
- Large messages: a 28.5 MB engine response and a 28.5 MB request through the shell plugin (under the real CSP, postMessage fallback) completed in 2.0 s and 1.0 s; ping round trip about 1 ms.

**tests**
- Exact-hash snapshots: the digest is a sha1 over every rounded record plus counts, so they are strict; 5 existing snapshot hashes are unchanged by the 175-line stitches.py change, and the working-tree ...
- Mutation score 36 killed of 67 (31 survived, 2 of those equivalent: B11 colour-change position is ignored by pyembroidery, D13 closing is redundant). Killed include: satin pull-comp sign, satin split ...
- Reverse file order of the whole engine suite passes (250 passed, 4 skipped); no order dependence between files; AI fake servers bind port 0; fill jitter is a deterministic hash so tests are ...
- CI workflow runs the engine suite, typecheck and UI tests on both windows-latest and macos-latest with fail-fast off; pnpm install is frozen.
- UI to engine contract: 58 literal .call(...) sites in the UI match the Python method signatures (names, required params, no extra keys).
- UI foundations: removeSelected followed by undo is one atomic step restoring every removed item and clearing the selection; all 163 registered commands have a shortcut, each matches its own key ...

**visual**
- Plain tatami fill: 16 shapes (square, holes, star, circle, ring, L, C, comb, dumbbell, heart, blob, multi-hole, thin, tiny, sharp triangle) at 0/30/45/90 degrees and 0.4 mm: 0 jumps, longest stitch ...
- Fuzz of about 120 random blob shapes (some with holes, random angles and spacings 0.3-1.0) plus 80 stroke-union shapes: no jumps or long stitches or leaks except the exact-1.2 mm spike case reported ...
- Contour fill stays inside the shape and has no straight travel threads; gradient rows open up as designed; random 0-50% and reverse keep stitches inside the outline; pull compensation adds 0.1 mm per ...
- Satin ribbons: straight, S-curve, closed circle/square, zigzag, hairpin; exact width (3.00 mm), miter limit 2x at corners, 0 jumps, underlay (centre, edge, zigzag) ends where the top starts; 0.5 mm ...
- Applique (circle, star, heart, square, L; zigzag and run tack): placement, tack and cover each end with a STOP and ties, cover rungs follow the outline; STOP counts survive a PES round trip; no ...
- Motif lines (wave, zigzag, scallop, blanket) on straight, curved, closed and zigzag lines at 3 sizes: stitches 0.3-2.5 mm, no jumps; triple and bean closed rings end on the start point.

## Gaps: what could not be checked

- Not run at all: keyboard-shortcut conflicts (live), feature walkthroughs for shape ops/auto-trace/guides/colorways/preview (live), performance with 30k+ stitch designs, completeness critic and follow-up round.
- Not exercised: the installed Tauri app, macOS, real stitch-outs, dependency audits and anything needing the network, rebuilding the frozen engine.
- [autotrace] I did not run the installed app or the browser preview (not my browser lock), so on-canvas behaviour is from code reading plus a temporary vitest: Pixi's handling of EXIF-rotated or animated pictures, the look of the ...
- [autotrace] macOS and Linux were not tested; in particular whether the frozen sidecar can verify huggingface.co's TLS certificate for the model download (PyInstaller bundles often need certifi) is unknown. The real download was not ...
- [autotrace] The MobileSAM files' upstream hashes, the claim 'MIT license' for Acly/MobileSAM versus MobileSAM's own Apache-2.0 license, and whether huggingface 'main' has changed since release could not be checked offline.
- [compat] No browser or installed-app run (I do not hold the browser lock): the design browser, guides, stitch-edit drawing speed, rulers, garment preview, colorways, and the real 'One file per name' dialog flow were checked from ...
- [compat] Could not run the frozen sidecar (scripts/build_engine.py and the PyInstaller spec patch are off limits); not verified that the dropped opencv_videoio_ffmpeg DLL, the new makespec flow, or onnxruntime hooks work in the ...
- [compat] No network, so I could not check whether v1.0.1 was already published on GitHub (affects the versioning finding) or confirm the uv.lock wheel gap against PyPI.
- [docs-a] The live app (browser preview or installed) was not run: the measuring-tool readout (F1), hidden-picture clicks, real pointer behaviour, native dialogs, the Windows print dialog from an iframe and drag-drop were checked ...
- [docs-a] Stitch-edit canvas speed on 30k+ stitch designs was not measured (no browser). From source: drawStitchEdit loops every record and rebuilds the whole overlay Graphics on every pointer move during a drag; ...
- [docs-a] No stitch-out on the PE550D (deferred by project policy), so cut-stop and split-hooping results are paper-only; PES/JEF read-back was not re-verified beyond cut-stop counts.
- [docs-b] No browser lock and no installed app: all UI behaviour was checked by reading code plus vitest and engine runs; nothing was clicked. In particular, WebView2 browser accelerators that may bypass JS preventDefault (Ctrl+P ...
- [docs-b] No Mac or non-US keyboard: the Option/Alt and AltGr shortcut failures in F3 are inferred from how e.key behaves, not observed.
- [docs-b] Stitch-edit canvas performance on 30k+ stitch designs was not measured (needs the browser): code redraws one rect per needle point on every overlay refresh and stitchAt() is O(n) per pointer event.
- [docs-c] No PDF renderer (pdftoppm, mutool, gs) was available and I did not hold the browser lock, so I could not look at the manual PDF; pdftotext shows blanks where the gear and three-dot glyphs should be (e.g. 'Settings (, ...
- [docs-c] The installed app and the live UI were not driven (no browser lock, no tauri build): menu and label claims were checked by reading InfoPanel, Toolbar, ToolRail, SettingsDialog and FeatureDialogs, not by clicking. ...
- [docs-c] Could not verify offline: the MobileSAM licence and the Hugging Face file URLs, the installer file names Tauri will produce for 1.0.1, the '30 MB' and '14 MB' size claims in the CHANGELOG (needs a build), the '20 ...
- [export] No stitch-outs and no hardware: everything about how a PE550D or Janome treats the files is unverified, namely the PEC trim flag on every jump, a stitch in the old colour before a colour change that follows a jump, ...
- [export] I could only read the files with pyembroidery and my own decoders (scratchpad export/codec.py); no Embrilliance, PE-Design or Janome reader was available.
- [export] The installed Tauri app was not run: the native Save dialog's overwrite prompt and reserved-name handling, the folder picker used by One file per name and Batch convert, and the exact messages shown were reasoned from ...
- [fill] No browser or installed-app session (not in my lane): could not see how the UI shows fill warnings, whether the live canvas redraws are blocked by the slow cases, or how Wave/Stipple look on screen.
- [fill] No physical stitch-out: all judgments about gaps, row spacing and visible travel threads come from geometry (shapely raster and distance checks), not from sewing; the top-layer travel stitches between regions are laid ...
- [fill] PES/JEF export of fill output (rounding to 0.1 mm, trims, stops) was only exercised through layout.check/render, not through pe.write; golden export tests belong to another reviewer.
- [fuzz-rpc] The live app and browser preview were not used (no browser lock): UI-level effects (timeouts surfacing as toasts, the Names dialog, IPC cost of 70 MB requests, canvas performance with 30k+ stitches) are from code ...
- [fuzz-rpc] The AI tracing model and onnxruntime sessions are not installed and nothing may be downloaded, so segment.py was exercised with a stub encoder only.
- [fuzz-rpc] No real stitch-out or machine read: stray-thread and JEF behaviour judged from pyembroidery read-back, not on a Brother or Janome.
- [layout-ops] No browser lock: I could not drive the live app, so the stitch-edit canvas frame rate on a 30k-stitch file was not re-measured (code shows drawStitchEdit rebuilds every needle point on each pointer-move; the earlier QA ...
- [layout-ops] The Delete fall-through was confirmed with a temporary vitest against the real COMMANDS table and store, not in the running UI.
- [layout-ops] No machine stitch-out: whether red travel through a 1.0-1.5 mm row spacing is visible, and what the PE550D does with the lone stitch in an empty colour, are judged from geometry and pyembroidery's output only.
- [layout-order] No live app / browser run: UI claims (hidden color_sort warning, missing knockdown thread control, split dialog text) come from reading the React code; the knockdown thread finding is marked suspected for that reason
- [layout-order] No test stitch-outs: seam gap or ridge at hoop joins, practical effect of dense/needle-hit thresholds, basting behaviour and cut-stop behaviour on the PE550D are unverified (stitch-outs are deferred by the owner)
- [layout-order] Rotated hoopings are not implemented in split.py (hoop width/height only); I did not review them further. There is no time estimate in the app, so basting in a time estimate could not be checked
- [lettering] The installed Tauri app and the browser preview were not used (rule: no browser; build not allowed): the text-box typing race, the font list cap, native save/folder dialogs (Save as stitch font location, One file per ...
- [lettering] No genuine pre-rename .tlfont sample exists in the repo, so old-file compatibility was checked only with a copy converted to the 'threadline-font' format.
- [lettering] No stitch-out on the PE550D (deferred by project policy): letter satin quality, 7 mm satin rows on towel, thin-stroke text at 8 mm and cut-stop behaviour per letter are paper-only; stitch images were judged from Pillow ...
- [live-esc] Real Alt+Tab, OS-level mouse release outside the window and touch/pen hardware could not be driven; blur, pointercancel and second-pointer cases were exercised with scripted events (setPointerCapture accepted pointerId ...
- [live-esc] Installed Tauri app and macOS WKWebView were not exercised (ctrl+click context menus eating pointerup on the panel resizer, native dialog Esc/close-watcher differences).
- [live-esc] ExportDialog/BatchDialog busy state and the AI-settings Field were not driven live (would write real settings or need a long engine job); those findings are suspected.
- [live-state] Cannot kill or restart the real Tauri sidecar from the Vite preview (its dev bridge respawns on demand), so engine-death behaviour is by code only; native dialogs, the window close handler, drag-drop and shell stdout ...
- [live-state] The shared dev engine was slow (renders 2-12 s while other reviewers ran), so live timings are upper bounds; the quiet-machine numbers come from direct engine timing (6 fills: render 3.27 s, check 7.30 s; 2 fills 1.29 ...
- [live-state] Browser pane was hidden at times, so some javascript_tool calls timed out at 45 s (scripts still ran; results were read afterwards).
- [packaging] Could not run GitHub Actions, so release.yml/ci.yml behaviour (partial failure, draft asset URLs, tauri-action asset names such as `_aarch64.app.tar.gz`, the signing steps) is judged from reading only. No YAML parser or ...
- [packaging] No macOS or Linux machine: the macOS minimum-OS finding, the Intel/Linux freeze and the sidecar behaviour on those systems are from lockfile wheel tags and Tauri's source, not from runs. The macOS and Linux kill/leak ...
- [packaging] Did not install the NSIS installer or run the installed app. The `_MEI` leak was reproduced by killing the shipped sidecar with TerminateProcess, the same call Tauri's plugin makes, and the app-side path was confirmed ...
- [patterns] No stitch-out on the PE550D (deferred by project policy). Visual judgements (cross-stitch lattice, wave look, contour ridge, gradient fade) come from stitch plots I rendered and from computed thread density and ...
- [patterns] The UI was not run (no browser lock). The applique hole flow, the pattern-control visibility and the Fill pattern select were reviewed from code (InfoPanel.tsx, actions.ts) and by driving the engine with the same ...
- [patterns] JEF output of the five fill patterns was not re-verified beyond the applique JEF round trip; PES was verified for applique and zero-length stitches.
- [project] The installed Tauri app was not run: the two-window and double-click behaviours (findings 'Double-clicking a .ludd...' and 'One global recovery slot'), the close-time discard race, native Save dialog behaviour for ...
- [project] The frozen sidecar's long-path behaviour was not run (its binary contains a longPathAware string but LongPathsEnabled is 0 on this PC); all long-path tests used the dev Python 3.12.
- [project] Power-loss (no fsync) and real disk-full or USB-pulled behaviour were simulated by patched writers, not reproduced on hardware.
- [satin] The Satin tool, Width stepper, Split checkbox and Edge pad controls were not driven in the browser preview (that tool is for another reviewer); UI behaviour was checked by reading actions.ts, layout.ts, InfoPanel.tsx ...
- [satin] No stitch-out. Whether a PE550D accepts, splits or mishandles a single 12.4 mm or 30 mm PES stitch is unknown (no max_stitch is set for the profile); also whether Brother prefers 12.1 mm as the limit.
- [satin] Real-world thread behaviour for the 'diagonal rung' look at satin spacing below 0.3 mm (stitch_run drops one of each pair of needle points, halving penetrations but keeping the across-stitch count) was judged by ...
- [security] The installed Tauri app was not run: could not verify that Tauri's automatic CSP nonce/hash injection leaves style-src 'unsafe-inline' working for inline style attributes in the print iframe (print.ts:94 uses ...
- [security] GitHub Actions cannot be run offline: the untagged-URL problem in latest.json, signing steps and secrets handling were reviewed by reading only.
- [security] macOS and Linux paths (file permissions on the PLAIN key file and the chmod race, rglob and symlink behaviour, WKWebKit CSP inheritance) were reasoned about, not run.
- [shapeops] The live app was not run (the browser pane is not mine). Pointer behaviour (knife clicks, the cursor preview, dialog input handling) and the exact error text shown for a timed-out offset are from reading the code and ...
- [shapeops] Timings are the dev engine (uv run) on this machine with other reviewers running; I used process CPU time. The frozen PyInstaller sidecar was not timed and may be slower or faster.
- [shapeops] No JEF fixtures were present in the list I ran (11 PES), so JEF output for names or shape ops was not exercised. Windows reserved names (CON.pes) were not written, on purpose, and case-collision overwrite was not run.
- [tauri] No Mac or Linux here: RunEvent::Opened, Cmd+Q, WKWebView window.print, macOS signing/notarization entitlements for the PyInstaller onefile sidecar (the workflow has no entitlements file once Apple certs are added), the ...
- [tauri] window.print() of the hidden srcdoc iframe was not exercised (it opens a system dialog); only the page's styling under the real CSP was verified, and that alone breaks the template.
- [tauri] The ONNX tracing model download and use were not run (needs a download; forbidden). onnxruntime DLLs are in the bundle but import under the frozen exe was not exercised.
- [tests] Could not run macOS: the Alt-key and any macOS CI-only failures (paths under /private, fonts, tmp symlinks) are unverified.
- [tests] Browser lock not held: no check of the Stitch-edit canvas drawing every needle point on 30k+ stitch designs (engine side is fast), guide snapping behaviour, accordion/panel UI, or the installed-app folder picker and ...
- [tests] No TypeScript coverage tool is installed (@vitest/coverage-v8 absent), so UI coverage is by export-reference scan only, not line coverage.
- [visual] No browser lock, so I did not look at the live canvas: realistic-thread drawing, stitch-edit overlay performance on 30k+ stitch designs, guide and snap behaviour were checked only by reading code.
- [visual] 'One file per name' and the design-browser folder picker need the installed Tauri app; only the TypeScript logic (features.ts) and the engine export it calls were read.
- [visual] A full sweep of every glyph/size for the underlay-leak bug (6 fonts x 14 sizes, fill style) was killed for time; a cheaper validity sweep (5,364 glyph objects) found no invalid rotated polygons, so the leak only appears ...

## Claims that failed verification

- [compat] Version and changelog: about 25 new features are filed under 1.0.1 and the version is still 1.0.1 everywhere: [reproduce/refuted/ran] The reviewer's concern depends on 1.0.1 having already been tagged or published. It has not been. - `git ls-remote --tags --heads origin` (read-only, run with a timeout) returned only `refs/heads/main` at bb9bcc0 and `refs/tags/v1.0.0`. There is no remote v1.0.1 tag and no ...
- [patterns] Satin and applique spacing of 0.3 mm or less sews about half the stitches (Dense satin on Towel is sparser than Light): [reproduce/refuted/ran] The raw numbers reproduce, but the harm does not. I ran the reviewer's snippet from engine/ with uv run --frozen --no-sync. Needle points for a 40 mm x 3 mm satin: 0.5 -> 162, 0.4 -> 202, 0.32 -> 252, 0.3 -> 136, 0.29 -> 140, 0.25 -> 162, 0.2 -> 202. Towel Light/Normal/Dense ...
- (disputed) [visual] Spacing under 0.3 mm: stitch_run() drops the first penetration of each satin column and fill row, thinning satin rail edges and fill side edges: Disagreement with the reviewer: (1) the "denser means sparser (satin)" headline and the "real spacing 0.57 mm" figure are a misreading. Thread-line pitch across the column stays equal to `spacing` (0.286 at 0.29, 0.199 at 0.20). Only the stitch count and the per-rail penetration pitch change. The ...

## Appendix

- Per-area reviewer reports with every finding, repro and fix: `_salvage/area-<name>.md` in the session scratch folder; merged data in `merged.json` there.
- A reviewer wrote an earlier partial report into the repo as `docs/QA-REPORT-2026-10-11.md`, against the no-changes rule. It is separate from this file and can be deleted.
