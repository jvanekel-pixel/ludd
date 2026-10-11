# LUDD manual

Everything LUDD does, where to find it, and how to use it. For installing and a ten-minute first
design, see the [user guide](USER-GUIDE.md). Inside the app, press **F1** for Help: it searches
this same material, offline.

LUDD uses **Embrilliance's keyboard shortcuts** wherever Embrilliance has one, so if you know
Embrilliance, your fingers already know LUDD. The full list is at the end:
[Keyboard shortcuts](#keyboard-shortcuts).

---

## 1. The screen at a glance

| Area | Where | What it's for |
| --- | --- | --- |
| **Toolbar** | Top | New, Open, Save, Add design, Undo/Redo, **Save for machine**; your machine and hoop; **?** Help; **⚙** Settings; **⋯** everything else. |
| **Tool rail** | Left edge | Select, Line, Satin, Fill, Text, Shapes, Picture. The key for each tool is printed under it. |
| **Design area** | Middle | Your design on the fabric, the hoop outline and the grid. Scroll to zoom, drag empty space to pan. |
| **Panel** | Right | About the design, the fabric, whatever is selected, the sewing order, pictures, checks and threads. **Drag its left edge** to make it wider or narrower (double-click the edge to reset). **Click a section's heading** to fold it away. |
| **Stitch-out bar** | Bottom | Watch the design sew: play, step, jump by color, speed. |
| **Status bar** | Very bottom | Whether the stitch engine is connected, and the version. |

Messages appear in a strip under the toolbar. Click × to close them; most close by themselves.

**Esc lets go** of whatever you're in the middle of, one thing per press, newest first: a drag
(the shape goes back), an open menu or list, a value you were typing (the old one comes back), a
half-drawn shape, the measuring tool, the drawing tool (back to Select), a selected point, the
selection, playback.

---

## 2. Files

### Opening designs
- **Open** (Ctrl+O): opens embroidery files (PES, JEF, DST, EXP, VP3, XXX and 40 more) and LUDD
  projects (`.ludd`). You can also drag a file onto the window.
- **Add design** (Ctrl+Shift+O): places another stitch file into the design you have open, to
  combine designs. Dragging a file onto an open design adds it, too.
- **⋯ → Open a sample design** (Ctrl+Shift+E): five designs that come with LUDD, to try things
  on. They open as new designs, so Save asks where to keep yours.
- **New** (Ctrl+N, or Shift+D as in Embrilliance): an empty design on the fabric you used last.

### Projects
- **Save** (Ctrl+S) keeps a **LUDD project** (`.ludd`): drawn shapes, lettering, placed designs,
  pictures you trace and all settings, with the designs and pictures **embedded inside it**.
  Moving, renaming or deleting the originals can't break it, and it opens the same on another PC.
- **⋯ → Save project as** (Ctrl+Shift+S) makes a copy under a new name.
- **Autosave and recovery**: a few seconds after each change LUDD keeps a recovery copy. If it
  closes unexpectedly, next time it offers **Recover** or **Discard**.
- The window title shows a dot (•) when there are unsaved changes; closing asks first.

### Saving for your machine
**Save for machine** (Ctrl+E, the yellow button) writes the file your machine reads.

- The dialog says whether the design **fits your hoop**, the **file type** (PES for Brother, JEF
  for Janome; others under **More options**) and lists anything to **check** first.
- **Have the machine cut jump threads** (recommended for machines like the Brother PE550D that
  only cut at color changes): long jumps become stops in the same color, so the machine ties off
  and cuts; press Start at each stop, no thread change. **More options** sets how long a jump must
  be to be cut, and whether to add lock stitches.
- **Too big for the hoop?** Tick **Split it across hoopings**: one file per hooping ("name 1 of 2",
  "name 2 of 2"), each with **pink alignment crosses**. Sew file 1, re-hoop so the needle lands on
  the crosses when you start file 2, carry on, then pull the crosses out. A small map shows the
  hoopings; **More options** sets the overlap.
- The **stabilizer advice** for your fabric is shown at the bottom.

### Printing
**⋯ → Print template & thread list** (Ctrl+P): a real-size template with centre lines (for placing
the design on fabric), and a thread list with stitch counts, a tick box per color and the
stabilizer to use. Print at 100% ("Actual size") and check the ruler bars.

### Batch convert
**⋯ → Batch convert folder** (Ctrl+B): converts every design in a folder to another format.

---

## 3. Looking at your design

### Zoom and pan
- Mouse wheel zooms where the pointer is; drag empty space (or with the middle button) to pan.
- **A** zoom to all · **S** zoom to the selection · **0** zoom to the hoop · **1** real size ·
  **2–9** two to nine times real size · **+ / −** zoom in and out · the − / % / + / Fit buttons at
  the bottom right.

### Views
| Key | View | |
| --- | --- | --- |
| **T** | Realistic thread | Every stitch drawn as real thread: rounded, with a sheen that changes with the stitch's angle (so fills at different angles catch the light differently), a soft shadow, and true thickness. Sparse areas show fabric between rows; dense ones pile up. Turn it off for plain lines. |
| **P** | Stitch points | A dot at every needle penetration. |
| **N** | Stitches on/off | Hides the stitches and shows your drawn shapes' outlines. |
| **B** | Pictures on/off | Hides or shows the pictures you're tracing. |
| **J** | Trims, jumps and stops | Grey lines where the thread is cut, orange where a thread is left across the fabric, red marks at trims and stops. |
| **E** | Crosshairs | Lines across the whole design through the pointer, to line things up. |
| **G** / **H** | Grid / hoop | The grid (inches or mm) and the hoop outline. |
| **U** | Units | Inches or millimetres. |
| **Alt+D** | Density map | Colors the design where thread piles up: yellow-green (two layers), orange (the limit), red (too much). Also a tick box beside Checks. |

The design area follows **light or dark mode**; Settings can keep it on light fabric.

### Measuring
**M** (or ⋯) turns on the measuring tool: click two points to see the distance; click again to
measure something else. **M** or **Esc** puts it away.

### Watching it stitch
The bar at the bottom plays the design as the machine would sew it.

- **▶ / Space** plays and pauses. **⏮ / Home** goes to the start, **⏭ / End** shows it all.
- **◀▮ ▮▶ / Page Up, Page Down** jump to the previous or next color.
- **← →** step one stitch (Shift: 100), when nothing is selected.
- Drag the long slider to any point; the marks on it are color changes.
- **Speed** (🐢 slider 🐇): from 2 stitches a second up to 5,000. **Machine speed** is how fast a
  home machine really sews (about 12 a second). **Comma** slows down, **full stop** speeds up,
  **Shift+comma** sets machine speed. LUDD remembers your speed.

---

## 4. Drawing your own

### Tools (left rail)
| Tool | Key | Makes |
| --- | --- | --- |
| **Select** | V | Pick, move, resize and turn things. |
| **Line** | L (or Shift+X) | A running stitch line. |
| **Satin** | C | A satin column: click one side, then the other, back and forth along the column. |
| **Fill** | F | A filled area (tatami): click around its edge; it closes by itself. |
| **Text** | Shift+T | Lettering: click where it goes, then type. |
| **Shapes** | | Rectangle (Ctrl+Alt+1), circle (Ctrl+Alt+2), star (Ctrl+Alt+3), monogram (Ctrl+Alt+M). |
| **Picture** | Ctrl+I | A picture to trace over. |

Embrilliance's create keys work too: **D** switches between drawing and Select, **X** draws again
with the last tool, **Q** draws the same kind of shape as the last one, **W** the kind before that.

### Placing points (as in Embrilliance)
| Do this | Makes |
| --- | --- |
| **Click** | a **curve** point: the line flows smoothly through it |
| **Ctrl+click** | a **straight** point: the line comes in straight |
| **Shift+click** | a **sharp corner** (cusp) where two curves meet |
| **Alt** while clicking | keeps the new point on 15° steps from the last one |
| **Enter**, **right-click** or **double-click** | finishes the shape |
| **Ctrl+right-click** | finishes a line and closes it into a loop |
| **Backspace** | removes the last point |
| **Esc** | cancels the shape (press again to go back to Select) |
| **C** while drawing | switches the last point: curve → straight → corner |
| **Shift+G** | snaps new points to the grid (on/off) |

The line from your last point to the pointer shows what the next click will make. Points near
another shape's points snap to them, so shapes meet exactly. On screen, curve points are circles,
straight points squares, corners diamonds.

### Editing a shape's points
Select the shape, then:
- **Drag a point** to move it.
- **Right-click a point** to switch it: curve → straight → corner.
- **Double-click the outline** to add a point there.
- **Delete** removes the selected point.
- **K** (or Shape tab → Add points) picks the shape back up to add more points.
- **O** (or Shape tab → Add a hole) draws a hole in a fill: click around it, Enter to finish.
- **I** (or Stitches tab → Draw the angle) sets a fill's stitch direction: draw a line across it.

### Tracing a picture, with Trace Assist
1. **Picture** (Ctrl+I) adds a picture. Drag it into place and resize it from a corner.
2. In its panel: **See-through** slider, **📌 Pin to the board** (it can't move, and clicks go
   through it so you can draw over it), **Hide**, and **Set real size** (click two points whose
   real distance you know, then type it).
3. Draw over it. **Trace Assist** shows a ghost point where the line goes next:
   **Tab** takes it, **Shift+Tab** keeps going until a corner or fork, **1** or **2** picks a
   branch at a fork, **[ ]** make the steps shorter or longer. Clicking still works as normal.
   Turn Trace Assist on or off with Ctrl+Shift+A or in Settings.

---

## 5. Selecting and arranging

### Selecting
- **Click** a design or shape to select it. Click empty space (or **Esc**) to deselect.
- **Shift+click** (or Ctrl+click) adds to the selection or takes one out. **Ctrl+A** selects
  everything.
- Several selected things **move, turn, resize, mirror, copy, cut and delete together**; the panel
  shows "N selected".
- **Ctrl+G** groups them: clicking any one then selects them all. **Ctrl+U** ungroups.

### Moving, turning, resizing
- **Drag** to move; drag a **corner handle** to resize; drag the **round handle** to turn (hold
  Shift for 15° steps).
- **Arrow keys** nudge 1 mm; **Shift** 1 cm; **Ctrl** 0.1 mm.
- **R / Shift+R** turn 90° right/left. **Alt+H** mirrors left-right, **Alt+V** top-bottom. A fill's
  stitch direction turns and mirrors with it.
- Exact size: the **W** and **H** boxes (Shape tab for drawn shapes); 🔒 keeps the proportions.
  A stitch file resized more than about 20% may sew too dense or too sparse (LUDD warns you);
  drawn shapes and lettering re-stitch at any size.

### Pinning
**📌 Pin** stops something being dragged by accident. Pin designs and shapes from the 📌 in the
**Sewing order** list or **Shape tab → Pin in place**; pictures from the 📌 in the **Pictures**
list or their panel. A pinned picture also lets clicks through. Click the pin again to unpin.

### Copying and repeating
- **Ctrl+C / Ctrl+X / Ctrl+V** copy, cut and paste (pasted a little down and right).
- **Ctrl+D** duplicates.
- **Repeat…** (Ctrl+Shift+D, or the Repeat button): copies in a **row or grid**, round a
  **circle** (a carousel, each copy turned to follow it), or **mirrored ×4** like a quilt block.

### Sewing order
The **Sewing order** list in the panel shows every design, shape and piece of lettering in the
order they sew. **↑ ↓** move one earlier or later. Click a name to select it.

---

## 6. Stitch settings (the shape panel)

Select a drawn shape; its panel has three tabs. Every number has **−** and **+** buttons, or type
a value and press Enter (Esc puts it back).

### Thread tab
The shape's thread. Click it to choose another (from your own spools, a brand chart, or any
color). **✨ Ask the Stitch Advisor** appears here if the AI add-on is on.

