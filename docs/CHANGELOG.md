# Changelog

## Next (unreleased)

### Phase 6: fills and stitch quality (2026-11-26)
- **Blend** fill: the shape's color fades into a second (and a third) across the rows. Add a color, swap them, and set the **Balance**; each color sews in turn.
- **Motif** fill (rows of a little pattern across the shape), **Maze** (one path that winds in and back out; a shape with a hole or many narrow parts sews as several mazes, and LUDD says so), **Ripple** (rings spreading from the middle) and **Mesh** (a net; set the cell size and crossing angle).
- **My motifs** (Alt+Shift+M, the ⋯ menu, or under any Motif list): save a line you drew as a motif, use it on motif lines and motif fills, import and export motif files. A shape carries its own copy, so a project sews the same on a computer without it.
- **Carved lines** (Shift+C): draw lines over a fill sewn in rows; every row drops a needle on them, so they show as grooves.
- **Turning fills** (Shift+I): draw more than one direction line on a Tatami fill, and the rows turn smoothly to follow each. A turn too sharp for the shape leaves a crease, and LUDD says so.
- In Advanced: **Weave** (Standard, Brick, Twill, Smooth or Random needle points), **Feather** (ragged row ends on the left, right or both, to blend into what's beside them) and a **Hand-sewn look** slider for lines, satins and fills (small irregularities, the same every time).
- Turning or mirroring a fill keeps its feathered side and a blend's colors where they were on the shape.
- Nothing already in your designs sews differently.
- Projects that use any of these say so, and an older LUDD asks you to update instead of sewing them wrong.
- Not built: push compensation ("End trim"), which waits on a patent check.

### Phase 5: lettering and personalization (2026-11-25)
- **Several lines of text**: Enter starts a new line (Ctrl+Enter or clicking away finishes). Align them left, center or right and set the line spacing. On an arch the lines curve together; a circle or a drawn line takes the first line only. The lettering panel's **Advanced** fold is now **More options**.
- **Slant** letters up to 30° either way.
- **Envelopes** for straight text (bulge, pinch, pennant right or left, wave, arch top, arch bottom, with an Amount slider) and **Stack the letters** top to bottom.
- **Adjust single letters** (Alt+Shift+A): click a letter's dot, drag it or use the arrow keys, and set its size, turn, thread and stitch angle. **Put the letters back** (Alt+Shift+Z). A text in several colors now lists each one in Order & colors.
- **True satin**, a third look beside Satin look and Fill: each stroke is its own satin column. A letter that doesn't work out is sewn in Satin look, and a note says how many; that happens more on large letters.
- **Small letters**: letters that sew under 6 mm tall have no underlay, so they stay thin (this changes how small text already in your designs sews). Resizing with the handles and a single letter's own size count. LUDD also warns when a font's strokes are too thin to sew.
- **Make a stitch font from letter files** (Ctrl+Alt+F, or in the font list): one design file per letter. LUDD guesses each letter from the file name, lines them up on one baseline (you can nudge any) and saves a stitched font. Past 20% bigger or smaller it rebuilds the stitches at the new size; resizing with the handles only stretches them, and LUDD says so. Only use designs you're allowed to use this way.
- **One file per name** now loads a list (CSV or text, up to 2,000 rows), fills more than one piece of lettering (a name and a number), takes thread colors and file names from columns, shrinks long names to fit, and previews each name on the design. If a name can't be saved, the others still are, and LUDD says which and why. File names are made safe for every computer (very long ones are cut). **Name templates**: save a layout (Ctrl+Alt+P) and start from it later.
- **Monograms** take one to three letters in three styles (Classic, Block, Stacked), with six frames (circle, double circle, diamond, square, scallop circle, laurel). Lines get a new **Leaves** motif.
- **Shadow** and **outline** under More options; both follow the text as you change it.
- **Placement guides** (Alt+Shift+G, or ⋯): where designs usually go on towels, pillowcases, shirts, bags, napkins and caps, with a printed placement sheet.
- **Put back the original colors** also clears single letters' own colors. A text on two lines is named on one line.
- Projects that use any of these say so, and an older LUDD asks you to update instead of sewing them wrong.
- Not built: importing BX fonts (use the letter files that came with the font).

### Phase 4: repair bought designs (2026-11-25)
- **Repair this design** (Ctrl+Alt+D, a stitch file's Repair section, or **Fix it** on a check): tick the repairs, compare before and after numbers, **Show on the design** marks in red what would change, and nothing changes until **Accept**. Your stitch file is never changed, and each repair can be taken off again.
- **Rebuild stitches at a new size** (Alt+Shift+R): a resized bought design's fills, satins and lines are sewn again with their original spacing, so it's neither too dense nor too sparse. The resize warning suggests it.
- **Remove tiny stitches** (Alt+Shift+S) and **Thin out dense spots** (Alt+Shift+D), where the needle hits one spot over and over.
- **Limit density for this fabric** (Alt+Shift+L): fills and satins denser than the "Stitching on" fabric takes are made again at its normal spacing.
- **Fix it** buttons on the checks for very short stitches, needle clumps and thick spots in a stitch file.
- **Edit stitches** can add a stitch (Insert), turn a move into a jump (Shift+Insert) and lock both sides of a jump (Alt+Shift+T). Right-click selects the stitch first; stitches a repair or a lock added can't be picked.
- **Needle path view** (Shift+P): hairlines with a dot at every needle point, whatever the zoom.
- **Don't sew what's hidden under shapes on top** (⋯ menu, Alt+Shift+O), for shapes drawn in LUDD: fills leave out what a shape sewn later covers, keeping 1 mm under its edge (adjustable in the Design section). That kept edge is sewn by both shapes, and a short travel line can show across a lower fill (a known weak spot).
- Fixed: the note that an added stitch, jump or lock no longer fits now shows on the design.
- Not built: removing the hidden stitches of one stitch file under another (waiting on a patent check).

### Phase 3: spiral fill, more shapes (2026-11-24)
- **Spiral fill**: a new fill pattern that winds one line from the middle of the shape out to its edge. Set how far apart the rings are (Ring spacing).
- **More shapes**: the Shapes menu adds a rounded rectangle, an oval, a triangle, a polygon (you choose 3 to 12 sides) and a heart (Ctrl+Alt+4 to 8).
- **Behind the scenes**: the stitch engine and the panel were rearranged so new stitch types and tools can be added without touching the old ones; one command (`python scripts/check.py`) runs every check. Nothing that already existed sews differently.

## 1.0.1 (Oct 11, 2026)

### Sewing time and thread estimate (2026-11-24)
- **Design** section: **Sewing time** (about how long the machine sews at its top speed, plus how many thread changes) and **Thread** (top and bobbin). **Thread used** lists each color with about how much it uses, so you can check the spool before you start.
- Machine profiles have a new optional `speed_spm` (stitches per minute): 650 for the Brother PE550D and the generic Janome; 600 is assumed when a profile doesn't say.

### Phase 1 audit fixes (2026-11-24)
From docs/PHASE1-AUDIT-REVIEW.md. No stitch output changed.
- **S (Zoom to the selection)** with several things selected zooms to all of them (it zoomed to just one).
- **AI key**: the key file is written whole and readable only by you from the moment it's created (on a Mac or Linux it was briefly readable by other users, and a crash mid-save could leave half a file). Moving the key into the system keychain is still on the backlog.
- **Behind the scenes**: the developer-only browser preview's engine bridge refuses requests over 1 GB and no longer waits for an answer to a message that never gets one.

### QA pass 2 decisions (2026-11-24)
The owner's ten decisions from docs/QA-REPORT-2.md. Items 1-4 change stitch output (rows in docs/stitchout-log.md):
- **Thin necks in fills**: travel inside a fill follows its edges even where part of the shape is narrower than about 0.6 mm (it jumped, with a trim, across bare fabric and bounced between the two halves). A fill never ends on a jump, and the lock stitches at the end of a shape always come before any trim or jump (they could make one 10-15 mm stitch).
- **Zigzag underlay**: the way back always crosses the way out, like an X (on about half of wide satins it sewed the same zigzag twice).
- **Applique**: a move of more than 3 mm between edges (holes, separate pieces) is marked for trimming, as in fills. With cut-stops on, that can add machine stops.
- **Sharp corners**: with Split long stitches on, wide satin ribbons and applique borders get an extra needle point at sharp corners, so no stitch passes the Longest setting (they reached 8.6 mm).
- **Edited stitch files keep their edits on the right stitches**: once a placed stitch file has edits (colors changed, colors or stitches deleted, stops or trims added, stitches moved), it sews from LUDD's private copy taken when it was added, even if the original is saved again in another program. Without edits it still follows the file. Old projects open as before.
- **Samples**: the ready-to-sew sample PES/JEF files are made again from their projects, and a test checks that each sample project still sews like its PES.
- **Ctrl+Z while drawing** removes the last point you placed (like Backspace) and leaves the rest of your work alone; Ctrl+Y does nothing until the shape is finished.
- **Behind the scenes**: a test fails when a Tauri plugin's Rust and JavaScript halves are on different versions; CI builds and tests the Rust code on a Mac on every push, and releases run the Rust tests on every system; this changelog uses US spelling throughout.

### QA pass 2 (2026-11-24)
A second full review (docs/QA-REPORT-2.md). Fixed:
- **One tool at a time**: the knife, stitch editing, the measuring tool (M) and the angle line (I) no longer stay on together (two clicks "to measure" cut the shape). Starting one ends the others; picking a drawing tool ends stitch editing; the angle line ends when its fill is deleted or undone.
- **Late engine answers**: the knife, merge, outlines and Optimize jumps no longer bring back an undone shape or lose a nudge made while they worked; they say "The design changed while …: try again". In Auto-trace, clicking the next shape while the last one is still being added keeps the new guess on screen.
- **Ctrl+X** with nothing selected on a one-shape design now cuts the shape (it only copied). If a delete fails, what was selected stays selected.
- **Sewing order**: dragging a row ends properly when the mouse is let go outside the window or the panel closes. **Sew in the shortest order** groups threads exactly as the saved file does (it could add a color change).
- **Projects**: damaged parts of a project are left out with a note instead of leaving the design blank; very large or hostile project files are refused (over 64 pictures, or 768 MB unpacked). Added designs and pictures whose originals are gone keep working after the engine restarts (it forgot its private copies).
- **AI add-on**: LUDD never follows a redirect from an AI service, so your key can't be sent on to another address.
- **Thread charts**: importing a chart never replaces one with a different name (every non-Latin name, and names like "Isacord 40" / "Isacord-40!", shared one file).
- **Tracing**: a very small picture traces quickly (1 mm wide took 50 s); a picture under 0.5 mm, or a damaged placement, says so plainly; a 1-pixel picture finds nothing instead of failing. Settings → AI tracing now really checks that the AI can run on this computer.
- **Stitch settings**: odd satin and line settings (empty or text values) and bad points in holes give plain messages (a hole with a bad point was silently sewn over). With Split long stitches on and Longest over 7 mm, the warning says to set Longest to 7 or less (it said to tick the box already ticked). No stitch output changed.
- **Docs**: the knowledge base lists the 40 formats LUDD opens (it said 47); stale section links, US spelling, Help's "Color sets" place, Browse designs' Refresh.
- **Behind the scenes**: the engine smoke test checks that ONNX Runtime loads; tests check that every version number agrees, guides and color sets survive saving, and the whole-picture flow. Dependencies updated on Nov 15: the Tauri updater (2.14), shell (2.6), dialog and process plugins, `@tauri-apps/api` 2.12, PixiJS 8.23, React 19.3, Zustand 5.1; TypeScript 7, vitest 5, jsdom 31 for tests; CI fixes for macOS and the engine smoke test. To check in the installed app before release: installing an update, and Show in folder.
- Decisions left to the owner (stitch output and process changes) are listed in docs/QA-REPORT-2.md.

### QA decisions (2026-11-14)
- **Pinned shapes** also ignore the arrow keys, R and Alt+H/V (a note says it's pinned); pinned pictures ignore the arrows with the same note.
- **Browse designs** has a **Refresh** button.
- **The AI send preview** also shows LUDD's fixed instructions to the AI.
- **The AI tracing model download** is pinned to one upstream revision and each file is checked against its SHA-256; an older download that doesn't match is fetched again.
- **Spelling**: the app and its docs use US spelling (Center in the hoop, Millimeters, Licenses, color).
- **Repository**: GitHub Actions are pinned by commit SHA, and Dependabot proposes monthly updates.
- **Tests**: panels can now be tested in a browser-like page (jsdom): name the file `*.dom.test.tsx` and start it with `// @vitest-environment jsdom`.
- **Docs**: AGENTS.md matches the app (networkx, onnxruntime, schemas, light fabric). Decisions on the 20 open QA items are in docs/QA-RESPONSE.md.

### Self-audit fixes (2026-10-13)
A review of the whole app after the changes above; fixed:
- **Satins**: a start point off the satin (left behind when its points were moved) no longer sews a line across bare fabric; a dragged start now lands on the satin's nearest stitch. Moving a satin's tips or turning it another way (Shift+W) drops the old start and end, which no longer fit.
- **Fills in several pieces** (a hole cutting them in two) end on the piece the red dot is on.
- **Optimize jumps** can again improve lines and satins whose dots were moved by hand.
- **Lettering**: letters hand over to each other only where they're fills (a stitch-font satin stroke is never split to meet a point); moving only a letter's end keeps its automatic start; One file per name and Put the text on the line don't carry the chosen starts and ends to the new letters; clicking the look or shape already chosen no longer resets them. New command **Reset the letters' starts and ends** (Ctrl+Alt+R). Break into shapes keeps the lettering's pin and group and says if its stops and trims were left out, and builds on the newest design.
- **Pinned shapes**: their points and dots can't be dragged, deleted or added any more (only their outline shows).
- **Dots**: a dot let go stays put until the new stitches arrive (it used to jump back for a moment), and is never drawn on another shape picked meanwhile; double-clicking a dot doesn't edit the outline; the frame's handles win over letter and direction dots on top of them; a satin's purple tips sit clear of the side handles; dots aren't drawn where they can't be dragged (several selected, applique). Contour, stipple and cross-stitch fills show their red dot but it can't be moved (their pattern decides where they end).
- **Engine answers that arrive late** (moving a dot, satin tips, Satin fill, Shift+W, Break into shapes, Cut out) are dropped if the shape was changed or undone meanwhile, instead of overwriting the newer edit.
- **Groups**: a picture underneath doesn't take a drag inside the group's frame; Shift+click on empty space keeps the selection.
- **Arrow keys** nudge the selected shape even while a drawing tool is still chosen (they moved the view instead). Esc while drawing a hole goes back to the tool and the fill. K (add points) works right after drawing.
- **Commands** are only offered where they work: Cut a hole and Set the stitch angle for fills, Add a satin border for fills and closed lines, the knife for fills, lines and ribbons, Cut out with two or more selected. Alt+T also recolors several selected one-color stitch files.
- **Order & colors**: a changed color can be put back (**Back to …**); right-clicking a row selects it alone; Match… leaves the basting box and knockdown alone (its count was off); with neither on, no stray "Basting box" row. The thread picker forgets the last search and mixed color when it closes and never shows the previous thread's matches; "Found in" sees newly added spools; words like "facade" aren't taken for color codes. The context menu scrolls instead of closing in a short window, and opening it no longer resets an open thread picker.
- **Knife and Cut out** pieces get their own start, end and direction (each used to copy the whole shape's); Cut out pieces keep the color change, pin and group.
- **Stitch Advisor** looks at shapes where they are now (moved, turned, resized), not where they were drawn.
- **Auto-trace**: a drawn shape inside another's hole is no longer ignored when fitting guesses around your shapes.
- Picture right-click menu: "See-through stitches (all)" and "Show pictures (all)" say they're for every picture, plus **Hide this picture**. The panel's ⋯ menu has Change thread, Center in the hoop, Sew first / last, and for lettering Change the words and Break into shapes.
- Docs: PES re-save note in the manual, guide and Help; missing shortcuts added; leftover "Threads" wording.

### Knowledge base for a help agent
- **`docs/LUDD-KNOWLEDGE-BASE.md`**: every feature, shortcut, limit and known problem, sorted for a help agent (IDs, yes/partly/no status, a capability index, troubleshooting, a glossary of Embrilliance names, the change history and the full command list). `docs/LUDD-HELP-AGENT-INSTRUCTIONS.md` sets up a separate help agent that answers from it and writes change requests. `scripts/kb_commands.py` regenerates its command list; a test checks it's complete.

### Order & colors, and better groups
- **Threads and Sewing order are one section, Order & colors**: every step in sewing order with its thread. Click a step's color square (or ✎) to change it; a stitch file's colors are listed under it, numbered as the machine shows them, each with ✎ and 🗑. A **Palette** at the top shows each thread in use once: click one to change it everywhere. Match…, color options and color sets moved with it.
- **Several selected are all highlighted in the list**, and Shift+click (or Ctrl+click) a row adds it to the selection or takes it out. Clicking a grouped row picks the whole group (▣ marks grouped rows).
- **One thread for everything selected**: changing the thread of one selected thing (its ✎ in the list, the new 🧵 button at the top of the panel, right-click → Change thread…, or Alt+T) changes all of them. A stitch file with several colors keeps its own.
- **Fixed: a group couldn't be dragged from the space between its pieces**: a click inside the group's frame grabbed the background. Dragging anywhere inside the frame now moves the whole group.

### PES files sit in the middle of the hoop on the machine
- **Fixed: on the PE550D a PES file saved by LUDD showed whole in the file list, but once opened it sat up and to the left, mostly outside the hoop, and couldn't be moved back.** LUDD wrote the design centered on (0, 0); Brother machines read a PES design from its top-left corner, as Embrilliance and PE-Design write it. PES files now run from (0, 0) like theirs, and the machine centers them in the hoop. Save your designs for the machine again (the stitches are the same, only their position in the file changed). JEF files were not affected.

### Satins start and stop anywhere; lettering has a start and end per letter
- **Fixed: a satin's start and stop dots were stuck at its two ends.** A satin (ribbon, column or satin fill) now starts and stops wherever you drag its dots along it: to stop part way it's sewn in two parts that meet there, and every move between parts runs along its middle under satin sewn later. On a wide satin it ends on the side the dot is on.
- **Lettering shows every letter's start and end** (small green and red dots) when it's selected; drag one along the letter's edge to move it, and **Reset starts and ends** puts them back. Letters now hand over to each other: each starts by where the one before ended and ends towards the next, so jumps between letters are shorter (in the tests, the trims between the letters of "IOX" went from 2 to none).
- The Lettering panel says how the letters are stitched (Satin look: long satin stitches across each letter's strokes; Fill: woven fill).
- **Break into shapes** (Ctrl+Alt+X, in the Lettering panel and on the right-click menu): lettering becomes ordinary shapes, one per letter part, grouped and in place, keeping their starts and ends, to edit one by one.

### A looped line set to Satin fills the shape
- **A line drawn all the way round (closed, or ending where it began) set to Stitch as → Satin is now one satin column filling the shape**, like a fill set to Satin, instead of a satin ribbon round its edge. For a satin outline round it, use Add satin border (Shift+B).

### Start, stop and direction dots on the design
- **The green (start) and red (end) dots follow the edge as you drag them**, like a magnet, and stay exactly where you let go. A fill can start anywhere on its outside edge and stop anywhere on any edge: its rows are planned so the last one finishes there (the rows before it are sewn towards it, and the move on to the far rows is covered by them, so nothing crosses the finished stitching). A closed line or border starts exactly where you put it. An open line's dots move its end points; drop one on the other end to sew the line the other way round.
- **New purple direction dots**: on a fill, two dots on its outline with a line between them show the way the rows run; drag either one round the edge to set the stitch angle. On a satin column or satin fill, the purple dots (just past each end) are its tips: slide them round the outline and the satin is rebuilt to run from one to the other.
- A fill's start, end and direction dots move, turn and resize with it (before, a fill's start point stayed behind when it was moved).

### Right-click menus
- **Right-click anything** for what you can do with it, each with its shortcut: a shape (change thread, cut / copy / duplicate / remove, add points, cut a hole, knife, satin border, outline, sew first / earlier / later / last, turn, mirror, center in the hoop, repeat, pin, rename, zoom to it, Stitch Advisor), several shapes (group, merge, cut out, text on a line), lettering (change the words, one file per name), a stitch file (edit its stitches), a picture (auto-trace, pin / unpin, see-through, hide, remove) and the empty canvas (paste, select all, draw, shapes, add a picture, zoom, view options). Right-clicking selects the thing first. A right-click still finishes a shape while drawing, uses the guess in Auto-trace and switches a point's kind.
- **Rows in the panel too**: a step in the Sewing order, a color in Threads (change it, remove its stitches, match all, color options) and a picture in Pictures.
- New commands, also on the keyboard: **Change thread…** (Alt+T), **Sew earlier / later** (Ctrl+[ / Ctrl+]), **Sew first / last** (Ctrl+Shift+[ / ]), **Center in the hoop** (Ctrl+Shift+M), **Change the words** of lettering (Ctrl+Alt+W).

### The tool you chose stays chosen
- Auto-trace, Text and a hole (O) no longer drop you back to Select: after using a guess you can click the next shape straight away, and after placing text you can click to place more (clicking a text picks it). V or Esc still go back to Select.

### Thread search
- **Search threads by color code**: type #FF7A1A (or FF7A1A, or #F70) in Change thread and the chart is listed closest first, with **Use exactly #FF7A1A** for that exact color. Thread numbers come exact match first.
- **A number that isn't in this chart** says which of your other charts has it, one click to switch.
- **Or mix your own color**: a color picker under the list, for a thread you don't have a chart for. The thread's own color code shows next to its name.

### Auto-trace sees the whole design
- **Guesses fit around what you've already made**: a guess that runs over shapes you've drawn or traced comes cut around them (tucked 0.3 mm under, so there's no gap and nothing is sewn twice), labeled "fitted around your shapes"; Tab still offers the whole area, "over your shapes". Click on a shape you've made to trace that spot again as it is.
- **The AI tracing model is told what's already there**: the shapes nearest your click are "not this" to it, so its outline stops at them instead of swallowing them.
- **The Stitch Advisor sees the neighbors**: each shape's picture now shows the shapes around it in their thread colors, so its advice fits the design as a whole.

### Settings in a small window
- Settings (and every dialog) scrolls with the mouse wheel when the window is too short to show all of it; before, the bottom of Settings could be out of reach.

### Pictures in one place
- The panel's **Picture** and **Pictures** sections are one: **Pictures** lists your pictures, and the selected picture's see-through and real-size settings open right under its name.

### Stretch handles
- **Side handles** on the selection frame stretch a shape one way only (wider or taller), the opposite side staying put; several selected things stretch together. The corners still resize evenly.
- **The resize pointer points the right way at every corner** (it showed the same diagonal at all four), and ↔ / ↕ on the sides.
- Resizing several things together keeps each one exactly in place relative to the others.

### Optimize jumps, density slider
- **Optimize jumps** (Ctrl+Alt+J, next to Sew in the shortest order): keeps the sewing order and chooses where each piece starts and ends, so same-color pieces hand over to each other like magnets (on the Flower sample, 132 mm of jumps became 45 mm, all tucked under the center). Lines and satins are turned round, borders start at the nearest point, fills start at the nearest edge.
- **Density is adjustable again in view**: a Lighter ↔ Denser slider with its number under it (mm between rows and rows per mm, or per inch), updating as you drag, plus the exact spacing to type, under Light / Normal / Dense for fills and satins.

### Satin fill, holes, Shapes menu
- **Satin fill**: set a closed shape to Stitch as → Satin (or choose Satin fill in Auto-trace) and it's filled with one satin column that turns and changes width with the shape, as in Embrilliance: petals, leaves and swooshes sewn as shape-shifting satin. Shift+W turns the stitches another way. Wide ones split their long stitches. (Before, Satin made a ribbon round the outside.)
- **Cut a hole** is a button in a fill's section (and in Shapes and ⋯, O as before). **Cut out with a shape** (Shift+O): put any shape over a fill, select both, and it's cut out: a hole, a bite or separate pieces.
- **Shapes** on the tool rail opens a proper menu beside the rail (it used to be cut off in a scrolling strip).

### Sewing order, see-through stitches, satin edge fit
- **Drag and drop in the Sewing order**: drag a row by its grip (⠿) up or down; the other rows make room as you go, Esc puts it back. ↑ ↓ still move one step.
- **See-through stitches** (Shift+N, or the ◐ button by the zoom): the thread is drawn faint so you can see the picture you're working over.
- **Satin borders that fit the edge**: draw a satin along the edge of a shape you've made and LUDD offers to fit it. Tab lays it exactly along the edge, round corners and curves; Tab again tries all the way round, just outside the edge, or only the part you traced; Esc puts your clicks back.
- Clicking a button on the toolbar, tool rail, zoom or player no longer keeps the keyboard focus, so Enter, Space and Tab still go to your drawing (before, Enter could press the last button clicked instead of finishing the shape).

### Realistic thread, redone
- **Thread looks like thread at every zoom.** Each stitch is shaded round with a glossy highlight and visible twist, lit from one direction (upper left) whichever way it was sewn; stitches dip into the fabric at the needle holes, so fill patterns show; every shape casts a soft shadow on the fabric and on the shapes under it, so later layers look raised. Zoomed out, threads are smoothed instead of sparkling.
- **The design sits on light fabric by default**, in dark mode too (as the shadows and colors need); Settings → Always show the design on light fabric turns it off.
- **A stitch file opens in the middle of the hoop.** Many PES files start at a corner, so they used to appear off to one side (they always sewed centered). Added designs land in the middle too, a little down and right of the last one.

### Mouse pointers
- **LUDD has its own mouse pointers**, and each one says what a click or drag will do there: select and move, drag a point, resize, turn, move a guide, move the view, and a crosshair with a badge for each drawing tool (line, satin, fill, text, knife, measuring, stitch angle, stitch editing). While drawing, the middle of the crosshair shows the kind of point the next click makes. Auto-trace has a wand. See "The mouse pointer" in the manual.
- Fixed: after pointing at a ruler or a guide, the "resize" arrows stayed on as you drew.

### Fixes from the QA review, phase 4: everything else
The Medium and Low findings, area by area (details in `docs/qa-phase4/`).

**Auto-trace**
- **Much faster on busy pictures**: clicking a line in detailed line art takes about a second the first time, then is instant; Whole picture is 3 to 5 times faster.
- **Click inside a solid black shape** and Auto-trace offers "Fill, this dark area".
- **Whole picture, cleaner results**: one thread per real color (all dark parts share one black, JPEG shades merge); bold lettering is one fill per letter; no thin ring fills from soft edges; satin outlines reach the ends of the lines.
- **Leave out the background** works on dark backgrounds too, keeps shapes that touch the edge, and no longer sews the paper inside letters and rings.
- **Whole picture's bar** has its own Points every and Spread; the preview follows them and the picture's place.
- **Pictures**: 16-bit gray PNGs trace correctly; huge pictures use far less memory (one too big says so); a picture changed in another program after you added it is no longer traced or saved instead of the one you see.
- **AI tracing**: if the model can't run, Auto-trace says so and still shows its usual guesses; a broken-off download says what went wrong and leaves nothing behind.

**Stitches & fills**
- **Every piece is sewn**: fills and appliques whose outline crosses itself, or that a hole cuts in two, no longer leave part bare; the underlay reaches every piece and runs round holes.
- **Stipple** fills every part of the shape (and says when a part is too thin); moving it no longer reshuffles the pattern.
- **Cross-stitch** looks like little Xs (no bars, far fewer threads over finished crosses); big squares get a needle point mid-diagonal.
- **Contour** finishes one part at a time, keeps its corners, and is much faster on jagged outlines. **Gradient** really fades out.
- **Spacing under 0.3 mm** really sews denser; no double needle drops where rows and travel meet; travel keeps to the shape's corners.
- **Heavy fabrics** (knit, fleece, towel, stretch) get a firmer fill base; wobbly outlines and many holes fill several times faster.
- **Applique** borders sew at the spacing you set; wide borders are split automatically.
- **Knife**: one cut across a closed line gives two pieces; pieces keep their colors, stops, pin and group; small holes are kept; clicks snap; a missed cut leaves the knife ready. **Merge** keeps the first-selected shape's settings and refuses shapes that only meet at a corner.
- **Outline / offset** no longer follows hidden travel and rings small holes too; an empty inset says to come closer to 0.
- **Shape panel** shows only the settings each pattern uses; fill length up to 7 mm; no lock-stitch boxes on appliques (they did nothing).
- A shape far bigger than any hoop (a typing slip) is refused with a message instead of freezing the engine.

**Satin**
- **Split long stitches** splits the underlay too, and no piece is longer than Longest. Satins warn from 7 mm (was 10) unless split.
- **New warnings**: a satin curving tighter than it is wide, satin sides that cross, a line too short to sew. Ribbons are at least 1 mm wide.

**Lettering**
- **Missing letters** are left out with a message naming them (no more stitched question marks).
- **True letter height** in every font (some scripts were up to a fifth off); modern fonts' kerning is used; © and ® stitch completely.
- **Satin-look stitches stay across the strokes** when lettering is turned, mirrored, curved or put on a line; no false "long stitches" warning on big letters.
- **Circle** goes all the way round; **Smile** letters no longer bump; straight text keeps its baseline.
- **Text on a line** reads upright whichever way the line was drawn, stands outside a closed shape, and stays on the line whatever its turn or size.
- **Fonts travel with the project**; the fabric preset adjusts lettering; moving lettering is instant; small-text advice is now 6 mm.
- **Save as stitch font** saves every letter with accents and kerning straight into LUDD's fonts folder, ready in the font list; damaged stitch fonts give a clear message.
- **Lettering panel**: typing is never undone by a slow update; Esc brings back the text from before; the font list says when it shows only 200.

**Layout & sewing order**
- **Sort colors** never sews a shape before the one meant to be under it; colors that can't be gathered safely stay apart, with a note.
- **Sew in the shortest order** works with Fewer jumps & trims on, mixes fills and lines, and only keeps overlapping shapes in order. Fewer jumps & trims hides a move only under rows close enough to cover it.
- **Stops and trims** can be inserted in lettering, survive deleting their stitch, and leave a note if their shape changes. **Trim jumps longer than 3 mm** covers designs added later.
- **Knockdown**: pick its thread with the ✎ in Order & colors (then the Threads list). The basting box comes in closer to fit the hoop.
- **Stitch editing**: Delete with nothing selected no longer deletes the design; a drag is one edit.

**Splitting & saving for the machine**
- **Split**: the overlap setting is the real overlap; empty hoopings are left out; pink crosses go on bare fabric; single-stitch dots are kept; fewer lock stitches at the seam; earlier files are never replaced.
- **"Make it N% smaller"** for a design just a little too big for the hoop.
- **JEF**: long stitches are sewn in pieces (no needle-up jumps) and the design is centered on the hoop.
- **Safer files**: never half-written; accented thread names stay readable in PES; over 255 PES color steps or nothing to sew is refused with an explanation.
- **Cut-stops**: Save for machine says when long jumps aren't marked for trimming (so won't be cut). Thick spots inside bought designs are a note, not a warning.
- **One file per name** saves the other names when one fails, and says which. **Batch convert** into the folder it reads from works.

**Projects & safety**
- **Opening a project** says plainly when it's missing, in use, damaged or from a newer LUDD; an older LUDD asks you to update instead of sewing a newer project wrong. Reopened designs keep their real names.
- **A project's machine and hoop apply to that project only**; your usual machine stays the default.
- **Saving** waits when antivirus or OneDrive holds the file, works in very long folder paths, and cleans up after an interrupted save.
- **Crash recovery**: Recover only says "recovered" when the work is back; an unreadable copy is kept aside; autosave keeps going if a picture's file is gone.
- **My threads and charts** are saved safely; one broken file no longer hides the others. Old Threadline data is brought over even if a Ludd folder exists.
- **Projects can't make LUDD read files outside them**; damaged or oversized projects and pictures over 120 megapixels are refused plainly. Private copies unused for 90 days are deleted.
- **AI**: an Ollama on another computer shows "what will be sent" first; the dialog names where it goes; cloud addresses must use https; on Mac and Linux the key message is true for them; broken AI settings no longer stop every AI feature.
- **The engine keeps running** after a damaged request; a real bug says "Something went wrong in LUDD's engine… Please report this."

**Working in the app**
- **Esc**: holding it lets go of one thing; with a dialog open it only closes the dialog; in an AI-settings box it puts the old value back.
- **Quick edits don't lose each other**; a change that changes nothing isn't an undo step; Close and Open ask about an edit still updating, and Save waits for it.
- **Duplicate** copies everything selected; emptying a number box puts the old value back; "Added" or "Merged" only appear when it worked.
- **Option-key shortcuts** (Alt+A, Alt+H, Alt+V, Alt+D, Alt+[ ]) work on a Mac. F5, Ctrl+R and the browser's right-click menu no longer reload the window.
- **Zooming** a big design is smoother and keeps a dragged shape under the pointer; points snap to guides with snap to grid on.
- **Design browser**: typing a name searches the whole folder; folder shortcuts no longer loop.
- **Settings → About → Licenses…** lists the licenses of the software and fonts LUDD includes. In-app Help matches the manual again.

**Installer & updates**
- **On a Mac**, double-clicking a .ludd opens it, Cmd+Q asks about unsaved changes, and LUDD needs macOS 14 or newer (it says so at install).
- **Updates**: unticking "Tell me when a new version is out" on the first-run card is respected; offline, Check for updates says to check the connection.
- **The installer includes the licenses** of the libraries and fonts LUDD uses.
- Behind the scenes: every build starts the packaged engine once to check it; CI tests Windows, both kinds of Mac and Linux; more stitch-outs are pinned by tests.

**Small fixes**
- **Shift+,** (stitch out at machine speed) works.
- **Shapes** from the Shapes menu start with your remembered fill settings.
- **Backspace** with a point selected removes just the point.
- **Hidden pictures** (B) can't be clicked or dragged by accident.

### Fixes from the QA review, phase 3: the installed app and releases
- **No more 180 MB left in the temp folder each time you quit.** LUDD now lets its engine stop by itself so it cleans up, and the engine deletes folders that earlier crashed or killed runs left behind (only its own, and only ones no running copy is using). (C23)
- **Double-clicking a project while LUDD is open** opens it in the window that's already open, instead of starting a second LUDD that showed a false "LUDD closed without saving" message. A project double-clicked while there's work to recover opens after you choose Recover or Discard. (C24)
- **If the engine stops**, LUDD starts it again by itself, and the status bar has a **Restart engine** button; your work stays on screen and can be saved. An engine that fails to start is no longer left running. (C25)
- **Updates**: the update file now points at the release's permanent download links (before, they stopped working once the release was published, so updating failed). (C11)
- **Intel Macs**: LUDD builds and runs without the optional AI-tracing runtime, which has no Intel Mac version; Settings says so. (C21)
- The engine tests pass on a fresh copy of the code (they no longer need the owner's private designs). (C26)

### Fixes from the QA review, phase 2: broken features
- **Knife and merge** work on shapes as you see them after a move, turn or resize (before, a cut missed or landed in the wrong place, and merging a copy lost it). **Ctrl+D** copies of drawn shapes now carry no hidden offset. (C13)
- **Outline / offset** round a whole design takes 1-2 s instead of 10-20 s (it used to time out). (C14)
- **Measuring tool** shows the distance (and how far across and down), and is in the ⋯ menu. (C16)
- **Dragging** a shape no longer fails silently when the design finishes redrawing mid-drag. (C17)
- **Holding an arrow key** moves smoothly: a few redraws instead of one per key repeat, and the whole move is one undo step. (C18)
- **Text tool**: the new text box is ready for typing, so the first keys you type replace "Text" instead of running shortcuts (Backspace no longer deletes the new lettering). (C20)
- **Stitch Advisor** works on satins drawn with the Satin tool (it used to fail), and can turn a line into a satin ribbon or back. (C10)
- **Printing** (template and thread list) keeps its styling in the installed app. (C22)
- **Text on a line** warns when the text is longer than the line.
- **Stitch editing**: moved stitches turn and resize with the design afterwards.
- MobileSAM's license is Apache-2.0 (it said MIT).

### Fixes from the QA review (docs/QA-REPORT.md), phase 1: stitch-out and data safety
- **Splitting across hoopings keeps every stop** (applique placement and tack-down, stops you added) in each hooping's file. Before, they were dropped and the satin border sewed onto bare garment. (C1)
- **Splitting keeps the layering across hoopings**: runs are cut at the seams, and a run is sewn whole only where that can't put a lower layer on top of a higher one in a later hooping. (C5)
- **Fewer jumps & trims**, rebuilt: no more crash on thin running stitches (C2); about 100× faster (no work unless two same-thread shapes are joined; covers cached; C3); judged on the final sewing order, so Sort colors can't leave travel stitches on top (C6).
- **Deleting every stitch of a color** removes that color from the file; the thread list no longer shifts (C4). Deleting everything is refused with a message.
- **Wave fill** rows no longer cross each other (they ripple together; C15).
- **Applique holes** get their own placement, tack-down, satin edge and cutting line (C8).
- **Missing fonts**: a project whose font isn't installed opens, showing that text in a standard font with a warning (C7).
- **One file per name** uses your machine's settings (cut-stops, hoop check), reports names too wide for the hoop, never replaces existing files, and picks your machine's file type each time (C12).
- **Saving no longer deletes a crash-recovery copy** that's still waiting for Recover or Discard (C9).
- **An edit made while a project is still opening** no longer makes the next Save overwrite the previous project (C19).

### Features from comparing LUDD with Hatch
- **Auto-digitize the whole picture** (Alt+A, ⋯, or Whole picture… in Auto-trace): every area of color becomes a fill in the picture's color, solid dark areas become fills, and the dark lines become satin ribbons along their middles (thin ones running stitch); big areas first, outlines last. A preview first; Add all or Dismiss.
- **Outlines & offsets** (Ctrl+Shift+K): a satin border, line or triple line a set distance around anything selected, following its stitches (lettering, stitch files, groups), optionally round holes too.
- **Knife** (Shift+K): cut a fill, line or satin ribbon along a line into pieces. **Merge** (Ctrl+M): join touching fills into one.
- **Fewer jumps & trims**: moves between same-thread shapes that will be covered by later stitching are sewn as hidden travel instead of a jump and trim (on for new designs; Ctrl+Alt+T or the Design section). **Sew in the shortest order** (Ctrl+Alt+O) reorders separate same-thread shapes.
- **Fill patterns**: Gradient (dense to sparse), Wave, Contour (rings following the outline), Stipple (one meandering, never-crossing line: quilting style) and Cross-stitch, besides Tatami. **Motif lines**: wave, zigzag, scallop or blanket stitch repeated along a line.
- **Stitch editing** of placed stitch files (Ctrl+Alt+E): click, Shift+click or box-select stitches, drag to move them, Delete to remove; kept as edits in the project.
- **Browse designs** (Ctrl+Alt+B): a folder of designs as thumbnails with size, stitches and colors; open or add.
- **Lettering**: text along a line you draw (Ctrl+Alt+L); **One file per name** (Ctrl+Alt+N) saves a machine file for each name in a list.
- **Color sets** (colorways) in Threads (now Order & colors): save, switch and delete sets of colors. **Preview on** a T-shirt, tote, towel, bodysuit or cap in a fabric color.
- **Rulers and guides**: drag guides from the rulers (Ctrl+R), drop them back to remove; points snap to them; saved in the project.

### Other 1.0.1 changes
- **Fixed: the design area stayed blank (gray) in the installed app.** The installed app runs under a strict security policy that forbids building code at run time, which the drawing library (PixiJS) does by default; the development version doesn't have the policy, so it never showed there. LUDD now loads PixiJS's add-on for this, so the policy stays strict. A test fails if that ever goes missing, and if the design area can't start for any other reason LUDD now says so instead of showing gray.
- **The Windows installer shows the LUDD logo**: on its welcome and finish pages, in the banner on the other steps, and as its icon. (`scripts/make_installer_art.py` makes the pictures.)
- The PDF manual (`docs/LUDD-User-Manual.pdf`) and the script that makes it.
- **The right panel is reorganized into folding sections** (two levels, no tabs). What you select opens its own section (Fill, Satin, Line, Applique, Lettering, Stitch file, Picture) with everyday settings in view and smaller folds inside for Underlay, Advanced stitch settings, lettering Shape and Advanced, and a stitch file's Rotation and position. Then Size and points, Design (with the fabric and File details), Threads, Sewing order, Check before stitching and Pictures. Closed headings show a one-line summary; nothing selected opens Design and Threads; open/closed is remembered per kind of selection; Ctrl+click a heading opens only that one, Alt+click opens or closes everything inside. A header that stays in view names the selection and holds turn, mirror, duplicate and a ⋯ menu (Repeat, Pin, Remove).
- **Hold Space and drag to move around** without grabbing anything, also mid-shape (as in Embrilliance); a tap of Space still plays and pauses. While drawing, the arrow keys move the view 1 cm and the view scrolls when the pointer reaches the edge.
- **Esc drops a half-drawn shape, even a single point**, and says so; the next Esc goes back to Select. Fixed: a click on the panel's resize edge could leave Esc tied to a finished drag.
- New command **Pin in place / unpin** (Ctrl+L).
- **Auto-trace** (new tool on the left, Shift+A): click inside a shape in a picture and LUDD finds its outline (it looks for dark lines and clear color changes), with points about 3 mm apart (− / + or [ ]; remembered). Click on a dark line instead for a satin ribbon along its middle, as wide as the line. Tab shows the next guess (to the middle of the outline, inside it, similar shades joined, everything inside the dark lines; for lines, through where lines meet). Nothing is added until you choose Fill (Enter), Fill + satin border (Shift+Enter), Satin, or Line; then it's an ordinary shape whose points you drag to adjust. Colors come from the picture. Classic image analysis (OpenCV) on your computer: no AI service, no network. The engine now includes OpenCV (the app is about 30 MB bigger; its unused video library is left out).
- **Satin is now a ribbon**: click along the middle, like a line, and set its **Width** (new satins start as wide as the last). Closed ribbons (Ctrl+right-click) make rings. **Add a satin border** (Shift+B, or the button on a fill) puts a ribbon around a fill's edge, sewn right after it. **Stitch as** now offers Satin for lines and outlines. Satins in older projects (clicked side by side) still sew and edit as before.
- **Rename** anything (double-click a name, F2, or ⋯ → Rename) to keep track of layers; stitch files can be renamed too.
- **Your stitch settings carry over**: change a shape's density, length, underlay or other settings and new shapes of that kind start with them (not a fill's angle). "Use the standard settings for new fills" puts them back.
- Trace Assist (the ghost next point) is now off unless turned on.
- **Auto-trace, better guesses**:
  - **Simplified colors**: a new first guess reduces the picture to its 12 main colors and follows shading band by band, so gradients, soft edges and JPEG noise no longer stop it. Dark but colorful areas (navy, brown) are no longer mistaken for lines.
  - **Spread** (− / + in the bar, Alt+[ / Alt+]): how readily a guess spreads into similar colors. Remembered.
  - **Shift+click** adds another area to the guess, **Alt+click** cuts one out; separate areas become separate fills (each with its border if asked). Thin line-shaped holes (a drawn smile) are filled under instead of left as gaps.
  - **It learns your usual guess**: the kind you accept most comes first next time (Settings can forget this).
  - **AI tracing (optional)**: Settings → AI tracing downloads MobileSAM (about 45 MB, Apache-2.0 license, from huggingface.co/Acly/MobileSAM) after asking; it runs on this computer with ONNX Runtime. Its guesses come first, and Shift/Alt+clicks guide it. The engine now includes ONNX Runtime (about 14 MB).
- **Sewing order**: each step's color dot shows the thread it's actually sewn in (a color changed in Threads was not shown before); the ✎ now changes that step's thread (Threads follows); double-click a name to rename it (a single click waits a moment so the panel doesn't move under a double-click). The shape and lettering panels also show a color changed in Threads.
- **The thread fades while you hold a point**, so the outline and the picture underneath are easy to see; it comes back when you let go.
- **Double-click a point to delete it** (as in Embrilliance). Deleting a hole's points below three deletes the hole.
- Fixed: Esc could do nothing on its first press (often in Auto-trace). A click on the design area that was released somewhere else (over a bar, the panel or outside the window) left Esc tied to a drag that had ended. The Auto-trace bar also has a ✕ Dismiss button.

## 1.0.0 (Oct 11, 2026)

### From the first hands-on test
- **Embrilliance's keyboard shortcuts** throughout (from its manual): A zoom all, S zoom to the selection, 0 the hoop, 1–9 real-size multiples, T realistic thread, P stitch points, N stitches on/off, B pictures on/off, E crosshairs, M measure, D Create/Select, X/Shift+X/Q/W draw again, O add a hole, I stitch angle by drawing a line, Ctrl+A/G/U select all, group, ungroup, Ctrl+C/X/V, Ctrl+arrows nudge 0.1 mm, Shift+D new design. Moved to make room: Fill is F, Text Shift+T, mirror Alt+H/Alt+V, density map Alt+D, snap to grid Shift+G.
- **Curves by default, as in Embrilliance**: a click places a curve point, Ctrl+click a straight point, Shift+click a sharp corner; Alt keeps 15° steps; right-click finishes (Ctrl+right-click closes a line). The rubber band shows what the next click makes; points show as circle, square or diamond; right-click a point to switch it. A new "straight" point type in the engine; older projects keep their shape.
- **Realistic thread rebuilt**: every stitch is its own piece of thread between two needle holes, at true thickness, rounded, with a fine twist, a shadow on the fabric and a sheen that changes with the stitch's angle, so fills at different angles catch the light differently and you can see density without the density map. Plain lines (T off, or while dragging) as before.
- **Shape panel in tabs (Thread · Stitches · Shape)** with every setting in view and − / + steppers: underlay buttons (Auto, Edge, Cross-hatch / Centre, Edge, Zigzag), density, angle (or draw it with I), stitch length, **Random** (new: moves needle points so no lines show across a fill), **Edge pad** (pull compensation, Auto or set), **Reverse** (new: sew a fill from the other end), satin **Split long stitches** (new), lock stitches.
- **Select several things**: Shift+click, Ctrl+A; they move, turn, resize, mirror, copy, cut and delete together, about their common centre. **Groups** (Ctrl+G) select as one.
- **📌 Pin** pictures, designs and shapes so they can't be dragged by accident: from the Sewing order and Pictures lists, the picture panel, or the Shape tab. A pinned picture lets clicks through so you can draw over it.
- **Stitch-out speed**: a slider from 2 to 5,000 stitches a second with a "machine speed" setting (about 12 a second, like a real home machine); comma and full stop slow down and speed up; remembered. The default is 200 a second (was 2,000, too fast to follow).
- **Resizable panel**: drag the right panel's left edge (up to 60% of the window; double-click resets; remembered). Panel sections fold away by clicking their headings. Dialogs move by dragging their title.
- **New tool icons**: clean line drawings that follow light and dark mode.
- Fixed: turning or mirroring a fill now turns its stitch direction with it.
- Release builds: Mac builds no longer try to sign without a certificate; the Intel Mac build uses GitHub's current Intel runner.
- New: [docs/USER-MANUAL.md](USER-MANUAL.md), every feature and where to find it, with all shortcuts.

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
