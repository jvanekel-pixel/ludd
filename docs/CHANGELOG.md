# Changelog

## 1.0.0 (Oct 11, 2026)

### M10 Release 1.0
- **Installers** for Windows (per-user, no administrator password), Mac (Apple chip and Intel) and Linux, built by GitHub Actions on each version tag and placed on a draft release for the owner to publish. `.ludd` projects open LUDD when double-clicked.
- **Updates**: LUDD asks GitHub on start whether a newer version exists (a tick box on the welcome screen and in Settings turns this off; nothing about you is sent) and offers **Install and restart**. Updates are signed; the app refuses unsigned ones. Settings shows the version and has Check now.
- **Sample designs** come with the app (Star badge, Flower, Applique heart, Wreath, and a Banner too big for a 4" hoop to try splitting): *Or try one of the sample designs* on the start screen, or ⋯ → Open a sample design. Each passes LUDD's own checks. They open as new designs, so Save asks where to keep yours.
- **User guide** (`docs/USER-GUIDE.md`), written for someone who's never used it, from installing (including "Windows protected your PC") to the first design on the machine; release notes and a maintainer's guide to releasing and code signing.
- Fixed (found while making the samples): fills could leave long loose stitches where an edge runs almost along the rows (a star's arms, up to 23 mm); those rows are now joined by travel inside the shape.
- The "too much thread" check ignores thin bands where a border overlaps a fill's edge (normal practice) and still catches real piles of thread.
- Code signing is prepared but needs a certificate (see `docs/RELEASING.md`); until then Windows and macOS ask once before opening LUDD.


### M9 AI add-on (done Oct 11, 2026)
- **Off by default, and everything works without it.** Settings → AI add-on: Off, On this computer (Ollama, models on your own PC; unloaded straight after each answer so they don't hold the graphics card), or Cloud (Anthropic, or any OpenAI-compatible service, with your own key and account). Per-feature switches for the Stitch Advisor and AI answers in Help, and a Test connection button.
- **Your key** is stored apart from the settings, encrypted for your Windows account (DPAPI); LUDD only ever shows whether one is saved.
- **Before anything goes to the cloud**, LUDD shows what will be sent (the pictures and the text), the token count, and, if you enter your service's prices, the most it can cost. Send or Cancel; Cancel sends nothing.
- **Stitch Advisor** (✨ in a drawn shape's panel, the ⋯ menu, or Ctrl+Shift+I): for the selected shape, or every drawn shape, the model sees a picture of each one (over the picture you're tracing) and its measurements, and suggests stitch type, fill angle, density, underlay and sewing order, each with a one-line reason. They arrive as a checklist: Accept or Dismiss each, or Accept all (one Ctrl+Z undoes it). Answers are checked strictly; anything malformed, about other shapes, or not a real stitch type is thrown away, and suggestions that match what a shape already has aren't shown.
- **Help** (F1 or ?): a user guide covering every feature, searched as you type. It works offline and with AI off. With AI on, Ask AI answers in plain words from the matching guide sections, shown above them.
- The engine keeps working while a model thinks: AI requests run in the background, so the canvas never freezes.
- Checked with a stand-in model on this PC (no real service or key): Advisor proposals appear and only accepted ones change the design; Help answers; in Cloud mode the send preview appears and Cancel sends nothing. AI settings were put back to Off afterwards.
- Not in this milestone: SAM click-to-region, Design Review explanations and palette suggestions (backlog).

### M8 Applique and layout (done Oct 11, 2026; stitch-out deferred)
- **Split across hoopings.** When a design is bigger than the hoop, Save for machine offers to split it (on by default) and shows a small map of the hoopings. LUDD saves one file per hooping ("name 1 of 2.pes", …), each centred and inside the hoop. Shapes that fit in one hooping stay whole; bigger ones are cut on the seam, with lock stitches so the cut ends can't unravel. Each hooping ends, and the next begins, with **pink alignment crosses** on the seam: re-hoop so the needle lands on them. The overlap between hoopings is under More options (default 10 mm). The hoopings are also drawn, numbered, on the design while the dialog is open.
- **Applique**: any closed shape can be an Applique (Line | Fill | Applique in the panel). It sews a placement line and stops (lay the fabric), a tack-down (zigzag or straight) and stops (trim), then a satin border over the edge, with lock stitches around each stop. Border width is adjustable; the placement line can be left out for pieces cut beforehand. **Save cut file (SVG)** writes every piece's cutting line at real size, for a Cricut, ScanNCut or Silhouette, or to print and cut by hand.
- **Repeat…** (Ctrl+Shift+D, a button by Duplicate, or the ⋯ menu): copies in a row or grid, round a circle (a carousel, each copy turned to follow it) or mirrored four ways. One undo takes them all out.
- **Knockdown stitches** (⋯ menu, Ctrl+Shift+N): a light grid of stitches under the whole design, 2 mm past its edge, sewn first in a thread you match to the fabric. It flattens towel loops and fleece pile so the design sits on top.
- **Dark mode reaches the design area.** It used to stay light grey around everything; now it's dark too, with the grid, hoop and handles drawn in light colors. Settings can keep the design on light fabric (easier for judging black and navy threads). The window no longer flashes white while it opens.
- Engine: `layout.split_plan`, `layout.export_split`, `applique.export_svg`; applique objects (`kind: "applique"`); `layout.knockdown`.
- Patent note (docs/PLAN.md): splitting is a plain grid with whole-object placement and straight seams, documented in `engine/threadline_engine/split.py`. Not legal advice; check before a public release.

### M7 Fabric profiles and quality checks (done Oct 11, 2026; stitch-out deferred)
- **"Stitching on"** in the design panel: Cotton or other woven (default), Denim or canvas, T-shirt knit, Fleece or sweatshirt, Towel or terry, Stretchy sportswear, Felt. The fabric sets the density, pull compensation and underlay of drawn satins and fills, and the panel says which **stabilizer** (and topping, for towels and fleece) to use. The advice is also in Save for machine and on the printed thread list. New designs start on the fabric used last.
- New shapes leave **pull compensation and underlay on Automatic** (a tick box under More options; untick to set them by hand, as before). Automatic underlay follows the column's width: a centre run for narrow satins, an edge run for medium ones, edge plus zigzag for wide ones, more on stretchy and lofty fabrics.
- **Geometry-aware pull compensation**: on Automatic, each satin stitch is widened according to the column's width there (wide columns pull in more).
- **Too-thin satins are widened automatically** to 1 mm, about their middle, with a note saying how many stitches were widened.
- **Checks**, in the design panel and in Save for machine, each saying why it matters and what to do, with **Show me** to jump to the spot: too much thread in one place, the needle hitting one spot over and over, many very short stitches, long loose stitches (over 7 mm), and shapes that almost touch (a line of bare fabric can open between them). "✓ Nothing to fix" when all is well.
- **Density map** (Shift+D, a tick box by the checks, or the ⋯ menu): colors the design where thread piles up, from yellow-green (two layers) through orange (the limit) to red.
- Fixed (found by the new check): a fill's move from its edge underlay to its cross-hatch underlay could be one long stitch (16 mm on a 2 cm square).
- Engine: `fabrics.list`, `layout.check` (checks, optional density map, fabric advice); `layout.preview_export` includes the checks. Lettering doesn't follow the fabric yet.

### LUDD: new name, logo, light and dark mode, Esc (Oct 11, 2026)
- The app is now **LUDD**. The logo (a hammer and a needle crossed in a hoop, with a loose thread) is in the toolbar, the welcome card, Settings and the app icon. Brand colors: ink, bone and a pale techno yellow; the wordmark uses Archivo, bundled so it works offline.
- **Light and dark mode**, logo included. Follows the computer's setting by default; **Settings** (⚙ in the toolbar, the ⋯ menu, or Ctrl+,) can fix it to Light or Dark. The window frame follows too. Settings also holds the machine, units, hoop, grid, realistic thread and Trace Assist.
- **Esc lets go** of whatever you're in the middle of, one thing per press, newest first: a drag (the shape, point or picture goes back), an open menu or font list, a value you were typing (the old one comes back), a half-drawn shape (queued Tab presses are dropped too), measuring, the drawing tool (back to Select), a selected point, the selection, playback.
- Fixed: a key shared by several commands only ever tried the first. Esc never reached Back to Select or Deselect, and the arrow keys never stepped the player when nothing was selected.
- Fixed: Esc in a number box saved the half-typed value instead of putting the old one back.
- Fixed: double-clicking to finish a shape added the last point twice (on a satin, onto the other side).
- Lettering: a project opened on another computer finds its font by name if the font file is somewhere else.

### Audit fixes (Oct 11, 2026)
- **Crash recovery is safe until you answer.** Opening or starting something else before clicking Recover no longer deletes or overwrites the recovered work; closing without answering keeps it for next time.
- **Quick edits never get lost.** A second edit made while the first was still being stitched (holding an arrow key, a recolor then a nudge) used to drop the first, and Undo could then go back two steps.
- **Added pictures and designs survive the original being moved or deleted before the first save** (or a USB stick being unplugged): LUDD keeps its own copy the moment they're added. Trace Assist keeps working too.
- Clicking into a size box and out again no longer resizes the design by a hair (and adds an undo step); same for letter height and curve size.
- "Continue drawing" (K) kept a fill's holes and a closed line's closing.
- Letter keys no longer switch tools mid-shape (A sits next to Tab); switching with the tool buttons finishes the shape first if it has enough points. R and M don't rotate or mirror a design while you're drawing.
- Measuring and a selected point are let go when their picture or shape is gone (clicks on the canvas used to do nothing). Recovering resets the tool.
- Saving "Bob v1.2" makes "Bob v1.2.ludd" (it used to make, and could overwrite, "Bob v1.ludd").
- A focused slider keeps its arrow keys, and a button or tick box reached with the keyboard keeps Space and Enter.
- Trace Assist turns phone photos the way they're shown on screen.
- An edit made while saving still counts as unsaved. "+" zooms in too. The Picture button waits for the engine. The installed program is LUDD.exe.
- Projects are now `.ludd` and stitch fonts `.luddfont`; `.thl` and `.tlfont` still open. User data moved from `%APPDATA%\Threadline` to `%APPDATA%\Ludd` automatically (thread charts, My threads, fonts, recovery). The desktop app asks for your machine once more (its window settings are stored under the new name).

### M6 Lettering (done Oct 11, 2026; stitch-out deferred)
- **Text tool** (T): click where the text goes and type. The panel has the text box (stitches update after a short pause), a searchable font list of every installed TrueType/OpenType font (206 on the user's PC), letter height in inches or mm (capital height), thread, **Satin look** or **Fill**, and the shape: Straight, Arch, Smile (under a curve), Circle, with its radius. Extra letter spacing is under More options. Realistic thread moved to Shift+T.
- **Satin look**: each letter is stitched with long stitches across its strokes (rows narrower than 7 mm are single stitches), with the angle chosen per letter to cross its strokes best; edge underlay and pull compensation. **Fill**: tatami with underlay, for big letters.
- Letters follow the font's winding rule, so overlapping strokes in script fonts are stitched once and counters (the holes in o, A, B, 8) stay open.
- **Monograms**: a tick box (or Shapes → Monogram) for three initials with a bigger middle letter.
- **Open stitch-font format** (.tlfont, JSON): letters as Threadline objects at a design height, scaled to any size. "Save this font as a stitch font…" converts an installed font for hand-tuning; .tlfont files in Threadline's fonts folder appear in the font list.
- Warnings: letters under 5 mm tall, text longer than its circle, specks too small to stitch.
- Checked: "Emma Rose" in Segoe Script at 10 mm (satin look) renders clearly legible; on an arch it fits the 4" hoop.
- Engine: `fonts.list`, `fonts.export_stitch_font`; `layout.*` accept `text` items, cached per text and per letter.

### M5 Trace Assist (done Oct 11, 2026)
- While drawing a line, fill or satin over a picture, a **ghost point** shows where the line goes next (fainter when less sure). **Tab** accepts it; **Shift+Tab** keeps accepting until a corner, a fork, an unsure spot or the start of a fill (which closes the shape). At a fork a second, orange ghost appears: **1** or **2** chooses. **[ / ]** shorten or lengthen the step (default 3 mm); **C** switches the last point between corner and curve. Clicking always works as before.
- Satin columns get both sides proposed at once, from the stroke's width at that spot.
- Classic image analysis, no AI and no network: a darkness map for line art (follows the middle of a line) and an edge map for filled shapes and photos (follows the outline); the picture's kind is detected automatically. On/off in the ⋯ menu (Ctrl+Shift+A), on by default.
- Tab presses are queued, so pressing quickly never loses one or moves keyboard focus.
- Measured against the plan's targets (70% of points by Tab, under 30 ms): a line-art circle 78/78 points by Tab (100%), each within 0.5 mm of the line; median 1.0 ms, p95 1.5 ms per suggestion (first look at a picture about 190 ms). In the app, one Shift+Tab traced a whole circle (75 points). A filled square's edges: at least 70%, stopping at each corner for a click.
- Uses Pillow and NumPy rather than OpenCV: the same results for this job at a fraction of the install size.


### M4 Digitizing core (done Oct 11, 2026; stitch-out deferred)
- **Drawing tools** (left rail): Select (V), Line (L), Satin (C), Fill (A), plus ready-made shapes (rectangle, circle, star). Left-click places a corner, right-click a curve point (as in Embrilliance and Hatch); Enter or double-click finishes; Backspace removes the last point; Esc cancels. A hint bar says what to do next ("Now click the other side of the column").
- **Snapping**: the pen snaps to existing points within a few pixels so shapes meet exactly; Shift snaps to the grid.
- **Node editing**: a selected shape shows its points (square = corner, round = curve) with its entry (green) and exit (red); drag a point, right-click it to switch corner/curve, double-click the outline to add one, Delete to remove one. **Continue drawing** (K) adds points to the selected shape.
- **Stitch types** (engine, written from scratch): running stitch (single, triple, bean); satin column from two rails with rungs at each pair of points, centre / edge / zigzag underlay, pull compensation, width warnings (over 10 mm or under 0.8 mm); tatami fill with angle, density, stitch length, staggered rows, edge and cross-hatch underlay, pull compensation, holes, self-intersection repair. Fill regions are joined by hidden travel inside the shape, routed around holes, so typical fills sew with no jumps or trims. Lock stitches at start and end.
- **Shape panel**: thread (click to change), Line / Fill switch, Single / Triple / Bean, Light / Normal / Dense, fill angle slider; More options for stitch length, spacing, pull compensation, underlay and lock stitches. Moving, turning, resizing and mirroring a drawn shape changes its points, and resizing keeps the stitch density right.
- **Pictures to trace** (Ctrl+I or drop an image): placed at hoop width with its proportions; drag, resize, rotate; see-through slider; lock so clicks pass through; hide; **Set real size** by clicking two points and typing the real distance.
- **Projects (.thl)**: New (Ctrl+N), Open (Ctrl+O, also opens designs), Save (Ctrl+S), Save as (Ctrl+Shift+S). Pictures and placed stitch files are **embedded**, with each picture's exact position, size, rotation, see-through and lock. Saves are atomic. Verified in the app: save, delete the original picture, reopen: the picture is back exactly where it was.
- **Autosave and crash recovery**: a recovery copy (pictures included) a few seconds after each change; on the next start Threadline offers to recover it. Closing or opening with unsaved changes asks Save / Don't save / Cancel. The window title shows a dot for unsaved changes.
- **Save for machine** moved to **Ctrl+E** (Ctrl+Shift+S is now Save project as).
- The hoop now stays fixed at the centre of the canvas and the grid is centred on it; designs and drawings move inside it.
- Undo covers everything in the document, pictures included.
- Engine: `image.load`, `project.save`, `project.open`, `project.autosave`, `project.recovery`, `project.restore`, `project.discard_recovery`; `layout.*` accept drawn objects (`run`, `satin`, `fill`), cached per object, consecutive same-thread objects joined without a color change (trim only when the gap is over 3 mm).
- Measured: a 96 mm fill with two holes generates in about 160 ms; a 90 mm satin in 3 ms.

### Competitive research follow-ups (Oct 11, 2026)
- Machine functions on the canvas (J): grey travel where the thread is cut, amber where a thread is left, red crosses at trims, pause signs at stops.
- Realistic thread view (T, on by default): each stitch drawn with an edge, body and sheen.
- Research findings recorded in docs/PLAN.md ("Competitive research").


### M3 Edit existing designs (done Oct 11, 2026; stitch-out deferred)
- **Layouts**: one or more stitch files placed together and edited without ever changing the files. Every edit is one undo step (Ctrl+Z / Ctrl+Y, toolbar ↶ ↷).
- **Add design** (Ctrl+Shift+O, or drop a file onto an open design) combines designs; "Designs, in sewing order" lists them with ↑ ↓ to reorder.
- **Select and transform on the canvas**: click a design to select it; drag to move; drag a corner to resize; drag the knob to rotate (Shift snaps to 15°). Arrow keys nudge 1 mm (Shift: 1 cm). R / Shift+R rotate 90°, M / Shift+M mirror, Ctrl+D duplicates, Delete removes, Esc deselects.
- **Selected design panel**: rotate and mirror buttons, width and height in inches or mm with a proportion lock, "% of original" with a warning past ±20% (stitch files don't gain or lose stitches when resized). More options: exact rotation and position, reset.
- **Colors**: change (✎) or remove (🗑) any color; ⋯ menu to combine same colors next to each other, sort colors to the fewest thread changes (with a check-overlaps note), or put back the original colors. Recolors show "was …".
- **Stitch tools** (⋯ menu): insert a stop or trim at the player's needle position, trim untrimmed jumps longer than 3 mm, add a basting box (5 mm margin, 4 mm stitches, its own first color).
- **Print** (Ctrl+P): a real-size template with centre lines for hooping, the hoop outline and 1 inch / 25 mm check bars, plus a thread list in sewing order with stitch counts and a Done column.
- **Grid**: squares centred on the hoop so a 4" hoop's edges sit on the 1" lines; spacing adapts with zoom (from 1/32" to 12" squares, or mm); covers the whole canvas at any zoom. G toggles it, U switches inches/mm (inches by default).
- **Zoom**: − / % / + / Fit controls on the canvas; = and - keys, 1 for real size (100%); zoom range 3% to about 10,000%.
- Saving for machine now saves the layout, and lists what changed ("moved, turned, new thread colors…"); the suggested name is "<design> edited".
- Engine: `layout.render`, `layout.preview_export`, `layout.export`. Rendering reports, for every stitch, which design and source stitch it came from, so edits always refer to the original files.
- Dev: the plain browser preview (`pnpm dev`) now runs the real engine through a dev-server bridge (`apps/desktop/vite-engine-bridge.ts`); the desktop app is unaffected.
- Measured: rendering Key.PES takes about 70 ms; Key + Frieren combined and rotated (41,000 stitches) about 170 ms.


### M2 Machines, hoops, threads (done Oct 11, 2026; stitch-out deferred)
- Machine profiles: built-in **Brother PE550D** (PES, 4" × 4" hoop, cuts only at color changes) and a generic Janome profile (JEF, four hoops). Add or override profiles as JSON in `%APPDATA%\Threadline\machines` (schema: `schemas/machine.schema.json`).
- Machine and hoop pickers in the toolbar, remembered between sessions.
- Hoop outline on the canvas, centred on the design (H to toggle); red when the design doesn't fit. The info panel says whether it fits, fits only rotated 90°, or is too big.
- **Cut-stops**: the PE550D has no jump-trim setting (Operation Manual 888-M36, p. 26–27), so export can turn each trim into a same-color stop. In PES a stop is a color change to the same palette color, so the machine ties off and cuts, then waits for Start. Options: minimum jump length (default 3 mm), include untrimmed jumps, lock stitches before and after each cut. The export screen shows how many stops it adds. On by default for color-change-only machines when the design has trims; also available in Batch convert.
- Export screen (Ctrl+Shift+S): format defaults to the machine's; live warnings for hoop fit, wrong format for the machine, stitch and color limits, and ignored trims.
- Thread charts: built-in Brother machine palette (64) and Janome (78); import any brand from CSV (Ctrl+T). Charts are stored in `%APPDATA%\Threadline\threads`.
- Recolor: change any thread from a chart (closest matches listed first), or "Match all…" to propose the nearest chart thread for every color by CIEDE2000, accepted per thread. Changes show "was …", apply on export, and never touch the source file.
- Engine: `machines.list`, `threads.charts`, `threads.chart`, `threads.import_csv`, `threads.delete_chart`, `threads.match`, `design.preview_export`; `design.export` and `design.convert_folder` take machine, hoop, thread and cut-stop options.
- Fixed: the canvas kept its old width when the info panel opened, covering the panel and off-centring the design.

#### Beginner-first pass ("Don't make me think")
- Toolbar is now Open, **Save for machine**, your machine, and a ⋯ menu (My threads & charts, Batch convert, Show hoop, Show jumps, Fit) that lists each shortcut.
- First launch asks "Which embroidery machine do you have?"
- Save for machine shows plain results (fits the hoop, saves as PES for your machine) and one recommended choice, "Have the machine cut jump threads", with the stop count. Format, jump length, untrimmed jumps and lock stitches are under More options.
- Info panel shows size, stitches and colors; file type, stops, trims and jumps are under More details. Thread edit buttons are always visible.
- Match results say "same / very close / close / different" instead of ΔE numbers (the number is in the tooltip).
- **My threads**: the spools you own, mixed brands allowed. Add by ticking threads in any chart ("I own all" for a whole kit) or by color with just a name (for unbranded Amazon kits). Matching prefers My threads once it has spools.
- CSV import accepts vendor-style headers such as "Madeira Code, Color Name, HEX".
- Fixed: an edit script saved `actions.ts` partly in Windows-1252, which would have shown garbled "–" and "…".

#### Cut-stops on the user's designs (3 mm minimum)
Evangelion.PES 20, Key.PES 18, Test.PES 9, Frieren.Cut.PES 8, Gunter_Jewels.PES 8, Heart.thin.PES 6, PuppyPrideFlag.PES 4, NewFrog.PES 2, BMOFACE.PES 1, both Inclusive Pride files 0 (all their trims follow color changes, which already cut).

### M1 Viewer and converter (done Oct 11, 2026; stitch-out deferred)
- Open any of the 41 formats pyembroidery reads: Open button, Ctrl+O, or drag a file onto the window.
- Stitch view in thread colors at real thread width; pan by dragging, zoom with the wheel, Fit (F).
- Info panel: size (mm and inches), stitches, colors, color changes, stops, trims, jumps; thread list with brand and number, highlighting the color being sewn.
- Stitch player: play/pause (Space), scrub, step (←/→, Shift for 100), previous/next color (PgUp/PgDn), speed ([ / ]), color-change ticks on the scrubber.
- Optional jump/trim travel lines (J).
- Export as… (Ctrl+Shift+S) to PES, JEF, DST, EXP, VP3, XXX, U01, PEC, TBF. Exporting over the original is refused.
- Batch convert a folder (Ctrl+B), optionally with subfolders. Never overwrites: existing names get " (1)". Reports converted, failed (with reason) and skipped files.
- Every action is in a command registry with a keyboard shortcut.
- Engine: `formats.list`, `design.open`, `design.export`, `design.convert_folder`; file problems return a user-facing error (code -32000).
- Golden tests on the user's own designs (git-ignored `fixtures/`): open, and round-trip to PES, JEF and DST with identical stitch positions and bounds.

#### Format decisions (from round-tripping real files)
- PES is written as version 6, which keeps thread names and brands (version 1 replaces them with the nearest Brother palette color).
- JEF is written and read with pyembroidery's `trims` option. JEF has no trim command; without it, Key.PES lost 14 of 32 trims.

#### Known limitations
- Embrilliance `.be` working files can't be opened (proprietary format). Export to PES from Embrilliance first.
- JEF: pyembroidery may write a stop without color change as a color change (seen on the final stop of BMOFACE.PES). Janome machines pause either way, but the machine lists one extra color.
- DST has no stop command, so stops become color changes. This is a property of the format.
- Trims right after a color change are dropped on export; the color change already cuts the thread.

### M0 Scaffold (done Oct 11, 2026)
- Tauri 2 + React + TypeScript + Vite desktop app (`apps/desktop`).
- Python 3.12 engine (`engine/`) speaking JSON-RPC 2.0 over stdio, with `ping` and `engine.info`.
- Engine frozen with PyInstaller and bundled as a Tauri sidecar (`scripts/build_engine.py`).
- Status bar shows engine state: starting, connected (with version), disconnected (with reason).
- CI: engine and UI tests on Windows and macOS; Windows installer (NSIS + MSI) uploaded as a build artifact.
- Fixed: in development, React's double start made the status bar show "Engine disconnected" while the engine was running.
- Verified: installer built, installed and opened on the user's PC with "Engine connected".