### Stitches tab
| Setting | Fill | Satin | Line | What it does |
| --- | --- | --- | --- | --- |
| **Type** | Line · Fill · Applique | | Line · Fill · Applique | Switch a closed shape between a running stitch outline, a fill and an applique. |
| **Underlay** | Auto · Edge · Cross-hatch | Auto · Centre · Edge · Zigzag | | The foundation sewn first so the top stitches sit flat. **Auto** chooses from the fabric and the width. |
| **Density** | ✓ | ✓ | | Distance between rows in mm: smaller is denser. **Light / Normal / Dense** presets below. |
| **Angle** | ✓ | | | Direction of the rows (0–179°). **Draw the angle (I)** sets it with a line. |
| **Length** | ✓ | | ✓ | Stitch length. |
| **Random** | ✓ | | | Moves needle points a little at random (0–50%) so no lines show across the fill. |
| **Edge pad** | ✓ | ✓ | | Pull compensation: widens the shape because stitches pull the fabric in. **Auto** chooses from the fabric and the width. |
| **Reverse** | ✓ | | | Sews the fill from the other end. |
| **Split long stitches** | | ✓ | | Splits satin stitches longer than the length you set, so they can't snag. |
| **Style** | | | Single · Triple · Bean | One pass, three passes end to end, or each stitch three times. |
| **Lock stitches** | ✓ | ✓ | ✓ | Tiny tie-in and tie-off stitches so the thread can't unravel. |

