# LUDD knowledge base

<!--
For machines first, people second. This file is the single source a LUDD help agent answers from.
Kept up to date by the developer (Claude Code in the LUDD repository) with every user-visible
change, in the same commit as docs/CHANGELOG.md. Never edited by the help agent.
-->

| Key | Value |
| --- | --- |
| Product | **LUDD** (formerly *Threadline*), free embroidery digitizing software |
| Version described | **1.0.1** (in development; installers built from the working copy) |
| Last updated | **2026-11-24** |
| Owner | One hobbyist user (the person asking questions), with a **Brother PE550D** (4" × 4" hoop) |
| Source of truth, in order | 1. this file · 2. `docs/USER-MANUAL.md` · 3. `docs/CHANGELOG.md` · 4. the app's own Help (F1) |
| Developer | Claude Code, in the LUDD repository chat. The help agent never changes code or files. |

---

## 0. How to read this file (instructions for the agent)

- Every feature has an **ID** (`F-…`), every known gap an ID (`L-…`), and every troubleshooting
  entry an ID (`T-…`). Quote IDs when you answer, so the developer can find them.
- **Status words** used everywhere:
  - **YES**: LUDD does this today. Say how (where it is, the keys, the steps).
  - **PARTIAL**: it does some of it. Say what it does, what it doesn't, and the workaround.
  - **NO**: it doesn't. Say so plainly, give any workaround, and offer to write a change request
    (section 24).
  - **FIXED**: was a bug, fixed in the version noted. If the person still sees it, they may be on an
    older installer, or have an old file (see the entry).
- Keyboard keys are written for **Windows**: `Ctrl` (⌘ on a Mac), `Alt` (⌥ Option on a Mac).
  In the command registry (section 25) `Mod` means Ctrl / ⌘.
- UI paths are written `Place → Place → Thing`. "The panel" is the right-hand panel; "the rail"
  is the tool rail on the left; "⋯" is the toolbar's More menu (top right) unless it says "the
  panel's ⋯" (the menu at the top of the panel, for what's selected).
- If something isn't in this file, say you're not sure, say what the closest feature is, and
  suggest checking the app (F1 Help) or asking the developer. Don't invent features or keys.

---

## 1. Product facts

