# LUDD QA/QC report, second pass

*Date: 2026-11-24. Code at e415eb3 (main), worktree `qa-pass-2-b93602`. Brief: docs/QA-PROMPT.md.*

The second pass ran the brief's ten areas again in five groups (stitch output; layout and projects;
auto-trace, shape ops, security and packaging; UI state; docs and tests). Everything already fixed
or decided in docs/QA-REPORT.md, docs/QA-RESPONSE.md, docs/qa-phase4/ and BACKLOG.md was left out.
What the lead did about each finding is in the **Outcome** column; a decision list for the owner
follows.

## Summary

42 new findings: **no Critical, no High**, 17 Medium, 25 Low. The first pass's 420 findings
have not come back: thread tables, hidden travel, hoop splitting and PES/JEF export held up under
fuzzing (details under "Solid").

The biggest themes:
- **Stitch output edge cases** (S1-S4): a hairline neck in a fill turns travel into jumps and can
  end with a 10-15 mm stitch; the zigzag underlay sews the same diagonal twice on about half of
  wide satins; applique jumps are never trimmed; sharp corners of wide satins pass 7 mm. All change
  stitch output, so they are on the owner's decision list.
- **Edits applied to a design that changed meanwhile** (U4, U5): knife, merge, offset, Optimize
  jumps and the Auto-trace accept use the engine's answer even if you undid or moved something
  while waiting.
- **Modes that overlap** (U1, U2, U6): the knife or stitch editing stays on under the ruler, the
  angle line or a new tool, so clicks do the wrong thing.
- **Hostile or damaged files** (P1, P4, T1): a tiny project can make the engine build gigabytes;
  a damaged item blanks the canvas; the AI key follows a redirect to another server.
- **Work kept after an engine restart** (P2): the private copy of a design whose original is gone
  is forgotten after the engine restarts.
- **Docs** (D1-D10): the knowledge base lists 47 formats (the app opens 40), stale section numbers,
  leftover UK spelling, and tests that can't catch some doc drift.

## All findings

Status: **C** confirmed (reproduced), **S** suspected (code reading). Outcome: **Fixed** (in this
pass, with a test), **Decision** (owner list below), **Backlog**.