### Shape tab
Size (W, H), turn and mirror buttons, **Duplicate**, **Repeat…**, **Add points (K)**,
**Add a hole (O)** for fills, **📌 Pin in place**, **Remove**.

### Satin columns
Click alternately on one side and the other: each pair of clicks is a "rung" the stitches follow.
Satins wider than about 10 mm make long loose stitches (use Split long stitches or a fill); thin
spots under 1 mm are widened automatically.

---

## 7. Lettering
**Text** (Shift+T), then click where it goes. In its panel:
- The **text** (stitches update after a short pause).
- **Font**: any font installed on your computer (type to search). Stitch fonts (`.luddfont`) too.
- **Letter height** (capital letters), **thread**, **Satin look** (smooth, shiny; best for names)
  or **Fill** (for big letters).
- **Shape**: Straight, Arch, Smile (under a curve) or Circle, with the curve's size.
- **Monogram**: three initials with a bigger middle one.
- **More options**: extra letter spacing; **Save this font as a stitch font** to fine-tune.
Letters under about 5 mm tall are hard to sew; LUDD warns you.

---

## 8. Applique
Make any closed shape an **Applique** (Stitches tab → Type). The machine sews:
1. a **placement line**, then stops: lay your fabric piece over it;
2. a **tack-down** (zigzag, or straight for felt and non-fraying fabric), then stops: trim the
   fabric close to the stitching;
