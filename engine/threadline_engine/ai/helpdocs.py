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
Pick a tool on the left: Line (L, or Shift+X) for running stitch, Satin (C) for columns, Fill (F) for areas, Text (Shift+T) for lettering. D switches between drawing and Select; X draws again with the last tool; Q draws the same kind as the last shape, W the kind before that. As in Embrilliance, a click places a curve point, Ctrl+click a straight (line) point, and Shift+click a sharp corner (cusp) between curves; Alt keeps the new point on 15-degree steps. Enter or right-click finishes the shape; Ctrl+right-click finishes and closes a line. Backspace removes the last point, Esc cancels. For a satin, click alternately on one side and the other. Shapes (left rail) adds a rectangle, circle, star or monogram. Shift+G turns snapping to the grid on or off; points near another shape's points snap to them. O draws a hole in the selected fill.

## Editing shapes and points
Select (V) a shape to move it, resize it from the corner handles, or turn it with the round handle. Drag a point to reshape; right-click a point to switch it between curve, straight and sharp corner; double-click the outline to add a point; Delete removes the selected point. K adds more points to the selected shape. The arrow keys nudge 1 mm (Shift: 1 cm, Ctrl: 0.1 mm). R and Shift+R turn by 90 degrees; Alt+H mirrors left-right and Alt+V top-bottom. Ctrl+D duplicates; Ctrl+C, Ctrl+X and Ctrl+V copy, cut and paste. Ctrl+Z undoes, Ctrl+Y redoes.

## Selecting several things, groups and pinning
Shift+click (or Ctrl+click) adds a design or shape to the selection, or takes it out; Ctrl+A selects everything. Several selected things move, turn, resize, mirror, copy and delete together. Ctrl+G groups them so clicking any one selects them all; Ctrl+U ungroups. Pin (the pin button in the Sewing order or Pictures list, or Pin in place on the Shape tab) stops something being dragged by accident; a pinned picture also lets clicks through, so you can draw over it. Unpin it the same way.

## Esc lets go
Esc lets go of whatever you're in the middle of, one thing per press: a drag (the shape goes back), an open menu or list, a value you were typing (the old one comes back), a half-drawn shape, measuring, the drawing tool (back to Select), the selected point, the selection, playback.

## Stitch settings: density, angle, underlay, pull compensation
Select a shape: its panel has three tabs. Thread: the thread colour. Stitches: the stitch type (Line, Fill or Applique), underlay (Auto, or Edge and Cross-hatch for fills, Centre, Edge and Zigzag for satins), density (row spacing in mm, smaller is denser, with Light, Normal and Dense presets), and for fills the angle, stitch length, Random (moves needle points a little so no lines show) and Reverse (sew from the other end). Edge pad is pull compensation: Auto chooses it from the fabric and the shape's width, or set it yourself. Satins can split long stitches so they don't snag. Every number has minus and plus buttons. Shape: size, turning, mirroring, duplicate, repeat, add points, add a hole, pin and remove. I lets you draw a line across a fill to set its stitch angle.

## Fabric and stabilizer
"Stitching on" in the design panel sets the fabric: woven cotton, denim, T-shirt knit, fleece, towel, stretchy sportswear or felt. The fabric sets density, pull compensation and underlay for drawn shapes, and LUDD tells you which stabilizer to use (and topping for towels and fleece). Knits and stretchy fabrics need a cut-away stabilizer; towels and fleece need a water-soluble topping on top.

## Checks before stitching and the density map
The Checks list in the design panel warns about problems before you stitch: too much thread in one place, the needle hitting one spot over and over, very short stitches, long loose stitches over 7 mm, and shapes that almost touch (a line of fabric can show between them). Each check says why it matters and what to do; Show me jumps to the spot. The density map (Alt+D) colors where thread piles up: yellow-green, orange at the limit, red beyond it. With realistic thread on (T) you can also see density directly: every stitch is drawn as real thread, so sparse areas show fabric and dense ones pile up.