| ID | Sev | St | Finding | Where | Outcome |
|---|---|---|---|---|---|
| S1 | Med | C | A fill with a neck under ~0.6 mm loses all edge routing: trimmed jumps across bare fabric, and a fill ending on a jump gets a 10-15 mm lock stitch | digitize/stitches.py:144-197, 1069-1076, 123-131 | Decision 1 |
| S2 | Med | C | Zigzag underlay retraces its own legs when the zigzag count is even (about half of satins ≥5 mm with auto underlay) | stitches.py:609-614 | Decision 2 |
| S3 | Low-Med | C | Applique moves between edges/holes/pieces are bare jumps (up to 45 mm), never trimmed | digitize/applique.py:174-182 | Decision 3 |
| S4 | Low | C | Wide satin ribbons and applique borders at sharp corners make 7.8-8.6 mm stitches with Split long stitches on, no warning | stitches.py:436-443, 559-622; applique.py:147-151 | Decision 4 |
| S5 | Low | C | With Longest over 7 mm the satin warning says "tick Split long stitches" though it is ticked | stitches.py:584-587 | Fixed |
| S6 | Low | C | Satin/run settings set to null or text crash as "engine bug" (fills were fixed, these weren't) | stitches.py:229-244, 291-303, 1138; fabrics.py:74 | Fixed |
| S7 | Low | C | Fill/applique holes with a NaN or huge point aren't checked; a NaN hole silently disappears | stitches.py:721-731; applique.py:95 | Fixed |
| S8 | Low | C | Stipple at 1 mm on a 95 mm square takes 6.5 s; wave's stitch-count estimate is 7x low | digitize/patterns.py:112-179; stitches.py:1093 | Backlog |
| P1 | Med | C | A 39 KB .ludd makes the engine build 624 MB of picture data (pictures sharing one member, no count/total limit) | project.py:461-475, 112-135, 55-56 | Fixed |
| P2 | Med | C | Private copies are forgotten when the engine restarts: a design whose original is gone can't be shown or saved; autosave drops the picture | kept.py:17, 68-79 | Fixed |
| P3 | Med | C | Stitch-file edits (recolors, deleted colors/stitches, stops, moves) silently land on other stitches if the placed file is re-saved elsewhere | layout.py:960-975, 173-228 | Decision 5 |
| P4 | Low | C | A damaged item opens fine, then every render fails with "Please report this" and the canvas is blank | project.py:425-449; layout.py | Fixed |
| P5 | Low | C | Sew in the shortest order groups threads differently from the renderer (ignores names), can add a color change | layout.py:829-833 | Fixed |
| P6 | Low | C | Shipped sample PES/JEF (1.0.0) no longer match their own .ludd projects; no test pins how old projects sew | samples/, scripts/make_samples.py | Decision 6 |
| T1 | Med | C | AI API key follows an HTTP redirect to another host, also https → http; a redirect from a local Ollama address skips the send preview | ai/providers.py:60-64 | Fixed |
| T2 | Med | C | Importing a thread chart can silently replace a different chart (non-Latin names all become "chart"; "Isacord 40"/"Isacord-40!" collide; CON/nul fail oddly) | threads.py:142-144, 285-290 | Fixed |
| T3 | Med | C (gap) | Nothing checks that ONNX Runtime really loads in the frozen engine; `runtime()` only finds the package | scripts/smoke_engine.py; ai/segment.py:66-72 | Fixed |
| T4 | Low | C | Tiny picture placements make Whole picture very slow (2 mm: 14 s, 1 mm: 50 s); zero/NaN sizes and 1×1 pictures give raw errors | autotrace.py:899-901, 942-949; trace.py:175 | Fixed |
| T5 | Low | S | Merge and knife apply a stale answer (same as U4) | features.ts | Fixed with U4 |
| T6 | Low | S | Dependabot can open Tauri plugin bumps that move only one side (crate vs npm) and fail the installer build | .github/dependabot.yml | Decision 7 |
| T7 | Low | C | macOS and Linux Rust code is compiled for the first time on release day (CI builds Rust on Windows only) | ci.yml:41-76; release.yml:92-97 | Decision 8 |
| U1 | Med | C | Knife or stitch editing stays on under the ruler (M) or angle line (I): hint says measure, two clicks cut the shape; Esc lets go of the older mode first | actions.ts toggleRuler/startAngle; features.ts:215 | Fixed |
| U2 | Med | C | A tool key during stitch editing picks the tool, but stitch editing stays on, takes the clicks and holds Esc | store.ts:431 | Fixed |
| U3 | Med | C | Ctrl+Z while drawing throws away the half-drawn shape and also undoes the previous edit | actions.ts:647 | Decision 9 |
| U4 | Med | C | Knife, merge, offset and Optimize jumps apply an answer worked out from the old design (a nudge is lost; an undone shape comes back as pieces) | features.ts:151, 225, 264, 354 | Fixed |
| U5 | Med | C | Auto-trace: clicking the next shape while an accept is still adding makes the new guess disappear; Esc during the accept still adds | autoTrace.ts:212-262 | Fixed (Esc during an accept stops it only while satins are worked out; otherwise one Ctrl+Z removes it) |
| U6 | Low | C | The angle line (I) outlives its fill after Delete or undo | store.ts:413 | Fixed |
| U7 | Low | C | Ctrl+X with nothing selected on a one-shape design copies but doesn't cut | actions.ts:1794, 789 | Fixed |
| U8 | Low | S | Sewing-order row drag lacks the lost-mouse-up and unmount guards the other drags got | InfoPanel.tsx:822-861 | Fixed |
| U9 | Low | S | Delete drops the selection before it knows the delete worked | actions.ts:800-802 | Fixed |
| D1 | Med | C | Knowledge base says LUDD opens 47 formats and lists 7 it can't open; the app opens 40 | LUDD-KNOWLEDGE-BASE.md:53, 219 | Fixed |
| D2 | Med | C | Whole-picture auto-digitize has no UI tests (stale answers, dismiss, empty result, one-undo accept) | features.ts:94-147 | Fixed (tests) |
| D3 | Low | C | In-app Help says "Threads, Color sets"; Color sets is in Order & colors | ai/helpdocs.py:107 | Fixed |
| D4 | Low | C | Manual's Browse designs paragraph still says "choose the folder again", two lines after Refresh | USER-MANUAL.md:165-171 | Fixed |
| D5 | Low | C | KB section 0 points to the wrong sections (9→24, 8→25, "section 10"→L-016) | LUDD-KNOWLEDGE-BASE.md:28, 32, 272 | Fixed |
| D6 | Low | C | KB history files the QA fixes under 1.0.0 / Oct 11 | LUDD-KNOWLEDGE-BASE.md:841 | Fixed |
| D7 | Low | C | Leftover UK spellings and two dead label names in the unreleased 1.0.1 changelog | manual, guide, KB, helpdocs, CHANGELOG | Fixed (older changelog prose: Decision 10) |
| D8 | Low | C | CHANGELOG leaves out the Nov 15 dependency upgrades; the jsdom note misses the `// @vitest-environment jsdom` line | CHANGELOG.md:5-13 | Fixed |
| D9 | Low | C | test_helpdocs can't catch a key documented for the wrong command, and skips bare keys | engine/tests/test_helpdocs.py | Backlog |
| D10 | Low | C | knowledgeBase.test.ts stays green when a command is removed, re-keyed or retitled | knowledgeBase.test.ts | Backlog |
| D11 | Low | C | Nothing checks that the version numbers agree | — | Fixed (test) |
| D12 | Low | C | Guide snapping and garment preview have no tests; guides/color sets round trip untested (works) | StitchCanvas.tsx:1437-1460 | Fixed (round-trip test; snapping on backlog) |

## Decision list for the owner

These change stitch output, behavior you might rely on, or process.

**Owner's decision (2026-11-24): all ten approved as recommended; item 9 is (a), Ctrl+Z removes
the last point.** In short:

| # | Decision |
|---|---|
| 1 | Fix: travel inside a fill follows its edges even with a thin neck; a fill never ends on a jump (no long lock stitch) |
| 2 | Fix: the zigzag underlay's return pass always crosses the first |
| 3 | Fix: moves over 3 mm between applique edges get a trim, as fills do |
| 4 | Fix: add a needle point at sharp corners so no stitch passes the Longest setting |
| 5 | Edited stitch files sew from LUDD's copy taken when they were added (edits stay on their stitches) |
| 6 | Regenerate the samples and add a test pinning each sample project against its PES |
| 7 | Add a fast test that fails when a Tauri plugin's crate and npm package differ in major.minor |
| 8 | Add a Rust build/test on macOS to CI |
| 9 | (a) Ctrl+Z while drawing removes the last point placed, like Backspace |
| 10 | Convert the 1.0.1 changelog's older prose to US spelling |

Items 1-4 change stitch output: each gets a row in docs/stitchout-log.md.


1. **S1 Thin necks in fills.** Route travel inside a fill along the shape's edges even when part
   of it is narrower than ~0.6 mm, and never end a fill on a jump. *Changes stitches only for such
   shapes; removes 10-15 mm stitches and untidy trims. Recommended: yes.*
2. **S2 Zigzag underlay.** Make the return pass always cross the first one. *Changes stitches for
   every satin with zigzag underlay and an even count (about half of wide satins). Recommended: yes,
   with a stitch-out row.*
3. **S3 Trims between applique edges.** Mark moves over 3 mm between applique edges for trimming,
   as fills do. *With cut-stops on, that adds machine stops. Recommended: yes.*
4. **S4 Sharp corners on wide satins.** Add a needle point at corners so no stitch passes the
   Longest setting, or just warn. *Recommended: add the point.*
5. **P3 Edits on a placed stitch file that changed on disk.** Either keep sewing the copy LUDD made
   when the file was added (recommended), or drop the edits with a note.
6. **P6 Samples.** Regenerate the sample PES/JEF files from their projects and add a test that
   pins how old projects sew.
7. **T6 Dependabot and Tauri plugins.** Stop Dependabot bumping Tauri plugins (do them by hand
   in pairs), or add a fast test that fails when the pairs differ. *Recommended: the test.*
8. **T7 Mac/Linux Rust in CI.** Add a Rust build on macOS to CI (costs Mac CI minutes on every
   push). *Recommended: yes, because the Mac code has never been compiled.*
9. **U3 Ctrl+Z while drawing.** Choose: Ctrl+Z removes the last point (like Backspace; recommended),
   or Ctrl+Z only drops the half-drawn shape. Today it does both that and undoes the edit before.
10. **D7 Older changelog wording.** The 1.0.1 section's prose uses UK spelling in about 20 places.
    The label names are fixed; should the rest be rewritten to US spelling?

## Top five fixes (in order)

1. T1: refuse redirects when sending to an AI service (keeps the key on the server you chose).
2. P2: remember private copies across engine restarts (stops "File not found" on save).
3. U4 + U5 + T5: drop engine answers when the design changed meanwhile.
4. U1 + U2 + U6: only one of knife, stitch editing, ruler and angle line at a time.
5. P1 + P4: limits and plain errors for hostile or damaged project files.

The first five decisions (S1-S4, P3) are the next most valuable, but they change stitch output.

## Checked and solid
- **Fills:** 6 patterns × 8 hard shapes × 4 angles: no stitch over 3.51 mm, nothing more than
  0.3 mm outside the shape. Degenerate shapes give plain messages.
- **PES/JEF export:** every needle point within 0.14 mm; stitch counts, color changes and applique
  stops survive; JEF stops as color steps; `long_stitch_contingency` set.
- **Hidden travel:** 120 random layouts with sort/merge: 0 of 67 travel segments left uncovered.
- **Thread tables:** 300 random edited layouts: threads = color changes + 1 every time.
- **Splitting:** 4 designs × 4 hoops: nothing outside the field; stops kept.
- **Auto-trace:** 33 synthetic pictures (noisy JPEG, gradients, transparency, odd formats, 108 MP):
  nothing crashed except the 1×1 case (T4); rotated placements trace in place.
- **Network:** only the AI add-on, the model download (Settings button only, pinned, SHA-256) and the
  updater. CSP and capabilities tight. API key in DPAPI. `library.scan` skips links.
- **Esc:** every `holdEscape` is released on every way out. No order-dependent shortcut conflicts.
  Canvas drags handle capture, blur, cancel and a second pointer.
- **Docs:** every documented shortcut points at the right command; ⋯ paths, Settings sections and
  limits match the code; no user-facing "Threadline". Versions agree at 1.0.1 everywhere.

## Gaps (not checked, and why)
- No stitch-outs (deferred by the owner); new rows are queued in docs/stitchout-log.md if output changes.
- The installed app, the frozen engine build and the Mac/Linux bundles were not built or run.
- The AI model was not downloaded; redirect behavior was tested against local servers only.
- Canvas click routing (U1, U2) was checked by reading `onDown`; the state side was reproduced in vitest.
- Lettering with real fonts was not fuzzed, so how often S1 hits real letters is unmeasured.

---

# Details

The sections below are the reviewers' full notes, with repro steps and suggested fixes. Finding
numbers inside each section map to the IDs above in order (stitch 1-8 = S1-S8, layout 1-6 =
P1-P6, trace/security 1-7 = T1-T7, UI 1-9 = U1-U9, docs M1, M2, L1-L10 = D1-D12). Scratch repro
scripts lived in a temporary folder; the essential repros are quoted inline.

## QA pass 2: stitch output correctness (area 1)

Reviewer scope: `engine/threadline_engine/digitize/` (stitches.py, satinfill.py, patterns.py, applique.py, paths.py) and what PES/JEF export writes (layout.render -> prepare -> design.write).
Checked against `docs/QA-REPORT.md`, `docs/QA-RESPONSE.md`, `docs/qa-phase4/*.md` and `BACKLOG.md`: none of the items below are in them.

### Findings (most severe first)

#### 1. A thin neck anywhere in a fill turns its inside travel into trimmed jumps, and can end the fill with a 10-15 mm stitch
- **Severity:** Medium. **Status:** confirmed.
- **Where:**
  - `engine/threadline_engine/digitize/stitches.py:144-150` (`Zone.rings` returns `[]` when `poly.buffer(-0.3)` is a MultiPolygon).
  - `stitches.py:157-180` (`_edge_route` then finds no route).
  - `stitches.py:193-197` (`travel` falls back to TRIM+JUMP).
  - `stitches.py:1069-1076` (the end-point travel can leave the fill ending on a JUMP).
  - `stitches.py:123-131` and `1158-1159` (`tie_off` appends its lock after that JUMP).
- **What happens:** Take one connected fill in which some part is narrower than about 0.6 mm. Common causes are a hairline connection from auto-trace or a thin serif. The 0.3 mm-shrunk zone then splits in two, so `Zone.rings()` gives up on *every* edge route, including routes in parts nowhere near the neck.
  - **Visible jump:** a C-shape joined to a square by a 0.3 mm neck (pull comp 0, no underlay) gets a trimmed 22 mm jump straight across the C's open mouth. That is bare fabric, outside the shape. The same C without the neck sews with 0 jumps.
  - **Extra trims:** with the default edge and cross-hatch underlay, a 0.5 mm neck gives 3 trims of 15-44 mm inside the one fill. The underlay bounces between the two lobes in this order: edge C, edge square, cross-hatch C, cross-hatch square (`stitches.py:1037-1056`). On the PE550D each trim either leaves a loose thread or, with cut-stops on, becomes one more machine stop.
  - **Long final stitch:** when an end point is set (the red dot, Fewer jumps, lettering's "end toward the next letter"), the closing travel can also fail. The records then end `STITCH, TRIM, JUMP`. `tie_off` appends its two lock stitches *after* the jump, at the old position, so the machine sews one **10.7-14.5 mm stitch** back from the jump destination (7 of 154 end points tried).
- **Should:** Travel inside one connected shape should follow the shape's edges. A fill must never end on a jump, and no lock stitch should come after one.
- **Repro** (in `test_qa2_stitch.py`; both tests fail):
  ```python
  def neck_shape(neck=0.3):
      C = box(0, 0, 30, 30).difference(box(8, 8, 30, 22))
      g = unary_union([C, box(30, 23, 40, 23 + neck), box(40, 18, 55, 30)])
      return [[x, y, "c"] for x, y in list(g.exterior.coords)[:-1]]

  def test_a_thin_neck_elsewhere_does_not_turn_travel_into_jumps():
      recs, _ = generate({"kind": "fill", "geometry": {"outline": neck_shape()},
                          "params": {"underlay": [], "pull_comp_mm": 0, "angle_deg": 0}})
      assert not [r for r in recs if r[2] in (JUMP, TRIM)]      # gets [(0,29.8,TRIM),(40,29.8,JUMP)]

  def test_a_fill_never_ends_with_a_long_lock_stitch_after_a_jump():
      recs, _ = generate({"kind": "fill", "geometry": {"outline": neck_shape()},
                          "params": {"underlay": [], "pull_comp_mm": 0, "end_mm": [20, 15]}})
      ...  # consecutive STITCH distance: 14.51 mm
  ```
- **Fix:**
  - In `Zone.rings` take the rings of every polygon in `polygons(zone)`, not only a single Polygon. Better still, route on `poly` itself (for example, walk `self.poly`'s own rings with the coverage check).
  - In `_fill_part`, drop the end-point travel when it would be a jump.
  - Make `tie_off`/`tie_in` act on the last/first STITCH and insert the lock *before* any trailing JUMP/TRIM.
  - Optionally, sew each underlay piece's edge run and cross-hatch together, to avoid the back-and-forth.
- **Stitch output changes:** only for shapes with a neck under about 0.6 mm (and any fill ending on a jump). The owner should know, but it is a clear bug, not a judgement call.

#### 2. The zigzag underlay retraces its own legs instead of crossing them (about half of all wide satins, default settings)
- **Severity:** Medium. **Status:** confirmed.
- **Where:** `engine/threadline_engine/digitize/stitches.py:609-614` (the `fwd`/`back` lists in `satin_from_pairs`).
- **What happens:** The way back is meant to lay the other diagonals, as the zigzag in a criss-cross. That only works when the number of zigzag points `len(zz)` is **odd**.
  - When it is even, `back` starts on the same side `fwd` ended on, and then visits exactly the points `fwd` visited, in reverse. So the second pass sews the same zigzag again: the base is doubled on one diagonal and missing on the other.
  - Auto underlay (the in-app default via `fabrics.apply`) picks edge+zigzag for satins 5 mm and wider on normal fabric, and 2-5 mm on heavy fabrics. So the zigzag is common.
  - A 6 mm ribbon 20 mm long gives 36 diagonal legs, 36 distinct. At 22 mm long it gives 40 legs, only 29 distinct. Which result a satin gets depends only on its length.
- **Should:** The return pass always crosses the outgoing one (an X pattern), whatever the count.
- **Repro** (fails at 50 rungs: 69 legs, 60 distinct; 55 rungs passes):
  ```python
  def test_zigzag_underlay_crosses_back_instead_of_retracing():
      for rungs in (50, 55):
          pairs = [((i * 0.4, 0.0), (i * 0.4, 4.0)) for i in range(rungs)]
          recs, _ = satin_from_pairs(pairs, SatinParams(underlay=("zigzag",), spacing_mm=0.4))
          legs = [(round(a[0], 2), round(a[1], 2), round(b[0], 2), round(b[1], 2))
                  for a, b in zip(recs, recs[1:]) if a[2] == b[2] == STITCH]
          under = legs[: len(legs) - (rungs - 1)]
          und = [tuple(sorted([(l[0], l[1]), (l[2], l[3])])) for l in under]
          assert len(set(und)) == len(und)
  ```
- **Fix:** Build `back` from the side opposite to the one `fwd` used at each rung: `back = [ab[1] if fwd_side[i]==0 else ab[0] for i, ab in reversed(enumerate(zz))]`. You can also start `back` with a short step to the other side of the last rung.
- **Stitch output changes:** yes, for every satin with zigzag underlay and an even zigzag count. The snapshot `satin` cases with zigzag will need re-recording. It is a correctness fix, but the owner should approve the output change (and add a stitch-out entry).

#### 3. Applique: moves between edges (holes, separate pieces) are bare jumps, never marked for trimming
- **Severity:** Low-Medium. **Status:** confirmed.
- **Where:** `engine/threadline_engine/digitize/applique.py:174-182` (`section` appends `pe.JUMP` only).
- **What happens:** An applique with holes, or one whose self-crossing outline makes several pieces, moves between its edges with plain JUMPs.
  - A 60x20 mm piece with two holes has 8 jumps, 0 trims, the longest 45.3 mm. Six of the jumps are inside sections, before a stop.
  - Cut-stops only cut travels marked TRIM unless "Also cut jumps" is ticked. So these threads are never cut by the PE550D: they lie over the fabric during tack-down and over the finished cover.
  - Fills do mark the same kind of move with a TRIM (`stitches.py:1111` via `travel`), so the two behave differently.
- **Should:** A move over 3 mm (`TRIM_TRAVEL_MM`) between edges gets a TRIM before the JUMP, as `travel()` does.
- **Repro:** `test_applique_moves_between_edges_are_trimmed` in `test_qa2_stitch.py` ("untrimmed 45.3 mm move").
- **Fix:** In `section`, when `out` is non-empty and the last record isn't a STOP, use `travel(out[-1][:2], recs[0][:2])` (TRIM+JUMP over 3 mm) instead of the bare JUMP.
- **Stitch output changes:** trims added (the file changes; the needle path doesn't). With cut-stops on, extra machine stops. That is the owner's call.

#### 4. Satin ribbons and applique borders at sharp corners: stitches over 7 mm even with "Split long stitches", no warning
- **Severity:** Low. **Status:** confirmed.
- **Where:**
  - `stitches.py:436-443` (ribbon mitre, up to 2x half-width).
  - `applique.py:147-151` (`_offset_rails` mitre, `cos_half >= 0.5`).
  - `stitches.py:559-568` and `616-622` (the split only divides stitches *across* the column, never the step along the outer edge between rungs).
  - `stitches.py:584-587` (no warning once split is on).
- **What happens:**
  - A ribbon 8 mm wide with Split long stitches at 7 mm has a longest stitch of **8.46 mm** at a 30° corner and 7.95 mm at a 45° corner, with no warnings.
  - The applique cover on a 5-point star (25 mm / 7.5 mm radii) with an 8 mm border has **10 stitches of 7.8-8.6 mm** in the cover, again with no object warning.
  - phase-4 `stitches.md` says the applique border is "split at 7 mm". That holds across the border, not at the tips. Only the export-time quality check catches these stitches.
- **Should:** No stitch over the Longest setting, or a warning on the object.
- **Repro:** `test_split_long_stitches_holds_at_sharp_corners` in `test_qa2_stitch.py`. Also `s4.py` (applique star).
- **Fix:** Run the outer-rail step through `_subdivide` (add a needle point midway along the edge) whenever consecutive same-side points are more than `split_mm` apart. Otherwise lower the mitre cap when split is on.
- **Stitch output changes:** yes, only at sharp corners of wide satins and borders.

#### 5. "Split long stitches" with Longest over 7 mm: the warning tells you to tick the box that is already ticked
- **Severity:** Low. **Status:** confirmed.
- **Where:**
  - `stitches.py:584-587` (`split` treated as off for the warning when `split_mm > 7`).
  - `InfoPanel.tsx:666` (Longest stepper allows 2-12).
- **What happens:**
  - A 12 mm ribbon with split 8 sews stitches of at most 6.10 mm, yet warns "Parts of this satin are 12.0 mm wide… tick Split long stitches".
  - With split 12, pieces are 8.13 mm and the warning gives the same, unfixable advice.
- **Should:** When split is on but `split_mm > 7`, say "Longest is over 7 mm; set it to 7 or less". When the actual stitches are 7 mm or less, give no warning.
- **Fix:** Base the warning on the longest top piece actually produced, not on `params.split_mm <= 7`.
- **Stitch output changes:** no. Message only.

#### 6. Satin and running-stitch settings: null or non-number values crash as "engine bug" (fills were fixed, these weren't)
- **Severity:** Low. **Status:** confirmed.
- **Where:**
  - `stitches.py:229-244` (`RunParams.from_dict`).
  - `stitches.py:291-303` (`SatinParams.from_dict`).
  - `stitches.py:1138` (`float(g.get("width_mm", 3.0))`).
  - `fabrics.py:74` (`float(p.get("spacing_mm", 0.4))`).
- **What happens:** Each of these raises a raw TypeError or ValueError, which reaches the user as "Something went wrong in LUDD's engine":
  - `width_mm: null`
  - `spacing_mm: null`
  - `underlay: null`
  - `stitch_mm: "x"`

  `FillParams` already uses `_finite` ("null means default; non-numbers refused", phase-4 stitches.md row 50). Satin and run never got the same treatment. NaN is caught, by luck, by the range checks.
- **Fix:** Use `_finite` in `RunParams`/`SatinParams`, treat `underlay: null` as the default, and wrap `width_mm`.
- **Stitch output changes:** no.

#### 7. Fill and applique holes are not checked for NaN or huge points; a bad hole silently disappears
- **Severity:** Low. **Status:** confirmed.
- **Where:** `stitches.py:721-731` (`check_points(shell)` only) and `applique.py:95`.
- **What happens:** A hole with a NaN point is silently dropped: you get a shapely RuntimeWarning and the fill sews straight over where the hole was (564 stitches, the same as with no hole). A hole with a point at 1e9 is accepted, and cuts an arbitrary sliver out of the shape.
- **Should:** "This shape has a point that isn't a number" or "far bigger than any hoop", the same as for the outline.
- **Fix:** Call `check_points` on each hole ring in `fill_parts` and `_pieces`.
- **Stitch output changes:** no (errors only).

#### 8. Stipple with small loops on a hoop-sized shape takes over 6 s
- **Severity:** Low. **Status:** confirmed (timing). The cause is suspected.
- **Where:** `patterns.py:112-179` (`stipple_paths`). Suspected costs: the per-cell `inner.contains` over about 9,000 cells, and `unary_union(MultiLineString(lines)).buffer` with about 9,000 segments.
- **What happens:** A 95x95 mm square with `stipple_mm: 1` takes 6.5 s and gives 6,803 stitches. Every other pattern on the same size takes 0.1-0.4 s (contour at 0.2 mm, cross at 1 mm, tatami at 0.2 mm). Wave at 0.2 mm with a 2 mm wavelength takes 2.8 s and makes 72k stitches, about 7x the `MAX_STITCHES` estimate, which ignores wave's shorter step (`stitches.py:1093`). The brief's target is a few seconds per call, and each redraw re-runs this.
- **Fix:** Use a prepared geometry (`shapely.prepare(inner)`, or vectorised `shapely.contains_xy`) for the cell test. Buffer the tree in one call from a single MultiLineString without the `unary_union`. Include wave's `min(stitch, wave_len/4)` step in the stitch-count estimate.
- **Stitch output changes:** no (speed only).

### Solid areas (checked, no problems found)
- **Fills, 6 patterns x 8 shapes x 4 angles** (5- and 12-point stars, comb, crescent, 4 random blobs): no stitch over 3.51 mm at default settings. No stitch segment more than 0.3 mm outside the shape. All under 1.5 s.
- **Degenerate inputs give plain DigitizeErrors:** collinear or duplicate fill points, a hole equal to or bigger than the shell, NaN or string nodes, NaN settings, a zero-length ribbon, a one-rung column. These work without trouble: a hole touching the edge, a hole outside the shell, a two-point hole, 0.6-1 mm strips (tatami, wave, contour), tiny or thin appliques, and an applique with a hole touching its edge.
- **PES/JEF export is faithful.** A fill + satin + run design round-trips with the same stitch count (1,550). Every needle point is within 0.14 mm of the rendered design in PES and within 0.10 mm in JEF (0.1 mm units confirmed).
  - Color changes are kept.
  - Applique STOPs survive in PES (`STOP, T, J` per stop).
  - JEF writes stops as extra color steps (header 3 for placement/tack/cover), which Janome expects.
  - Cut-stops add the STOP with locks.
  - `long_stitch_contingency: SEW_TO` is now set, so the earlier JEF 12.7 mm hand-over is resolved.
- **Satin:** zero-width and same-rail columns warn and don't crash. The 20 mm-wide column split at 7 mm has a longest stitch of 6.73 mm. Closed ribbons with a start point are fine. The underlay always ends where the top starts.
- **Motif lines:** a zero-length or 0.01 mm line gives the single-needle-drop warning and no garbage.

### Gaps (not covered)
- Lettering with real fonts was not run, so I could not show how often finding 1 (necks under 0.6 mm) occurs in real glyphs or in auto-traced shapes. Its frequency is suspected, not measured.
- Layout-level joins, `travel_under` and Fewer jumps are area 2, and were not reviewed here.
- No stitch-out and no visual check in the app. The JEF read-back relies on pyembroidery's own reader.

## QA pass 2: layout/render pipeline and projects/files (areas 2 and 6)

Scope: `engine/threadline_engine/layout.py`, `jumps.py`, `split.py`, `prepare.py`, `project.py`, `storage.py`, `kept.py`.
I checked every finding against `docs/QA-REPORT.md`, `docs/QA-RESPONSE.md`, `docs/qa-phase4/*.md` and `BACKLOG.md`. None of these is listed there as fixed or decided.
I edited no repo files. The repro scripts are in
Run each with `cd engine && uv run --locked python <abs path>`. Every script sets `THREADLINE_DATA_DIR` to a temp folder.

---

### 1. Medium (security/robustness), confirmed: a tiny .ludd can make the engine build gigabytes of picture data
**Where:** `project.py:461-475` (the `open_project` images loop), `project.py:112-135` (`load_image`), `project.py:55-56` (`MAX_MEMBER_BYTES`)

**What happens:** Each member's size is checked, but nothing limits how many pictures a project lists or how many bytes they add up to. Several `images` entries can point at the same embedded member. That member is extracted once, but `load_image` then runs once per entry and builds a new base64 `data_url` each time, about 53 MB for a 40 MB member. A picture that is mostly zeros still passes `_check_pixels`, because only the header is read.
- With 12 entries, a **39 KB** `.ludd` produced 624 MB of data URLs. Peak memory was 715 MB and it took 3.7 s.
- With 200 entries it would be about 10 GB, which crashes the engine. Anything that does get through is sent to the UI in one JSON-RPC answer.
- Distinct members work too: N different 64 MB designs, or 40 MB pictures, compress to almost nothing and are all written into `project-files/`. That can fill the disk.

**Should:** A shared or downloaded project file can't exhaust memory or disk.

**Repro (`proj1.py 12`):**
```python
png = <10x10 PNG> + b"\0" * (39 << 20)
name = "images/" + sha256(png).hexdigest()[:32] + ".png"
manifest = {"format": "ludd-project", "version": 1, "layout": {"items": []},
            "images": [{"id": str(i), "embedded": name} for i in range(12)]}
## zip with ZIP_DEFLATED -> 39 KB file
p = project.open_project(path)
assert sum(len(i["data_url"]) for i in p["images"]) < 200 << 20   # fails: 624 MB
```

**Suggested fix:** Limit the number of pictures and items (for example 64 pictures). Also limit the total uncompressed size of all members read (for example 256 MB, summed from `ZipInfo.file_size`). Build each member's data URL once and reuse it, or refuse a project where two pictures share a member.

---

### 2. Medium (loses work), confirmed engine-side: the private copies are forgotten when the engine restarts
**Where:** `kept.py:17` (`_copies`, held only in memory), `kept.py:68-79` (`readable`), `layout.py:61-83` (`_load`), `project.py:222-225, 238-247` (`_pack`)

**What happens:** `kept.keep` writes the private copy to `project-files/<sha>.<ext>`. The only record of which original path it belongs to is the in-memory dict `_copies`. When the engine restarts, the copies are still on disk but nothing points to them. The engine restarts by itself after a crash (`engine/manager.ts`, C25) and from the status bar's Restart button, while the UI keeps the open document.

In this repro a design and a picture were added, then deleted from disk (an unplugged USB stick), then the engine restarted:
- `layout.render` fails with "File not found: usb.pes", so the design can't be shown.
- `project.save` fails with "Couldn't read the design usb.pes", so the work can't be saved.
- `project.autosave` succeeds but **silently leaves out the picture** (0 pictures), because autosave sends pictures by path only. It also keeps the design only as a link to the missing file.
- The as-added protection from leftovers.md (a picture edited elsewhere is not saved in place of the one on screen) also stops working after a restart: `readable(..., as_added=True)` falls back to the edited original.

`kept.py`'s own docstring promises the design keeps working "on a USB stick that's unplugged before the first save". That holds only until the first engine restart.

**Repro (`kept1.py`, two processes sharing one data dir):**
```
process 1: render(design); load_image(pic); delete both originals   -> render OK, save OK
process 2: copies on disk: ['07ac…pes', 'cbfc…png']
           render   -> LayoutError File not found: usb.pes
           save     -> ProjectError Couldn't read the design usb.pes
           autosave -> ok, but 0 pictures; design item still linked to the missing path
```

**Suggested fix:** Keep the mapping where a new engine can find it. Either return the copy's name (`<sha>.<ext>`) from `load_image` and `_load` and store it on the item or picture (the UI already round-trips item fields), or keep a small JSON index in `project-files/`. Then `kept.readable` uses the stored hash when the original is missing.

---

### 3. Medium (wrong stitch-out, silently), confirmed: stitch-file edits are re-applied to a different file once the original changes on disk
**Where:** `layout.py:960-975` (file items in `render`), `layout.py:173-228` (`_apply_ops`), `layout.py:61-83` (`_load` follows the file on disk)

**What happens:** Recolours (`threads[b]`), `delete_block`, `delete_stitches`, inserted stops and trims, and `move_stitches` all refer to the source file's colour-block and record numbers. `_load` re-reads the file whenever its time or size changes. If the placed `.pes` is saved again from another program while it is in a LUDD design or an unsaved session, every edit lands on whatever now sits at those numbers. No note or warning appears.
- Drawn shapes already handle this: an insert records the shape's record count `n` and is dropped with a note when that no longer matches.
- Files have no such check. The next Save then embeds the new file with the misplaced edits.

**Repro (`filechange.py`):**
```python
write(f, [("#ff0000", row 0), ("#0000ff", row 1)])
lay = {"items": [{"id": "a", "path": f, "threads": [None, {"color": "#00ff00", "name": "Green"}],
                  "ops": [{"op": "delete_stitches", "indices": [3, 4, 5]}, {"op": "delete_block", "block": 0}]}]}
L.render(lay)   # blocks ['Green'], 9 stitches     (blue row recoloured, red row deleted)
write(f, [("#ffff00", ...), ("#ff0000", row 0), ("#0000ff", row 1)])   # file re-saved elsewhere
L.render(lay)   # blocks ['Green', '#0000ff'], 18 stitches, warnings []
                # the RED row is now sewn in Green, the deleted colour is a different one, no note
```

**Suggested fix (owner's call; changes behaviour):** Once an item has edits, pin it to the bytes it had when it was added. The kept copy works for this, as `as_added` does for pictures. Alternatively, store a fingerprint (sha or record count) on the item, and when it no longer matches, drop the edits with a note as drawn shapes do.

---

### 4. Low, confirmed: damaged items open without complaint, then every render fails with "Please report this"
**Where:** `project.py:425-430` (only checks that items are dicts), `project.py:445-449` (a file item without `embedded` loses its `path`), `layout.py:966` (`_load(it["path"])`), `layout.py:96-102` (`Transform.from_dict`), `layout.py:181-200` (`ops` handling)

**What happens:** `open_project` accepts any item that is a dict. The first `layout.render` then fails for the **whole design** with -32603 "Something went wrong in LUDD's engine … Please report this", so nothing shows. Results from `proj2.py`:

| item in project.json | result |
|---|---|
| `{"id":"a","path":"C:/x.pes"}` (file not embedded) | open OK (path dropped) -> render -32603 "something is missing (path)" |
| `{"kind":"sequins"}` (kind from a newer LUDD) | -32603 "something is missing (path)" |
| `transform.scale_x: "2"` | -32603 "'<=' not supported…" |
| `ops: "oops"` / `ops: [5]` | -32603 "'str'/'int' object has no attribute 'get'" |
| `threads: ["red"]`, `thread: "red"`, `params: [1]`, `rotate: null` | -32603 each |
| `geometry` missing | -32000 "Fill 2 has no points" (fine) |

**Should:** Per QA-PROMPT area 6, damaged files fail gracefully. Either the item is left out with a note ("a design inside this project is missing"), or open refuses the file in plain words. One bad item shouldn't blank the canvas.

**Suggested fix:** In `open_project`, drop file items left with no path, plus items whose kind is unknown or whose `transform`, `ops`, `threads`, `thread` or `params` have the wrong type, and report how many were dropped. Alternatively, in `render`, catch `(KeyError, TypeError, ValueError, AttributeError)` per item and raise `LayoutError(f"{name} is damaged")`.

---

### 5. Low, confirmed: "Sew in the shortest order" groups threads differently from the renderer and can add a thread change
**Where:** `layout.py:829-833` (`optimize_order.key`) vs `layout.py:300-301` (`_thread_key`)

**What happens:** `optimize_order` treats shapes as one thread when colour, brand and catalog match. It ignores the name and compares brand without lowercasing. `render` (`_thread_key`) uses the name when there is no catalog number, and lowercases the brand. So two same-hex threads with no catalog number but different names ("Red" and "Cherry") form one run in the optimizer but are two colours in the file. The optimizer can then interleave them.

**Repro (`order_key.py`):** items `a`(Red, x=0), `b`(Red, x=60), `c`(Cherry, x=20), `d`(Cherry, x=40), all `#cc2222`, catalog "".
```python
o = L.optimize_order({"items": items})   # order a, c, d, b; saved_mm 50.1
## colour changes: before 1, after 2  -> one more thread swap on the PE550D
```

**Suggested fix:** Use `_thread_key({**thread, **override})` as the run key in `optimize_order`.

---

### 6. Low, confirmed: the shipped samples' ready-to-sew PES/JEF no longer match their own .ludd projects (old projects don't sew the same, and no test pins it)
**Where:** `samples/*.pes|.jef` (from LUDD 1.0.0, commit a5b44eb), `scripts/make_samples.py`; no test renders a sample `.ludd` against its `.pes`

**What happens:** The 1.0.0 sample projects (version 1, no features) now render differently from the PES files shipped beside them:

| sample | stitches now | stitches in the PES |
|---|---|---|
| Flower | 2594 | 2612 |
| Star badge | 4833 | 4766 |
| Wreath | 1915 | 1940 |

This is most likely the deliberate stitch changes from the QA phases, and they are documented. But a user who opens `Star badge.pes` from the samples gets different stitches than one who opens `Star badge.ludd` and saves for the machine. Nothing in CI would catch an *unintended* change to how a v1 project sews either. `test_golden` only round-trips the PES/JEF files.

**Suggested fix (owner's decision):**
- Regenerate `samples/` with `scripts/make_samples.py`.
- Add a golden test: render each `samples/*.ludd`, export it to PES, and compare it with the committed PES (exact or within a tolerance). Any future change to stitch output for old projects then has to be made on purpose.

---

### Checked and solid
- **Hidden travel is never left on top.** I fuzzed 120 random layouts: 4-9 fills, lines and satins in 1-3 threads, with `color_sort` and `merge_colors` set at random and `travel_under` on. Every hidden-travel stitch (item -1, src -1) was covered within 0.45 mm by stitching sewn after it (67 travel segments, 0 uncovered; `fuzz_travel.py`). Objects don't end in a TRIM, so no travel starts from a cut thread.
- **Thread tables and colour blocks after edits.** I fuzzed 300 random layouts of the sample PES/JEF files with `delete_block`, `delete_stitches`, inserts, recolours, rotation, colour sort, merge, basting, knockdown and the layout-wide trim-jumps setting. Every time, the thread count equalled colour changes + 1, `render_summary` blocks matched the rendered blocks one for one, and the colours matched (`blocks_fuzz.py`).
- **Splitting.** I split Banner, Flower, Applique heart and Star badge for hoops of 100x100, 60x60, 40x40 and 130x180 mm. No stitch landed outside the hoop's field or ran longer than 12.1 mm. Threads matched colour changes, and applique stops were kept in every hooping that sews placement or tack-down (`split_check.py`). The `safe()` layering rule holds pairwise as runs are moved.
- **Moved stitches next to an inserted stop or trim.** The stop or trim stays at the old position in the render, but PES, JEF and DST writers emit it at the needle's real position, so the output is unaffected.
- **Old-format checks.** `.thl` and `threadline-project` open; rail satins render (all four rail-satin samples). Old projects keep `travel_under` off. Embedded pictures survive deletion of the original within one engine session. Path traversal is blocked by `_safe_member` plus the hash check, and a lying `file_size` is bounded by zipfile plus the CRC.

### Gaps (not checked, and why)
- **Live UI.** I didn't run the app or the preview. Finding 2 is reproduced in the engine across two processes. That the UI keeps the document across an engine restart is from reading `engine/manager.ts`.
- **Real machine.** No stitch-outs (deferred by the owner).
- **Big pictures or zips.** I didn't push finding 1 to an actual out-of-memory crash, to keep this PC usable.
- **Other areas.** I didn't look at `jumps.optimize_jumps` beyond reading it, or at `prepare.add_cut_stops` (reviewed in phase 4).

### Top fixes first
1. Finding 2 (pin private copies across engine restarts).
2. Finding 3 (stitch-file edits on a changed file).
3. Finding 1 (total size and picture count limits on open).
4. Finding 4 (damaged items).
5. Finding 6 (regenerate samples plus a golden `.ludd` -> PES test).

## QA pass 2: auto-trace, shape ops, security & privacy, packaging (areas 3, 4, 7, 8)

Scope: `autotrace.py`, `trace.py`, `ai/segment.py`, `shapeops.py` + `features.ts` shape-op UI, Tauri CSP/capabilities/`lib.rs`, network code, AI key storage, path handling (`library.scan`, export, chart ids), `scripts/build_engine.py`, `smoke_engine.py`, `ci.yml`, `release.yml`, `dependabot.yml`, version numbers.
Everything already in `docs/QA-REPORT.md`, `docs/QA-RESPONSE.md`, `docs/qa-phase4/*.md` and `BACKLOG.md` was excluded (grepped before reporting).

---

### 1. Medium: the AI API key follows an HTTP redirect to another host (and over plain http)
**Confirmed.** `engine/threadline_engine/ai/providers.py:60-64` (`_post`, `urllib.request.urlopen`).

**What happens:** `_post` uses urllib's default opener. On a 301/302/303, urllib re-sends the request as a GET to the `Location`, copying every header added via `Request(headers=...)`, including `authorization: Bearer <key>` (OpenAI-compatible) and `x-api-key` (Anthropic). It does this for any host and also from https to http. The settings check that the cloud address is `https://` (`ai/settings.py` save) does not cover where the request ends up after a redirect. The same applies to "On this computer" Ollama addresses: a redirect off the machine skips the "before you send" preview, because `on_this_computer` only looks at the configured URL.

**Should:** the key goes only to the host the user configured, never over plain http to the internet. A redirect should be refused, or followed only to the same origin.

**Repro** (`redir.py`): server A on 127.0.0.1 answers POST with `302 Location: http://127.0.0.2:<port>/elsewhere`; server B records headers.
```
p = providers.OpenAICompatible("sk-SECRET-TEST", "m", "http://127.0.0.1:<A>/v1"); p.ask(Request(system="s", text="t"))
-> server B (other host) got: GET {'Host': '127.0.0.2:…', 'Authorization': 'Bearer sk-SECRET-TEST'}
Anthropic("sk-ant-SECRET", …) -> server B got {'X-Api-Key': 'sk-ant-SECRET'}
```
**Suggested fix:** build the opener with a `HTTPRedirectHandler` subclass whose `redirect_request` returns `None` (or raises `AIError("The AI service redirected to <host>; check the address in Settings")`). Alternatively, follow only same-scheme, same-host redirects. Add a pytest with two local `http.server`s, as above. No owner decision needed.

---

### 2. Medium: importing a thread chart silently replaces another chart with a different name
**Confirmed.** `engine/threadline_engine/threads.py:142-144` (`_slug`), `:285-290` (`import_csv`); `apps/desktop/src/actions.ts:1999` (no check).

**What happens:** the chart id is `_slug(name)` (lower-case ASCII letters, digits and dashes) and the file is written to `threads/<id>.json` with no existence check. Two different names that slug alike overwrite each other ("Isacord 40" and "Isacord-40!" both become `isacord-40`). Any name without Latin letters or digits becomes `chart`, so every Cyrillic, Greek, CJK, Hebrew or Arabic-named chart replaces the previous one. Neither the UI nor the engine warns.
Names like `CON` / `nul` give "Couldn't save the chart: Cannot create a file when that file already exists" (a Windows reserved device name). It fails safely, but the message is confusing.

**Repro:**
```
import_csv(a.csv, "Нитки Мадейра") -> id "chart"
import_csv(b.csv, "糸チャート")     -> id "chart"   # the first chart is gone
list_charts()[-1] -> ('chart', '糸チャート', 2)
import_csv(a.csv, "Isacord 40"), import_csv(b.csv, "Isacord-40!") -> both "isacord-40"; only the second remains
```
**Suggested fix:** if `<id>.json` exists and holds a chart with a different `name`, add `-2`, `-3`, … to the id. When the slug is empty, use a short hash of the name instead of `chart`. Prefix Windows reserved stems (`con`, `prn`, `aux`, `nul`, `com1-9`, `lpt1-9`). **Owner decision:** should re-importing the *same* name replace the chart (today's behavior, useful for updating it) or ask first?

---

### 3. Medium: nothing checks that ONNX Runtime actually loads in the frozen engine
**Confirmed gap** (code). Today's local Windows build is fine; failure is **suspected**, not seen. `scripts/smoke_engine.py:96-110`, `engine/threadline_engine/ai/segment.py:66-72` (`runtime()`).

**What happens:** the smoke test proves OpenCV (`trace.digitize_all`) and GEOS. It never touches ONNX Runtime. `runtime()`, which Settings shows as "AI tracing can run here", uses `importlib.util.find_spec("onnxruntime")`. That finds the package even when its native `onnxruntime.dll` / `_pybind11_state` is missing or can't load (missing VC++ runtime, a PyInstaller hook change after a dependency bump). If that breaks, every build passes, and the user only finds out after pressing Download (a plain "isn't available" message, or a failed model load after the 45 MB download).
Checked here: the existing local sidecar (`threadline/apps/desktop/src-tauri/binaries/threadline-engine-x86_64-pc-windows-msvc.exe`, 1.0.1) contains `cv2\cv2.pyd`, `onnxruntime\capi\onnxruntime.dll`, `onnxruntime_providers_shared.dll` and `onnxruntime_pybind11_state.pyd`, and no `opencv_videoio_ffmpeg` (PyInstaller archive_viewer). Its `ai.trace_model` reports `runtime: true`.

**Should:** per AGENTS.md / QA-PROMPT, the frozen engine must include a *working* ONNX Runtime everywhere except Intel Macs, and the build should fail otherwise.

**Suggested fix:** make `runtime()` really `import onnxruntime` (catch `ImportError`/`OSError`, cache the result). In `smoke_engine.py`, call `ai.trace_model` and assert `runtime` is true, except when `platform.machine()=="x86_64"` on darwin. Better still, add a tiny RPC or smoke step that builds an `InferenceSession` from a few-byte ONNX model (e.g. an Identity node, embedded as bytes), so the native library is actually loaded. No owner decision needed.

---

### 4. Low: small picture placements make Whole picture very slow; degenerate placements and pictures give raw errors
**Confirmed** (engine). How a placement reaches width 0 from the UI is **suspected** from the code.
- `engine/threadline_engine/autotrace.py:899-901` (`_solid_dark`: `solid_r = round(SOLID_MM/2*ppm)`, unbounded, then `cv2.dilate` with a `(2*solid_r+3)²` ellipse)
- `trace.py:175-176` (`Placement.from_dict`: no validation)
- `autotrace.py:942-949` (1×1 picture)
- `apps/desktop/src/components/StitchCanvas.tsx:2059, 2183` (scale clamps each drag to ×0.05 and then `round2` the width)

**What happens:** px-per-mm grows as the placement shrinks, so the dilate kernel grows with it. Timings for `logo.png` (800×600), `digitize_all`:

| Placement width | 20 mm | 10 mm | 5 mm | 2 mm | 1 mm |
|---|---|---|---|---|---|
| Time | 0.5 s | 0.7-1.3 s | 2.2 s | 13.9 s | 50.4 s |

At 0.5 mm it hadn't finished after several minutes (killed). 14.6 of the 14.9 s at 2 mm is `cv2.dilate`. During that time the engine's background worker is pinned at full CPU.
Degenerate input also leaks raw exceptions to the user:
- width 0: `ZeroDivisionError` (digitize_all) / `OverflowError` (region)
- negative width: `OverflowError`
- NaN: `ValueError`
- 1e-6 mm: OpenCV "Insufficient memory"
- a 1×1-pixel picture: `ValueError: cannot reshape array of size 1 into shape (3)` in `_cv_lab_to_cie`

From the UI, a picture can be shrunk by repeated corner drags (each drag clamps to ×0.05 of the current size, then `round2`) until `width_mm` is `0`.

**Should:** stay under a few seconds at any placement, and give a plain message for unusable placements and pictures.

**Repro:** `autotrace.digitize_all(logo.png, {"x":0,"y":0,"width_mm":2,"height_mm":1.5,"rotate":0})` takes about 14 s. With `width_mm=0` it raises `ZeroDivisionError`. A 1×1 PNG raises `ValueError`.

**Suggested fix:**
- In `_solid_dark`, return early when `core` is empty, and replace the disk dilate with `cv2.distanceTransform(1-core) <= solid_r+1` (constant cost); or cap `solid_r` at `max(pic.w, pic.h)`.
- In `Placement.from_dict`, reject non-finite or < 0.5 mm sizes with a `TraceError`.
- Have `digitize_all` return no shapes for pictures under ~4 px.
- Clamp a picture's size in `setPicture` (e.g. ≥ 1 mm).

No owner decision needed.

---

### 5. Low: Merge (and the knife) apply the engine's answer to a design that may have changed meanwhile
**Suspected** (code reading; the window is the engine round trip). `apps/desktop/src/features.ts:264-281` (`mergeSelected`), `:225-258` (`finishKnife`).

**What happens:** `cutOutSelected` (line ~297) guards with `if (currentLayout() !== before) return info("The design changed while cutting…")`. `mergeSelected` doesn't. After the await it rebuilds from `currentLayout()` using the `items` captured before the call. If an undo or delete removed the first-selected shape in the meantime, the `.map` finds nothing to replace, but the `others` filter still deletes the remaining selected fills. Result: the shapes vanish and no merged shape appears (one Ctrl+Z brings them back).
`finishKnife` similarly passes the old geometry to `insertObjects(parts, o.id, [o.id])`. If the shape was moved or edited during the cut, the pieces come from the old shape and replace the edited one.
This class was reported for Delete, reorder and shortestOrder (QA-REPORT "Edits computed from a stale snapshot") but not for merge or knife.

**Repro (suggested vitest):** mock `engine().call("shape.merge")` with a deferred promise. Call `mergeSelected()` with A and B selected. Before resolving, commit a layout without A. Resolve, then expect B still present (today: B is removed and nothing is added).

**Suggested fix:** copy the `before` guard from `cutOutSelected` into `mergeSelected` and `finishKnife`. No owner decision needed.

---

### 6. Low: Dependabot can open Tauri plugin bumps that fail the installer build
**Suspected** (config reading; history suggests it already happened: commit aba3b02 "Tauri plugins … together (replaces #2 and #11)"). `.github/dependabot.yml` (separate `npm` and `cargo` groups), `apps/desktop/src-tauri/Cargo.toml:18-21` ("keep on the same minor as @tauri-apps/plugin-…").

**What happens:** each plugin is pinned to the same minor version on both sides: `tauri-plugin-shell ~2.6` with `@tauri-apps/plugin-shell ~2.6.0`, and likewise for dialog, updater and process. The Tauri CLI refuses to build when the crate and npm major.minor differ. Dependabot's `npm` and `cargo` groups both accept minor updates, but in separate PRs, so each PR moves one side only. Today all four pairs match (lockfiles: dialog 2.8.4, process 2.4.0, shell 2.6.0, updater 2.14.1 on both sides; `tauri` 2.12.3 vs `@tauri-apps/api` 2.12.4).

**Should:** a Dependabot PR is either buildable or not opened.

**Suggested fix:** in `dependabot.yml`, ignore `version-update:semver-minor` for `tauri-plugin-*` / `tauri` (cargo) and `@tauri-apps/*` (npm) and bump those pairs by hand. Or add a vitest in `release.test.ts` that reads `Cargo.toml` and `package.json` and fails when a pair's major.minor differ, so the PR goes red in the fast test job rather than in the installer job. **Owner decision** (process).

---

### 7. Low: macOS and Linux Rust code is compiled for the first time on release day
**Confirmed** (workflow reading). `.github/workflows/ci.yml:41-76` (Rust is only built in the Windows `windows-installer` job), `release.yml:92-97` (the release "Tests" step runs no `cargo test`).

**What happens:** `lib.rs` has macOS-only code (`with_asking_quit`, `RunEvent::Opened`, menu replacement). platform.md says it "could not be compiled here; watch the first macos-latest build". CI's Mac and Linux legs run only engine and UI tests, so this code first compiles when a release tag is pushed. The release legs never run the `lib.rs` unit tests on Mac or Linux.

**Suggested fix:** add a `cargo test --locked --lib` (or `cargo check`) step on `macos-latest` in CI. `tauri-build` needs `binaries/threadline-engine-<triple>` and `binaries/THIRD-PARTY-NOTICES.txt` to exist, so create empty placeholders first, or run `pnpm build:engine` there. Also add `cargo test --lib` to release.yml's Tests step. **Owner decision** (extra CI minutes).

---

### Solid (checked)
- **Auto-trace robustness** (region click + whole picture + Trace Assist `info`), 33 synthetic pictures. No crash except the 1×1 case above:
  - JPEG q10/30/60, heavy Gaussian noise, linear and radial gradients, fully transparent / semi-transparent / transparent-shape PNGs, palette PNG with transparency, LA, 1-bit, CMYK JPEG, EXIF-rotated JPEG, animated GIF, WebP, BMP, TIFF, float TIFF
  - all-white, all-black, 2×2, 3×1, 1×500, 4000×2, a 16×12 logo
  - 63 MP PNG (1.2 s) and 108 MP JPEG (1.0 s)
  - Timings are all under 1.2 s except random-noise whole picture (4.8 s, 373 shapes; progress/cancel is already on the backlog) and an all-black click (2.0 s).
  - JPEG logos give the same 5 shapes as the PNG.
- **Rotated placements** (0°, 90°, −30°): the clicked area's outline is centred on the click, and whole-picture shapes are identical.
- **Large placements** (1e6 mm) and spread out of range (0, −5, 100) don't crash.
- **AI model download** happens only from the Settings Download button (`AISettings.tsx:203` → `ai.trace_model_download`). It is pinned to a revision with SHA-256 checks and atomic `.part` → replace; region clicks only use AI when the model is installed and the runtime is present.
- **Network code:** only `ai/providers.py` (opt-in add-on), `ai/segment.py` (model download) and the Tauri updater. No `fetch`/XHR/WebSocket in the UI except the dev-only `/__engine` bridge; no external URLs in `index.html`/CSS (fonts are bundled); no `subprocess`/`webbrowser` in the engine.
- **CSP and capabilities:** CSP (`default-src 'self'`, connect-src limited to IPC, no `unsafe-eval`; pictures go through `Texture.from(el)`, no blob workers). Capabilities: `shell:allow-spawn` scoped to the sidecar, no fs/opener/http plugins. `third_party_notices` reads one resource file; `launch_file` / single-instance only pass existing files.
- **AI key and settings:** DPAPI with `CRYPTPROTECT_UI_FORBIDDEN`. Cloud http refused unless loopback (apart from redirects, finding 1).
- **Paths:** `library.scan` skips symlinks and junctions, visits each folder once, caps at 5,000 folders and 600 files. Chart ids are checked against `[a-z0-9-]` before any file access.
- **Shape ops** (13 edge cases): knife through corners, along an edge, through a hole, on a bowtie, on a closed satin, on a 2-point run, on a rotated fill; merge of identical, corner-touching or empty shapes; cut-out of the whole fill or with an open line. All give correct results or plain `ShapeError` messages (a NaN knife point gives a raw GEOS error, but the UI can't send one).
- **Packaging:** the local frozen sidecar contains cv2 and onnxruntime and drops `opencv_videoio_ffmpeg`. Version 1.0.1 agrees in root/desktop `package.json`, `tauri.conf.json`, `Cargo.toml`, `Cargo.lock`, `pyproject.toml`, `uv.lock` and `__init__.py`. After the dependency bumps: Actions are SHA-pinned and consistent between ci.yml and release.yml; vitest 5.1.0 / vite 6.4.4 / jsdom 31.0.1 / TypeScript 7.0.2 resolve together; `pnpm test` passed 204/204.

### Gaps
- **`pnpm typecheck`** failed during my run on `src/zz-qa2-ui.test.ts`, another reviewer's scratch file. It was gone by the end of the session, so I didn't re-run typecheck.
- **Frozen engine and CI:** I didn't build the frozen engine (not allowed). I inspected the existing local Windows sidecar only; the Mac and Linux bundles are unchecked. I couldn't verify the Tauri CLI version-mismatch behavior in finding 6 or the GitHub-hosted workflow runs without the network.
- **Real AI:** the AI model path wasn't exercised (no download). Redirect behavior was tested against local servers only.
- **Browser preview:** I didn't run the knife/merge UI there (shared preview); finding 5 is from reading the code.

### Top fixes first
1. Refuse redirects in `providers._post` (finding 1).
2. Unique chart ids on import (finding 2).
3. Make `runtime()` and the smoke test really load ONNX Runtime (finding 3).
4. Bound `_solid_dark`'s kernel and validate placements (finding 4).
5. Add the stale-layout guard to merge and knife (finding 5).

## QA pass 2: area 5, UI state and interaction model

Scope: `actions.ts`, `store.ts`, `features.ts`, `autoTrace.ts`, `commands.ts`, `escape.ts`, `keys.ts`, `StitchCanvas.tsx`, `InfoPanel.tsx`, `Accordion.tsx`, `TextPanel.tsx`, dialogs.
Checked against `docs/QA-REPORT.md`, `docs/QA-RESPONSE.md`, `docs/qa-phase4/*.md` (ui.md, leftovers.md) and `BACKLOG.md`: everything below is new.

How it was tested: one temporary vitest file, `zz-qa2-ui.test.ts`, using the real actions/store/features/autoTrace/keys and a fake engine with a delay per method (same pattern as `ui.qa.test.ts`). All 8 repro tests passed, which means each bug happened. The file was deleted afterwards and `git status` is clean. A copy is at
To run it: copy it to `apps/desktop/src/`, then `cd apps/desktop && corepack pnpm vitest run src/zz-qa2-ui.test.ts`.

---

### 1. Medium · confirmed: the knife (or stitch editing) stays active under the ruler or angle line; clicks cut the shape while the hint says "measure"
**Where:** `actions.ts` `toggleRuler` (~1766) and `startAngle` (~1751) don't end the knife or stitch editing. `features.ts:215` `startKnife` doesn't end the ruler or angle line either. `StitchCanvas.tsx:1729/1737/1761/1767`: `onDown` handles the knife first, then stitch editing, then the ruler, then the angle line. `ToolRail.tsx:103/122/129` shows the ruler hint *before* the knife and stitch-edit hints.

**What happens:** Select a fill, press Shift+K (knife), then M (measure). Both `knife` and `ruler` are now set. The hint bar says "Click two points to see the distance". The canvas gives those clicks to the knife, so two clicks **cut the shape in two**. Esc also breaks the "newest first" rule: the first Esc removes the knife (the older mode, because it holds Esc), and the ruler stays. The same happens with stitch editing plus M: the hint says measure, but clicks select stitches and drags move them. Shift+K while the ruler is open works the same way.

**Should:** Only one of knife, stitch edit, ruler and angle line is active at a time. Starting one ends the others.

**Repro (passes, so the bug happens):**
```ts
setDoc(fakeEngine(), [fill("a")]); useStore.getState().select("a");
F.startKnife(); run("view.measure");
expect(useStore.getState().ruler).toEqual([]); expect(useStore.getState().knife).not.toBeNull();
onKeyDown(key("Escape"));
expect(useStore.getState().knife).toBeNull(); expect(useStore.getState().ruler).toEqual([]); // older mode let go first
```
**Fix:** Add one "end modal modes" helper, called by `toggleRuler`, `startAngle`, `startKnife` and `startStitchEdit`: `setKnife(null)`, `endStitchEdit()`, `setRuler(null)`, `setAngleFor(null)`, except for the mode being started. Owner decision: none (a plain bug).

### 2. Medium · confirmed: a tool key during stitch editing picks the tool, but stitch editing stays on and eats the clicks
**Where:** `store.ts:431` `setTool` clears `knife`, `autoTrace`, `autoAll`, `ruler` and `angleFor`, but not `stitchEdit`. `StitchCanvas.tsx:1737` handles stitch editing before drawing.

**What happens:** In stitch editing, press F (or L, C, Shift+T, Shift+A). The tool rail highlights Fill, but the hint still reads "Editing stitches", every click selects stitches instead of drawing, and the Esc hold stays (`heldCount()===1`). ui.md says "Knife then tool change ... leaves a stale Esc hold: Fixed"; that fix only covers the knife.

**Repro:** `startStitchEdit()` on a file, then `run("tool.fill")`. Result: `tool==="fill"`, `stitchEdit` not null, `heldCount()===1`.

**Fix:** In `setTool`, also set `stitchEdit: null`. The features.ts subscription already releases its hold. Owner decision: none.

### 3. Medium · confirmed: Ctrl+Z while drawing throws away the half-drawn shape *and* undoes the edit before it
**Where:** `actions.ts:647` `undoEdit` runs `setPen(null)` and then `showHistory(undo(...))`. `canUndo` (2068) stays on while drawing. It also skips `cancelTraceQueue()` and the hole tool's `holeBack` restore that `penCancel` (1037) does.

**What happens:** Nudge a shape, then start drawing a fill (4 points) and press Ctrl+Z. All 4 points are gone with no "Shape dropped" note, and the nudge is undone too: two things for one press. Ctrl+Y brings back the nudge but not the points. When drawing a hole (O), the tool stays on Fill instead of going back.

**Repro:** see test "Ctrl+Z while drawing": after `onKeyDown(ctrl+z)`, `pen===null` and the item differs from the nudged state.

**Should:** While drawing, Ctrl+Z either removes the last point (like Backspace), or only drops the shape and leaves the history alone.

**Fix:** In `edit.undo`/`edit.redo`, when `drawing()` is true, run `penUndoPoint()` (or `penCancel()`) and return. Otherwise undo as now. **Owner decision:** which of the two (Embrilliance-style "Ctrl+Z removes the last point" seems most natural). The manual (line 884) should say it.

### 4. Medium · confirmed: knife, merge, offset and "Optimize jumps" apply an engine answer worked out from the old design
**Where:** `features.ts:225` `finishKnife`, `:264` `mergeSelected`, `:151` `addOffset`, `:354` `optimizeJumps`. Compare `cutOutSelected` (`:301`, "The design changed while cutting") and `actions.ts` `unchanged()` (used by `convertObject`, `satinOtherWay`, `textToShapes`, `moveStitchEnd`), which guard against this. The phase-4 stale-snapshot fix covered Delete, the order arrows and `shortestOrder`, but not these four.

**What happens (both reproduced):**
- **Merge:** press Ctrl+M, then nudge with an arrow key before the reply comes. The merged shape uses the pre-nudge geometry and its transform is reset, so the nudge is silently lost even though it is in the undo history.
- **Knife:** finish a cut, then press Ctrl+Z before the reply (the shape is undone and disappears). When the reply comes, `insertObjects` adds the two pieces anyway, so the undone shape comes back as pieces. Redo is then empty.
- By reading the code: `addOffset` places rings around the old position. `optimizeJumps` writes old-geometry `changes` over a shape whose points were dragged meanwhile.

**Repro:** see tests "merge: a nudge made while merging is thrown away" and "knife: the shape undone while cutting comes back as pieces". Use `fakeEngine({"shape.merge": 40})` / `{"shape.split": 40}`, then `run("arrange.right")` or `A.undoEdit()` during the wait.

**Fix:** Snapshot the involved items before the call. After it, if `!unchanged(id, before)` for any of them, drop the answer with "The design changed while …: try again". This is the cut-out pattern. Owner decision: none.

### 5. Medium · confirmed: Auto-trace: clicking the next shape while the last accept is still adding makes the new guess disappear
**Where:** `autoTrace.ts:212-262` `acceptGuess`. After `await addTraced(...)` it calls `dismissAutoTrace()` (`:260`) without checking that the guess on screen is still the one it accepted. `autoTraceAt` doesn't refuse clicks while `busy`.

**What happens:** Press Enter on a guess, then click the next shape right away (normal rhythm on a slow render). The new click starts a new guess and its reply arrives. When the first accept finishes, `dismissAutoTrace()` removes the **new** guess (and `seq++` throws away a reply still on its way). The user sees their click do nothing. Likewise, Esc during the accept dismisses the guess, but the shape is still added.

**Repro:** see test "the new guess is dismissed when the earlier accept finishes" (render delay 40 ms, `autoTraceAt(20,20)` during the accept, then `autoTrace===null`).

**Fix:** Before the await, keep `const mine = s.autoTrace`. Afterwards, only dismiss and show the note if `useStore.getState().autoTrace` is still `mine` (or its busy copy). Optionally ignore canvas clicks while `autoTrace.busy`. Owner decision: none.

### 6. Low · confirmed: the angle line (I) outlives its fill
**Where:** `store.ts:413` `setHistory` drops `knife`, `stitchEdit`, `autoTrace`, `autoAll`, `measure` and `selectedNode` for items that are gone, but not `angleFor`.

**What happens:** Select a fill, press I, then Delete (still enabled) or Ctrl+Z its creation. `angleFor` keeps the dead id, the hint stays, two clicks run `finishAngle` on nothing (a silent no-op), and Esc is needed.

**Repro:** test "angleFor keeps the dead id".

**Fix:** In `setHistory`: `angleFor: s.angleFor && hasItem(s.angleFor.id) ? s.angleFor : null`. Owner decision: none.

### 7. Low · confirmed: Ctrl+X with nothing selected copies but doesn't cut
**Where:** `actions.ts:1794` `copySelected(true)` copies `selectionIds()`, which falls back to `targetId()` (the only item). Then it calls `removeSelected()` (`:789`), which returns early when `!s.selectedId`. `edit.cut` is enabled through `hasTarget`.

**What happens:** On a one-shape design with nothing selected, Ctrl+X puts the shape on the clipboard and leaves it in place. There is no message (Ctrl+C at least says "Copied"). Ctrl+V then adds a second copy.

**Repro:** test "Ctrl+X on a one-shape design copies but doesn't remove".

**Fix:** In `copySelected`, remove `items` directly: `commit(items.reduce((l, it) => removeItem(l, it.id), currentLayout()))`, then `select(null)`. Owner decision: none.

### 8. Low · suspected (code reading): the sewing-order row drag misses the lost-mouse-up and unmount guards the other drags got
**Where:** `InfoPanel.tsx:822-861` `startDrag`.

**What happens:** Unlike PanelResizer and dragDialogs (fixed in phase 4), the row drag has no `ev.buttons === 0` check. A mouse-up the window never hears leaves the row following the pointer until the next click or Esc. The window listeners and the Esc hold are also not removed if the panel unmounts mid-drag (for example, Ctrl+N or Ctrl+O from the keyboard while dragging). In that case a later pointerup calls `moveItemTo(id, to)` on whatever design is open then, and setState runs on an unmounted component.

**Fix:** In `move`, `if (ev.buttons === 0) return drop()` (or `putBack`). Keep `end` in a ref and call `end(false)` from a `useEffect` cleanup. Owner decision: none.

### 9. Low · suspected: `removeSelected` drops the selection before knowing the delete worked
**Where:** `actions.ts:800-802` calls `void commit(l); s.select(null);`.

**What happens:** If the render fails (an engine error), the items stay on screen with the error, but nothing is selected any more, so the user must reselect before trying again. Other edits (duplicate, paste, merge) select only after `ok`.

**Fix:** `void commit(l).then((ok) => ok && …)`. The immediate deselect is there so the next Delete press doesn't act on stale ids. Keep that, and restore the selection on failure. Owner decision: none.

---

### Solid areas (checked, nothing new)
- **`escape.ts` holds:** every `holdEscape` call is released on unmount or end: ContextMenu, Menu, FontPicker (effect cleanup), PanelResizer (with stop), InfoPanel row drag (with end; see 8), StitchCanvas (`cancelDrag`, `onUp`, effect cleanup), satinFit (released when the pen moves on), autoTrace, autoAll, knife and stitch edit (store subscriptions). The stale `release` closures that remain after an Esc pop are harmless (`lastIndexOf` misses).
- **`keys.ts`:** fields (`input`/`select`/`textarea`) keep all their keys. Esc order is holds, then field, then commands. Esc auto-repeat is ignored. Modal dialogs block everything (all dialogs use `showModal`). Space and Enter go to focus-visible buttons.
- **COMMANDS conflicts:** all shared keys checked. Esc×8, Delete/Backspace×3 each, Enter×3, Tab/Shift+Tab×3, `[`/`]`×3, `1`/`2`, arrows (pan, then nudge, then player), C (pen kind, then satin tool), D/Shift+D, digits. The `enabled` conditions are mutually exclusive or deliberately ordered. No two commands without `enabled` share a key except the intentional `player.fasterAlt`/`slowerAlt` fallbacks at the end of the list.
- **StitchCanvas drags:** pointer identity, capture, blur, cancel, a second pointer and a lost pointer-up are all handled. A render during a drag re-places the ghost.
- **Render queue (`showHistory`/`runRender`), the open/edit race, `commitImages` while a render is pending, and no-op edits:** as fixed in phase 4. No regressions found.
- **Auto-trace `ask()` and whole-picture replies:** guarded by sequence counters and by checking the mode still exists. `setHistory` drops modes for removed pictures.

### Gaps
- Canvas behaviour (findings 1-2: which handler gets the click) was checked by reading `onDown`, not in a DOM. The state side was reproduced.
- No browser or Tauri run (no dev server, as instructed). Findings 8 and 9 are code reading only.
- Not checked in depth: TextPanel text-box races (the lettering owner's area in phase 4), and AltGr (Ctrl+Alt) letters on non-US layouts matching `Mod+Alt+…` shortcuts via the `e.code` fallback outside text fields. For example, German AltGr+M (µ) would add a monogram and AltGr+E (€) would start stitch editing. This doesn't matter for the owner's US keyboard, so it was not written up.
- Stitch-edit `selected` indices are not remapped after an undo that brings back deleted stitches. The highlight moves to other stitches, consistently with what Delete would remove, so it was not reported.

## QA pass 2: docs vs reality (area 9) and test quality (area 10)

Reviewer: docs/tests. Worktree `qa-pass-2-b93602` at e415eb3. Nothing in the repo was edited.
Already-known items (QA-REPORT, QA-RESPONSE, qa-phase4/*, BACKLOG, the PDF) were grepped and left out.

Runs: engine `CI=1 uv run --locked pytest -q`: **650 passed, 1 skipped** (the opt-in real AI model test).
UI `vitest run`: **40 files, 196 tests passed**. `pnpm typecheck`: clean (TypeScript 7).
`scripts/kb_commands.py` run against a copy of actions.ts + the knowledge base: 179 commands, **byte-identical output (a no-op)**.

---

### Medium

#### M1. The knowledge base says LUDD opens 47 formats; it opens 40 (7 listed extensions don't open)
- **Confirmed** (ran `design.formats()`).
- Where: `docs/LUDD-KNOWLEDGE-BASE.md:53` ("Opens (47 formats)" and the list), `docs/LUDD-KNOWLEDGE-BASE.md:219` ("47 formats (section 1)").
- What happens: the list includes `col`, `csv`, `edr`, `inf`, `json`, `gcode` and `pmv`. `design.formats()["read"]` returns 40 extensions, without those seven (`gcode` is in `HIDDEN_FORMATS`; the others are thread-color or non-embroidery categories that `formats()` filters out, so `open_design` refuses them). The manual (`USER-MANUAL.md:101`), README, release notes and in-app Help all correctly say 40. The help agent answers from the KB first ("Source of truth, in order: 1. this file"), so it will tell the owner LUDD opens CSV/JSON/G-code/.edr files.
- Should: the KB lists the same 40 the app opens.
- How to check: `cd engine && uv run python -c "from threadline_engine import design as d; print(len(d.formats()['read']), [e['ext'] for e in d.formats()['read']])"`.
- Fix: replace the list with the 40 from `formats()` and say 40 in both places. Optionally add a check to `knowledgeBase.test.ts`/test_helpdocs that the KB count equals `len(formats()['read'])`. No owner decision.

#### M2. Whole-picture auto-digitize has no UI test (the engine side is now well covered)
- **Confirmed** (grep of every `*.test.ts(x)`: no `digitizeWholePicture`, `acceptWholePicture`, `autoAll` or `autotrace.all`).
- Where: `apps/desktop/src/features.ts:94-147`.
- What: the known soft spot "whole-picture digitize (one test)" is fixed on the engine side (test_autotrace.py now has about 10 `digitize_all` tests: JPEG, transparent background, rings, ribbons, thin strokes, blank picture). The UI flow has none: the `allSeq` guard that drops an older run's answer, the "dismissed while working" return, the empty-result message, the failure path clearing `autoAll`, and "Add all" being one undo step that keeps the preview if adding fails. These are exactly the stale-answer bugs earlier QA phases found elsewhere.
- How to check: grep above; the code at the lines above has no caller in tests.
- Fix: a `features.autoall.test.ts` with the fake engine used in `leftovers.qa.test.ts`: two overlapping calls (only the newest answer lands), dismiss during a call (nothing lands), empty result (message, `autoAll` null), accept (one Ctrl+Z removes all shapes). No owner decision.

---

### Low

#### L1. In-app Help still names the old "Threads" section for Color sets
- **Confirmed.**
- Where: `engine/threadline_engine/ai/helpdocs.py:107` ("Threads, Color sets: save and switch sets of colors.").
- What: the panel has no Threads section any more; Color sets is a fold inside **Order & colors** (`InfoPanel.tsx:1270`; manual section 9 "Colors (in Order & colors)"; Help line 62 itself says Order & colors "used to be Threads and Sewing order").
- Fix: "Order & colors → Color sets: …". Could add `"Threads, Color sets" not in g` to `test_help_says_what_the_app_does_now`. No owner decision.

#### L2. Manual's Browse designs paragraph contradicts the new Refresh button
- **Confirmed.**
- Where: `docs/USER-MANUAL.md:165-171`.
- What: line 165 says **Refresh** looks through the folder again for new, changed or removed designs; lines 170-171 (written before QA decision 17) still say "choose the folder again to see designs added since". The KB (F-207) was updated; the manual has both sentences.
- Fix: drop "; choose the folder again to see designs added since" (or say "press Refresh"). No owner decision.

#### L3. Knowledge base points the help agent at the wrong sections
- **Confirmed.**
- Where: `docs/LUDD-KNOWLEDGE-BASE.md:28` ("offer to write a change request (section 9)"; it is section 24, section 9 is Selecting and arranging), `:32` ("In the command registry (section 8)"; it is section 25, section 8 is Pictures and tracing), `:272` ("stitch-out tests are queued; see section 10"; section 10 is Shape operations, the queue is L-016 in section 20 / `docs/stitchout-log.md`).
- What: sections were renumbered when the KB grew; section 0 (the agent's own instructions) still has the old numbers. `LUDD-HELP-AGENT-INSTRUCTIONS.md:53` has the right one (24), so the impact is limited, but the KB is "source of truth #1".
- Fix: 9 → 24, 8 → 25, "section 10" → "L-016". No owner decision.

#### L4. KB change history files the QA fixes under 1.0.0 / Oct 11
- **Confirmed.**
- Where: `docs/LUDD-KNOWLEDGE-BASE.md:841` ("2026-10-11 | 1.0.0 release; … QA review fixes (phases 1–4)").
- What: the QA report is dated 2026-10-12 (`QA-REPORT.md:3`), the CHANGELOG puts all four QA phases under 1.0.1 (`CHANGELOG.md:113-230`), and phase 4 landed in the 2026-11-14 commits. A help agent told "fixed in 1.0.0" will tell the owner an old 1.0.0 installer has fixes it doesn't.
- Fix: move "QA review fixes (phases 1–4)" to its own row(s) dated when they landed, version 1.0.1. No owner decision.

#### L5. Leftover UK spelling and old UI labels after the US-spelling decision (grouped)
- **Confirmed.** QA decision 15 made the app labels, docs and Help US; these were missed:
  - `docs/USER-MANUAL.md:229` and `:1008`, `engine/threadline_engine/ai/helpdocs.py:74`: "full stop" (US: "period").
  - `docs/USER-GUIDE.md:109`: "drag LUDD from Applications to the Bin" (macOS calls it the Trash).
  - `docs/LUDD-KNOWLEDGE-BASE.md:111, 175, 451` "recolour", `:453, 614` "multicolour", `:715, 839` "neighbours".
  - `docs/LUDD-HELP-AGENT-INSTRUCTIONS.md:15, 24, 91-94`: "colour(s)", "behaviour".
  - `docs/CHANGELOG.md` 1.0.1 section (unreleased, so it becomes the release notes): names labels that no longer exist, "Centre in the hoop" (`:31`) and "Settings → About → Licences…" (`:184`), plus about 20 "colour/centre/licence" spellings in prose.
- Fix: search-and-replace in those files; for the CHANGELOG at least the two UI label names. Whether to rewrite historical changelog prose is the owner's call (owner decision only for that part).

#### L6. CHANGELOG doesn't mention the Nov 15 dependency upgrades, and the jsdom note is incomplete
- **Confirmed** (`git log`, `git show aba3b02 e415eb3`).
- Where: `docs/CHANGELOG.md:5-13`; `BACKLOG.md:249`.
- What: after the last CHANGELOG edit (ed160f1), commits aba3b02/e415eb3/86344ce/c5bf802 moved the shipped app to `tauri-plugin-updater ~2.14`, `tauri-plugin-shell ~2.6`, `@tauri-apps/api 2.12`, PixiJS 8.23, React 19.3, Zustand 5.1, and the toolchain to TypeScript 7, vitest 5, jsdom 31; 320267c/46b0de4 fixed CI. None is in the CHANGELOG or the KB history. The updater and shell plugins are in the installed app (update install, Finder/Explorer open), so this matters for the next release's "what to check". Separately, CHANGELOG:12 and BACKLOG:249 say naming a file `*.dom.test.tsx` gives jsdom; in fact `vite.config.ts` sets `environment: "node"` and only the file's first line `// @vitest-environment jsdom` switches it (as `AIPanels.dom.test.tsx:1-4` says).
- Fix: a "Behind the scenes" bullet listing the upgrades and a note to check updater install and Show-in-folder in the installed app; add "and start it with `// @vitest-environment jsdom`". No owner decision.

#### L7. The Help/manual shortcut test can't catch a key documented for the wrong command, and skips most keys
- **Confirmed** (ran the test's regex).
- Where: `engine/tests/test_helpdocs.py:14` (`KEY`), `:17-22`, `:28-40`.
- What: the test only checks that each `Ctrl/Shift/Alt+…` combination in Help and the manual exists **somewhere** in COMMANDS. `KEY.findall("Knife (Ctrl+M). Rename F2. Select V. Next guess Shift+Tab, use Shift+Enter. Nudge Ctrl+ArrowLeft.")` returns only `['Ctrl+M']`, which passes because Ctrl+M is registered (to Merge). Bare keys (V, L, C, K, O, I, F2, Delete, Space, [ ]), Shift+Tab, Shift+Enter, arrow combos are never checked, and a key written next to the wrong action passes. (I cross-checked every documented combination by hand with a script: all are currently bound to the action the docs describe, so this is a guard gap, not a live bug.)
- Fix: check the manual's shortcut tables row by row: parse `| Do this | Press |`, map each key to the registered command(s) and assert at least one title shares a key word with "Do this" (or keep a small id map per row); extend `KEY` to Tab/Enter/F-keys/arrows. No owner decision.

#### L8. The knowledge-base test passes when a command is removed or renamed
- **Confirmed** (read).
- Where: `apps/desktop/src/knowledgeBase.test.ts:11-14`; `scripts/kb_commands.py:24-28`.
- What: the test only asserts every **current** command has a `` | `shortcut` | `id` | `` row. A removed or re-keyed command's old row stays in the KB (the agent keeps offering it) and a changed title is never compared. `kb_commands.py` also hard-codes the titles of the templated commands (e.g. "Trim jumps longer than 3 mm"), so changing that title in actions.ts leaves the KB stale with a green test. (The `.replace(/\|/g, "\|")` on line 12 is a no-op: `"\|"` is just `"|"`; harmless today because no shortcut contains `|`.)
- Fix: have the test rebuild the table the way `kb_commands.py` does (or call it with an output-to-stdout flag in CI) and compare the whole block, so any drift fails. No owner decision.

#### L9. Nothing checks that the five version numbers agree
- **Confirmed** (grep of tests and workflows).
- Where: versions in `apps/desktop/package.json:5`, `src-tauri/tauri.conf.json:5`, `src-tauri/Cargo.toml:3`, `engine/pyproject.toml:3`, `engine/threadline_engine/__init__.py:1` (all 1.0.1 today, plus Cargo.lock/uv.lock).
- What: release.yml only compares the tag with tauri.conf.json, and knowledgeBase.test.ts only the KB with tauri.conf.json. RELEASING.md step 1 lists the files by hand; a missed one (e.g. the engine's `__version__`, shown in the status bar and Settings) would ship silently.
- Fix: a small vitest or pytest that reads all five (and the lockfiles' own entries) and asserts one value. No owner decision.

#### L10. Guides snapping and the garment preview have no tests; guides/colorways persistence isn't tested
- **Confirmed** (grep), persistence **confirmed working** by a scratch script (`project.save` then `open_project` kept `layout.guides` and `layout.colorways`).
- Where: guide snapping is an inline closure in `apps/desktop/src/components/StitchCanvas.tsx:1437-1460` (not reachable from a unit test); garment preview `apps/desktop/src/design/garments.ts`, store `preview`; persistence `engine/threadline_engine/project.py` (no test mentions `guides` or `colorways`).
- What: the soft spot "colorways/preview/guides (no tests)" is partly fixed: `features.colorways.test.ts` covers color sets and set/clear/undo of guides. Still untested: points snapping onto a guide (and the guide winning over Snap to grid on its axis, as the manual promises at `USER-MANUAL.md:213-214`), the garment preview, and guides/colorways surviving save and reopen. Also the comment at `StitchCanvas.tsx:1435-1436` says "holding Shift snaps to the grid"; the code uses the Shift+G toggle (`st.snapGrid`).
- Fix: move `snapped` into a pure function in `design/grid.ts` (guides, grid step, points) and test it; add a project round-trip test with guides and colorways. Fix the comment. No owner decision.

---

### Solid (checked, no problem found)
- `scripts/kb_commands.py` regenerates an identical command table (no-op), 179 rows.
- Versions agree at 1.0.1 in package.json, tauri.conf.json, Cargo.toml (+ Cargo.lock), pyproject.toml (+ uv.lock), `__init__.py`, the KB and the CHANGELOG heading; only tag v1.0.0 exists.
- Every Ctrl/Shift/Alt shortcut in the manual, Help and KB maps to the command the text describes (script over the registry); every row of the manual's shortcut tables, bare keys included, checked by hand against COMMANDS.
- Manual `⋯ →` paths all exist in `Toolbar.tsx`; Settings sections (Look, My machine, Measurements, Workspace, AI tracing, AI add-on, Updates, About/Licenses) match `SettingsDialog.tsx`/`AISettings.tsx`; status text "Engine disconnected" and the `Flower.ludd` sample exist.
- Limits match code: pictures 40 MB / 120 MP, Browse 600, font list 200, kept copies 90 days, ribbon width 1-12 mm, angle 0-179, random 0-50%, speeds 2-5,000 with machine speed 12, satin-fill split from 6.5 mm, small text 6 mm, Ollama model `qwen2.5vl:7b`.
- No dead internal links or anchors in USER-MANUAL, USER-GUIDE or the KB; every F-/L-/T- ID referenced in the KB is defined.
- No user-facing "Threadline" left (only the intended "formerly Threadline" notes); no UK spelling left in UI strings.
- Tests: no `or True`, bare `except`, always-true skips or `.only`/`.skip` in either suite; snapshot tests fail on a missing entry under `CI` (GitHub sets it); golden PES/JEF tests run on committed samples and pin the PES top-left placement; knife/merge/offset now have UI tests (`leftovers.qa.test.ts`).

### Gaps (not checked, and why)
- Did not run the app or browser preview (docs/tests scope); manual claims were checked against code, not clicked through.
- Did not read every manual paragraph against behaviour; spot-checked shortcuts, menus, settings, limits and the sections changed by the QA decisions.
- `test_rpc.py:257-260` skips the whole every-method dispatcher test if no outline font is installed; did not check whether a CI runner (Linux) can hit that (it didn't skip on Windows).

### Top fixes first
1. M1: correct the KB format list to the real 40.
2. M2: UI tests for whole-picture digitize (stale answers, dismiss, one-undo accept).
3. L1 + L2 + L3: three stale sentences/refs the help agent and Help will repeat.
4. L7 + L8: make the doc-shortcut and KB tests fail on wrong-action and stale rows.
5. L6: log the Nov 15 dependency upgrades and check the updater in the installed app before the next release.

