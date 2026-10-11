"""The LUDD user guide, searched by Help (with or without AI). Keep it true to the app."""

GUIDE = r"""
## Getting started
LUDD opens embroidery designs, lets you change them, draw your own, and saves them for your machine. Pick your machine the first time (you can change it in Settings, the gear button at the top right). Open a design with Open (Ctrl+O) or start a new one with New (Ctrl+N). Drag a design file, a LUDD project or a picture onto the window to open or add it.

## Sample designs and updates
To try LUDD, open a sample: on the start screen click "Or try one of the sample designs", or use ... → Open a sample design (Ctrl+Shift+E). Samples open as new designs, so Save asks where to keep yours. The Banner sample is too big for a 4 inch hoop, to try splitting. LUDD tells you when a new version is out and offers Install and restart; turn this off in Settings, or use Check now there. Settings also shows which version you have.

## Saving your work and projects
Save (Ctrl+S) keeps a LUDD project (.ludd) with everything in it: drawn shapes, lettering, placed designs and the pictures you trace, embedded in the file. Moving or deleting the originals can't break a project. Save as (Ctrl+Shift+S) makes a copy under a new name. LUDD also keeps a recovery copy a few seconds after each change; if it closes unexpectedly it offers to get your work back next time. Old .thl projects open too.

## Saving for the machine (PES, JEF)
Save for machine (Ctrl+E) writes the file your machine reads: PES for Brother, JEF for Janome, and other formats under More options. The dialog says whether the design fits your hoop, lists anything to check first, and recommends settings for your machine. A project (.ludd) is for editing; the machine file is what you put on the USB stick.

## Cutting jump threads (cut-stops)
Some machines, like the Brother PE550D, only cut the thread at a color change, so jumps between parts leave threads you snip by hand. Turn on "Have the machine cut jump threads" in Save for machine: LUDD turns each long jump into a stop with the same color, so the machine ties off and cuts. At each stop just press Start again; no thread change is needed. Under More options you can choose how long a jump must be to be cut.

## Hoop too small: splitting across hoopings
If a design is bigger than your hoop, Save for machine offers to split it (on by default) and shows a map of the hoopings. LUDD saves one file per hooping, named "1 of 2", "2 of 2" and so on. Each file ends, and the next one begins, with pink alignment crosses on the seam. Sew file 1, re-hoop the fabric so that when you start file 2 the needle lands on the pink crosses, then carry on. Pull the pink crosses out at the end. The overlap between hoopings is under More options.

## Drawing shapes: line, satin, fill
Pick a tool on the left: Line (L) for running stitch, Satin (C) for columns, Fill (A) for areas, Text (T) for lettering. Click to place corner points, right-click for curve points. Enter finishes, Backspace removes the last point, Esc cancels. For a satin, click alternately on one side and the other. Shapes (the ... button) adds a rectangle, circle, star or monogram. Holding Shift snaps to the grid; points near another shape's points snap to them.

## Editing shapes and points
Select (V) a shape to move it, resize it from the corner handles, or turn it with the round handle. Drag a point to reshape; right-click a point to switch corner and curve; double-click the outline to add a point; Delete removes the selected point. K continues drawing the selected shape. The arrow keys nudge (Shift for 1 cm). R and Shift+R turn by 90 degrees, M and Shift+M mirror. Ctrl+D duplicates. Ctrl+Z undoes, Ctrl+Y redoes.

## Esc lets go
Esc lets go of whatever you're in the middle of, one thing per press: a drag (the shape goes back), an open menu or list, a value you were typing (the old one comes back), a half-drawn shape, measuring, the drawing tool (back to Select), the selected point, the selection, playback.

## Stitch settings: density, angle, underlay, pull compensation
Select a satin or fill to see its settings. Density: Light, Normal or Dense. Fills have a stitch angle. Under More options: spacing, stitch length, pull compensation and underlay. Underlay is the foundation stitched first so the top stitches sit flat; pull compensation widens shapes slightly because stitches pull the fabric in. Both are on Automatic by default, chosen from the fabric and the shape's width.

## Fabric and stabilizer
"Stitching on" in the design panel sets the fabric: woven cotton, denim, T-shirt knit, fleece, towel, stretchy sportswear or felt. The fabric sets density, pull compensation and underlay for drawn shapes, and LUDD tells you which stabilizer to use (and topping for towels and fleece). Knits and stretchy fabrics need a cut-away stabilizer; towels and fleece need a water-soluble topping on top.

## Checks before stitching and the density map
The Checks list in the design panel warns about problems before you stitch: too much thread in one place, the needle hitting one spot over and over, very short stitches, long loose stitches over 7 mm, and shapes that almost touch (a line of fabric can show between them). Each check says why it matters and what to do; Show me jumps to the spot. The density map (Shift+D) colors where thread piles up: yellow-green, orange at the limit, red beyond it.

## Tracing a picture and Trace Assist
Add a picture to trace (Ctrl+I). Set its see-through, lock it, or measure a known distance to set its real size. While drawing over it, Trace Assist shows a ghost point where the line goes next: Tab takes it, Shift+Tab keeps going until a corner or fork, 1 or 2 picks a branch, [ and ] change the step, C switches the last point between corner and curve. Turn Trace Assist on or off in Settings or with Ctrl+Shift+A.

## Lettering and monograms
The Text tool (T): click where the text goes and type. Choose any installed font, the letter height (capital letters), the thread, Satin look or Fill, and the shape: straight, arch, smile or circle. Letters under about 5 mm are hard to sew. Monogram makes three initials with a bigger middle letter. "Save this font as a stitch font" makes an editable .luddfont.

## Threads, colors and My threads
The thread list shows each color in sewing order; click the pencil to change a thread. Match finds the closest thread from your own spools (My threads) or a brand chart for every color. Add spools you own in My threads & charts, including Amazon assortments by color; import brand charts from CSV. Color options can combine same colors next to each other or sort colors to sew each thread once.

## Applique
Make a closed shape an Applique (Line | Fill | Applique in its panel). The machine sews a placement line and stops: lay your fabric piece over it. Then it sews a tack-down and stops: trim the fabric close to the stitching. Then a satin border covers the raw edge. Save cut file (SVG) writes each piece's outline at real size for a cutting machine (Cricut, ScanNCut, Silhouette) or to print and cut by hand.

## Repeat, carousel and mirror
Repeat (Ctrl+Shift+D or the Repeat button) copies the selected design in a row or grid, round a circle (a carousel, each copy turned to follow the circle), or mirrored four ways like a quilt block. One Ctrl+Z takes all the copies out.

## Knockdown, basting and placing designs
Knockdown stitches (... menu) sew a light grid under the design first, so towel loops and fleece pile don't poke through; set its thread to match the fabric. A basting box (... menu) sews a frame around the design first to hold the fabric to the stabilizer; remove it afterwards. Add design (Ctrl+Shift+O) places another stitch file in the same layout. Resizing a stitch file more than about 20% makes stitches too dense or too sparse; drawn shapes and lettering resize cleanly.

## Printing a template
Print (Ctrl+P) prints a real-size template with centre lines, for placing the design on the fabric, and a thread list with stitch counts and the stabilizer to use. Print at 100% (actual size) and check the ruler bars.

## Light and dark mode, Settings
Settings (Ctrl+, or the gear) holds light or dark mode (Automatic follows your computer), whether the design shows on light fabric, your machine and hoop, inches or millimetres, the hoop and grid, realistic thread, Trace Assist and the AI add-on.

## The AI add-on
AI is optional and off by default; everything else works without it. In Settings, choose Off, On this computer (Ollama, a free program that runs models on your own PC) or Cloud (Anthropic or an OpenAI-compatible service, with your own key and your own account). Before anything goes to the cloud, LUDD shows exactly what will be sent and, if you enter the service's prices, an estimated cost. AI suggestions never change your design by themselves: you accept or dismiss each one.

## Stitch Advisor
Select one or more drawn shapes and choose Stitch Advisor (... menu or the panel). The AI looks at each shape (and the picture you're tracing) and suggests the stitch type, fill angle, density, underlay and sewing order, each with a one-line reason. Accept the suggestions you like, one at a time or all at once; dismiss the rest. Suggestions that don't make sense are thrown away.

## Keyboard shortcuts
New Ctrl+N, Open Ctrl+O, Save Ctrl+S, Save for machine Ctrl+E, picture Ctrl+I, print Ctrl+P, undo Ctrl+Z, redo Ctrl+Y. Tools: Select V, Line L, Satin C, Fill A, Text T. Zoom with the mouse wheel, + and -, F fits the design. Space plays the stitch-out, the arrow keys step through it. H hoop, G grid, U units, J shows trims and jumps, Shift+T realistic thread, Shift+D density map. Help is F1.
"""