## Tracing a picture and Trace Assist
Add a picture to trace (Ctrl+I). Set its see-through, pin it to the board so it can't move, or measure a known distance to set its real size. B hides or shows pictures. While drawing over it, Trace Assist shows a ghost point where the line goes next: Tab takes it, Shift+Tab keeps going until a corner or fork, 1 or 2 picks a branch, [ and ] change the step, C switches the last point between curve, straight and sharp corner. Turn Trace Assist on or off in Settings or with Ctrl+Shift+A.

## Lettering and monograms
The Text tool (T): click where the text goes and type. Choose any installed font, the letter height (capital letters), the thread, Satin look or Fill, and the shape: straight, arch, smile or circle. Letters under about 5 mm are hard to sew. Monogram makes three initials with a bigger middle letter. "Save this font as a stitch font" makes an editable .luddfont.

## Threads, colors and My threads
The thread list shows each color in sewing order; click the pencil to change a thread. Match finds the closest thread from your own spools (My threads) or a brand chart for every color. Add spools you own in My threads & charts, including Amazon assortments by color; import brand charts from CSV. Color options can combine same colors next to each other or sort colors to sew each thread once.

## Applique
Make a closed shape an Applique (Line | Fill | Applique in its panel). The machine sews a placement line and stops: lay your fabric piece over it. Then it sews a tack-down and stops: trim the fabric close to the stitching. Then a satin border covers the raw edge. Save cut file (SVG) writes each piece's outline at real size for a cutting machine (Cricut, ScanNCut, Silhouette) or to print and cut by hand.

## Repeat, carousel and mirror
Repeat (Ctrl+Shift+D or the Repeat button) copies the selected design in a row or grid, round a circle (a carousel, each copy turned to follow the circle), or mirrored four ways like a quilt block. One Ctrl+Z takes all the copies out.

## Watching it stitch, measuring and views
The bar at the bottom plays the stitch-out: Space plays and pauses, the arrow keys step a stitch (Shift: 100), Page Up and Page Down jump a colour, Home and End go to the start and the whole design. The speed slider runs from 2 stitches a second up to 5,000; "machine speed" is how fast a home machine really sews. Comma slows down, full stop speeds up, Shift+comma sets machine speed. M is the measuring tool: click two points to see the distance. Views: T realistic thread, P stitch points, N stitches on or off (outlines only), B pictures, E crosshairs, J trims and jumps, G grid, H hoop. Zoom: A all, S the selection, 0 the hoop, 1 to 9 real size times 1 to 9, the mouse wheel, + and -. The panel on the right can be made wider or narrower by dragging its left edge; its sections fold away when you click their headings; dialogs move when you drag their title.

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
LUDD uses Embrilliance's keys where they exist. Files: New Ctrl+N (or Shift+D), Open Ctrl+O, Save Ctrl+S, Save for machine Ctrl+E, picture Ctrl+I, print Ctrl+P, Help F1, Settings Ctrl+comma. Editing: undo Ctrl+Z, redo Ctrl+Y, copy Ctrl+C, cut Ctrl+X, paste Ctrl+V, select all Ctrl+A, group Ctrl+G, ungroup Ctrl+U, duplicate Ctrl+D, turn R, mirror Alt+H and Alt+V, nudge arrows (Shift 1 cm, Ctrl 0.1 mm). Drawing: D Create or Select, V Select, L or Shift+X Line, C Satin, F Fill, Shift+T Text, X last tool, Q and W shapes like the last ones, O add a hole, I stitch angle, K add points, click curve, Ctrl+click straight, Shift+click corner, Alt 15 degrees, Enter or right-click finish, Esc cancel. View: A zoom all, S zoom selection, 0 hoop, 1-9 real size multiples, T realistic, P stitch points, N stitches, B pictures, E crosshairs, J jumps, G grid, H hoop, M measure, U units, Alt+D density map, Shift+G snap to grid. Stitch-out: Space play, comma slower, full stop faster.

"""
