# LUDD manual

*For LUDD 1.0.1, October 2026.*

Everything LUDD does, where to find it, and how to use it. For installing and a ten-minute first
design, see the [user guide](USER-GUIDE.md). Inside the app, press **F1** for Help: it searches
a shorter version of this material, offline.

LUDD uses **Embrilliance's keyboard shortcuts** wherever Embrilliance has one, so if you know
Embrilliance, your fingers already know LUDD. The full list is at the end:
[Keyboard shortcuts](#keyboard-shortcuts).

---

## 1. The screen at a glance

| Area | Where | What it's for |
| --- | --- | --- |
| **Toolbar** | Top | New, Open, Save, Add design, Undo/Redo, **Save for machine**; your machine and hoop; **?** Help; **⚙** Settings; **⋯** the rest (files, machine extras, views). Commands for what you've selected are in the panel's own **⋯** (see below). |
| **Tool rail** | Left edge | Select, Line, Satin, Fill, Text, Auto-trace, Shapes, Picture. The key for each tool is printed under it. |
| **Design area** | Middle | Your design on the fabric, the hoop outline and the grid. Scroll to zoom; **hold Space and drag** to move around (nothing gets grabbed). |
| **Panel** | Right | Folding sections: whatever is selected, then Design, Order & colors, Checks and Pictures (see **The panel** below). **Drag its left edge** to make it wider or narrower (double-click the edge to reset). |
| **Stitch-out bar** | Bottom | Watch the design sew: play, step, jump by color, speed. |
| **Status bar** | Very bottom | Whether the stitch engine is connected, and the version. If the engine ever stops, LUDD starts it again; if it can't, click **Restart engine** here (your work stays on screen). |

Messages appear in a strip under the toolbar. Click × to close them; most close by themselves.
Every dialog can be moved by dragging its title (My threads & charts by the empty part of its tab
bar); Esc while dragging puts it back.

**Esc lets go** of whatever you're in the middle of, one thing per press, newest first: a drag
(the shape goes back), an open menu or list, a value you were typing (the old one comes back), a
half-drawn shape, the measuring tool, the drawing tool (back to Select), a selected point, the
selection, playback. A single point placed with a drawing tool counts: Esc drops it, and the next
Esc takes you back to Select. While carving lines into a fill, Esc drops the line you're drawing,
and the next one stops carving.

### The mouse pointer
The pointer shows what a click or drag will do where it is:

| Pointer | Means |
|---|---|
| Arrow | Nothing under it: click to deselect, drag to move the view. |
| Arrow with a green **move** badge | A shape or picture: click to select it, drag to move it. |
| Arrow with a green **point** badge | A shape's point: drag to move it, double-click to delete it. |
| Two-headed diagonal arrow | A corner handle: drag to resize. |
| Circular arrow | The turn handle: drag to turn. |
| Green double arrow on a line | A ruler or guide: drag out (or move) a guide. |
| Open hand / closed hand | Space held: drag to move the view (closed while dragging). |
| Crosshair with a green badge | A tool is in use: the badge shows which (line, satin, fill, text, knife, measuring, stitch angle, stitch editing). The click lands in the middle of the crosshair. |
| Crosshair mark: circle / square / diamond | Drawing: the next point is a curve point / a corner (Shift) / a straight-line point (Ctrl). |
| Wand | Auto-trace: the sparkle at its tip is the spot that's clicked. |
| Arrow with a spinner | LUDD is working out an auto-trace. |

### Right-click
**Right-click anything** to see what you can do with it, with each command's shortcut beside it,
so you can find a command and learn its key in one go:

- **A shape**: Change thread…, Cut, Copy, Duplicate, Remove, Add points, Cut a hole, Set the stitch
  angle, Knife, Add a satin border, Outline / offset, Sew first / earlier / later / last, turn and
  mirror, Center in the hoop, Repeat, Pin, Rename, Zoom to it and the Stitch Advisor. **A fill**
  also: Add another angle line, Carve lines into the fill, and Remove carved lines once it has some
  (right-clicking a turning fill's purple line removes that line).
- **Several shapes** (Shift+click them first): also Group, Merge, Cut out and Put the text on the line.
- **Lettering**: also Change the words and One file per name. **A stitch file**: Edit stitches.
- **A picture**: Auto-trace, Auto-digitize the whole picture, Pin / unpin (a pinned picture lets
  clicks through, but a right-click still finds it), See-through stitches, Show pictures, Remove.
- **The empty canvas**: Paste, Select everything, the drawing tools and shapes, Add a picture,
  zoom, and the view options (ticked when on).
- **In the panel**: a step or one of its colors in **Order & colors**, and a picture in
  **Pictures** have menus too.

Right-clicking a thing selects it first. While you draw, a right-click still finishes the shape;
in Auto-trace it uses the guess shown; on a shape's point it switches the point between curve,
straight and corner. Arrow keys move through a menu, Enter picks, Esc closes it.

### The panel
The right panel is a stack of **folding sections**. Click a heading to open or close it; a
closed heading still shows a one-line summary ("Fill · Normal · 45°", the thread colors, how many
checks), so you rarely need to open one just to look.

- **At the top**, always in view: the name of what's selected, and its most-used buttons: turn
  ⟲ ⟳, mirror ⇋, duplicate ⧉, and **⋯** (the panel's menu) for Repeat, mirror top-bottom,
  **Pin in place** (Ctrl+L), Rename, Outline / offset, Knife, Edit stitches and Remove. With
  several things selected it offers Group, turn, mirror and duplicate, and its **⋯** has Repeat,
  Outline / offset, Merge and **Put the text on the line**.
- **What you selected** comes first and opens by itself: **Fill**, **Satin**, **Line**,
  **Applique**, **Lettering**, **Stitch file** or **Picture**. The everyday settings are in view;
  the rest sit in smaller folds inside it (**Underlay**, **Advanced stitch settings**, lettering
  **Shape** and **More options**, a stitch file's **Rotation and position**).
- Then **Size and points** (for drawn shapes), **Design** (size, stitches, sewing time, thread,
  hoop fit, the fabric; **Thread used** and **File details** inside), **Order & colors**, **Check before stitching** and
  **Pictures**.
- With **nothing selected**, Design and Order & colors open. Select something and its own section opens
  instead. LUDD remembers what you open or close for each kind of thing: close Underlay once and
  it stays closed for every fill.
- **Ctrl+click** a heading to open only that section; **Alt+click** to open or close everything
  inside it too.

---

## 2. Files

### Opening designs
- **Open** (Ctrl+O): opens embroidery files (40 formats: PES, JEF, DST, EXP, VP3, XXX and 34
  more) and LUDD projects (`.ludd`). You can also drag a file onto the window.
- **Add design** (Ctrl+Shift+O): places another stitch file into the design you have open, to
  combine designs. Dragging a file onto an open design adds it, too.
- **⋯ → Open a sample design** (Ctrl+Shift+E): five designs that come with LUDD, to try things
  on (three of them also as PES and JEF files, which sew exactly like their projects). They open as new designs, so Save asks where to
  keep yours.
- **New** (Ctrl+N, or Shift+D as in Embrilliance): an empty design on the fabric you used last.

### Projects
- **Save** (Ctrl+S) keeps a **LUDD project** (`.ludd`): drawn shapes, lettering, placed designs,
  pictures you trace and all settings, with the designs, pictures and the lettering's fonts
  **embedded inside it**. Moving, renaming or deleting the originals can't break it, and it opens
  the same on another PC, even one without the font. If another program (antivirus, OneDrive) is
  holding the file, Save waits a moment and tries again.
- **⋯ → Save project as** (Ctrl+Shift+S) makes a copy under a new name.
- **Opening a project** uses the machine and hoop it was made for, for that project only: your
  usual machine stays your default. A project from a newer LUDD asks you to update instead of
  opening wrongly; a missing, damaged or in-use file says so in plain words. If only some parts
  of a project are damaged, the rest opens and a note says how many parts were left out (save
  under a new name to keep the original as it was).
- **Autosave and recovery**: a few seconds after each change LUDD keeps a recovery copy. If it
  closes unexpectedly, next time it offers **Recover** or **Discard**. The copy is only removed
  once the work is really back (or you choose Discard); one that can't be read is kept aside.
- The window title shows a dot (•) when there are unsaved changes; closing asks first.
- **Where LUDD keeps things** (Windows: `%APPDATA%\Ludd`): your threads, settings, stitch fonts
  (`fonts`), the recovery copy (`recovery`; `unrecovered-….ludd` files there are crash copies that
  couldn't be opened) and private copies of the pictures and designs you add (`project-files`;
  copies unused for 90 days are deleted). These copies keep your design working even if LUDD's
  engine restarts after the original was moved or its USB stick unplugged.

### Saving for your machine
**Save for machine** (Ctrl+E, the yellow button) writes the file your machine reads.

- The dialog says whether the design **fits your hoop**, the **file type** (PES for Brother, JEF
  for Janome; others under **More options**) and lists anything to **check** first.
- **Have the machine cut jump threads** (recommended for machines like the Brother PE550D that
  only cut at color changes): the long jumps the design **marks for trimming** become stops in the
  same color, so the machine ties off and cuts; press Start at each stop, no thread change.
  **More options** sets how long a jump must be to be cut, whether to add lock stitches, and
  **Also cut jumps the design doesn't mark for trimming** (some bought designs leave long jumps
  unmarked; the dialog tells you when there are any, because the machine won't cut them).
- **A little too big for the hoop** (up to about 5%)? **Make it N% smaller** fits it in one
  hooping; or tick **Or split it across hoopings**.
- **Too big for the hoop?** Tick **Split it across hoopings**: one file per hooping ("name 1 of 2",
  "name 2 of 2"), each with **pink alignment crosses**, placed on bare fabric where there's room.
  Sew file 1, re-hoop so the needle lands on the crosses when you start file 2, carry on, then
  pull the crosses out. A small map shows the hoopings; **More options** sets the overlap: the
  least the hoopings overlap each other (more overlap can mean one more hooping). Hoopings with
  nothing to sew are left out, and files already in the folder are never replaced ("name (1) 1 of
  2").
- The **stabilizer advice** for your fabric is shown at the bottom.
- **PES files saved by LUDD before 13 October 2026** put the design off-center, so on a Brother
  machine it loaded shifted up and left, mostly off the hoop, and couldn't be moved back. Open the
  project (or the file) and **Save for machine** again; files saved now are placed like
  Embrilliance's.
- Saving never leaves a half-written file. A design with nothing to sew isn't saved, and a PES
  file can't hold more than 255 color steps (cut-stops count as steps), so LUDD says so before
  saving.

### Printing
**⋯ → Print template & thread list** (Ctrl+P): a real-size template with center lines (for placing
the design on fabric), and a thread list with stitch counts, a tick box per color and the
stabilizer to use. Print at 100% ("Actual size") and check the ruler bars.

### Browse designs
**⋯ → Browse designs** (Ctrl+Alt+B): every design in a folder (and its subfolders) as a picture,
with its size, stitch count and colors. **Choose folder…** once; LUDD remembers it. **Refresh** looks through the folder again for new,
changed or removed designs. It shows
the newest 600; type part of a name to find one (in a bigger folder this searches the whole
folder). Click a design to open it, or **+ Add** to place it in the design you have open. The
pictures are kept while LUDD is open, so going back to the folder is quick; press **Refresh**
to see designs added since.

### Batch convert
**⋯ → Batch convert folder** (Ctrl+B): converts every design in a folder to another format,
into a `converted` folder inside it unless you pick another (**Include subfolders** to take those
too). For a machine that only cuts at color changes it can add cut-stops as Save for machine
does. Existing files are never replaced.

---

## 3. Looking at your design

### Zoom and pan
- Mouse wheel zooms where the pointer is; drag empty space (or with the middle button) to pan.
- **Hold Space and drag** to move around without grabbing anything, even in the middle of drawing
  a shape (as in Embrilliance). A quick tap of Space still plays and pauses the stitch-out.
- While drawing, the **arrow keys** move the view 1 cm, and taking the pointer to the edge of the
  design area scrolls that way, so you can keep drawing past the edge of the screen.
- **A** zoom to all · **S** zoom to the selection (everything selected) · **0** zoom to the hoop · **1** real size ·
  **2–9** two to nine times real size · **+ / −** zoom in and out · the − / % / + / Fit buttons at
  the bottom right.

### Views
| Key | View | |
| --- | --- | --- |
| **T** | Realistic thread | Every stitch drawn as real thread, lit from the upper left like a photo of a stitch-out: rounded and shaded, with a glossy highlight and visible twist, dipping into the fabric at each needle hole. Stitches at different angles catch the light differently, so satins look rounded and fills show their direction, and each shape casts a soft shadow on the fabric and on what's sewn under it. True thickness: sparse areas show fabric between rows; dense ones pile up. Stays smooth when zoomed out. Turn it off for plain lines. |
| **P** | Stitch points | A dot at every needle penetration. |
| **N** | Stitches on/off | Hides the stitches and shows your drawn shapes' outlines. |
| **Shift+N** | See-through stitches | Draws the thread faint, so you can see the picture you're working over (also the **◐ See-through stitches** button next to the zoom). Press again for solid thread. |
| **B** | Pictures on/off | Hides or shows the pictures you're tracing. |
| **J** | Trims, jumps and stops | Gray lines where the thread is cut, orange where a thread is left across the fabric, red marks at trims and stops. |
| **E** | Crosshairs | Lines across the whole design through the pointer, to line things up. |
| **G** / **H** | Grid / hoop | The grid (inches or mm) and the hoop outline. |
| **U** | Units | Inches or millimeters. |
| **Shift+P** | Needle path view | Hairlines with a dot at every needle point, the same size at any zoom, to read a thick spot stitch by stitch. Works with the density map. |
| **Alt+D** | Density map | Colors the design where thread piles up: yellow-green (two layers), orange (the limit), red (too much). Also a tick box beside Checks. |

The design sits on **light fabric**, in dark mode too, so threads and shadows look as they'll sew; untick **Always show the design on light fabric** in Settings for a dark design area.

### Rulers and guides
Rulers run along the top and left of the design area (**Ctrl+R** or ⋯ turns them off). **Drag
from a ruler** onto the design to make a guide line: from the top ruler a horizontal one, from
the left a vertical one. Drag a guide to move it (it lands on the grid when the grid is on);
drag it back onto a ruler to remove it. **⋯ → Remove all guides** (Ctrl+Alt+G) clears them.
Points you place or drag near a guide snap onto it (with Snap to grid on, a guide still wins
in its direction and the grid applies in the other). Guides are saved in the project.

### Measuring
**M** (or ⋯ → Measure) turns on the measuring tool: click two points and the bar above the
canvas shows the distance, and how far across and down; click again to measure something else.
**M** or **Esc** puts it away. Only one of the measuring tool, the knife, stitch editing and the
angle line (I) is on at a time: starting one ends the others, and picking a drawing tool ends
stitch editing.

### Watching it stitch
The bar at the bottom plays the design as the machine would sew it.

- **▶ / Space** plays and pauses. **⏮ / Home** goes to the start, **⏭ / End** shows it all.
- **◀▮ ▮▶ / Page Up, Page Down** jump to the previous or next color.
- **← →** step one stitch (Shift: 100), when nothing is selected.
- Drag the long slider to any point; the marks on it are color changes.
- **Speed** (🐢 slider 🐇): from 2 stitches a second up to 5,000. **Machine speed** is how fast a
  home machine really sews (about 12 a second). **Comma** (or **[**) slows down, **period**
  (or **]**) speeds up, **Shift+comma** sets machine speed. LUDD remembers your speed. (While
  Auto-trace or Trace Assist is in use, [ and ] change their points instead.)

---

## 4. Drawing your own

### Tools (left rail)
| Tool | Key | Makes |
| --- | --- | --- |
| **Select** | V | Pick, move, resize and turn things. |
| **Line** | L (or Shift+X) | A running stitch line. |
| **Satin** | C | A satin ribbon: click along its middle, like a line; set its width in the panel. |
| **Fill** | F | A filled area (tatami): click around its edge; it closes by itself. |
| **Text** | Shift+T | Lettering: click where it goes, then type. |
| **Auto-trace** | Shift+A | Click a shape (or a line) in a picture: LUDD finds its outline for you. |
| **Shapes** | | Opens a menu beside the rail: rectangle (Ctrl+Alt+1), circle (Ctrl+Alt+2), star (Ctrl+Alt+3), rounded rectangle (Ctrl+Alt+4), oval (Ctrl+Alt+5), triangle (Ctrl+Alt+6), polygon (Ctrl+Alt+7), heart (Ctrl+Alt+8), monogram (Ctrl+Alt+M), and cutting holes (below). |
| **Picture** | Ctrl+I | A picture to trace over. |

A ready-made shape is added as a fill in the middle of the hoop, selected, ready to move, resize or
edit like any fill. **Polygon** asks how many sides (3 to 12): type a number, then press Enter, or
Esc to cancel. It remembers the last number you used.

Embrilliance's create keys work too: **D** switches between drawing and Select, **X** draws again
with the last tool, **Q** draws the same kind of shape as the last one, **W** the kind before that.

**The tool you pick stays picked** until you choose another (or press **V** or **Esc** for Select):
after a shape, a traced guess or a piece of text you can go straight on to the next one. With the
Text tool, clicking a text that's already there selects it. After **Cut a hole** (O) you're back in
the tool you were using (Esc while drawing the hole drops it and goes back too). With a shape
selected, the arrow keys nudge it even while a drawing tool is chosen.

### Placing points (as in Embrilliance)
| Do this | Makes |
| --- | --- |
| **Click** | a **curve** point: the line flows smoothly through it |
| **Ctrl+click** | a **straight** point: the line comes in straight |
| **Shift+click** | a **sharp corner** (cusp) where two curves meet |
| **Alt** while clicking | keeps the new point on 15° steps from the last one |
| **Enter**, **right-click** or **double-click** | finishes the shape |
| **Ctrl+right-click** | finishes a line and closes it into a loop |
| **Backspace** or **Ctrl+Z** | removes the last point (Ctrl+Z doesn't undo anything else while you draw; Ctrl+Y waits until the shape is done) |
| **Esc** | cancels the shape (press again to go back to Select) |
| **C** while drawing | switches the last point: curve → straight → corner |
| **Shift+G** | snaps new points to the grid (on/off) |

The line from your last point to the pointer shows what the next click will make. Points near
another shape's points snap to them, so shapes meet exactly. On screen, curve points are circles,
straight points squares, corners diamonds.

### Editing a shape's points
Select the shape, then:
- **Drag a point** to move it. While you hold a point the thread fades, so you can see the outline
  (and the picture underneath); it comes back when you let go.
- **Right-click a point** to switch it: curve → straight → corner.
- **Double-click the outline** to add a point there; **double-click a point** to delete it.
- **Delete** removes the selected point. Take a hole down below three points and the hole goes
  (handy for a hole Auto-trace left that you don't want).
- **K** (or Size and points → Add points) picks the shape back up to add more points.
- **Cut a hole** (**O**, the **✂ Cut a hole** button in a fill's section, Shapes, or ⋯): click around
  the hole, Enter to finish.
- **Cut out with a shape** (**Shift+O**, Shapes, or ⋯ with several selected): put a circle, star or
  any shape you've drawn over the fill, select the fill and that shape (Shift+click), and cut. Where
  the shape sits inside the fill it becomes a hole; where it overlaps the edge it takes a bite; right
  across, the fill is cut in pieces. The shape you cut with stays, selected: press Delete if it was
  only for cutting.
- **I** (or the Fill section → Draw the angle) sets a fill's stitch direction: draw a line across it.
- **Drag the green dot** (where it starts sewing) or **the red dot** (where it stops). As you drag,
  the dot slides along the shape's edge, following the point nearest the mouse (like a magnet),
  and stays exactly where you let go:
  - **A fill** starts anywhere on its outside edge and can stop anywhere on any edge (a hole's
    too). The rows are planned so the last one finishes there.
  - **A closed line or border** starts and stops anywhere along it.
  - **A satin** (a ribbon, column or satin fill) starts and stops anywhere along it. To stop part
    way along, it's sewn in two parts that meet at your stop; the moves between run along its
    middle, under satin sewn afterwards, so they don't show.
  - **An open running line** starts and stops at its ends: drag a dot to move that end, or drop
    it on the other end to sew the line the other way round.
- **Drag the purple dots** to set the stitch direction:
  - **A fill**: the purple line between them is the direction of the rows. Each dot slides round
    the outline; the angle in the panel follows (typing an angle there puts the line back across
    the middle). A turning fill shows a line with two dots for each direction instead (section 6,
    Turning fills).
  - **A satin column or satin fill**: the purple dots, just past each end, are its two tips. Slide
    them round the outline and the satin is rebuilt to run from one to the other, its stitches
    straight across the shape between them (Shift+W still tries LUDD's own suggestions).
  - The dots move, turn and resize with the shape. **Optimize jumps** (Ctrl+Alt+J) chooses all
    the starts and ends again for fewer jumps. A shape cut with the knife or cut out gets fresh
    dots on each piece.
  - A **pinned** shape shows its outline only: its points and dots can't be moved until you unpin
    it. With several things selected the dots aren't shown.
  - **Contour, Stipple, Cross-stitch, Spiral, Motif, Maze, Ripple and Mesh** fills end where
    their pattern does: the red dot shows it but can't be moved. Stipple, Cross-stitch, Spiral and
    Ripple also start where their pattern does (a Spiral or Ripple in the middle), wherever you
    drag the green dot. **Sew from the other end (reverse)** on a fill clears a chosen end.

### Tracing a picture
1. **Picture** (Ctrl+I) adds a picture (up to 40 MB and about 120 megapixels). Drag it into place
   and resize it from a corner.
2. In **Pictures** in the panel (the list of your pictures; the selected one's settings open under
   its name): **See-through** slider, **📌 Pin to the board** (it can't move, and clicks go
   through it so you can draw over it), **Hide**, and **Set real size** (click two points whose
   real distance you know, then type it).
3. Trace it with **Auto-trace**, or draw over it with the other tools. To see the picture through
   what you've already stitched, turn on **See-through stitches** (Shift+N, or the ◐ button by the zoom).

### Satin borders that fit the edge
Drawing a satin along the edge of a shape you've already made (a fill, an applique, a hole, or a
line)? After a couple of clicks along the edge, LUDD notices, shows a faint satin along it, and says
**Tab fits the satin**. Press **Tab** and the satin follows the edge exactly, round every corner and
curve. Not quite right? Press **Tab** again for the next way:
1. all the way round, centered on the edge (the classic satin border);
2. all the way round, just outside the edge (it frames the shape and covers its edge);
3. only from your first click to your last, along the edge, the way you were going.

**Shift+Tab** goes back one, **Enter** keeps it, **Esc** puts your own clicks back. Nothing changes
until you press Tab, so you can always just keep clicking.

### Auto-trace (Shift+A)
Auto-trace finds shapes in your picture for you: it looks for dark outlines and for places where
one color clearly changes to the next.

1. Pick **Auto-trace** on the left (or press **Shift+A**).
2. **Click inside a shape** in the picture (a face, a leaf, a letter). Its outline appears as a
   preview with its points. Or **click on a dark line** for a satin ribbon along that line, as
   wide as the line. Click inside a solid black or very dark shape and it offers **Fill, this
   dark area**.
3. Not quite right? **Tab** shows the next guess (**Shift+Tab** goes back). For an area the
   guesses are: by simplified colors (the picture reduced to its main colors, so shading and
   soft edges don't stop it), up to the middle of its outline (best under a satin border),
   inside the outline, with similar shades joined, and everything inside the dark lines. For a
   line: up to where it meets other lines, then straight on through them. The kind of guess you
   use most comes first next time.
4. Fix it with more clicks: **Shift+click** another area to add it to the guess, **Alt+click** an
   area to cut it out. Separate areas become separate fills.
5. **Spread** (− and + in the bar, or **Alt+[** and **Alt+]**) is how readily a guess spreads into
   similar colors: lower if it leaks into the next shape, higher if it stops short. **Points
   every** (**[** and **]**) sets how far apart the points are: closer for small, detailed shapes,
   further for big smooth ones. LUDD remembers both.
6. Use it:
   - **Fill** (**Enter**, or right-click): a fill in the picture's color.
   - **Fill + satin border** (**Shift+Enter**): the fill, and a black satin ribbon on its outline
     (as wide as the picture's line), sewn right after it.
   - **Satin fill**: the area filled with one satin that turns and changes width with it (see
     *Satin fill* below), in the picture's color. An area with holes stays a fill. For a line:
     **Satin** / **Line**.
   - **Esc** (or **✕ Dismiss**) throws the guess away. Nothing is added until you choose.
7. It's an ordinary shape now. Auto-trace stays on, so click the next shape straight away; press
   **V** to drag the new shape's points and fix whatever the guess got wrong.

**It sees what you've already made.** When a guess runs over shapes you've already drawn or
traced, it comes **fitted around them** (it says so), tucked 0.3 mm under their edge so there's no
gap once sewn and nothing is stitched twice. **Tab** still offers the whole area ("over your
shapes"), for something meant to sit on top. Clicking on one of your shapes traces that spot again
as it is. The AI model (below) is also told about the shapes near your click, so its outline stops
at them.

The colors come from the picture; **Order & colors → Match…** swaps them for real threads.

**AI tracing (optional).** For photos and shaded art, get the AI tracing model in **Settings → AI
tracing**: a small model (MobileSAM, about 45 MB, Apache-2.0 license) that runs on your computer. LUDD
asks before downloading it and sends nothing anywhere. The download is a fixed version, checked
against its checksum before it is kept. With it, Auto-trace's first guesses are
the AI's (marked "AI guess", with how sure it is); Shift+click and Alt+click tell it "this too"
and "not this". The first click on a new picture takes a second or two while it reads the
picture, after that well under a second. The **AI** tick box in the bar turns it off for a
picture it doesn't suit. If the model can't run, Auto-trace says so and shows its usual guesses
(removing the model in Settings and getting it again may help). **Forget which Auto-trace
guesses I usually pick** (in Settings → AI tracing) puts the guesses back in their standard
order.

### Auto-digitize the whole picture (Alt+A)
**⋯ → Auto-digitize the whole picture**, or **Whole picture…** in Auto-trace's bar (before you
click a shape), turns the whole picture into shapes at once: every area of color becomes a fill
(in the picture's color, out to the middle of its outline), solid dark areas (pupils, solid
black shapes, bold dark lettering: one fill per letter) become fills, and the dark lines become
**satin ribbons** along their middles (as wide as the lines, reaching their ends; very thin lines
become running stitch). All dark lines and dark areas share one thread, and nearly equal colors
(JPEG noise) become one thread. Big areas sew first, outlines last.

You see it all as a preview first (it takes a few seconds; up to a minute for a busy picture).
**Satin outlines on the dark lines** and **Leave out the background** can be turned off. The
background is the color all round the picture's edge, light or dark; it's left out wherever it
shows, also inside letters and rings, while shapes that touch the edge are kept. The bar has its
own **Points every** and **Spread** (with Auto-trace as the tool, also [ ] and Alt+[ ]); the preview is read again when you
change them or move the picture. **Add all** (Enter) adds every shape in one go (one Ctrl+Z takes
them all out); **Dismiss** (Esc) adds nothing. A picture made smaller than 0.5 mm can't be traced: make it
bigger first. Then fix what needs fixing: drag points, merge
pieces, delete specks, and use **Order & colors → Match…** to pick real threads for the colors.

The older **Trace Assist** (a ghost "next point" while you draw, Tab to take it) is still there
but off unless you turn it on (Ctrl+Shift+A or Settings).

---

## 5. Selecting and arranging

### Selecting
- **Click** a design or shape to select it. Click empty space (or **Esc**) to deselect.
- **Shift+click** (or Ctrl+click) adds to the selection or takes one out. **Ctrl+A** selects
  everything.
- Several selected things **move, turn, resize, mirror, copy, cut, recolor and delete together**;
  the panel shows "N selected", and each of them is highlighted in **Order & colors**. Changing
  the thread of one (its ✎, the 🧵 button at the top of the panel, or **Alt+T**) changes them all.
- **Ctrl+G** groups them: clicking any one (on the design or in the list) then selects them all,
  and **dragging anywhere inside the group's frame** moves the whole group, even between its
  pieces. **Ctrl+U** ungroups.

### Moving, turning, resizing
- **Drag** to move; drag a **corner handle** to resize evenly; drag a **side handle** (the small
  squares in the middle of each side) to **stretch** one way only, wider or taller, while the
  opposite side stays put; drag the **round handle** to turn (hold Shift for 15° steps). The pointer
  shows which way each handle pulls. (Side handles appear once the shape is big enough on screen;
  zoom in on a small one.)
- **Arrow keys** nudge 1 mm; **Shift** 1 cm; **Ctrl** 0.1 mm.
- **R / Shift+R** turn 90° right/left. **Alt+H** mirrors left-right, **Alt+V** top-bottom. A fill's
  stitch direction turns and mirrors with it.
- Exact size: the **W** and **H** boxes (Size and points for drawn shapes); 🔒 keeps the proportions.
  A stitch file resized more than about 20% may sew too dense or too sparse (LUDD warns you):
  **Rebuild stitches at this size** (Alt+Shift+R) fixes that (see Repairing bought designs).
  Drawn shapes and lettering re-stitch at any size.

### Pinning
**📌 Pin** stops something being dragged by accident. Pin designs and shapes from the 📌 in the
**Order & colors** list or **⋯ → Pin in place** at the top of the panel (Ctrl+L); pictures from the
📌 in the **Pictures** list or at the top of the panel. A pinned picture also lets clicks through. A pinned design or shape
also ignores the arrow keys, R, Alt+H / Alt+V and the resize handles (a note tells you it's pinned). Click the pin again to unpin.

### Outlines & offsets
**⋯ → Outline / offset…** (Ctrl+Shift+K, with something selected) puts a ring around whatever is
selected, a set distance out from its stitches: a border around lettering, an edge for a patch,
an outline round a design (several things close together get one outline). Sew it as a **Satin
border** (with its width), a **Line** or a **Triple line**; tick **Also around the inside of holes**
for the middle of an O. It's sewn right after what it goes around. A negative distance makes an
inset inside the stitches instead; if nothing is left that far in, try a smaller inset (closer
to 0).

### The knife, and merging
- **Knife** (Shift+K, or ⋯ → Knife at the top of the panel): with a fill, line or satin ribbon
  selected, click two points (they snap to points, guides and the grid); it's cut along that line
  (extended right across the shape) into separate pieces, each with the same settings and thread,
  colors changed in Order & colors, stops and trims, pin and group. One cut across a closed line or ring
  gives two pieces. Holes stay with the piece they're in. It cuts the shape where you see it, even
  after it's been moved, turned or resized. A cut that misses leaves the knife ready to try again.
- **Cut out** (Shift+O): see *Cut out with a shape* above.
- **Merge** (Ctrl+M): select two or more fills that touch or overlap (Shift+click) and they become
  one shape, with the settings, thread and sewing place of the one you selected first. Fills that
  don't touch, or only meet at a corner, can't be merged.
- If you change or undo the shapes while the knife, merge, an outline or Optimize jumps is still
  working, LUDD leaves the design as you made it and says "The design changed while …: try again".

### Copying and repeating
- **Ctrl+C / Ctrl+X / Ctrl+V** copy, cut and paste (pasted a little down and right).
- **Ctrl+D** duplicates.
- **Repeat…** (Ctrl+Shift+D, or ⋯ → Repeat at the top of the panel): copies in a **row or grid**, round a
  **circle** (a carousel, each copy turned to follow it), or **mirrored ×4** like a quilt block.

### Editing stitches of a stitch file
Placed stitch files (PES, JEF, DST…) are edited stitch by stitch. Select the design, then **Edit
stitches** (in its section, ⋯, or Ctrl+Alt+E). Every needle point shows.
- **Click** a stitch to select it; **Shift+click** adds or takes one away.
- **Drag a box** (from anywhere but a selected stitch) to select every stitch inside;
  Shift+drag adds to the selection.
- **Drag a selected stitch** to move all the selected ones. Moved stitches stay put on the
  design: turn or resize the design afterwards and they turn and resize with it.
- **Delete** (or Backspace) removes the selected stitches (with none selected it does nothing, so
  the design is safe).
- **Esc** or **Done** finishes. Every edit (a whole drag, too) is one Ctrl+Z.
The edits are kept with the design in the project; the original file isn't changed. Once a placed
file has edits, LUDD sews it from its own copy, made when you added it: if the original is saved
again in another program, your edits still land on the right stitches. To use the new version, add
it again and redo the edits.

With **one stitch selected** you can also add to the file (right-clicking a stitch selects it and
offers these too; Mac keyboards have no Insert key, so use the right-click menu):
- **Insert** adds a stitch halfway to the next one, selected, ready to drag.
- **Shift+Insert** turns the move to the next stitch into a jump (no thread sewn across).
- **Alt+Shift+T** locks both sides of the jump after the stitch (three short stitches on each
  side), so you can cut the thread there without it unraveling.
Stitches made by a repair or a lock aren't the file's own, so they can't be picked.

### Repairing bought designs
Merged and resized bought designs often end up too dense, too sparse or full of tiny stitches,
which can break needles and nest thread. **Repairs** fix that without ever changing your stitch
file: they're kept with your design and applied whenever it's drawn or saved for the machine.

Select the design, open **Repair** in its panel section and press **Repair this design…**
(Ctrl+Alt+D), or press **Fix it** on a check. Tick what you want:
- **Rebuild stitches at this size** (shown when the design is resized by 10% or more, ticked past
  20%): sews its fills, satins and lines again at the new size with their original spacing. Parts
  it can't recognize (such as motif fills, cross-stitch or special fill patterns) are resized as
  they are, and a note says how much was rebuilt. Complicated shapes can get a few extra jumps.
- **Remove tiny stitches** (shorter than 0.4 mm; adjustable): they can make the machine nest
  thread. The lock stitches at the start and end of each thread stay.
- **Thin out dense spots**: where the needle goes into one spot more than 5 times (adjustable),
  takes some of those stitches out without changing the shape.
- **Limit density for this fabric**: fills and satins sewn closer than your fabric takes
  (**Stitching on**) are sewn again at its normal spacing. Thick spots made by layers stay.

The window shows **before and after** numbers, including the **densest spot** (red when it's too
thick). **Show on the design** moves the window aside and marks in red the stitches that would
change. Nothing changes until **Accept**; **Cancel** or Esc leaves the design as it was.

The panel's **Repair** section lists what's on; **✕** takes a repair off. You can also turn one on
or off directly: **Alt+Shift+R** rebuild, **Alt+Shift+S** tiny stitches, **Alt+Shift+D** dense
spots, **Alt+Shift+L** density limit. Removing the stitches of one design that are hidden under
another isn't built yet (Alt+Shift+H says so).

While a repair that remakes stitches is on (Rebuild or the density limit), Edit stitches shows only
the stitches the repair didn't remake. To edit the others, take the repair off, edit, and turn it
on again.

### Order & colors
One list in the panel for what sews when and in which thread (it used to be two sections,
Threads and Sewing order). Every design, shape and piece of lettering is a row, in the order they
sew:

- **Drag a row by its grip (⠿)** up or down to sew it at another place: the other rows make room
  as you go, and Esc while dragging puts it back. **↑ ↓** move one a step earlier or later.
- **Click a name** to select it; **Shift+click** (or Ctrl+click) adds it to the selection or takes
  it out. Everything selected is highlighted in the list, and a group is picked whole (▣ marks a
  grouped row).
- **Click the color square** (or **✎**) to change that step's thread. With **several selected**,
  the thread you pick goes to **all of them** (also from right-click → Change thread…, Alt+T, or
  the 🧵 button at the top of the panel).
- **A stitch file with several colors** lists them under its row, numbered in sewing order (the
  numbers your machine shows), each with its thread, brand and number: **✎** changes one,
  **🗑** removes that color's stitches. "was …" shows a color you've changed; **Back to …** (in its
  thread list, or on its right-click menu) puts the original back.
- **Palette**, at the top: every thread the design uses, once each. Point at one to see how many
  times it's used; **click it to change it everywhere** at once.
- The basting box and knockdown stitches are listed first, by name; knockdown has a ✎ to match its
  thread to the fabric. While the stitch-out plays, the step being sewn is marked at its left edge.

**Right-click** a step for its menu (change thread, sew first / earlier / later / last, remove…).
**Ctrl+[** and **Ctrl+]** sew the selected thing one step earlier or later; **Ctrl+Shift+[** and
**Ctrl+Shift+]** sew it first or last.

**Rename** anything so you can find your layers ("Face fill", "Left eye outline"): double-click
its name (in the list or at the top of the panel), **F2**, or **⋯ → Rename**. Enter keeps the name, Esc puts the old one back; an empty name puts the standard
one back. Names are saved in the project.

---

## 6. Stitch settings (the shape panel)

Select a drawn shape and its section opens at the top of the panel (**Fill**, **Satin**, **Line**
or **Applique**). Every number has **−** and **+** buttons, or type a value and press Enter (Esc
puts it back, and so does emptying the box).

### In view
The shape's **thread** (click it to choose another, from your own spools, a brand chart, or any
color), **Stitch as**, **Style** for lines, **Density** (Light, Normal, Dense), a fill's **Angle**
and **Draw the angle**, and an applique's border, tack-down and cut file.

### Underlay and Advanced stitch settings (folds inside the section)
**Underlay** holds the underlay buttons. **Advanced stitch settings** holds the exact spacing,
length, random, edge pad, **Weave**, **Feather**, the **Hand-sewn look**, **Carve lines**,
reverse, split and lock stitches, and **✨ Ask the Stitch Advisor** if the AI add-on is on. Only
the settings that do something for the shape are shown (an applique has no lock-stitch boxes;
open fill patterns, listed below, hide the row settings they don't use).

**Your settings carry over.** Change a shape's density, length, underlay or any other stitch
setting and the next shape of that kind starts with it: make a fill 0.6 mm and every new fill is
0.6 mm until you change it again. (A fill's angle and angle lines aren't carried over; they
belong to their shape.)
**Use the standard settings for new fills** (at the end of Advanced) goes back to the standard
ones; shapes already drawn keep theirs.

| Setting | Fill | Satin | Line | What it does |
| --- | --- | --- | --- | --- |
| **Stitch as** | Line · Satin · Fill · Applique | Line · Satin · Fill · Applique | Line · Satin · Fill · Applique | Switch a shape between a running stitch line, a satin ribbon, a fill and an applique (fill and applique need a closed shape). |
| **Underlay** | Auto · Edge · Cross-hatch | Auto · Center · Edge · Zigzag | | The foundation sewn first so the top stitches sit flat. **Auto**: for a fill, an edge run on light fabrics and an edge run plus cross-hatch on the others (closer on knit, fleece, towel and stretch); for a satin, it goes by the fabric and the satin's width. |
| **Density** | ✓ | ✓ | | **Light / Normal / Dense** for a quick choice, then a **Lighter ↔ Denser** slider with its number right under it (e.g. **0.40 mm between rows · 2.5 rows per mm**, or rows per inch when you work in inches; it changes as you drag), and the exact **Spacing** to type, all in view. A value between the presets leaves none of them lit. |
| **Angle** | ✓ | | | Direction of the rows (0–179°). **Draw the angle (I)** sets it with a line. |
| **Length** | ✓ | | ✓ | Stitch length (up to 7 mm for fills). |
| **Random** | ✓ | | | Moves needle points a little at random (0–50%) so no lines show across the fill. |
| **Weave** | ✓ | | | How neighboring rows' needle points line up: Standard, Brick, Twill, Smooth or Random (Tatami, Gradient and Blend; below). |
| **Feather** | ✓ | | | Ragged row ends on the left, right or both, for fills sewn in rows (below). |
| **Hand-sewn look** | ✓ | ✓ | ✓ | Small irregularities, as if sewn by hand (fills sewn in rows; not motif lines; below). |
| **Edge pad** | ✓ | ✓ | | Pull compensation: widens the shape because stitches pull the fabric in. **Auto** chooses from the fabric (and, for satins, the width). |
| **Reverse** | ✓ | | | Sews the fill from the other end. |
| **Split long stitches** | | ✓ | | Splits satin stitches longer than the length you set (underlay too, and the outer edge at sharp corners), so they can't snag. |
| **Style** | | | Single · Triple · Bean · Motif | One pass, three passes end to end, each stitch three times, or a motif (below). |
| **Lock stitches** | ✓ | ✓ | ✓ | Tiny tie-in and tie-off stitches so the thread can't unravel. (An applique always locks round its stops.) |

### Fill patterns
A fill's **Pattern** (in its section) changes how the area is stitched:

| Pattern | Looks like | Its setting |
| --- | --- | --- |
| **Tatami** | Rows of stitches: the standard fill. | |
| **Gradient** | Rows that open out from dense to sparse across the shape: shading, fading out. | **Sparse end**: the spacing at the light end (the dense end uses Density). The Angle sets which way it fades. |
| **Wave** | Rows that ripple like water. | **Wave height** and **Wave length**. |
| **Contour** | Rows that follow the outline inwards, ring by ring. | Row spacing is the density; Light gives an open, ringed look. |
| **Stipple** | One meandering line over every part of the shape, never crossing itself: the quilting look, great for backgrounds and applique. It says if a part is too narrow for the loop size. | **Loop size**. |
| **Cross-stitch** | Little Xs on a square grid. Squares over about 5 mm get a needle point in the middle of each diagonal. | **Square** size. |
| **Spiral** | One line that starts in the middle of the shape and winds out to its edge in rings. Where the shape cuts the rings short, LUDD sews the nearest piece next and joins them along the edge, never across the rings, so most shapes get a light outline (a circle hardly any). A satin border covers it on the outside edge. With Underlay on **Auto** it has none. Rings closer than 0.6 mm can pucker, and LUDD says so. | **Ring spacing**: how far apart the turns are (0.4 to 6 mm, normally 1.5). Stitch Length goes up to 4 mm. |
| **Blend** | The shape's color fades into a second (and a third) across the rows. | Its other colors and **Balance** (below). |
| **Motif** | Rows of a little pattern across the shape. | **Motif**, **Repeat**, **Height**, **Row gap**, **Shift alternate rows** and Angle (below). |
| **Maze** | One path that winds into the shape and back out, never crossing itself. | **Path spacing** (0.8 to 6 mm, normally 2). |
| **Ripple** | Rings spreading from the middle, like a drop in water. | **Ring spacing** (0.6 to 8 mm, normally 2). |
| **Mesh** | A net of two sets of lines. | **Cell size** (1 to 10 mm, normally 3), **Crossing angle** (45 to 90°) and Angle. |

Tatami, Gradient, Wave and Blend are **fills sewn in rows**. Contour, Stipple, Cross-stitch,
Spiral, Motif, Maze, Ripple and Mesh are **open patterns**: they skip the cross-hatch underlay
(it would show through) and have no Random or Edge pad. Only Motif and Mesh have an Angle, and
only Contour has Density. A Gradient and a Blend skip the cross-hatch too, so they really fade;
on **Auto**, Blend, Motif, Maze, Ripple and Mesh have no underlay at all. A project that uses any
of the new patterns or settings below needs this version of LUDD or newer to open.

### Blend
**Pattern → Blend** fades the shape's color into another across the rows. The rows are evenly
spaced, just where a one-color fill puts them, and each row goes to one of the colors: more of
them to a color where it is stronger. So each color thins where the next one thickens, and
together they cover like one fill (Density is the coverage of all the colors together). Where a
color thins out it sews at least two rows side by side, never one lone row.

    =============   first color
    =============
    -------------
    =============
    -------------
    -------------   second color

Under Pattern: click the **Second color** to change it (it starts white, or navy on a light
shape), **Add a color** (up to three; choose its color), **Swap the colors** to fade the other
way, and **Balance** for which color takes more of the shape. The fade runs across the rows, so
turn the **Angle** (or drag the purple dots) to point it. Each color sews in turn, with a thread
change between them; Order & colors lists each one. Turning or mirroring the shape keeps every
color on the same side of it. If a blend looks stripy, make it denser or set Weave to Smooth.
Every color is sewn whenever there are at least two rows per color. A small shape or a wide
Spacing may have fewer rows than that: the blend then sews the colors it can, and a warning says
which color is left out (make the shape bigger or the Spacing smaller).

### Motif fill and My motifs
**Pattern → Motif** covers the shape with rows of a little pattern: Wave, Zigzag, Scallop,
Blanket stitch, Leaves, or one of your own.

    /\/\/\/\/\/\/\    Repeat: how long one repeat is
      /\/\/\/\/\/\    Height and Row gap: how tall rows are, and the space between
    /\/\/\/\/\/\/\    Shift alternate rows: moves every other row along

**My motifs** (Alt+Shift+M, ⋯ → Motifs…, or **My motifs…** under the Motif list) shows the
built-in motifs and yours. To make one, draw **one repeat** as a line from left to right, select
it, open the window and choose **Save the selected line as a motif…**. The line's start and end
become the repeat's start and end (at least 2 mm apart; the line can't be closed). Choose it under
**Motif** on a motif line or a motif fill. **Import…** and **Export…** move motifs between
computers; **Delete** removes one of yours. A motif so busy that it would sew far more stitches
than any design is refused with a message. A shape keeps its own copy of the motif it uses, so a
project sews the same anywhere, even if the motif isn't in that computer's list (Export it and
Import it there to use it on new shapes).

### Maze, ripple and mesh

    Maze              Ripple            Mesh
    +----------+        .------.        +--+--+--+
    | +------+ |      .' .--.  '.       |  |  |  |
    | | +--  | |     (  (    )   )      +--+--+--+
    | | +----+ |      '. '--' .'        |  |  |  |
    | +---------        '----'          +--+--+--+

**Maze** is one path that winds in to the middle and back out between its own turns, never
crossing itself; it starts near the green dot and ends beside it. A shape with a hole, or one
pinched into many parts, is sewn as several mazes, and LUDD suggests Contour. **Ripple** spreads
rings from the middle of the shape's widest part. **Mesh** crosses two sets of lines, square at
a Crossing angle of 90° or slanted below it. Stitch Length goes up to 4 mm on all three.

### Weave
In Advanced, **Weave** sets how the needle points (o) of neighboring rows line up:

    Standard         Brick            Twill
    o-----o-----o    o-----o-----o    o-------o----
    --o-----o----    ---o-----o---    --o-------o--
    ----o-----o--    o-----o-----o    ----o-------o
    o-----o-----o    ---o-----o---    ------o------

Standard is the usual fill; Brick looks like brickwork; Twill shows fine diagonal lines; Smooth
shows no lines; Random gives a matte surface. Wave keeps its own weave.

### Carved lines
Carved lines press a drawing into a fill sewn in rows: every row drops a needle exactly where it
crosses a carved line, so the line shows as a groove.

    ------\----------
    -------\---------     the \ is the carved line: each row
    --------\--------     has a needle point on it
    ---------\-------

Select the fill and press **Shift+C** (or Advanced → **Carve lines**, or right-click → Carve
lines into the fill). Draw a line over it with the usual clicks; **Enter** finishes it. Draw
more, or press **Esc** when you're done. The lines move and resize with the shape, never change
its size, and their points can be dragged like a hole's while the fill is selected. **Remove
carved lines** is in the panel's ⋯ menu and the right-click menu. A line that runs along the
rows won't show (LUDD says so): turn the fill's Angle, or draw the line across the rows.

### Feathered edges

    ===============-
    ===========          Feather → Right ends: each row stops short
    ================     by a different amount, so the edge is ragged
    ============

In Advanced, **Feather** makes the row ends ragged on the left, the right or both, to blend a
fill into what's beside it (fur, shading, or two fills feathered into each other). **Depth** (0.5
to 6 mm, normally 2) is how far in the ends can reach. Left and right mean the ends of the rows as
they run at 0° (the panel shows a picture); turning or mirroring the shape keeps the ragged side
where it was. On Auto underlay a feathered fill has no edge run, which would show.

### Hand-sewn look

    ----- ------- ---- ------ -----      stitches a little uneven,
    --- ------ ------- ---- ------       like sewing by hand

The **Hand-sewn look** slider (Advanced, 0 to 100%) on lines, satins and fills sewn in rows makes
stitches a little irregular: line stitches vary in length and wander a touch, satin edges and
spacing vary, and a fill's row ends and needle points move. The same design always sews the same
way. Motif lines don't have it.

### Turning fills

    \\\  |||  ///     two or more angle lines:
     \\\ ||| ///      the rows turn smoothly to
      \\\|||///       follow each one

On a **Tatami** fill, press **Shift+I** (or **Add another line** under Angle, or right-click → Add
another angle line) and click twice to draw a second direction line: the rows turn smoothly to
follow each line where it lies, like the veins of a leaf. The fill's old direction becomes the
first line. Drag a line's purple dots to move it, right-click a line to remove it, **I** to draw
the first one again, or **Back to one angle** to keep only the first line's angle. The rows reach
every edge of the shape. If the turn is too sharp for the shape, the rows meet in a crease (the
shape stays filled), and when the crease is deep LUDD says so: move the lines further apart or make
the turn gentler. Two lines with their middles in the same place can't both be followed: the rows
follow the first one, and LUDD tells you to move the other at least 1 mm away. With three or more
lines in a row, keep neighbors fairly close in direction: lines at 0°, 60° and 120° side by side
leave the rows far off the middle one. Where a turning fill's rows are sewn in separate groups, a
thin line of thread can show across them. Other patterns don't use the lines, but they come back
with Tatami.

### Motif lines
A line's **Style → Motif** repeats a little pattern along it: **Wave**, **Zigzag**, **Scallop**,
**Blanket stitch** (the applique edge stitch), **Leaves** or one of **My motifs** (above), with
its **Repeat** length and **Width**. Use it for decorative borders, or round an applique with
blanket stitch. A motif line that would take more than about 60,000 stitches (a whole design is
usually 5,000 to 30,000) is refused: make the motif longer (Repeat) or simpler.

### Size and points
Size (W, H), **Add points (K)** and **Add a hole (O)** for fills. Turn, mirror, duplicate,
Repeat…, Pin and Remove are at the top of the panel.

### Satin ribbons
A satin is a band of smooth, shiny stitches sewn straight across from edge to edge: ideal for
outlines, borders and details over a fill. In LUDD you draw a satin like a line:

1. Pick **Satin** (C) and **click along the middle** of where the ribbon goes (curve points,
   Ctrl for straight, Shift for corners, as for a line). The pale band shows how wide it will be.
2. **Enter** or right-click finishes it; **Ctrl+right-click** closes it into a loop (a ring around
   a shape).
3. Set its **Width** in the panel (1 to 12 mm). New satins start as wide as the last one you set.

Ways to get a satin without drawing it:
- **Add a satin border** (Shift+B, or the button in a fill's section): a closed ribbon along the
  fill's edge, sewn right after it. This is the "fill blob, then satin outline" look.
- **Stitch as → Satin** turns an open line into a ribbon, and a fill (or a line drawn all the way
  round) into a **satin fill** (below).

### Satin fill (shape-shifting satin)
Set a closed shape (a fill, an applique, or a line drawn all the way round) to **Stitch as →
Satin**, or choose **Satin fill** in Auto-trace, and the whole shape is filled with **one satin column that turns and changes width with
the shape**, as Embrilliance does: petals, leaves, swooshes, hair, flames. LUDD finds the shape's two
tips, splits its outline there into the satin's two sides, and sews every stitch straight across
from side to side, so the stitches follow the shape's curve: wide where it's wide, narrow at the
tips. Build a design from many of these, as in a "Portrait of a Rose" style.
- **↻ Turn the stitches another way** (**Shift+W**, in its section) tries other tips, so the stitches
  run the other way across the shape. Press again for the next; it comes round to the first.
- Drag the points on either side to reshape it, as with any satin drawn by clicking both sides.
- A satin wider than about 6.5 mm gets **Split long stitches** turned on, so nothing snags; long, thin
  shapes look best. Holes can't be filled with one satin: such a shape stays a fill.
- **Stitch as → Fill** turns it back into a fill with the same outline.
- **Auto-trace** a dark line in a picture: the ribbon follows its middle, as wide as the line.

Satins wider than about 7 mm make long loose stitches: LUDD warns from 7 mm unless **Split long
stitches** is on (or use a fill instead); under about 1 mm the stitches pile up. LUDD also warns
when a satin curves tighter than it is wide (it folds over), when a satin's two sides cross, and
when a line is too short to sew. Satins from projects made before 1.0.1 were drawn by clicking
both sides; they still sew and edit as before.

---

## 7. Lettering
**Text** (Shift+T), then click where it goes. In its panel:
- The **text** (stitches update after a short pause; typing is never undone by an update, and
  Esc brings back the text from before you started typing). It can have several lines: **Enter**
  starts a new one, and **Ctrl+Enter** or clicking elsewhere finishes (a monogram's initials stay on
  one line).
- **Font**: any font installed on your computer (type to search; the list shows 200 at a time and
  says so). Stitch fonts (`.luddfont`) too. Letters a font doesn't have are left out, and LUDD
  names them.
- **Letter height** (the real height of a capital H, 2 to 200 mm), **thread**, **Satin look**
  (smooth, shiny; best for names), **True satin** or **Fill** (for big letters). Stitch fonts sew
  the stitches they were made with, so they don't offer these.
- **How the letters are stitched** is written under those buttons: with **Satin look** each
  letter is filled with long, smooth satin stitches across its strokes, at the angle that crosses
  them best; with **True satin** each stroke is its own satin column (see below); with **Fill**
  each letter is a woven (tatami) fill.
- **Each letter's start and end**: with the lettering selected, every letter shows a small green
  (start) and red (end) dot. Each letter starts by where the one before ended and ends towards the
  next, so the jumps between letters are short. **Drag a dot** and it slides along that letter's
  edge, staying where you let go. **Reset starts and ends** (Ctrl+Alt+R) puts them all back.
  (Changing the words, font, size, spacing, look, shape or a layout setting makes new letters, so
  the starts and ends chosen go back too; so do Put the text on a line and One file per name.
  Letters from a stitched font have no dots.)
- **Break into shapes…** (Ctrl+Alt+X, also on the right-click menu) turns the letters into
  ordinary shapes, grouped (in the lettering's own group, if it had one), in the same place and
  sewing order, pinned if it was, keeping their starts and ends: then each can have its own
  points, stitch type, density, direction and dots. Stops and trims added to the lettering are
  left out (LUDD says so). The words can't be retyped after that (Ctrl+Z undoes it).
- **Shape**: Straight, Arch, Smile (under a curve) or Circle (the letters spread evenly all the
  way round; use Arch for a short curve), with the curve's size.
- **Adjust single letters** (below) and **Monogram** (below).
- **More options** (inside the Lettering section; it was called Advanced): lines, slant, envelope
  and stacked letters; shadow and outline; extra letter spacing; **One file per name…**; **Save
  this font as a stitch font**.
Letters under 6 mm tall are hard to sew (dots and thin parts start to drop out), so LUDD leaves
their underlay out to keep them thin, and warns you, naming the smallest height (for a monogram,
its smallest letters). It goes by the height each letter sews at: resizing with the handles and a
single letter's own size count (making text only wider doesn't). A stitched font's letters keep
the underlay they were made with. It also warns when a font's strokes are so thin at your size that they sew as a single line: use a
bolder font or bigger letters. Projects carry their fonts inside them, so
lettering looks the same on another PC. If an older project uses a font that isn't installed on
this computer, its lettering is shown in a standard font (Arial) with a warning in Checks, so the
design still opens; install the font or pick another.

**Save this font as a stitch font** makes a `.luddfont` from the font: every Latin letter with its
accents, the punctuation the font has, and its kerning. It goes straight into LUDD's fonts folder
(Windows: `%APPDATA%\Ludd\fonts`; the message says where) and appears in the font list at once,
marked "stitch font". To fine-tune it, open the file in a text editor; changes show as soon as you
save. If a stitch font lacks a letter, LUDD uses the other case or the letter without its accent,
and says so.

**Text on a line of your own**: draw a **Line** where the text should go (any curve), select the
line and the lettering (Shift+click both), then **⋯ → Put the text on the line** (in the panel's
⋯, or Ctrl+Alt+L). The letters stand on the line, centered on it and upright whichever way you
drew it; on a closed shape they stand outside it, centered at the top. The line itself is used up.
Putting text on a line lets go of its turn and mirror (its size stays, as letter height), and
turning it afterwards pivots on the line. Its Shape then reads **On your line**; pick Straight,
Arch and so on to put it back. If the text is longer than the line, the extra letters bunch up at
its ends (or overlap, on a closed line) and Checks warns you: draw a longer line or make the
letters smaller. A monogram can't follow a line.

### Lines, slant, envelopes and stacked letters
These are under **More options**. With more than one line, **Align** puts the lines left, center
or right, and **Line spacing** sets the distance from line to line (0.8 to 3 letter heights, 1.3 to
start). On an arch the lines curve together; a circle or a line you drew takes only the first line.
**Slant** leans the letters up to 30° either way. **Envelope** bends straight text into a shape:
Bulge, Pinch, Pennant right or left, Wave, Arch top or Arch bottom, with an **Amount** slider. **Stack
the letters** puts them one under another (several lines become columns). Envelopes and stacking work
on straight text only, and not together; where they're off, the control says why.

### Adjust single letters
Press **Adjust single letters** (or Alt+Shift+A, or right-click the text). A dot appears on each
letter: click one, then drag it, or use the arrow keys (1 mm, with Shift 1 cm, with Ctrl 0.1 mm).
The panel shows that letter's **Size**, **Turn**, **Thread** and **Stitch angle** (not for True
satin or stitched-font letters), and **Put this letter back**. **Put the letters back**
(Alt+Shift+Z) undoes all of them. **Done** or Esc leaves. Letters in other colors are listed
separately in Order & colors; **Put back the original colors** clears them. Color sets don't save a
single letter's color.

### True satin
Each stroke of a letter is sewn as a satin column that follows it, the way hand-made embroidery
fonts are. Check the preview: if a letter looks wrong, use **Satin look**, or **Break into shapes**
and adjust its columns. When LUDD can't make good columns for a letter, it sews the whole letter in
Satin look and tells you how many. It works best on small and medium letters; very large letters
more often fall back.

### A stitch font from letter files
If you bought a font as one stitch file per letter, press **Make a stitch font from letter
files…** in the font list (or Ctrl+Alt+F). Choose the folder (or the files). LUDD shows every file
with the letter it guessed from the file's name: fix any that are wrong (files without a letter are
left out; one letter can't be used twice). Name the font and set the **Letter gap**. The preview
stands the letters on a line; click one that sits too high or low and nudge it (a lowercase j often
needs it). Save, and the font is in your font list. If the files have several colors, the text sews
color by color, and you can change each color in Order & colors. Choose its size with **Letter
height**: past 20% bigger or smaller than the font's own size, LUDD rebuilds the stitches at the new
size where it can (check the preview). The corner handles only stretch the stitches, and LUDD warns
you. These letters can't be broken into shapes, or have a shadow or outline. Only make fonts from
designs you're allowed to use this way.

### Monograms
Tick **Monogram** (or Ctrl+Alt+M) and type one to three initials. Choose **Classic** (small, big,
small), **Block** (all the same size) or **Stacked** (two small ones on top of each other, then a big
one). Add a **Frame**: circle, double circle, diamond, square, scallop circle or laurel, with the
**Frame gap** from the letters and its own thread if you like. The frame sews after the letters.

### Shadow and outline
Under **More options**, tick **Shadow** for a copy of the letters peeking out behind them (set how
far right and down, and its thread; only the part that shows is sewn). Tick **Outline** for a satin
or triple-run line around the letters (gap, width and thread). Both follow the text when you change
it. Not for stitched fonts.

### One file per name, and name templates
**One file per name** (Ctrl+Alt+N, or under More options): type a list of names, one per line, or
**Load a list…** (a CSV or text file, such as a spreadsheet saved as CSV; up to 2,000 rows). Choose
a file type and a folder, and LUDD saves one machine file per name (Emma.pes, Jack.pes…), each the
whole design with the selected lettering changed to that name. Each file is prepared just as **Save
for machine** would (your machine and hoop; for the PE550D, a stop wherever the thread needs
cutting). Files already in the folder are never replaced: a repeated name is saved as "Emma (1).pes",
and LUDD tells you which files got a number. Very long names are cut to 100 characters in the file
name, and the few names Windows keeps for itself (such as Con or Aux, even before a dot) get a _ in
front. It also tells you if any name is too wide for your
hoop, and if one name can't be saved, the others still are and a message names it, says why and
stays until you close it. It's offered when lettering is selected. For team shirts, party favors
and gifts.

To fill more than one piece (say a name and a number), tick each under **Lettering to fill** and
pick its column. If a cell is empty, that piece is left out of that file. **Shrink long names to
fit** keeps long names within the width you set. A column called **color** (a hex color or a thread
number) sets each file's thread, and a column called **file** names the file. **Preview on the
design** (◀ ▶) shows each name in place without changing your design.

**Name templates**: **Save this layout as a name template…** (Ctrl+Alt+P, also in that window)
keeps the whole design. Later, choose it under **Start from a template**: it opens as a new design,
so the template stays as it was.

### Placement guides
**⋯ → Placement guides…** (Alt+Shift+G) shows where designs usually go on a bath towel, hand
towel, pillowcase, sheet hem, left chest (adult or child), tote bag, napkin corner or cap, with the
measurements and a small drawing. **Print a placement sheet** prints them with a crosshair and your
design at real size. They're starting points: check on your own item.

---

## 8. Applique
Make any closed shape an **Applique** (its section → Stitch as). The machine sews:
1. a **placement line**, then stops: lay your fabric piece over it;
2. a **tack-down** (zigzag, or straight for felt and non-fraying fabric), then stops: trim the
   fabric close to the stitching;
3. a **satin border** over the raw edge (its width and density are adjustable; a border wider
   than 7 mm is split automatically so its stitches can't snag, sharp corners included).

Moving from one edge to the next (a hole, or another piece) more than 3 mm away is marked for
trimming, as in fills; with "Have the machine cut jump threads" on, the PE550D stops there to cut.

A piece with **holes** (O while it's selected, or a fill with holes turned into an applique) gets
all three round each hole's edge too, and the cut file has a cutting line for every hole.

**Save cut file (SVG)** (or ⋯, Ctrl+Shift+U) saves every applique piece's outline at real size,
for a cutting machine (Cricut, ScanNCut, Silhouette) or to print and cut by hand. Untick **Sew a
placement line first** if you cut pieces beforehand and place them by eye.

---

## 9. Threads and colors

### Colors (in Order & colors)
Each step's colors are in **Order & colors** (see *Order & colors* in section 5), with the
**Palette** of every thread in use at the top. **Match…** (it reads **Match to mine…** once you've
added your own spools) finds the nearest thread for every color, from your own spools first.
**⋯ (Color options)**: **Combine same colors next to each other** (Ctrl+Shift+C), **Sort colors**
so each thread is sewn once (Ctrl+Shift+L), **Put back the original colors** (Ctrl+Shift+R).
Sort colors never moves a shape ahead of one it should sit on top of: a color that can't be
gathered safely stays apart, and a note says so.

### Changing a thread
**✎** (or right-click → **Change thread…**, or **Alt+T** for the selected shape) opens the thread
list for the chosen chart, with the **closest matches** to the current color at the top. The
current color's code (like #7B2FF7) shows beside its name.

- **Search** by thread number, name or **color code**: type **#FF7A1A** (or FF7A1A) and the whole
  chart is listed closest to that color first. **Use exactly #FF7A1A** uses that exact color.
- A number that isn't in this chart? LUDD says which of your other charts has it; click to switch.
- **Or mix your own color**: pick any color under the list, for a spool you don't have a chart for.

### Color sets
**Order & colors → Color sets** keeps several color versions of one design: **Save colors** under a name
(Pink, Blue, School colors…), recolor the design, save that too, and **Use** switches between them
in one click (and one Ctrl+Z). They're saved in the project.

### Preview on a garment
**Design → Preview on**: show the design on a **T-shirt** (left chest), **tote bag**, **towel**
(corner), **baby bodysuit** or **cap**, or plain fabric, in a **fabric color** you choose. It's
only a picture behind the design, to see how it will look: nothing is stitched. Zoom out to see
the whole garment.

### My threads and charts
**⋯ → My threads & charts** (Ctrl+T):
- **My threads**: the spools you own. Add them from a brand chart, or with **Add a spool by
  color…** for unbranded Amazon assortments. Matching uses these first.
- **Brand charts**: Brother and Janome built in; import any brand from a CSV file. Importing
  under a name you've used before replaces that chart (to update it); any other name is kept
  as a chart of its own.

---

## 10. Fabric, checks and quality

### Stitching on (Design section of the panel)
Choose the fabric: cotton or woven, denim or canvas, T-shirt knit, fleece or sweatshirt, towel or
terry, stretchy sportswear, felt. LUDD adjusts the density of drawn shapes and lettering for the
fabric (also a density you set by hand: the panel shows your setting, the fabric scales it),
and the pull compensation and underlay of drawn shapes (pull compensation or underlay you set by
hand on a shape wins). It shows the **stabilizer** to use, plus a **topping** for towels and
fleece, and suggests **knockdown stitches** there.

### How long it sews, and how much thread
The Design section shows **Sewing time**: about how long your machine takes at its top speed (650
stitches a minute on the PE550D), plus how many times you'll change the thread. Long stitches slow
the machine down, so allow a little more. **Thread** shows about how much top thread the design uses,
and the bobbin (about a third of that). Open **Thread used** to see each color, so you can check
there's enough on the spool before you start. These are estimates: fabric and tension change them.

### Check before stitching
The **Check before stitching** list warns before you stitch: too much thread in one place, the
needle hitting one spot over and over, many very short stitches, long loose stitches (over 7 mm),
shapes that almost touch. Each says **why it matters** and **what to do**; **Show me** jumps to
the spot, and **Fix it** (on tiny stitches, needle clumps and thick spots in a stitch file) opens
**Repair this design** with the right repair ticked. Thick spots inside a stitch file you placed (a
bought design) are a note, not a warning: they often sew fine. The same checks appear in Save for
machine.

### Machine extras (⋯ menu)
- **Insert a stop / trim at the needle** (Ctrl+Shift+P / Ctrl+Shift+T): at the stitch-out bar's
  position, in a stitch file, a drawn shape or lettering. A stop or trim stays if you delete the
  stitch it was on. In a drawn shape or lettering it's left out (with a note) once the shape is
  changed, since its stitches move.
- **Trim jumps longer than 3 mm** (Ctrl+Shift+J): turns the design's long jumps into trims. It's
  one setting for the whole design, including designs added later.
- **Basting box** (Ctrl+Shift+B): a frame sewn first to hold fabric to stabilizer; remove it
  after. If the frame would make the design too big for the hoop, it comes in closer (down to
  2 mm from the design).
- **Knockdown stitches** (Ctrl+Shift+N): a light grid sewn first under the design so towel loops
  and fleece pile don't poke through. Set its thread to match the fabric: the ✎ next to
  **Knockdown** in Order & colors.
- **Don't sew what's hidden under shapes on top** (Alt+Shift+O), for shapes you draw in LUDD:
  a fill leaves out the part that a shape sewn later covers (a dense fill or satin, lettering or an
  applique), so overlaps don't sew thick and hard. It keeps a margin under the edge so no fabric
  shows (**More options → Keep under the edge**, 1 mm, in the Design section while it's on); the
  margin itself is sewn by both. It follows the shapes as you move them. A fill that would be
  completely hidden is sewn whole, with a note. Now and then a short travel line shows across the
  lower fill. If a gap shows at an edge, raise the margin.
- **Fewer jumps & trims** (Ctrl+Alt+T, also a tick box in the Design section; on for new
  designs): when the needle moves from one shape to the next in the same thread, and the way
  there will be covered by stitching sewn later (rows close enough to really hide it), it sews a
  few small travel stitches there instead of jumping. No jump, no trim, no thread to snip (handy
  on machines like the PE550D that only cut at color changes).
- **Sew in the shortest order** (Ctrl+Alt+O): shapes in the same thread (fills, satins and lines
  alike) are put in the order that keeps the moves between them shortest. Shapes whose stitches
  overlap keep their order, since it decides which is on top; the others move around them. If
  nothing can be shortened, LUDD says so.
- **Optimize jumps** (Ctrl+Alt+J, in the Design section and ⋯): keeps the sewing order, and instead
  chooses where each piece **starts and ends**, so that pieces in the same thread hand over to each
  other like magnets: each piece ends next to the one after it, and that one starts right there. A
  line or satin is sewn whichever way round suits; a border (a closed line or ribbon) starts at its
  point nearest the piece before; a fill starts at the edge nearest it, with its rows sewn the best
  way. LUDD says how much shorter the jumps got (e.g. 132 mm → 45 mm); Ctrl+Z undoes it. Stitch
  files, lettering and appliques stay as they are. Run it after the design is laid out (moving or
  reshaping pieces later can make it worth running again).

---

## 11. Settings (⚙, Ctrl+,)
- **Look**: Automatic (follows your computer), Light or Dark; **Always show the design on light
  fabric**.
- **My machine** and hoop.
- **Measurements**: inches or millimeters.
- **Workspace**: show the hoop, show the grid, realistic thread, Trace Assist.
- **AI tracing**: get (or remove) the optional AI tracing model for Auto-trace, turn its guesses
  on or off, and **Forget which Auto-trace guesses I usually pick**.
- **AI add-on** (below).
- **Updates**: tell me when a new version is out (asks GitHub when LUDD starts, never before
  you've answered the welcome card; nothing about you is sent), **Check now**, and the version you
  have.
- **About**: LUDD's own license (GPL-3.0-or-later) and **Licenses…**, the licenses of the free
  software and fonts LUDD is built with (also in `THIRD-PARTY-NOTICES.txt` in the install folder).

---

## 12. AI (optional, off by default)
Everything in LUDD works without AI. There are two separate, optional parts.

**AI tracing** (Settings → AI tracing) makes Auto-trace better at photos and shaded art. It's a
small model that runs on your own computer; LUDD asks before the one-time download (about 45 MB)
and never sends your pictures anywhere. See [Auto-trace](#auto-trace-shifta).

**The AI add-on** (Settings → AI add-on) is for the Stitch Advisor and AI answers in Help:
- **Off**: nothing is sent anywhere.
- **On this computer**: uses **Ollama**, a free program that runs AI models on your own PC (a
  graphics card with 8 GB helps). Install it, then `ollama pull qwen2.5vl:7b`. If its address
  points at another computer, LUDD treats it like the cloud and shows what will be sent first (the text,
  any pictures, and, under its own heading, LUDD's fixed instructions to the AI).
- **Cloud**: Anthropic, or any OpenAI-compatible service, with your own account and key (the
  address must start with `https://`). On Windows your key is stored encrypted for your Windows
  account; on a Mac or Linux, in a file only your user account can read. **Before anything is
  sent**, LUDD shows what will go (your question or the shapes' details, and any pictures; LUDD's
  own fixed instructions to the AI go too), where it goes, and, if you enter the service's prices,
  the most it can cost. If the service tries to send LUDD on to another address, LUDD stops
  there, so your key only goes to the address in Settings, and asks you to check that address.

**Stitch Advisor** (✨ in a shape's Advanced stitch settings, ⋯, or Ctrl+Shift+I): suggests stitch type, fill
angle, density, underlay and sewing order, each with a reason. **Accept** or **Dismiss** each, or
**Accept all** (one Ctrl+Z undoes it). Nothing changes unless you accept. A suggestion to turn a
line into a satin (or back) can be accepted; one to turn a fill into a satin can't (draw a satin,
or use **Add a satin border**).

**Help** (F1): with AI on, **Ask AI** answers in plain words from the guide.

---

## 13. Help and updates
- **Help** (F1, or **?** in the toolbar): type a question or a few words; matching sections of the
  guide appear. Works offline.
- **If the engine stops** (the status bar says so), LUDD starts it again by itself; if it can't,
  click **Restart engine** in the status bar. Your work stays on screen.
- **Updates**: when a new version is out, a strip offers **Install and restart** or **Later**.
  Your work is offered back after the restart if you hadn't saved. **⋯ → Check for updates** asks
  right away.

---

## Keyboard shortcuts

LUDD uses Embrilliance's keys where they exist. Ctrl is ⌘ and Alt is ⌥ (Option) on a Mac.
Shortcuts are also shown in every menu and on every button's tooltip.

### Files and app

| Do this | Press |
| --- | --- |
| Browse designs | Ctrl+Alt+B |
| Fewer jumps & trims (on/off) | Ctrl+Alt+T |
| Sew in the shortest order | Ctrl+Alt+O |
| Optimize jumps (starts and ends) | Ctrl+Alt+J |
| New design | Ctrl+N or Shift+D |
| Open… | Ctrl+O |
| Open a sample design… | Ctrl+Shift+E |
| Save project | Ctrl+S |
| Save project as… | Ctrl+Shift+S |
| Add another design… | Ctrl+Shift+O |
| Add a picture to trace… | Ctrl+I |
| Save for machine… | Ctrl+E |
| Print template & thread list… | Ctrl+P |
| Batch convert folder… | Ctrl+B |
| My threads & charts… | Ctrl+T |
| Settings… | Ctrl+, |
| Help | F1 |
| Check for updates | Ctrl+Shift+F1 |
| Stitch Advisor (AI)… | Ctrl+Shift+I |

### Editing and selecting

| Do this | Press |
| --- | --- |
| Undo / redo | Ctrl+Z / Ctrl+Y (or Ctrl+Shift+Z). While drawing, Ctrl+Z removes the last point and Ctrl+Y does nothing |
| Select several | Shift+click or Ctrl+click |
| Select everything | Ctrl+A |
| Group / ungroup | Ctrl+G / Ctrl+U |
| Copy / cut / paste | Ctrl+C / Ctrl+X / Ctrl+V |
| Duplicate | Ctrl+D |
| Remove | Delete or Backspace |
| Repeat, carousel or mirror ×4… | Ctrl+Shift+D |
| Pin in place / unpin | Ctrl+L |
| Outline / offset around the selection | Ctrl+Shift+K |
| Knife: cut the selected shape | Shift+K |
| Merge the selected fills | Ctrl+M |
| Edit stitches of a stitch file | Ctrl+Alt+E |
| While editing stitches: add a stitch / add a jump | Insert / Shift+Insert |
| While editing stitches: lock both sides of a jump | Alt+Shift+T |
| Repair this design… | Ctrl+Alt+D |
| Rebuild stitches at this size (on/off) | Alt+Shift+R |
| Remove tiny stitches (on/off) | Alt+Shift+S |
| Thin out dense spots (on/off) | Alt+Shift+D |
| Limit density for this fabric (on/off) | Alt+Shift+L |
| Remove hidden stitches (not built yet) | Alt+Shift+H |
| Put the text on the selected line | Ctrl+Alt+L |
| Break lettering into shapes | Ctrl+Alt+X |
| Reset the letters' starts and ends | Ctrl+Alt+R |
| One file per name | Ctrl+Alt+N |
| Adjust single letters / put the letters back | Alt+Shift+A / Alt+Shift+Z |
| Make a stitch font from letter files… | Ctrl+Alt+F |
| Save this layout as a name template… | Ctrl+Alt+P |
| Placement guides… | Alt+Shift+G |
| Rename | F2 |
| Change thread of the selected shape or text | Alt+T |
| Sew earlier / later | Ctrl+[ / Ctrl+] |
| Sew first / last | Ctrl+Shift+[ / Ctrl+Shift+] |
| Center in the hoop | Ctrl+Shift+M |
| Change the words of the selected lettering | Ctrl+Alt+W |
| Menu for the thing under the mouse | Right-click |
| Add a satin border to a fill | Shift+B |
| Let go of whatever you're doing | Esc |

### Drawing

| Do this | Press |
| --- | --- |
| Select and move | V |
| Line (running stitch) | L or Shift+X |
| Satin ribbon | C |
| Auto-trace | Shift+A |
| Auto-digitize the whole picture | Alt+A |
| Fill | F |
| Text | Shift+T |
| Switch between drawing and Select | D |
| Draw again with the last tool | X |
| Draw a shape like the last one / the one before | Q / W |
| Curve point / straight point / sharp corner | click / Ctrl+click / Shift+click |
| Keep the new point on 15° steps | hold Alt |
| Finish the shape | Enter, right-click or double-click |
| Finish a line and close it | Ctrl+right-click |
| Remove the last point | Backspace or Ctrl+Z (while drawing) |
| Switch the last point: curve, straight, corner | C (while drawing) |
| Drop the shape (even a single point) | Esc |
| Move around without grabbing anything | hold Space and drag |
| Move the view 1 cm while drawing | arrow keys |
| Snap new points to the grid | Shift+G |
| Add points to the selected shape | K |
| Add a hole to the selected fill | O |
| Cut the shapes on top out of the fill | Shift+O |
| Turn a satin fill's stitches another way | Shift+W |
| Set a fill's stitch angle with a line | I |
| Draw another angle line, so the rows turn (turning fill) | Shift+I |
| Carve lines into the selected fill | Shift+C |
| Motifs window (My motifs) | Alt+Shift+M |
| Remove the selected point | Delete |
| Rectangle / circle / star / monogram | Ctrl+Alt+1 / 2 / 3 / M |

### Auto-trace (with a guess on screen)

| Do this | Press |
| --- | --- |
| Next / previous guess | Tab / Shift+Tab |
| Use it (fill, or satin for a line) | Enter or right-click |
| Use it as a fill with a satin border | Shift+Enter |
| Points closer together / further apart | [ / ] |
| Add an area to the guess / cut one out | Shift+click / Alt+click |
| Spread less / more | Alt+[ / Alt+] |
| Dismiss the guess | Esc |

### Trace Assist (if turned on, while drawing over a picture)

| Do this | Press |
| --- | --- |
| Take the suggested point | Tab |
| Keep taking points to the next corner | Shift+Tab |
| Take branch 1 / 2 at a fork | 1 / 2 |
| Shorter / longer steps | [ / ] |
| Trace Assist on or off | Ctrl+Shift+A |

### Moving, turning and mirroring

| Do this | Press |
| --- | --- |
| Turn 90° right / left | R / Shift+R |
| Mirror left–right / top–bottom | Alt+H / Alt+V |
| Nudge 1 mm | arrow keys |
| Nudge 1 cm | Shift+arrow keys |
| Nudge 0.1 mm | Ctrl+arrow keys |

### Viewing

| Do this | Press |
| --- | --- |
| Move around (hand tool) | hold Space and drag |
| Rulers on/off | Ctrl+R |
| Remove all guides | Ctrl+Alt+G |
| Zoom to all | A |
| Zoom to the selection | S |
| Zoom to the hoop | 0 |
| Real size / 2–9× real size | 1 / 2–9 |
| Zoom in / out | + or = / − |
| Realistic thread (3D) | T |
| Stitch points | P |
| Stitches on/off | N |
| Pictures on/off | B |
| See-through stitches | Shift+N |
| Crosshairs | E |
| Trims, jumps and stops | J |
| Grid / hoop | G / H |
| Measure | M |
| Inches or millimeters | U |
| Density map | Alt+D |
| Needle path view | Shift+P |

### Stitch-out

| Do this | Press |
| --- | --- |
| Play / pause | Space |
| Back / forward one stitch | ← / → (nothing selected) |
| Back / forward 100 stitches | Shift+← / Shift+→ |
| Previous / next color | Page Up / Page Down |
| Start / whole design | Home / End |
| Slower / faster | comma / period (or [ / ]) |
| Machine speed | Shift+comma |

### Machine stitches and colors

| Do this | Press |
| --- | --- |
| Don't sew what's hidden under shapes on top | Alt+Shift+O |
| Combine same colors next to each other | Ctrl+Shift+C |
| Sort colors (fewest thread changes) | Ctrl+Shift+L |
| Put back the original colors | Ctrl+Shift+R |
| Insert a stop / trim at the needle | Ctrl+Shift+P / Ctrl+Shift+T |
| Trim jumps longer than 3 mm | Ctrl+Shift+J |
| Basting box | Ctrl+Shift+B |
| Knockdown stitches | Ctrl+Shift+N |
| Save applique cut file (SVG) | Ctrl+Shift+U |