3. a **satin border** over the raw edge (its width and density are adjustable).

**Save cut file (SVG)** (or ⋯, Ctrl+Shift+U) saves every applique piece's outline at real size,
for a cutting machine (Cricut, ScanNCut, Silhouette) or to print and cut by hand. Untick **Sew a
placement line first** if you cut pieces beforehand and place them by eye.

---

## 9. Threads and colors

### The thread list (panel, bottom)
Each color in sewing order. **✎** changes a thread; **🗑** removes that color's stitches.
**Match…** finds the nearest thread for every color, from your own spools first.
**⋯ (Color options)**: **Combine same colors next to each other** (Ctrl+Shift+C), **Sort colors**
so each thread is sewn once (Ctrl+Shift+L), **Put back the original colors** (Ctrl+Shift+R).

### My threads and charts
**⋯ → My threads & charts** (Ctrl+T):
- **My threads**: the spools you own. Add them from a brand chart, or with **Add a spool by
  color…** for unbranded Amazon assortments. Matching uses these first.
- **Brand charts**: Brother and Janome built in; import any brand from a CSV file.

---

## 10. Fabric, checks and quality

### Stitching on (top of the panel)
Choose the fabric: cotton or woven, denim or canvas, T-shirt knit, fleece or sweatshirt, towel or
terry, stretchy sportswear, felt. LUDD adjusts density, pull compensation and underlay of drawn
shapes (anything you set by hand on a shape wins) and shows the **stabilizer** to use, plus a
**topping** for towels and fleece.

### Checks
The **Checks** list warns before you stitch: too much thread in one place, the needle hitting one
spot over and over, many very short stitches, long loose stitches (over 7 mm), shapes that almost
touch. Each says **why it matters** and **what to do**; **Show me** jumps to the spot. The same
checks appear in Save for machine.

### Machine extras (⋯ menu)
- **Insert a stop / trim at the needle** (Ctrl+Shift+P / Ctrl+Shift+T): at the stitch-out bar's
  position.
- **Trim jumps longer than 3 mm** (Ctrl+Shift+J): turns the design's long jumps into trims.
- **Basting box** (Ctrl+Shift+B): a frame sewn first to hold fabric to stabilizer; remove it after.
- **Knockdown stitches** (Ctrl+Shift+N): a light grid sewn first under the design so towel loops
  and fleece pile don't poke through. Set its thread to match the fabric.

---

## 11. Settings (⚙, Ctrl+,)
- **Look**: Automatic (follows your computer), Light or Dark; **Always show the design on light
  fabric**.
- **My machine** and hoop.
- **Measurements**: inches or millimetres.
- **Workspace**: show the hoop, show the grid, realistic thread, Trace Assist.
- **AI add-on** (below).
- **Updates**: tell me when a new version is out (asks GitHub when LUDD starts; nothing about you
  is sent), **Check now**, and the version you have.

---

## 12. The AI add-on (optional, off by default)
Everything in LUDD works without it. **Settings → AI add-on**:
- **Off**: nothing is sent anywhere.
- **On this computer**: uses **Ollama**, a free program that runs AI models on your own PC (a
  graphics card with 8 GB helps). Install it, then `ollama pull qwen2.5vl:7b`.