| Fact | Detail |
| --- | --- |
| What it is | Desktop embroidery software: open, convert and edit stitch files; draw your own designs (digitize); lettering; trace pictures; save for the machine. |
| Platforms | Windows 10/11 64-bit (the owner's), macOS 14+ (Apple chip and Intel), Linux (glibc 2.35+, AppImage or .deb). AI tracing isn't available on Intel Macs. |
| Price / account | Free. No account, no sign-in. Works **offline**; the core makes **no network calls**. |
| Network use (only these) | Update check (asks GitHub at start-up, only if allowed on the welcome card or in Settings); one-time AI tracing model download (asks first); the optional AI add-on in Cloud mode (shows what will be sent first). |
| License | GPL-3.0-or-later. Settings → About → Licenses… lists the free software and fonts it uses. |
| Brand | Name LUDD; colors ink #121114, bone #EEE9DF, techno yellow #C8FF2E. Light and dark mode. |
| Units | Inches or millimeters (U, or Settings). Inside, LUDD works in millimeters. |
| Machines built in | **Brother PE550D** (hoop 4" × 4", 10 × 10 cm; saves PES; cuts the thread only at color changes). **Janome (generic)** (hoops SQ14 14 × 14 cm, A 12.6 × 11 cm, RE20b 14 × 20 cm, SQ20b 20 × 20 cm; saves JEF). More machines can be added as JSON profiles in the data folder's `machines` folder (advanced). |
| Opens (40 formats) | 100, 10o, bro, dat, dsb, **dst**, dsz, emd, **exp**, exy, fxy, gt, hus, inb, **jef**, jpx, ksm, max, mit, new, pcd, pcm, pcq, pcs, **pec**, **pes**, phb, phc, sew, shv, spx, stc, stx, tap, tbf, u01, **vp3**, **xxx**, zhs, zxy, plus LUDD projects (`.ludd`, and old `.thl`). |
| Saves for machines (9 formats) | **PES** (Brother, primary), **JEF** (Janome), DST, EXP, PEC, TBF, U01, VP3, XXX. |
| Can't open | Embrilliance working files (`.be`, `.bt`): they're a closed format. Open the PES/JEF Embrilliance saved, or recreate. See L-012. |
| Project file | `.ludd`: everything embedded (shapes, lettering, placed designs, traced pictures, the lettering's fonts). Old `.thl` projects and `.tlfont` stitch fonts still open. |
| Data folder (Windows) | `%APPDATA%\Ludd` (older installs: the old `Threadline` folder still works). Holds threads, settings, `fonts` (stitch fonts), `recovery`, `project-files` (private copies of added pictures/designs; unused 90 days → deleted), `machines` (extra machine profiles). |
| Installer location (developer builds) | `C:\Users\Copper Felix\HTML Stuffs\threadline\apps\desktop\src-tauri\target\release\bundle\nsis\LUDD_<version>_x64-setup.exe` |
| Releases | GitHub `jvanekel-pixel/ludd` → Releases. Installers aren't code-signed yet (Windows SmartScreen / macOS Gatekeeper warning; see T-001). |
| Shortcuts | Embrilliance's keys wherever Embrilliance has one. Every menu item and button tooltip shows its key. |

---

## 2. Quick capability index

One line per common question. Status, then where to read more.

| Question: "Can LUDD…" | Status | See |
| --- | --- | --- |
| open PES / JEF / DST / VP3 / EXP / XXX files? | YES | F-201 |
| open Embrilliance `.be` / `.bt` files? | NO | L-012 |
| save PES for my Brother PE550D? | YES | F-301 |
| save JEF for Janome? | YES | F-301 |
| send the design to the machine directly (USB cable / Wi-Fi)? | NO (save to a USB stick) | L-010 |
| cut jump threads on a machine that only cuts at color changes (PE550D)? | YES (cut-stops) | F-302 |
| hide jumps under later stitching (no jump, no trim)? | YES | F-1803 |
| choose where each piece starts and ends automatically for fewer jumps? | YES (Optimize jumps) | F-1805 |
| reorder for the shortest moves? | YES | F-1804 |
| set the start and stop point of a shape myself? | YES (green/red dots) | F-701 |
| set the start/stop of each letter in lettering? | YES | F-1405 |
| set the stitch direction by dragging on the design? | YES (purple dots) for fills and satin columns/fills | F-702 |
| set the stitch angle by typing / drawing a line? | YES | F-1302, F-603 |
| draw running-stitch lines, satins, fills? | YES | F-501 |
| add ready-made shapes (rectangle, rounded rectangle, circle, oval, triangle, polygon, star, heart)? | YES | F-501 |
| triple / bean / motif lines (blanket stitch, scallop…)? | YES | F-1306 |
| fill a shape with one shape-shifting satin (petals, leaves)? | YES (satin fill) | F-1308 |
| satin columns that start/stop anywhere along them? | YES | F-701 |
| fill patterns: gradient, wave, contour, stipple, cross-stitch, spiral? | YES | F-1305 |
| a two-color gradient / color blend? | NO (one-color density gradient only) | L-001 |
| cut holes in a fill, or cut shapes out of a fill? | YES | F-1202, F-1203 |
| knife a shape in two / merge fills? | YES | F-1204 |
| outline / offset around things? | YES | F-1205 |
| add a satin border to a fill? | YES (Shift+B) | F-1206 |
| applique (placement, tack-down, satin; cut file)? | YES | F-1501 |
| lettering with installed fonts? | YES | F-1401 |
| multi-line text in one text object? | NO (one line per text) | L-003 |
| text on an arch / circle / my own line? | YES | F-1403 |
| monograms? | YES | F-1404 |
| one machine file per name from a list? | YES | F-1406 |
| turn lettering into ordinary shapes? | YES (Break into shapes) | F-1407 |
| change a letter's stitch angle without breaking it apart? | NO | L-005 |
| reset all letters' starts and ends? | YES (`Ctrl+Alt+R`) | F-1405 |
| put a recolored color back to the original? | YES (Back to …, or Put back the original colors) | F-1601, F-1607 |
| trace a picture automatically? | YES (Auto-trace) | F-901 |
| turn a whole picture into a design in one go? | YES (Auto-digitize) | F-1001 |
| use AI to trace photos? | YES, optional, offline | F-904 |
| get stitch advice from AI? | YES, optional (Stitch Advisor) | F-2002 |
| photo stitch / portrait from a photo? | NO | L-008 |
| edit individual stitches of a bought design? | YES | F-1901 |
| change a bought design's stitch types (e.g. fill to satin)? | NO | L-007 |
| resize a bought design? | PARTIAL (±20% advised) | F-1104 |
| recolor threads, match to real thread brands? | YES | F-1601, F-1603 |
| search threads by color code (#hex)? | YES | F-1602 |
| keep my own spools (My threads)? | YES | F-1604 |
| change many items' color at once? | YES (select them, change one) | F-1105, F-1601 |
| save color versions (colorways)? | YES (Color sets) | F-1605 |
| preview on a T-shirt / towel / cap? | YES | F-1606 |
| sort colors to fewest thread changes? | YES | F-1607 |
| group things and move them together? | YES | F-1103 |
| undo / redo? | YES | F-103 |
| undo the last point while drawing (Ctrl+Z)? | YES (removes the last point, like Backspace) | F-103, F-502 |
| keep my edits on a stitch file that I later change in another program? | YES (sews LUDD's copy; the change isn't picked up) | F-1901, L-025 |
| autosave / crash recovery? | YES | F-203 |
| split a design too big for the hoop? | YES | F-303 |
| basting box / knockdown stitches? | YES | F-1801, F-1802 |
| insert a stop or trim at a point? | YES | F-1806 |
| print a template? | YES | F-205 |
| batch convert a folder? | YES | F-206 |
| browse a folder of designs as pictures? | YES | F-207 |
| density map / quality checks before stitching? | YES | F-1702, F-1703 |
| adjust for fabric (towel, knit, fleece…)? | YES | F-1701 |
| watch a simulated stitch-out? | YES | F-404 |
| see realistic 3D thread? | YES | F-402 |
| rulers, guides, grid, snap, measure? | YES | F-403, F-405 |
| tell me how long a design takes to sew, and how much thread it uses? | YES (estimate) | F-406 |
| right-click menus? | YES | F-104 |
| dark mode? | YES | F-2101 |
| work on a Mac / Linux? | YES | section 1 |
| use without internet? | YES | section 1 |
| stitch fonts I can fine-tune? | YES (`.luddfont`) | F-1408 |
| import a thread chart (CSV)? | YES | F-1604 |
| design for a bigger hoop than 4"×4"? | YES (pick a Janome hoop, or split) | F-303, section 1 |
| add my own machine? | PARTIAL (JSON file, advanced) | section 1 |
| freehand / pen tablet drawing? | PARTIAL (mouse or pen clicks; no freehand brush) | L-011 |
| 3D puff, sequins, chenille, cutwork? | NO | L-009 |

---

## 3. The screen

### F-101 Layout of the window — YES
- **Toolbar** (top): New, Open, Save, Add design, Undo/Redo, **Save for machine** (yellow), machine
  and hoop picker, **?** Help, **⚙** Settings, **⋯** More (files, machine extras, views).
- **Tool rail** (left): Select, Line, Satin, Fill, Text, Auto-trace, Shapes, Picture; each tool's
  key printed under it.
- **Design area** (middle): fabric, hoop outline, grid, rulers.
- **Panel** (right): folding sections (F-102). Drag its left edge to resize; double-click the edge
  to reset.
- **Stitch-out bar** (bottom) and **status bar** (engine connected, version, Restart engine).
- Messages show in a strip under the toolbar (× closes; most close by themselves).
- Dialogs can be dragged by their title; Esc while dragging puts the dialog back. Dialogs scroll
  with the mouse wheel when the window is short (fixed in 1.0.1: Settings' bottom was unreachable).

### F-102 The panel (folding sections) — YES
- Top, always in view: the selection's name and quick buttons (turn ⟲ ⟳, mirror ⇋, duplicate ⧉,
  **⋯** = the panel's menu: Repeat, mirror top-bottom, Pin, Rename, Outline/offset, Knife, Edit
  stitches, Remove). With several selected: "N selected", Group/Ungroup, 🧵 Thread (one thread for
  all), turn, mirror, duplicate, ⋯.
- Then the selection's own section (**Fill / Satin / Line / Applique / Lettering / Stitch file /
  Picture**) with everyday settings in view and small folds inside (Underlay, Advanced stitch
  settings, lettering Shape and Advanced, a stitch file's Rotation and position).
- Then **Size and points**, **Design** (size, stitches, hoop fit, fabric, File details),
  **Order & colors**, **Check before stitching**, **Pictures**.
- Nothing selected: Design and Order & colors open. Open/closed is remembered per kind of
  selection. Ctrl+click a heading = open only that one; Alt+click = open/close everything inside.

### F-103 Undo, redo, Esc — YES
- Undo `Ctrl+Z`, redo `Ctrl+Y` or `Ctrl+Shift+Z`. Most actions are one undo step (a whole drag,
  a whole "Add all", a batch recolor).
- **While drawing a shape**, `Ctrl+Z` removes the last point placed (like `Backspace`) and leaves the
  earlier work alone; `Ctrl+Y` does nothing until the shape is finished or cancelled (changed
  2026-11-24; before, Ctrl+Z threw the half-drawn shape away *and* undid the edit before it).
- **Esc lets go of one thing per press, newest first**: a drag (it goes back), an open menu or list,
  a value being typed (old value back), a half-drawn shape (even one point), measuring, the drawing
  tool (back to Select), a selected point, the selection, playback.
- Note: the owner's physical Esc key was faulty once (remapped 2026-10-12). If "Esc does nothing",
  check the key first (T-006).

### F-104 Right-click menus — YES (added 1.0.1)
- Right-click anything: a menu of what you can do with it, each with its shortcut. Right-clicking
  selects the thing first.
- **A shape**: Change thread…, Cut, Copy, Paste, Duplicate, Remove, Add points, Cut a hole, Set the
  stitch angle, Knife, Turn a satin fill another way (satins), Add a satin border, Outline/offset,
  Sew first/earlier/later/last, Rotate, Mirror, Center in the hoop, Repeat, Pin, Rename, Zoom to it,
  Stitch Advisor.
- **Several shapes**: also Group, Ungroup, Merge, Cut out, Put the text on the line.
- **Lettering**: Change the words, One file per name, Break into shapes. **Stitch file**: Edit
  stitches.
- **Picture**: Auto-trace, Auto-digitize the whole picture, Pin/unpin (finds a pinned picture too),
  See-through stitches, Show pictures, Remove, Zoom.
- **Empty canvas**: Paste, Select everything, the drawing tools, the ready-made shapes (F-501), Add
  a picture, zoom, view toggles (ticked when on), Measure.
- **Panel rows**: a step or one of its colors in Order & colors; a picture in Pictures.
- While drawing, right-click still **finishes the shape**; in Auto-trace it **uses the guess**; on
  a shape's point it **switches the point type**. Arrow keys move in a menu, Enter picks, Esc closes.
- Text boxes keep the normal copy/paste right-click menu.

### F-105 The mouse pointer — YES
The pointer shows what a click does: arrow (nothing), arrow + move badge (select/move), arrow +
point badge (drag a point / a dot), diagonal and side arrows (resize/stretch handles, pointing the
way they pull), circular arrow (turn), double arrow on a line (guide), hand (Space held), crosshair
+ badge (a tool in use; center is where the click lands; its mark shows curve/corner/straight
point), wand (Auto-trace), spinner (working).

### F-106 Tools stay chosen — YES (1.0.1)
After a shape, an Auto-trace guess, a hole or a piece of text, the tool stays chosen so you can go
straight on. `V` or `Esc` goes back to Select. With the Text tool on, clicking an existing text
selects it instead of adding another. After Cut a hole (O) the previous tool comes back (Esc while
drawing the hole too). With a shape selected, arrow keys nudge it even while a drawing tool is chosen.

---

## 4. Files and projects (section 2 of the manual)

### F-201 Open designs — YES
`Ctrl+O`, or drag a file onto the window. 40 formats (section 1) and `.ludd` projects. A stitch
file opens **centered in the hoop** (many PES files start at a corner).

### F-202 Add another design — YES
`Ctrl+Shift+O` (or drag a file onto an open design): places another stitch file in the current
design, to combine designs.

### F-203 Projects, autosave and recovery — YES
- **Save** `Ctrl+S` → `.ludd` with everything embedded (pictures, placed designs, fonts). Moving or
  deleting the originals can't break it; opens the same on another PC even without the font.
- **Save project as** `Ctrl+Shift+S`.
- Opening a project uses its own machine and hoop for that project only.
- Autosave: a recovery copy a few seconds after each change. After a crash LUDD offers **Recover**
  or **Discard**. The window title shows • for unsaved changes; closing asks first.
- If antivirus/OneDrive holds the file, Save waits and retries.
- A damaged project opens without its damaged parts and says how many were left out (2026-11-24;
  T-016). Very large or hostile projects (over 64 pictures, over 768 MB unpacked) are refused.
- Added designs and pictures keep working after the engine restarts, even if the original is gone
  (fixed 2026-11-24).

### F-204 Samples — YES
`Ctrl+Shift+E` (⋯ → Open a sample design): five sample designs (three also as PES and JEF). They
open as new designs (Save asks where). The PES/JEF files were made again on 2026-11-24, so they sew
exactly like their projects do today (the 1.0.0 ones had drifted slightly).

### F-205 Print template & thread list — YES
`Ctrl+P`: real-size template with center lines, plus a thread list (stitch counts, tick boxes,
stabilizer). Print at 100% / Actual size; check the ruler bars.

### F-206 Batch convert a folder — YES
`Ctrl+B` (⋯ → Batch convert folder): every design in a folder to another format, into a
`converted` folder (or one you pick), optionally with subfolders and cut-stops. Never overwrites.

### F-207 Browse designs — YES
`Ctrl+Alt+B`: a folder of designs as thumbnails with size, stitches, colors; search by name; open
or **+ Add**. Shows the newest 600. **Refresh** looks through the folder again (new, changed or
removed designs).

### F-208 New design — YES
`Ctrl+N` or `Shift+D`: empty design on the fabric used last.

---

## 5. Saving for the machine

### F-301 Save for machine — YES
`Ctrl+E` (yellow button). Shows: fits the hoop or not, file type (PES Brother / JEF Janome; others
under More options), checks to look at, stabilizer advice. Never leaves a half-written file.
- **PES placement (FIXED 2026-10-13)**: PES files now put the design's top-left corner at (0, 0),
  as Embrilliance/PE-Design do; the PE550D centers them. Older LUDD PES files appeared shifted up
  and left, mostly off the hoop, and couldn't be moved: **save them again** (T-002).
- A PES holds at most 255 color steps (cut-stops count); LUDD warns before saving.

### F-302 Cut-stops: have the machine cut jump threads — YES
Save for machine → **Have the machine cut jump threads** (recommended for the PE550D, which only
cuts at color changes). Long jumps marked for trimming become stops in the same color: the machine
ties off and cuts; press Start at each stop, no thread change. More options: minimum jump length to
cut, lock stitches, **Also cut jumps the design doesn't mark for trimming**. Not yet confirmed on
the real machine for every case (stitch-out tests are queued; see L-016).

### F-303 Too big for the hoop — YES
- Up to ~5% too big: **Make it N% smaller** fits it in one hooping.
- Bigger: **Split it across hoopings** → one file per hooping ("name 1 of 2"…), each with pink
  alignment crosses, a map, adjustable overlap. Sew file 1, re-hoop so the needle lands on the
  crosses, sew file 2, pull the crosses out. Existing files are never replaced.

---

## 6. Looking at the design

### F-401 Zoom and pan — YES
Wheel zooms at the pointer; drag empty space or middle button to pan; **hold Space and drag** to
pan without grabbing anything (also mid-shape). While drawing, arrow keys move the view 1 cm and the
view scrolls at the edge. `A` all · `S` selection (everything selected, 2026-11-24; it was only
one item) · `0` hoop · `1` real size · `2`–`9` × real size · `+`/`-`.

### F-402 Views — YES
`T` realistic thread (lit, shaded, shadows; on by default) · `P` stitch points · `N` stitches
on/off (shows outlines) · `Shift+N` see-through stitches (also the ◐ button by the zoom) · `B`
pictures on/off · `J` trims/jumps/stops · `E` crosshairs · `G` grid · `H` hoop · `U` inches/mm ·
`Alt+D` density map. The design sits on light fabric in dark mode too (Settings can turn that off).

### F-403 Rulers and guides — YES
`Ctrl+R` rulers on/off. Drag from a ruler for a guide; drag a guide back onto a ruler to remove;
`Ctrl+Alt+G` removes all. Points snap to guides. Guides are saved in the project.

### F-404 Watch it stitch (stitch-out player) — YES
Space play/pause (tap), Home/End, Page Up/Down previous/next color, ←/→ one stitch (Shift: 100)
when nothing is selected, slider (marks = color changes), speed 2–5,000 stitches/s (`,`/`.` or
`[`/`]`; `Shift+,` machine speed ≈12/s). The step being sewn is marked in Order & colors.

### F-405 Measure — YES
`M`: click two points; shows distance and across/down. `M` or Esc puts it away. Starting it ends
the knife, stitch editing and the angle line (only one of these is on at a time, 2026-11-24).

### F-406 Sewing time and thread estimate — YES (added 2026-11-24)
Panel → **Design** shows **Sewing time** ("about 14 min + 4 thread changes") and **Thread** (top
thread, and the bobbin). **Thread used** (in the Design section) lists each color with about how
much it uses, to check there's enough on the spool. How it's worked out: stitches ÷ the machine's top
speed (PE550D and the generic Janome profile: 650 stitches a minute; a profile without
`speed_spm` is taken as 600); thread changes (color changes plus stops) are counted, not timed. Thread
is the length of every stitch and of every jump not cut by a trim, plus about 1 mm per stitch for
going into the fabric; the bobbin is about a third of that. Lengths follow Settings → Units (m or yd).
These are estimates: machines slow down on long stitches, and fabric and tension change thread use,
so allow a little extra of both. Not shown for an empty design.

---

## 7. Drawing your own (digitizing)

### F-501 Drawing tools — YES
| Tool | Key | Makes |
| --- | --- | --- |
| Select | `V` | pick, move, resize, turn |
| Line | `L` / `Shift+X` | running stitch |
| Satin | `C` | satin ribbon: click along the middle; width in the panel (1–12 mm) |
| Fill | `F` | tatami fill: click around the edge; closes itself |
| Text | `Shift+T` | lettering (click where it goes) |
| Auto-trace | `Shift+A` | traces a picture (F-901) |
| Shapes | menu | rectangle `Ctrl+Alt+1`, circle `Ctrl+Alt+2`, star `Ctrl+Alt+3`, rounded rectangle `Ctrl+Alt+4`, oval `Ctrl+Alt+5`, triangle `Ctrl+Alt+6`, polygon `Ctrl+Alt+7`, heart `Ctrl+Alt+8`, monogram `Ctrl+Alt+M`, holes |
| Picture | `Ctrl+I` | a picture to trace over |

**Ready-made shapes** (Shapes menu, the empty canvas's right-click menu, or the keys): each adds a
fill in the middle of the hoop, selected, up to 60 mm wide (smaller on a small hoop), with your fill
settings. **Polygon** asks how many sides (3 to 12; it starts at the number used last, 6 the first
time): Enter adds it, Esc cancels. The rounded rectangle and the oval are 0.7 as tall as wide, the
heart about 0.9; a triangle or polygon has a corner at the top. Then edit them like any fill (F-601).

Embrilliance create keys: `D` toggle drawing/Select, `X` last tool again, `Q` same kind as the last
shape, `W` the kind before that.

### F-502 Placing points — YES
Click = curve point · `Ctrl`+click = straight point · `Shift`+click = sharp corner · hold `Alt` =
15° steps · `Enter` / right-click / double-click = finish · `Ctrl`+right-click = finish and close
(loop) · `Backspace` or `Ctrl+Z` = remove last point · `C` while drawing = switch last point type · `Esc` =
cancel · `Shift+G` = snap to grid. Points near other shapes' points snap to them. Curve = circle,
straight = square, corner = diamond on screen.

### F-503 Satin borders that fit an edge — YES
Draw a satin along an existing shape's edge: after a couple of clicks LUDD offers **Tab fits the
satin**. Tab cycles: all the way round centered on the edge → just outside the edge → only between
your first and last click. Shift+Tab back, Enter keeps, Esc restores your clicks.

### F-601 Editing points — YES
Drag a point (thread fades while held) · right-click a point: curve → straight → corner ·
double-click the outline to add a point · double-click a point (or Delete) to remove it · `K` add
more points to the shape · a hole with fewer than 3 points is removed.

### F-602 Resize, stretch, turn handles — YES
Corner handles resize evenly; **side handles stretch one way** (opposite side stays put; appear
when the shape is big enough on screen); round handle turns (Shift = 15° steps). The pointer
shows the pull direction at every handle.

### F-603 Draw the angle — YES
`I` (or Fill section → Draw the angle): draw a line across a fill to set its row direction. It
ends if the fill is deleted or undone.

### F-701 Start and stop points (green and red dots) — YES (reworked 1.0.1, 2026-10-13)
Select a shape: a **green dot** marks where it starts sewing, a **red dot** where it stops. **Drag
either**: it slides along the shape's edge, following the edge point nearest the mouse (like a
magnet), and stays exactly where you let go.
| Shape | Where the dots can go |
| --- | --- |
| Fill | Start anywhere on the outside edge; stop anywhere on any edge (holes too). The rows are planned so the last one finishes there; moves between parts run under rows sewn later. |
| Closed line / satin border (ribbon loop) | Anywhere along it (start = stop). |
| Satin (ribbon, two-sided column, satin fill) | Start and stop **anywhere along it**. To stop part way, it's sewn in two parts meeting at the stop; moves run along its middle, under satin sewn later. A wide satin finishes on the side the dot is on. |
| Open running line | At its ends only: dragging a dot moves that end point; dropping it on the other end sews the line the other way round (L-004). |
| Lettering | Each letter has its own small dots (F-1405). |
| Applique, stitch files | No dots to move. |
| Contour fills | Start movable; the red end dot shows but can't be moved (the pattern decides). |
| Stipple / Cross-stitch / Spiral fills | The red end dot shows but can't be moved. The green dot can be dragged, but the pattern still starts at the same place (a Spiral always in the middle). |
- **Pinned** shapes show only their outline: points and dots can't be moved. With several things
  selected the dots aren't shown. A satin's start always lands on the satin (its nearest stitch).
- Knife / Cut out pieces get fresh dots each. Moving a satin's purple tips or Shift+W drops its old
  start and end. "Sew from the other end (reverse)" clears a fill's chosen end.
- Dots move, turn and resize with the shape. **Optimize jumps** (F-1805) replaces hand-set starts
  and ends with its own choices.
- History: 2026-10-12 first version (dots drew a line and landed elsewhere) → 2026-10-13 magnet
  dragging, exact fill ends; satins anywhere (before: satins only at their two ends).

### F-702 Stitch direction (purple dots) — YES (added 2026-10-13)
- **Fill**: two purple dots on the outline with a purple line between them = the direction of the
  rows. Drag either dot round the outline; the Angle setting follows. Typing an angle puts the line
  back across the middle. Not shown for Contour, Stipple and Spiral patterns (they have no angle).
- **Satin column / satin fill**: the purple dots sit just past each end and are the satin's
  **tips**. Slide them round the outline; the satin is rebuilt to run from one to the other, with
  stitches straight across between them. Tips too close together → message, nothing changes.
- **Satin ribbons** (drawn with the Satin tool): no purple dots; stitches always run straight
  across the ribbon (L-006).
- Lettering letters: no purple dots unless broken into shapes (L-005).

---

## 8. Pictures, tracing and auto-digitizing

### F-801 Pictures to trace over — YES
`Ctrl+I` (≤ 40 MB, ~120 MP). Panel → **Pictures**: list of pictures; the selected one's settings
open under its name: see-through slider, 📌 pin (can't move, clicks go through), hide, **Set real
size** (click two points, type the real distance). Pictures are embedded in the project.

### F-901 Auto-trace — YES
`Shift+A`, click inside a shape in the picture (or on a dark line for a satin ribbon; inside a
solid dark area for "Fill, this dark area").
- Tab / Shift+Tab: next / previous guess (simplified colors, to the middle of the outline, inside
  it, similar shades joined, everything inside the dark lines; for lines: to junctions / straight
  through). The kind you use most comes first next time.
- Shift+click adds an area, Alt+click cuts one out. **Spread** (`Alt+[` / `Alt+]`) and **Points
  every** (`[` / `]`), remembered.
- Use it: **Fill** (Enter / right-click), **Fill + satin border** (Shift+Enter), **Satin fill**,
  for lines **Satin** / **Line**. Esc / ✕ dismisses. Nothing is added until you choose.
- **Sees what you've made (1.0.1)**: a guess that runs over existing shapes comes "fitted around
  your shapes" (tucked 0.3 mm under); Tab offers the whole area "over your shapes". Clicking on one
  of your shapes traces that spot as is.
- Auto-trace stays on after using a guess; `V` to edit the new shape's points.
- Colors come from the picture; use Order & colors → Match… for real threads.

### F-904 AI tracing (optional) — YES
Settings → AI tracing → download MobileSAM (~45 MB, asks first; runs on this PC, nothing sent).
Its guesses come first ("AI guess", with confidence); Shift/Alt+click guide it; the **AI** tick box
in the bar turns it off per picture. The download is pinned to one fixed upstream version and each
file is checked against its SHA-256 before it is kept (a file that doesn't match is thrown away).
It's told about your nearby shapes so it stops at them.
"Forget which Auto-trace guesses I usually pick" resets the order. Not on Intel Macs.

### F-905 Trace Assist (older helper) — YES, off by default
`Ctrl+Shift+A` or Settings: a ghost next point while drawing over a picture; Tab takes it, Shift+Tab
keeps going to a corner, 1/2 pick a branch, `[`/`]` step length.

### F-1001 Auto-digitize the whole picture — YES
`Alt+A` (⋯, or Whole picture… in Auto-trace's bar): every color area → fill; solid dark areas →
fills (one per letter for bold lettering); dark lines → satin ribbons (thin ones running stitch);
near-equal colors merged; background left out (optional); big areas first, outlines last. Preview
first (seconds to a minute); **Add all** (Enter, one undo) or Dismiss (Esc). A picture placed
under 0.5 mm wide can't be traced ("too small to trace").

---

## 9. Selecting and arranging

### F-1101 Select — YES
Click; Shift/Ctrl+click adds/removes; `Ctrl+A` all; Esc or click empty space deselects.

### F-1102 Move, nudge, turn, mirror — YES
Drag; arrows 1 mm, Shift 1 cm, Ctrl 0.1 mm; `R` / `Shift+R` turn 90°; `Alt+H` / `Alt+V` mirror
(a fill's direction turns and mirrors with it); exact W/H in Size and points (🔒 keeps proportions);
**Center in the hoop** `Ctrl+Shift+M`.

### F-1103 Groups — YES (improved 1.0.1)
`Ctrl+G` group, `Ctrl+U` ungroup. Clicking any member (on the design or in the list) selects the
whole group. A picture underneath doesn't steal a drag inside the group's frame; Shift+click on
empty space keeps the selection. **Drag anywhere inside the group's frame** to move it, even between pieces (FIXED
2026-10-13: it used to grab the background). Grouped rows show ▣ in Order & colors.

### F-1104 Resizing stitch files — PARTIAL
Stitch files (bought designs) resize, but beyond about ±20% they sew too dense or sparse (stitches
aren't added or removed; LUDD warns). Drawn shapes and lettering re-stitch at any size.

### F-1105 Several selected — YES
They move, turn, resize, mirror, copy, cut, delete **and recolor** together; all are highlighted
in Order & colors; changing the thread of one (its ✎ / color square, the 🧵 button, right-click →
Change thread…, `Alt+T`) changes all (a multicolor stitch file keeps its colors, with a message).

### F-1106 Pin — YES
`Ctrl+L` or 📌 in lists: can't be dragged by accident; a pinned picture lets clicks through. A pinned
shape also ignores the arrow keys, `R`, `Alt+H` / `Alt+V` and the resize handles (a note says it's pinned;
unpin it first). A pinned picture ignores the arrow keys too.

### F-1107 Rename — YES
Double-click a name (list or panel top), `F2`, or ⋯ → Rename. Saved in the project.

### F-1108 Copy, paste, duplicate, repeat — YES
`Ctrl+C/X/V` (pasted down-right; with nothing selected they act on the only shape), `Ctrl+D`; **Repeat…** `Ctrl+Shift+D`: row/grid, circle
(carousel), mirrored ×4.

---

## 10. Shape operations

### F-1202 Cut a hole — YES
`O` (or ✂ Cut a hole in a fill's section, Shapes, ⋯): click round the hole, Enter. The tool you were
using comes back afterwards.

### F-1203 Cut out with a shape — YES
`Shift+O`: put a shape over a fill, select the fill and it, cut → hole, bite or pieces. The cutter
stays (Delete it if only for cutting).

### F-1204 Knife and merge — YES
Knife `Shift+K`: cut a fill, line or satin ribbon along a line (two clicks) into pieces with the
same settings. Merge `Ctrl+M`: two or more touching/overlapping fills → one. If you change or undo
the shapes while knife, merge, outline or Optimize jumps is working, LUDD drops its answer and says
"The design changed while …: try again" (2026-11-24).

### F-1205 Outline / offset — YES
`Ctrl+Shift+K`: a ring a set distance from the selection's stitches, sewn as satin border, line or
triple line; optional round holes; negative = inset.

### F-1206 Add a satin border — YES
`Shift+B` (or the fill's button): a closed satin ribbon along a fill's (or closed line's) edge, sewn
right after it.

---

## 11. Stitch types and settings (section 6 of the manual)

### F-1301 Stitch as — YES
Line · Satin · Fill · Applique. **Fill → Satin** makes a satin fill (F-1308). **Closed line → Satin**
also makes a satin fill (changed 2026-10-13; before it made a ribbon around the edge). **Open line →
Satin** makes a ribbon. **Satin fill → Fill** gives the outline back. Fill/Applique need a closed
shape.

### F-1302 Settings in view and in folds — YES
In view: thread, Stitch as, Style (lines), **Density** (Light/Normal/Dense + Lighter↔Denser slider
with the number under it, e.g. "0.40 mm between rows · 2.5 rows per mm", + exact Spacing), fill
**Angle** and Draw the angle, applique options. **Underlay** fold: underlay buttons. **Advanced
stitch settings** fold: spacing, length, random, edge pad, reverse, split, lock stitches, Stitch
Advisor. Settings carry over to the next shape of that kind (not a fill's angle); "Use the standard
settings for new fills" resets.

### F-1303 Settings table — YES
| Setting | Fill | Satin | Line |
| --- | --- | --- | --- |
| Underlay | Auto · Edge · Cross-hatch | Auto · Center · Edge · Zigzag | – |
| Density | ✓ | ✓ | – |
| Angle (0–179°) | ✓ | – | – |
| Length | ✓ (≤ 7 mm) | – | ✓ |
| Random 0–50% | ✓ | – | – |
| Edge pad (pull compensation, Auto from fabric) | ✓ | ✓ | – |
| Reverse | ✓ | – | – |
| Split long stitches | – | ✓ | – |
| Style (Single, Triple, Bean, Motif) | – | – | ✓ |
| Lock stitches | ✓ | ✓ | ✓ |

### F-1305 Fill patterns — YES
Tatami (standard rows) · **Gradient** (dense → sparse; one color; "Sparse end" spacing; Angle sets
the fade direction) · **Wave** (height, length) · **Contour** (rings inward) · **Stipple** (one
meandering never-crossing line; loop size) · **Cross-stitch** (square size) · **Spiral** (one line
winding from the middle of the shape out to its edge, F-701). Contour/Stipple/Cross/Spiral skip the
cross-hatch underlay; Gradient keeps only its edge run.

**Spiral** settings: **Ring spacing** (how far apart the turns are) 0.4–6 mm, default 1.5; stitch
**Length** up to 4 mm (the turns near the middle get shorter stitches). No Angle, Density, Random or
Edge pad. With Underlay on Auto it has no underlay; you can still choose Edge, and the thread then
runs from the edge back to the middle before the spiral. Rings closer than 0.6 mm get a warning
that they can pucker. It starts in the middle of the widest part of the shape (a rectangle's
center; of several equally wide parts, such as the corners round a square hole, the top-left one). Where the shape cuts the spiral into pieces, LUDD sews the nearest piece next, from
whichever end is closer, and joins them along the edge (the outline or a hole's rim), so nothing
runs across the rings and only a light outline shows on most shapes (L-026). The sew simulator
shows the outer pieces being sewn area by area, not strictly from the middle out. A project with a
Spiral fill needs this version of LUDD or newer to open.

### F-1306 Line styles and motifs — YES
Single, Triple (three passes), Bean (each stitch three times), **Motif**: Wave, Zigzag, Scallop,
Blanket stitch, with Repeat length and Width.

### F-1307 Satin ribbons — YES
Draw like a line along the middle; width 1–12 mm (new ones start at the last width); Ctrl+right-click
closes a loop. Warnings: wider than ~7 mm without Split, narrower than ~1 mm, folding on tight
curves, crossing sides, too short. With **Split long stitches** on, no stitch is longer than the
Longest setting, sharp corners included (an extra needle point goes on the outer edge there; since
2026-11-24). The **zigzag underlay** sews out and back in an X (since 2026-11-24; on about half of
wide satins it used to sew the same zigzag twice).

### F-1308 Satin fill (shape-shifting satin) — YES
A closed shape set to Satin (or Auto-trace → Satin fill) becomes **one satin column** that turns and
changes width with the shape (petals, leaves, swooshes; "Portrait of a Rose" style). LUDD finds two
tips and splits the outline into two sides. **Shift+W** (↻ Turn the stitches another way) cycles
other tips; **purple dots** set the tips by hand (F-702). Wider than ~6.5 mm turns on Split long
stitches. Shapes with holes stay fills (L-013).

---

## 12. Lettering (section 7 of the manual)

### F-1401 Text — YES
`Shift+T`, click where it goes, type in the panel (one line; a line break becomes a space). Any
installed font (search; 200 shown at a time) or a `.luddfont` stitch font. Letter height = capital
H, 2–200 mm. Thread. **Satin look** or **Fill**. Letters under ~6 mm warn. Fonts are embedded in
the project; a missing font shows as Arial with a warning.

### F-1402 How letters are stitched — YES (stated in the panel since 2026-10-13)
- **Satin look**: each letter is a fill of long, smooth satin-like stitches across its strokes, at
  the single angle that crosses them best. They are **not** true satin columns.
- **Fill**: each letter is an ordinary woven (tatami) fill.
- **Stitch fonts**: each letter sews the stitches the font was made with.

### F-1403 Shapes and text on a line — YES
Shape: Straight, Arch, Smile, Circle (with curve size). **Text on your own line**: draw a Line,
select it and the text, ⋯ → Put the text on the line (`Ctrl+Alt+L`); the line is used up.

### F-1404 Monogram — YES
`Ctrl+Alt+M` or the Monogram tick box: three initials, bigger middle one.

### F-1405 Each letter's start and end — YES (added 2026-10-13)
With lettering selected, every letter shows small green (start) and red (end) dots. By default each
letter starts by where the one before ended and ends towards the next (short jumps; on a test word
the trims between letters went from 2 to 0). Drag a dot along the letter's edge to move it.
**Reset starts and ends** (Lettering panel, right-click, `Ctrl+Alt+R`) puts them back. Changing the
words, font, size, spacing, look or shape resets them (clicking the look/shape already chosen
doesn't); so do Put the text on a line and One file per name. Hand-overs apply to filled letters
(Satin look and Fill); stitch-font satin strokes are left to sew end to end.

### F-1406 One file per name — YES
`Ctrl+Alt+N`: a list of names → one machine file each (Emma.pes…), prepared like Save for machine;
never overwrites; warns about names too wide for the hoop.

### F-1407 Break into shapes — YES (added 2026-10-13)
`Ctrl+Alt+X`, Lettering panel → Break into shapes…, or right-click: the letters become ordinary
grouped shapes in place (in the lettering's own group if it had one; pinned if it was), keeping
their starts and ends. Then each letter has every shape tool (points, stitch type, density,
direction dots). Stops/trims added to the lettering are left out (a message says so). The words
can't be retyped afterwards (Ctrl+Z undoes).

### F-1408 Stitch fonts — YES
Lettering → Advanced → **Save this font as a stitch font**: a `.luddfont` in the data folder's
`fonts` folder (shows in the font list as "stitch font"); edit it in a text editor to fine-tune.
Missing letters fall back to the other case or the unaccented letter.

### F-1409 Change the words — YES
`Ctrl+Alt+W` puts the cursor in the selected lettering's text box.

---

## 13. Applique

### F-1501 Applique — YES
Stitch as → Applique on a closed shape: placement line → stop → tack-down (zigzag or straight) →
stop → satin border (width/density adjustable; split if wider than 7 mm, sharp corners included).
Holes get all three too. A move of more than 3 mm from one edge to the next (holes, separate pieces)
is marked for trimming, as in fills (since 2026-11-24; with cut-stops on, that can add stops).
**Save cut file (SVG)** `Ctrl+Shift+U` for Cricut / ScanNCut / Silhouette. "Sew a placement line
first" can be unticked.

---

## 14. Threads and colors

### F-1601 Order & colors (one section; was "Threads" + "Sewing order") — YES (merged 2026-10-13)
Every design, shape and lettering as a row in sewing order: drag the grip ⠿ to reorder (Esc puts it
back), ↑ ↓ one step; click a name to select, Shift/Ctrl+click to add; selected rows highlighted;
**color square or ✎ changes the thread** (all selected, if several); 📌 pin; ▣ = grouped.
Multicolour stitch files list their colors underneath, numbered as the machine shows them, each with
✎ and 🗑 (remove that color's stitches) and "was …" for changed colors (**Back to …** in its
picker or right-click menu restores the original). **Palette** at the top:
each thread once; click to change it everywhere. Basting and knockdown listed first. Match…, color
options and Color sets are here. Right-click a row for its menu. `Ctrl+[` / `Ctrl+]` sew
earlier/later, `Ctrl+Shift+[` / `]` first/last.

### F-1602 Changing a thread — YES
✎ / color square / right-click → Change thread… / `Alt+T`: thread list of the chosen chart, closest
matches first, current color's code shown. **Search by number, name or color code** (`#FF7A1A`,
`FF7A1A`, `#F70`; closest first, CIEDE2000); **Use exactly #…**; a number in another chart → "Found
in …" to switch; **Or mix your own color** picker.

### F-1603 Match threads — YES
Order & colors → **Match…** ("Match to mine…" once you have spools): nearest thread for every color,
your spools first; untick any to keep.

### F-1604 My threads & charts — YES
`Ctrl+T`: **My threads** (add from a brand chart, or "Add a spool by color" for unbranded Amazon
kits); **Brand charts** (Brother, Janome built in; import CSV with code + hex or R,G,B columns).
Importing under a name already used replaces that chart; a different name never replaces another
chart (fixed 2026-11-24: non-Latin names and names like "Isacord 40"/"Isacord-40!" did).

### F-1605 Color sets — YES
Order & colors → Color sets: save the current colors under a name, switch with **Use** (one undo).

### F-1606 Preview on a garment — YES
Design → Preview on: T-shirt, tote, towel, baby bodysuit, cap or plain fabric, any fabric color.
Picture only; nothing stitched.

### F-1607 Color options — YES
Combine same colors next to each other `Ctrl+Shift+C` · Sort colors (fewest changes, never puts a
shape under one it should sit on) `Ctrl+Shift+L` · Put back the original colors `Ctrl+Shift+R`.

---

## 15. Fabric and checks

### F-1701 Stitching on (fabric) — YES
Design section: cotton/woven, denim/canvas, T-shirt knit, fleece/sweatshirt, towel/terry, stretchy
sportswear, felt. Adjusts density, pull compensation and underlay of drawn shapes and lettering
(hand-set values win), shows the stabilizer (+ topping for towel/fleece), suggests knockdown.

### F-1702 Check before stitching — YES
Too much thread in one place, needle hitting one spot, many very short stitches, long loose stitches
(> 7 mm), shapes that almost touch; each with why and what to do, and **Show me**. Thick spots inside
a bought stitch file are a note. Same checks in Save for machine.

### F-1703 Density map — YES
`Alt+D`: yellow-green two layers, orange the limit, red too much.

---

## 16. Machine extras and jumps (⋯ menu)

### F-1801 Basting box — YES
`Ctrl+Shift+B`: a frame sewn first; shrinks inward to fit the hoop if needed.

### F-1802 Knockdown stitches — YES
`Ctrl+Shift+N`: light grid sewn first for towels/fleece; set its thread with its ✎ in Order & colors.

### F-1803 Fewer jumps & trims (hidden travel) — YES
`Ctrl+Alt+T` / Design section (on for new designs): same-thread moves that later stitching will
cover become small travel stitches instead of jump + trim.

### F-1804 Sew in the shortest order — YES
`Ctrl+Alt+O`: reorders same-thread shapes for the shortest moves; overlapping shapes keep their order.

### F-1805 Optimize jumps — YES
`Ctrl+Alt+J` (Design section, ⋯): keeps the order; chooses each piece's start and end so same-thread
pieces hand over like magnets (lines/satins turned round, borders started nearest, fills at the
nearest edge); reports the saving (e.g. 132 mm → 45 mm). Stitch files, lettering and appliques are
left alone. Replaces hand-set starts/ends.

### F-1806 Stops and trims at the needle — YES
`Ctrl+Shift+P` stop / `Ctrl+Shift+T` trim at the stitch-out bar's position. In drawn shapes/lettering
it's dropped (with a note) once the shape changes.

### F-1807 Trim jumps longer than 3 mm — YES
`Ctrl+Shift+J` (⋯): one setting for the whole design, including designs added later.

---

## 17. Editing stitch files

### F-1901 Edit stitches — YES
Select a placed stitch file → Edit stitches (`Ctrl+Alt+E`): click / Shift+click / box-select needle
points, drag to move, Delete removes, Esc or Done finishes. Edits are kept in the project (the
original file isn't changed) and turn/resize with the design.
- **A placed file with edits sews from LUDD's own copy**, taken when it was added (since
  2026-11-24). Edits (colors changed, colors or stitches deleted, stops or trims added, stitches
  moved) name stitches by number, so if the original is saved again in another program, LUDD keeps
  using its copy and the edits stay on the right stitches. To use the new version, add the file
  again and redo the edits. A placed file *without* edits follows the file on disk.

---

## 18. AI (optional, off by default)

### F-2001 AI add-on modes — YES
Settings → AI add-on: **Off** (nothing sent) · **On this computer** (Ollama; e.g. `ollama pull
qwen2.5vl:7b`; the owner has this set up) · **Cloud** (Anthropic or OpenAI-compatible, own key,
https only; key stored encrypted on Windows; on a Mac or Linux in a file only the user can read, from
the moment it's written, 2026-11-24). Before anything is sent, LUDD shows what, where and the
maximum cost: the text, any pictures, and (under its own heading) LUDD's fixed instructions to the AI.
If the service tries to redirect LUDD to another address, LUDD refuses (your key stays with the
address in Settings) and says to check the address (2026-11-24).

### F-2002 Stitch Advisor — YES
`Ctrl+Shift+I` (✨ in Advanced stitch settings, ⋯, right-click): suggests stitch type, angle,
density, underlay and sewing order with reasons; Accept / Dismiss each or Accept all (one undo). It
sees each shape over the picture plus its neighbors in their thread colors. A suggestion to turn a
fill into a satin can't be accepted (use Stitch as → Satin yourself).

### F-2003 Help with AI — YES
F1 → Ask AI answers from the built-in guide when the add-on is on.

---

## 19. Settings, help, updates

### F-2101 Settings — YES
`Ctrl+,`: Look (Automatic/Light/Dark; always show the design on light fabric), My machine and hoop,
Measurements, Workspace (hoop, grid, realistic thread, Trace Assist), AI tracing, AI add-on,
Updates (notify, Check now, version), About (licenses).

### F-2102 Help — YES
F1 / ?: search the built-in guide offline; AI answers if the add-on is on.

### F-2103 Updates — YES
A strip offers **Install and restart** or Later when a release is out; unsaved work is offered back
after the restart. `Ctrl+Shift+F1` checks now. (Developer builds installed by hand don't
auto-update from GitHub until a release is published.)

### F-2104 Engine restart — YES
The stitch engine runs alongside the app. If it stops, LUDD restarts it; if not, the status bar's
**Restart engine** button. Work stays on screen.

---

## 20. Not supported, and known limitations

| ID | What | Status | Workaround | Could it be built? |
| --- | --- | --- | --- | --- |
| L-001 | **Two-color gradient / color blend** (one color fading into another by interleaved rows) | NO | Gradient pattern fades one color to sparse; layer two Gradient fills at opposite angles by hand. | Yes: a "Blend" fill was offered and not yet requested. |
| L-002 | **Fill with holes may show a travel line on top**: when holes split a tatami fill into regions, the needle can travel across rows already sewn. | Known weakness | Cut the fill into hole-free bands with cuts parallel to the rows (Knife), or use Contour/Stipple. | Yes (engine route planning). |
| L-003 | **Multi-line text** in one lettering object | NO | One text per line; group them. | Yes. |
| L-004 | **Open running line starting mid-line** | NO (ends only) | Split it with the Knife, or close it into a loop. | Possibly. |
| L-005 | **Per-letter stitch angle / direction** in lettering | NO | Break into shapes (F-1407), then use each letter's purple dots. | Yes. |
| L-006 | **Direction dots on satin ribbons** | NO (stitches always straight across) | Convert to a satin fill (close the line and Stitch as → Satin) or draw a column. | Partly. |
| L-007 | **Change stitch types of a bought stitch file** | NO | Edit stitches (F-1901), or re-digitize by tracing a picture of it. | Unlikely (no shapes inside a stitch file). |
| L-008 | **Photo stitch** (photo → stitched portrait) | NO | Auto-digitize a simplified picture; satin-fill shapes by hand. | Yes, large. |
| L-009 | **Specialty techniques**: 3D puff foam, sequins, chenille, cutwork, free-standing lace presets | NO | — | Some (FSL, puff) could be added. |
| L-010 | **Sending to the machine directly** | NO | Save for machine to a USB stick; insert in the PE550D. | Not for the PE550D (USB stick only). |
| L-011 | **Freehand drawing / brush** | NO (point-by-point drawing only) | Click points; use Auto-trace on a sketch. | Yes. |
| L-012 | **Opening Embrilliance `.be` / `.bt`** | NO (closed format) | Open the PES/JEF exported from Embrilliance; it opens as a stitch file. | No. |
| L-013 | **Satin fill with holes** | NO | Stays a fill; add a satin border, or split into hole-free pieces. | Hard. |
| L-014 | **Satin stitch font look in TrueType lettering** (true satin columns per stroke) | NO (satin-look fills) | Break into shapes and set strokes to Satin; or make a stitch font by hand. | Yes, large. |
| L-015 | **Code-signed installers** | NO | Windows: More info → Run anyway (T-001). | Needs a certificate. |
| L-016 | **Real machine verification** | Pending | Stitch-out tests queued in `docs/stitchout-log.md`; the owner tests at ~95% done. | — |
| L-017 | **Optimize jumps on lettering, appliques, stitch files** | NO (left as they are) | Lettering already hands over letter to letter (F-1405). | Yes. |
| L-018 | **Machines other than PE550D / Janome generic built in** | PARTIAL | Add a JSON profile in the data folder's `machines`. | Yes. |
| L-019 | **Stitch Advisor turning a fill into a satin** | NO | Stitch as → Satin yourself (makes a satin fill). | Yes. |
| L-020 | **Resizing bought designs a lot** | PARTIAL (±20%) | Re-digitize for big changes. | Unlikely. |
| L-021 | **Fill end mid-way along an edge that runs with the rows** | PARTIAL | The rows finish at a row end; a short run along the last row (on top of it) takes the needle to the exact point. Usually invisible; on light fabric it can thicken that row slightly. Put the end near a corner, or turn the angle. | Yes (split the last row). |
| L-022 | **End point on Contour / Stipple / Cross-stitch / Spiral fills** | NO | Their pattern decides where they end (the red dot shows it). | Possibly. |
| L-023 | **Stitch Advisor changing a closed line to satin** | PARTIAL | It makes a satin border along the line; Stitch as → Satin makes a satin fill instead. | Yes. |
| L-024 | **Memory guard for damaged or crafted .vp3 / .hus files** | NO | Only open stitch files you trust (LUDD is offline, so this only matters for files from strangers). A damaged one can make LUDD use a lot of memory and slow down; close LUDD from the task manager if so. | Yes, by reading files in a separate memory-limited process. |
| L-025 | **A placed stitch file with edits doesn't pick up changes made to the original later** | By design (2026-11-24) | Add the changed file again and redo the edits (recolor, delete, stops). Without edits, a placed file follows the original. | Possibly (a "reload and keep what still fits" option). |
| L-026 | **Spiral leaves a light outline on most shapes**: where the shape cuts the rings, the thread joining the pieces runs along the edge (outline or hole rim), never across the rings. At most a few threads share any one spot (4 on most ready-made shapes at 60 mm, 5 on the Hexagon); the ready-made Circle has almost none | By design (not yet checked on fabric) | A satin border covers it round the outside, not round holes (**Add a satin border**, `Shift+B`). | No. |

---

## 21. Troubleshooting

| ID | Symptom | Cause | Fix |
| --- | --- | --- | --- |
| T-001 | "Windows protected your PC" when installing | Installer not code-signed | More info → Run anyway (once). Mac: System Settings → Privacy & Security → Open Anyway. |
| T-002 | PES loads on the PE550D shifted up-left / mostly off the hoop / can't be moved; machine shows a smaller size than LUDD | PES files saved by LUDD before 2026-10-13 were centered on (0, 0) | Install the current version and **Save for machine again**. Fixed copies of the owner's files: `Downloads\GrumpyBMO (fixed).pes`, `Documents\LUDD designs\Many Names, One Light (fixed).pes`. |
| T-003 | Design area is blank gray | Old 1.0.1 build issue (fixed) or graphics start failure | Update; LUDD now says why if the design area can't start. |
| T-004 | "Engine disconnected" | The stitch engine stopped | It restarts itself; else Restart engine in the status bar. Work is kept. |
| T-005 | Settings' bottom is cut off in a small window | Fixed 1.0.1 | Update; dialogs scroll with the wheel. |
| T-006 | Esc does nothing | Owner's Esc key was faulty once; or something earlier is "held" (a drag) | Check the key; press Esc again (it lets go one thing per press). |
| T-007 | Auto-trace guess leaks into the next area | Spread too high | Lower Spread (`Alt+[`), Alt+click the area to cut it out, or try the next guess (Tab). |
| T-008 | Auto-trace guess stops short | Spread too low / shading | Raise Spread (`Alt+]`), Shift+click to add, or try "simplified colors" / AI tracing. |
| T-009 | AI says it can't reach `http://localhost:11434` | Ollama isn't running | Start Ollama (it runs in the system tray); make sure the model is pulled (`ollama pull qwen2.5vl:7b`), then Settings → AI → Test. |
| T-010 | A long thin travel line shows across a fill with holes | L-002 | Split the fill into hole-free bands. |
| T-011 | Lettering trims between every letter | Older version, or letters far apart | Current version hands over letter to letter; drag letter dots to tune. |
| T-012 | The start/end dot "jumps somewhere else" when dropped | Pre-2026-10-13 build | Update; dots now follow the edge and stay put. |
| T-013 | Can't grab a satin's purple tip | It sits just past the end of the satin, outside the shape | Zoom in; grab the purple dot outside the tip (green/red dots win where they overlap). |
| T-014 | Too dense / puckers | Overlaps, density, fabric | Density map (`Alt+D`), Checks → Show me, lighter density, choose the fabric, cut holes under top shapes. |
| T-015 | Thread colors on the machine screen differ | Machine palette maps to its nearest colors | Match to Brother chart (Order & colors → Match…) before saving. |
| T-016 | "N parts of this project were damaged and left out" when opening | The project file was damaged, or made by a newer LUDD | The rest opened. Save under a new name to keep the original; send the original to the developer. |
| T-017 | "The AI service tried to send LUDD on to …" | The address in Settings → AI add-on redirects (old address, wrong port, http vs https) | Put in the final address the service uses. |
| T-018 | "This picture is too small to trace" | The picture was shrunk under 0.5 mm | Make the picture bigger, trace, then resize the shapes. |
| T-019 | I changed a stitch file in another program, but LUDD still sews the old one | The placed copy has edits, so LUDD keeps its own copy (L-025) | Add the file again (Ctrl+Shift+O) and redo the edits; delete the old copy. |
| T-020 | An applique now has more machine stops than before (cut-stops on) | Since 2026-11-24 moves over 3 mm between applique edges are trimmed, and cut-stops turn trims into stops | Expected: each stop cuts a thread that used to lie over the fabric. Untick "Have the machine cut jump threads" to sew without them. |

---

## 22. Glossary (embroidery words, LUDD names, Embrilliance names)

| Term | Means | In LUDD | In Embrilliance |
| --- | --- | --- | --- |
| Digitize | Turn artwork into stitch shapes | Drawing tools, Auto-trace | Create / Express |
| Running stitch | A single line of stitches | Line (`L`) | Line / Run |
| Bean / triple stitch | Line sewn 3× | Line → Style → Bean / Triple | Bean |
| Satin | Smooth stitches straight across a narrow column | Satin ribbon (`C`), satin column, satin fill | Satin / Column |
| Tatami / fill | Rows of short stitches filling an area | Fill (`F`) | Fill |
| Underlay | Stitches sewn first to hold fabric | Underlay fold | Underlay |
| Pull compensation | Widening to offset fabric pull | Edge pad | Pull comp |
| Density / spacing | Distance between rows | Density (mm between rows) | Density |
| Entry / exit point | Where a shape starts / stops | Green / red dots | Entry/exit points |
| Inclination / stitch direction | The angle of fill rows | Angle, purple dots, `I` | Inclination line (yellow dots) |
| Jump | Thread carried across without stitching | Jumps (`J` view) | Jump |
| Trim | Thread cut | Trim; cut-stops for the PE550D | Trim |
| Cut-stop | A stop in the same color so the PE550D cuts | Save for machine option | — |
| Color change / stop | Machine pauses for a new thread | Color step | Color change |
| Applique | Fabric piece sewn on | Applique | Applique |
| Knockdown | Light grid flattening towel pile | Knockdown stitches | Knockdown |
| Basting | Temporary frame holding fabric | Basting box | Baste |
| Stabilizer | Backing material | Shown per fabric | Stabilizer |
| Hoop | The frame (PE550D: 4"×4") | Machine & hoop picker | Hoop |
| Stitch file | Finished machine file (PES, JEF…) | Stitch file | Stitch file |
| Project | Editable working file | `.ludd` | `.be` (working file) |
| Colorway | Color version of a design | Color sets | Colorways |

---

## 23. Change history (what changed when; newest first)

Use this to answer "did that change?" or "why is it different?". Full detail: `docs/CHANGELOG.md`.

| Date | Change |
| --- | --- |
| 2026-11-24 | **Spiral fill and more shapes** (nothing already sewn changes): a new **Spiral** fill pattern (F-1305; the thread joining its pieces follows the edge, L-026); the Shapes menu adds a rounded rectangle, oval, triangle, polygon and heart (`Ctrl+Alt+4`–`8`, F-501). Behind the scenes, the stitch engine and panel were split into smaller parts, and `python scripts/check.py` runs every check. Also corrected: Stipple and Cross-stitch don't move their start with the green dot (F-701). |
| 2026-11-24 | **Sewing time and thread estimate** (F-406): the Design section shows about how long the design sews on your machine, how many thread changes, and about how much top and bobbin thread it uses, per color under **Thread used**. Machine profiles can set `speed_spm`. |
| 2026-11-24 | **Phase 1 audit fixes**: `S` zooms to everything selected (was one item); the AI key file is written whole and private from the start on Mac/Linux. No stitch changes. |
| 2026-11-24 | **QA pass 2 decisions** (changes stitches): fills with a thin neck travel along their edges and never end on a jump; zigzag underlay crosses back in an X; long moves between applique edges are trimmed; Split long stitches holds at sharp corners of ribbons and applique borders; a placed stitch file with edits sews from LUDD's copy taken when it was added; sample PES/JEF made again; Ctrl+Z while drawing removes the last point, Ctrl+Y waits; CI builds the Mac code. |
| 2026-11-24 | **QA pass 2** (docs/QA-REPORT-2.md): the knife, stitch editing, the ruler and the angle line no longer stay on together; picking a tool ends stitch editing; knife, merge, outline and Optimize jumps drop an answer if the design changed meanwhile; Auto-trace keeps the next guess while the last one is added; Ctrl+X cuts the only shape; a failed delete keeps the selection; damaged parts of a project are left out with a note; private copies are found again after an engine restart; AI services can't redirect your key elsewhere; thread charts with similar or non-Latin names no longer replace each other; tiny pictures trace fast or say they're too small; plain messages for odd satin and line settings and bad hole points; Settings knows if AI tracing really runs. |
| 2026-11-14 | **QA decisions**: pinned shapes ignore arrows, R and Alt+H/V; Browse designs has **Refresh**; the AI send preview shows LUDD's fixed instructions; the AI tracing model download is pinned and checked; US spelling in the app (Center, Millimeters, Licenses); GitHub Actions pinned by commit and Dependabot added. |
| 2026-10-13 | **Self-audit fixes**: satin start lands on the satin; multi-piece fills end on the right piece; Optimize jumps improves hand-set lines/satins; lettering hand-overs only for filled letters, new Reset (`Ctrl+Alt+R`); pinned shapes' points locked; dots don't snap back or appear on the wrong shape; late engine answers dropped if the shape changed; arrows nudge with a drawing tool chosen; commands only where they work; Back to … for changed colors; picker resets; context-menu scrolling; knife/cut-out pieces get fresh dots; Advisor sees moved shapes. |
| 2026-10-13 | Satins start/stop anywhere along them (were stuck at their ends); wide satins end on the chosen side. Lettering: per-letter start/end dots, letters hand over (fewer trims), panel explains satin look vs fill, **Break into shapes** (`Ctrl+Alt+X`). |
| 2026-10-13 | A looped line set to Satin becomes a satin fill (was a ribbon round the edge). |
| 2026-10-13 | Start/stop dots follow the edge like a magnet and stay exactly where dropped; fills end exactly at the red dot; **purple direction dots** for fills and satin columns/fills; dots move with the shape. |
| 2026-10-13 | **Order & colors** replaces Threads + Sewing order (per-item colors, Palette); multi-select highlighted in the list and recolored together (🧵, `Alt+T`); groups drag from anywhere inside their frame. |
| 2026-10-13 | **PES placement fixed** for the PE550D (designs were shifted off the hoop). |
| 2026-10-12 | Right-click menus everywhere; new commands Sew first/earlier/later/last, Center in the hoop, Change thread (`Alt+T`), Change the words. Tools stay chosen. Thread search by color code; mix your own color. Auto-trace fits around existing shapes; Stitch Advisor sees neighbors. Dialogs scroll in small windows. |
| 2026-10-12 | Draggable start/end dots (first version), satin fill, holes and cut out, Shapes menu, density slider with numbers, Optimize jumps, side stretch handles, custom pointers, realistic thread redone, drag-and-drop sewing order, see-through stitches, satin edge fit. |
| 2026-10-12 to 2026-11-14 | 1.0.1: QA review fixes (phases 1–4: docs/QA-RESPONSE.md). Not in 1.0.0 installers. |
| 2026-10-11 | 1.0.0 release; renamed LUDD (from Threadline); GPL-3.0-or-later. |

---

## 24. Writing a change request (bug or feature)

When the answer is **NO**, **PARTIAL**, or the person describes something that looks broken, offer:
"Would you like me to write a prompt you can paste into your LUDD developer chat?" If yes, ask for
anything missing (keep it to 1–3 short questions), then produce **one** prompt in this shape:

```
LUDD change request — <Bug | Feature | Improvement> — <short title>

What I want / what happened:
<plain description in the user's words>

Steps to reproduce (bugs):
1. …
2. …
Expected: …
Actual: …

Where in LUDD: <UI path, e.g. Order & colors → color square> (KB refs: F-…, L-…)
Shape/design involved: <fill / satin / lettering / stitch file…; file name if any>
How important: <blocking / annoying / nice to have>
Version: LUDD <version from Settings → Updates>, installed <date if known>

Done when:
- <observable result 1>
- <observable result 2>

Please keep the KB (docs/LUDD-KNOWLEDGE-BASE.md), manual and changelog in step, then build a fresh installer.
```

Triage rules for the agent:
- **User education** (the feature exists): answer how; don't write a request unless asked.
- **Bug**: something documented here as YES doesn't behave as described → request type Bug.
- **Feature**: marked NO, or not in this file → request type Feature.
- **Improvement**: it works but is awkward → request type Improvement.
- One request per prompt; don't bundle unrelated things.

---

## 25. Command registry (every command, its shortcut, its id)

The authoritative list of what can be done, from the app's command registry
(`apps/desktop/src/actions.ts → COMMANDS`). Shortcuts: `Mod` = Ctrl (⌘ on Mac). Several commands
share a key; the first that applies in the current situation wins (e.g. Tab in Auto-trace vs while
drawing a satin).

<!-- COMMANDS:START -->
| Command | Shortcut | id |
| --- | --- | --- |
| Delete the selected stitches | `Delete` | `stitch.deleteSelected` |
| Delete the selected stitches | `Backspace` | `stitch.deleteSelectedAlt` |
| Add every shape found in the picture | `Enter` | `autotrace.allAccept` |
| Auto-trace: next guess | `Tab` | `autotrace.next` |
| Auto-trace: previous guess | `Shift+Tab` | `autotrace.prev` |
| Auto-trace: use this guess | `Enter` | `autotrace.accept` |
| Auto-trace: use as a fill with a satin border | `Shift+Enter` | `autotrace.fillBorder` |
| Auto-trace: points closer together | `[` | `autotrace.closer` |
| Auto-trace: points further apart | `]` | `autotrace.further` |
| Auto-trace: spread less (stop at fainter changes) | `Alt+[` | `autotrace.spreadLess` |
| Auto-trace: spread more (join similar shades) | `Alt+]` | `autotrace.spreadMore` |
| Fit the satin along the edge (again: the next way) | `Tab` | `satin.fitEdge` |
| Fit the satin along the edge: the way before | `Shift+Tab` | `satin.fitEdgeBack` |
| Accept the suggested point | `Tab` | `trace.accept` |
| Keep accepting points | `Shift+Tab` | `trace.acceptMany` |
| Take branch 1 | `1` | `trace.pick1` |
| Take branch 2 | `2` | `trace.pick2` |
| Shorter steps | `[` | `trace.shorter` |
| Longer steps | `]` | `trace.longer` |
| Switch the last point: curve, straight, sharp corner | `C` | `pen.toggleKind` |
| Trace Assist (suggest the next point) | `Mod+Shift+A` | `trace.toggle` |
| Move the view left 1 cm (while drawing) | `ArrowLeft` | `view.panLeft` |
| Move the view right 1 cm (while drawing) | `ArrowRight` | `view.panRight` |
| Move the view up 1 cm (while drawing) | `ArrowUp` | `view.panUp` |
| Move the view down 1 cm (while drawing) | `ArrowDown` | `view.panDown` |
| Finish the shape | `Enter` | `pen.finish` |
| Remove the last point | `Backspace` | `pen.undoPoint` |
| Cancel the shape | `Escape` | `pen.cancel` |
| Put the measuring tool away | `Escape` | `ruler.cancel` |
| Stop setting the angle | `Escape` | `angle.cancel` |
| Stop measuring | `Escape` | `measure.cancel` |
| Settings… | `Mod+,` | `app.settings` |
| Help | `F1` | `app.help` |
| Stitch Advisor (AI)… | `Mod+Shift+I` | `ai.advisor` |
| New design | `Mod+N` | `file.new` |
| Open… | `Mod+O` | `file.open` |
| Save project | `Mod+S` | `file.save` |
| Save project as… | `Mod+Shift+S` | `file.saveAs` |
| Add another design… | `Mod+Shift+O` | `file.add` |
| Add a picture to trace… | `Mod+I` | `file.picture` |
| Open a sample design… | `Mod+Shift+E` | `file.samples` |
| Check for updates | `Mod+Shift+F1` | `app.updates` |
| Save for machine… | `Mod+E` | `file.export` |
| Print template & thread list… | `Mod+P` | `file.print` |
| Batch convert folder… | `Mod+B` | `file.batch` |
| Undo | `Mod+Z` | `edit.undo` |
| Redo | `Mod+Y` | `edit.redo` |
| Redo | `Mod+Shift+Z` | `edit.redoAlt` |
| Select and move | `V` | `tool.select` |
| Draw a running stitch line | `L` | `tool.run` |
| Draw a satin ribbon | `C` | `tool.satin` |
| Auto-trace a shape in a picture | `Shift+A` | `tool.autotrace` |
| Auto-digitize the whole picture… | `Alt+A` | `autotrace.all` |
| Knife: cut the selected shape in two | `Shift+K` | `tool.knife` |
| Merge the selected fills into one | `Mod+M` | `object.merge` |
| Outline / offset around the selection… | `Mod+Shift+K` | `object.offset` |
| Hide moves under later stitching (fewer jumps & trims) | `Mod+Alt+T` | `layout.travelUnder` |
| Sew in the shortest order | `Mod+Alt+O` | `layout.shortestOrder` |
| Optimize jumps (where each piece starts and ends) | `Mod+Alt+J` | `layout.optimizeJumps` |
| Browse designs… | `Mod+Alt+B` | `file.browse` |
| Edit stitches of the selected design | `Mod+Alt+E` | `edit.stitches` |
| Put the text on the selected line | `Mod+Alt+L` | `text.onLine` |
| One file per name… | `Mod+Alt+N` | `text.names` |
| Rulers (drag from them for guides) | `Mod+R` | `view.rulers` |
| Remove all guides | `Mod+Alt+G` | `view.clearGuides` |
| Add a satin border | `Shift+B` | `object.border` |
| Draw a fill shape | `F` | `tool.fill` |
| Add text (click where it goes) | `Shift+T` | `tool.text` |
| Switch between Create and Select | `D` | `create.toggle` |
| Draw again with the last tool | `X` | `create.again` |
| Draw a line (running stitch) | `Shift+X` | `create.line` |
| Draw a shape like the last one | `Q` | `create.same` |
| Draw a shape like the one before the last | `W` | `create.prior` |
| Cut a hole in the selected fill (draw round it) | `O` | `object.hole` |
| Cut the shapes on top out of the fill (select the fill and them) | `Shift+O` | `object.cutOut` |
| Turn a satin fill's stitches another way | `Shift+W` | `satin.otherWay` |
| Set the stitch angle with a line | `I` | `object.angle` |
| Add a monogram | `Mod+Alt+M` | `text.monogram` |
| Add a rectangle | `Mod+Alt+1` | `shape.rectangle` |
| Add a circle | `Mod+Alt+2` | `shape.circle` |
| Add a star | `Mod+Alt+3` | `shape.star` |
| Continue drawing this shape | `K` | `draw.continue` |
| Back to Select | `Escape` | `tool.escape` |
| Rotate 90° right | `R` | `arrange.rotateCw` |
| Rotate 90° left | `Shift+R` | `arrange.rotateCcw` |
| Select everything | `Mod+A` | `edit.selectAll` |
| Group (select and move together) | `Mod+G` | `arrange.group` |
| Ungroup | `Mod+U` | `arrange.ungroup` |
| Mirror left–right | `Alt+H` | `arrange.mirrorX` |
| Mirror top–bottom | `Alt+V` | `arrange.mirrorY` |
| Duplicate | `Mod+D` | `arrange.duplicate` |
| Remove the selected point | `Delete` | `node.delete` |
| Remove the selected point | `Backspace` | `node.deleteAlt` |
| Remove | `Delete` | `arrange.delete` |
| Remove | `Backspace` | `arrange.deleteAlt` |
| Let go of the point | `Escape` | `node.deselect` |
| Deselect | `Escape` | `arrange.deselect` |
| Stop playing | `Escape` | `player.stop` |
| Nudge left | `ArrowLeft` | `arrange.left` |
| Nudge right | `ArrowRight` | `arrange.right` |
| Nudge up | `ArrowUp` | `arrange.up` |
| Nudge down | `ArrowDown` | `arrange.down` |
| Nudge left 1 cm | `Shift+ArrowLeft` | `arrange.leftBig` |
| Nudge right 1 cm | `Shift+ArrowRight` | `arrange.rightBig` |
| Nudge up 1 cm | `Shift+ArrowUp` | `arrange.upBig` |
| Nudge down 1 cm | `Shift+ArrowDown` | `arrange.downBig` |
| Combine same colors next to each other | `Mod+Shift+C` | `colors.merge` |
| Sort colors (fewest thread changes) | `Mod+Shift+L` | `colors.sort` |
| Put back the original colors | `Mod+Shift+R` | `colors.reset` |
| Insert a stop at the needle | `Mod+Shift+P` | `stitch.stop` |
| Insert a trim at the needle | `Mod+Shift+T` | `stitch.trim` |
| Trim jumps longer than 3 mm | `Mod+Shift+J` | `stitch.jumpsToTrims` |
| Add a basting box | `Mod+Shift+B` | `stitch.basting` |
| Knockdown stitches (towels, fleece) | `Mod+Shift+N` | `stitch.knockdown` |
| Pin in place / unpin | `Mod+L` | `arrange.pin` |
| Rename | `F2` | `arrange.rename` |
| Sew earlier | `Mod+[` | `arrange.earlier` |
| Sew later | `Mod+]` | `arrange.later` |
| Sew first | `Mod+Shift+[` | `arrange.first` |
| Sew last | `Mod+Shift+]` | `arrange.last` |
| Center in the hoop | `Mod+Shift+M` | `arrange.centre` |
| Change thread… | `Alt+T` | `object.thread` |
| Break the lettering into shapes | `Mod+Alt+X` | `text.toShapes` |
| Reset the letters' starts and ends | `Mod+Alt+R` | `text.resetEnds` |
| Change the words | `Mod+Alt+W` | `text.edit` |
| Repeat, carousel or mirror… | `Mod+Shift+D` | `arrange.repeat` |
| Save applique cut file (SVG)… | `Mod+Shift+U` | `applique.svg` |
| New design | `Shift+D` | `file.newAlt` |
| Density map | `Alt+D` | `view.density` |
| Zoom to all | `A` | `view.fit` |
| Show trims, jumps and stops | `J` | `view.jumps` |
| Realistic thread (3D) | `T` | `view.realistic` |
| Show hoop | `H` | `view.hoop` |
| Show grid | `G` | `view.grid` |
| Measure in millimeters | `U` | `view.units` |
| Zoom in | `=` | `view.zoomIn` |
| Zoom in | `Shift++` | `view.zoomInPlus` |
| Zoom in | `+` | `view.zoomInPad` |
| Zoom out | `-` | `view.zoomOut` |
| Zoom to the selection | `S` | `view.zoomSelected` |
| Zoom to the hoop | `0` | `view.zoomHoop` |
| Zoom to 2× real size | `2` | `view.zoom2` |
| Zoom to 3× real size | `3` | `view.zoom3` |
| Zoom to 4× real size | `4` | `view.zoom4` |
| Zoom to 5× real size | `5` | `view.zoom5` |
| Zoom to 6× real size | `6` | `view.zoom6` |
| Zoom to 7× real size | `7` | `view.zoom7` |
| Zoom to 8× real size | `8` | `view.zoom8` |
| Zoom to 9× real size | `9` | `view.zoom9` |
| Measure (click two points) | `M` | `view.measure` |
| Show stitch points | `P` | `view.points` |
| Show stitches | `N` | `view.stitches` |
| See-through stitches (to work over a picture) | `Shift+N` | `view.seeThrough` |
| Show pictures | `B` | `view.pictures` |
| Crosshairs | `E` | `view.crosshair` |
| Snap new points to the grid | `Shift+G` | `view.snap` |
| Copy | `Mod+C` | `edit.copy` |
| Cut | `Mod+X` | `edit.cut` |
| Paste | `Mod+V` | `edit.paste` |
| Nudge left 0.1 mm | `Mod+ArrowLeft` | `arrange.leftFine` |
| Nudge right 0.1 mm | `Mod+ArrowRight` | `arrange.rightFine` |
| Nudge up 0.1 mm | `Mod+ArrowUp` | `arrange.upFine` |
| Nudge down 0.1 mm | `Mod+ArrowDown` | `arrange.downFine` |
| Zoom to real size (100%) | `1` | `view.zoomActual` |
| My threads & charts… | `Mod+T` | `threads.charts` |
| Play / pause (tap Space; hold Space and drag to move around) | `Space` | `player.toggle` |
| Back one stitch | `ArrowLeft` | `player.back` |
| Forward one stitch | `ArrowRight` | `player.forward` |
| Back 100 stitches | `Shift+ArrowLeft` | `player.back100` |
| Forward 100 stitches | `Shift+ArrowRight` | `player.forward100` |
| Previous color | `PageUp` | `player.prevColor` |
| Next color | `PageDown` | `player.nextColor` |
| Stitch out slower | `,` | `player.slower` |
| Stitch out faster | `.` | `player.faster` |
| Stitch out at machine speed | `Shift+,` | `player.machineSpeed` |
| Go to start | `Home` | `player.start` |
| Show whole design | `End` | `player.end` |
| Faster playback | `]` | `player.fasterAlt` |
| Slower playback | `[` | `player.slowerAlt` |
| Repair this design… | `Mod+Alt+D` | `stitch.repair` |
| Remove stitches hidden under what's on top | `Alt+Shift+H` | `stitch.removeHidden` |
| Thin out dense spots | `Alt+Shift+D` | `stitch.declump` |
| Remove tiny stitches | `Alt+Shift+S` | `stitch.filterSmall` |
| Limit density for this fabric | `Alt+Shift+L` | `stitch.densityLimit` |
| Rebuild stitches at this size | `Alt+Shift+R` | `stitch.rebuild` |
| Insert a stitch here | `Insert` | `stitch.insert` |
| Insert a jump here | `Shift+Insert` | `stitch.insertJump` |
| Lock both sides of this jump | `Alt+Shift+T` | `stitch.lockJump` |
| Remove stitching hidden under shapes on top | `Alt+Shift+O` | `object.removeOverlap` |
| Needle path only | `Shift+P` | `view.wireframe` |
| Add a rounded rectangle | `Mod+Alt+4` | `shape.roundedRect` |
| Add an oval | `Mod+Alt+5` | `shape.ellipse` |
| Add a triangle | `Mod+Alt+6` | `shape.triangle` |
| Add a polygon | `Mod+Alt+7` | `shape.polygon` |
| Add a heart | `Mod+Alt+8` | `shape.heart` |
<!-- COMMANDS:END -->

---

## 26. Maintenance (for the developer)

- Update this file in the **same change** as any user-visible change (with `docs/CHANGELOG.md` and
  `docs/USER-MANUAL.md`): add or edit the `F-` entry, the capability index row (section 2), limits
  (section 20), troubleshooting (section 21) and the history table (section 23); bump *Last updated*.
- Regenerate section 25: `python scripts/kb_commands.py` (rewrites the block between the COMMANDS
  markers from `COMMANDS`).
- Never remove an ID; mark it superseded instead, so old answers stay traceable.