- **Cloud**: Anthropic, or any OpenAI-compatible service, with your own account and key. Your key
  is stored encrypted for your Windows account. **Before anything is sent**, LUDD shows exactly
  what will go and, if you enter the service's prices, the most it can cost.

**Stitch Advisor** (✨ on a shape's Thread tab, ⋯, or Ctrl+Shift+I): suggests stitch type, fill
angle, density, underlay and sewing order, each with a reason. **Accept** or **Dismiss** each, or
**Accept all** (one Ctrl+Z undoes it). Nothing changes unless you accept.

**Help** (F1): with AI on, **Ask AI** answers in plain words from the guide.

---

## 13. Help and updates
- **Help** (F1, or **?** in the toolbar): type a question or a few words; matching sections of the
  guide appear. Works offline.
- **Updates**: when a new version is out, a strip offers **Install and restart** or **Later**.
  Your work is offered back after the restart if you hadn't saved. **⋯ → Check for updates** asks
  right away.

---

## Keyboard shortcuts

LUDD uses Embrilliance's keys where they exist. Ctrl is ⌘ on a Mac. Shortcuts are also shown in
every menu and on every button's tooltip.

### Files and app

| Do this | Press |
| --- | --- |
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
| Undo / redo | Ctrl+Z / Ctrl+Y (or Ctrl+Shift+Z) |
| Select several | Shift+click or Ctrl+click |
| Select everything | Ctrl+A |
| Group / ungroup | Ctrl+G / Ctrl+U |
| Copy / cut / paste | Ctrl+C / Ctrl+X / Ctrl+V |
| Duplicate | Ctrl+D |
| Remove | Delete or Backspace |
| Repeat, carousel or mirror ×4… | Ctrl+Shift+D |
| Let go of whatever you're doing | Esc |

### Drawing

| Do this | Press |
| --- | --- |
| Select and move | V |
| Line (running stitch) | L or Shift+X |
| Satin column | C |
| Fill | F |
| Text | Shift+T |
| Switch between drawing and Select | D |
| Draw again with the last tool | X |
| Draw a shape like the last one / the one before | Q / W |
| Curve point / straight point / sharp corner | click / Ctrl+click / Shift+click |
| Keep the new point on 15° steps | hold Alt |
| Finish the shape | Enter, right-click or double-click |
| Finish a line and close it | Ctrl+right-click |
| Remove the last point | Backspace |
| Switch the last point: curve, straight, corner | C (while drawing) |
| Cancel the shape | Esc |
| Snap new points to the grid | Shift+G |
| Add points to the selected shape | K |
| Add a hole to the selected fill | O |
| Set a fill's stitch angle with a line | I |
| Remove the selected point | Delete |
| Rectangle / circle / star / monogram | Ctrl+Alt+1 / 2 / 3 / M |

### Trace Assist (while drawing over a picture)

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
| Zoom to all | A |
| Zoom to the selection | S |
| Zoom to the hoop | 0 |
| Real size / 2–9× real size | 1 / 2–9 |
| Zoom in / out | + or = / − |
| Realistic thread (3D) | T |
| Stitch points | P |
| Stitches on/off | N |
| Pictures on/off | B |
| Crosshairs | E |
| Trims, jumps and stops | J |
| Grid / hoop | G / H |
| Measure | M |
| Inches or millimetres | U |
| Density map | Alt+D |

### Stitch-out

| Do this | Press |
| --- | --- |
| Play / pause | Space |
| Back / forward one stitch | ← / → (nothing selected) |
| Back / forward 100 stitches | Shift+← / Shift+→ |
| Previous / next color | Page Up / Page Down |
| Start / whole design | Home / End |
| Slower / faster | comma / full stop |
| Machine speed | Shift+comma |

### Machine stitches and colors

| Do this | Press |
| --- | --- |
| Combine same colors next to each other | Ctrl+Shift+C |
| Sort colors (fewest thread changes) | Ctrl+Shift+L |
| Put back the original colors | Ctrl+Shift+R |
| Insert a stop / trim at the needle | Ctrl+Shift+P / Ctrl+Shift+T |
| Trim jumps longer than 3 mm | Ctrl+Shift+J |
| Basting box | Ctrl+Shift+B |
| Knockdown stitches | Ctrl+Shift+N |
| Save applique cut file (SVG) | Ctrl+Shift+U |
