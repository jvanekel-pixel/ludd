# Stitch-out log

One entry per test stitch-out. Photograph each run.

## Pending machine tests

The user is testing on the machine once the software is about 95% done (decided Oct 11, 2026). Until then these are unverified on real thread:

| Milestone | Test | File | What to check |
| --- | --- | --- | --- |
| M1 | Converted PES stitches like the original | Any fixture, Save for machine → PES | Same look, colors in order, stops where expected |
| M2 | **Cut-stops** on the PE550D | Key.PES, Save for machine with "Have the machine cut jump threads" (18 stops) | At each stop the machine ties off and cuts; pressing Start continues in the same color; stitches after each cut hold (lock stitches) |
| M2 | Recolored PES keeps thread names | Any fixture after "Match threads" | Machine screen shows the new colors |
| M3 | Rotated and resized designs | Key.PES rotated 90°, and another at 90% size | Stitches as shown; density still fine at 90% |
| M3 | Combined designs | Two small designs added together | Sewn in the listed order; color changes where expected |
| M3 | Inserted stop and basting box | Any design with a stop inserted and basting on | Machine stops at the inserted stop; basting box sews first |
| M3 | Printed template is real size | Ctrl+P, print at 100% | The 1 inch and 25 mm bars measure correctly; centre lines match the stitched design |
| M4 | Three-object test design | A fill, a satin column and a running stitch drawn in LUDD | Fill covers without gaps or puckering at Normal density; satin edges are smooth; no loose jump threads |
| M4 | Fill angles and density | The same rectangle at 0°, 45° and 90°, Light / Normal / Dense | Each looks even; Dense isn't stiff; Light doesn't show fabric |
| M4 | Satin widths | Satins about 2, 5 and 8 mm wide | All lie flat; pull compensation keeps them full width |
| M4 | Fill with a hole | A circle with a smaller circle inside | No thread across the hole; no trims |
| M6 | **10 mm name in a script font** (M6 acceptance) | "Emma Rose", Segoe Script, 10 mm, Satin look | Legible; letters don't pucker; small loops stay open |
| M6 | Block letters, satin vs fill | A name in Arial at 10 mm (satin look) and 25 mm (fill) | Clean edges; fill doesn't show fabric |
| M6 | Text on an arch and a monogram | Name on an arch; a three-letter monogram | Letters evenly spaced around the curve; monogram centred |
| M7 | **Fabric presets** (M7 acceptance) | The same 3 cm fill and 4 mm satin on woven cotton, a T-shirt and a towel, each on its own preset with the advised stabilizer | No puckering; satin edges stay full width on the knit; towel loops don't poke through |
| M7 | Automatic underlay and width-aware compensation | A satin tapering from 1 mm to 8 mm, Automatic on | Edges look parallel along the taper (no narrowing at the wide end) |
| M8 | **Two-hooping split** (M8 acceptance) | A 160 × 60 mm design (two fills joined by a satin) split for the 4" hoop: sew 1, re-hoop, sew 2 | The pink crosses of file 2 land on those of file 1; the satin and fills meet at the seam without a gap or a double line |
| M8 | Applique | A 4 cm square applique in cotton on denim, cut from the SVG cut file | The machine stops twice; the piece matches the placement line; the border covers the raw edge |
| M8 | Knockdown on a towel | A name with knockdown on, on a towel, with topping | Letters sit on top; no loops poke through |
| 1.0.1 | **Satin ribbons** | Ribbons 1.5, 3 and 6 mm wide along an S curve, and a closed ring with sharp corners | Even width round curves; corners full and not gappy; the ring meets itself without a bump |
| 1.0.1 | **Fill + satin border (Auto-trace)** | A cartoon face auto-traced as Fill + satin border, 1.3 mm border | The border covers the fill's edge with no fabric showing between them |
| 1.0.1 | **Fill patterns** | A 40 mm square in each pattern: gradient, wave, contour, stipple, cross-stitch | Each looks like its name; stipple lies flat without puckering; cross-stitch Xs are crisp; gradient fades without gaps at the dense end |
| 1.0.1 | **Motif lines** | Wave, zigzag, scallop and blanket stitch along a 60 mm curve; blanket stitch round a felt applique | Even repeats; blanket stitch catches the applique edge |
| 1.0.1 | **Hidden travel** | Two small red shapes under a later blue patch, Fewer jumps & trims on | No thread to snip between the red shapes; the travel stitches don't show through the blue |
| 1.0.1 | **Whole-picture auto-digitize** | A simple cartoon digitized with Alt+A, then fixed up | Fills meet their satin outlines without fabric showing between them |
| 1.0.1 | **Split applique keeps its stops** | A 180 mm applique split for the 4" hoop | Each hooping stops for placement and tack-down |
| 1.0.1 | **Applique with a hole** | A 40 mm square applique with a 10 mm hole, cut from the SVG | The hole's edge is placed, tacked and covered like the outside |
| M7 | Gap check | Two fills 0.3 mm apart (the check warns), then overlapped 0.5 mm | The first shows a thin line of fabric; the second doesn't |
| 1.0.1 | **Text on a line** | A name on a drawn S curve, and the same name on a line drawn right to left | Letters stand upright on the line, evenly spaced; satin rows cross each stroke |
| 1.0.1 | **Outline around lettering** | "Emma" (Arial 20 mm, satin look) with a 2 mm satin outline from Outline / offset | The outline sits evenly round the name without touching it; no thread across the letters |
| 1.0.1 | **Edited stitches** | A fixture with a few stitches dragged in Edit stitches, then the design turned 90° | The moved stitches sit where they were put, relative to their neighbours |
| 1.0.1 | **Shortest order** | Six same-thread fills scattered in the hoop, two of them overlapping, Sew in the shortest order with Fewer jumps & trims on | Short moves between shapes; the overlapping pair keeps its layering |
| 1.0.1 | **Optimize jumps** | The Flower sample after Optimize jumps (petals and leaves) | Each petal starts where the one before ended; the short jumps sit under the yellow centre; no gaps where a fill starts at its new edge |
| 1.0.1 | **Satin fill** | A curved petal about 40 × 12 mm and a 40 × 8 mm bar, each a fill switched to Satin; the petal again after Shift+W | Stitches straight across the shape and turning with the curve, no gaps at the sides, tips not piled up; the bar sewn across its short side; the Shift+W version runs the other way |
| 1.0.1 (phase 4) | **Whole picture, cleaner** | A logo saved as JPEG (quality 50–90) with black outlines, a bold word (stems 3–4 mm) and a red ring, Whole picture with Leave out the background on | One black thread; no white fills inside letters or the ring; satin outlines reach the line ends; each bold letter sews as one fill |
| 1.0.1 (phase 4) | **Every piece of a split fill** | A bow-tie fill (outline crossing itself), and the same shape as an applique | Both lobes sewn, locked and trimmed between; the applique places, tacks and covers each piece |
| 1.0.1 (phase 4) | **Open patterns round a hole** | A 50 mm donut in Cross-stitch, in Contour and in Stipple; a 40 mm Gradient square with Auto underlay | Crosses are clean Xs with no bars and few threads over them; contour has no ridge; stipple fills every part; the gradient fades with no cross-hatch showing |
| 1.0.1 (phase 4) | **Dense fill** | A 20 mm square fill at 0.25 mm spacing | Rows reach both edges; not stiff; no puckering |
| 1.0.1 (phase 4) | **Split satin** | A 9 mm satin with Split long stitches at 4 mm | No stitch longer than 4 mm, top or underlay; the split points are staggered (no visible line) |
| 1.0.1 (phase 4) | **Applique border** | A 30 mm square applique, 3 mm border | Border stitches evenly spaced, covering the raw edge; corners full |
| 1.0.1 (phase 4) | **Turned and curved lettering** | "Emma" Arial 20 mm satin look turned 45°; "HAPPY BIRTHDAY" on Arch radius 40; "WOW MOM" on Smile 15 mm radius 40; "Hello Ag" Arial 25 mm satin look | Satin rows run across each stroke; Smile letters don't touch; no loose long stitches in the big letters |
| 1.0.1 (phase 4) | **Letter size and kerning** | "Hi" in Segoe Script at 20 mm; "AVATAR" in Roboto 20 mm | The H measures 20 mm; A–V and V–A sit close, as in print |
| 1.0.1 (phase 4) | **Lettering on a towel** | A name on the Towel preset with knockdown and topping | Denser than on woven; letters sit on top of the loops |
| 1.0.1 (phase 4) | **Knife keeps colors and stops** | A fill recolored in Threads, with a stop inserted, cut in two with the knife | Both pieces sew in the new color; the machine stops at the stop |
| 1.0.1 (phase 4) | **Split across hoopings, revised** | The "Banner (two hoopings)" sample split for the PE550D's 4" hoop | No gap or double line at the seam; pink crosses on bare fabric and easy to pull out; lock stitches only where the thread was cut |
| 1.0.1 (phase 4) | **Basting box that fits** | A design 2–3 mm smaller than the hoop, basting box on | The box sews inside the hoop, close round the design |
| 1.0.1 (phase 4) | **JEF on a Janome** | Key.PES saved as JEF; a 13 mm wide satin saved as JEF; an applique saved as JEF | The design sits centred in the hoop; the wide satin sews in pieces (no needle-up jumps); the applique stops twice (stop codes and hoop size are untested on a Janome) |
| 1.0.1 (phase 4) | **Accented thread names** | A PES whose thread is named "Grün" | The machine reads the file; the thread list shows "Grun" |
| 1.0.1 | **PES placement on the PE550D** | GrumpyBMO (fixed).pes and any design saved for the machine again | Opens centred in the hoop with its full size shown (75.7 × 90.4 mm for GrumpyBMO), and the arrow keys move it |
| 1.0.1 | **Auto-trace fitted round shapes** | A traced area next to a shape already made, "fitted around your shapes" | No gap and no double layer where they meet (0.3 mm tuck) |
| 1.0.1 | **Cut out with a shape** | A circle cut out of a fill (Shift+O), the circle sewn on top | Clean hole edge; the circle covers it with no fabric showing |
| 1.0.1 | **Lettering hand-overs and satin stops** | "Hello" at 25 mm, Satin look; a satin leaf with its stop dragged to the middle of one side | Short jumps between letters (no trims where letters touch); the satin finishes at the chosen side with nothing showing across it |
| 1.0.1 (QA2 1) | **Fill with a thin neck** | Two fills joined by a strip about 0.4 mm wide (for example a traced shape with a hairline join), default underlay, then the same with its red end dot set | No thread across bare fabric and no trims inside the one fill; the last stitch isn't a long loose one |
| 1.0.1 (QA2 2) | **Zigzag underlay crosses** | Two 6 mm satin ribbons, 20 mm and 22 mm long, Automatic underlay | Both lie flat and even; the underlay looks the same in both (an X, not one diagonal sewn twice) |
| 1.0.1 (QA2 3) | **Trims between applique edges** | A 60 × 20 mm applique with two holes, Have the machine cut jump threads on | No thread left lying between the edges; any extra stops resume cleanly |
| 1.0.1 (QA2 4) | **Sharp corners with Split long stitches** | An 8 mm ribbon with a 30° corner, and a star applique (25 mm points) with an 8 mm border | Corners full, with no loose stitch at the outer tip |
| 1.0.1 | Dragged start, end and direction dots | A rectangle fill with its red dot dragged to the middle of an edge and its purple dots set to 20°; a satin fill with its tips moved; a closed line started mid-side | The fill's last stitch is at that spot with no thread showing across the fill; rows run at 20°; the satin runs between the chosen tips |
| Phase 3 | **Spiral fill** | A 40 mm circle and a 40 mm star in Spiral at 1.5 mm; the circle again at 0.8 mm; a 48 × 28 mm oval and the ready-made Heart at 1.5 mm | One unbroken line starting in the middle; rings evenly spaced; no pucker in the middle at 0.8 mm; nothing runs across the rings on the oval or the heart; on the heart and the star, only a light outline of joining thread along the edge, with no stiff ridge or broken thread there (L-026) |
| Phase 4 | **Don't sew what's hidden** | A 40 mm fill with a 20 mm fill on top, switch on | No ridge or gap at the upper shape's edge; the overlap feels as thin as the rest; whether the travel line across the lower fill shows (L-002) |
| Phase 4 | **Rebuild at a new size** | A bought design at 150% and at 60%, each with Rebuild | Coverage like the original: not stiff at 60%, no fabric showing at 150%; satin edges smooth; any extra jumps clean |
| Phase 4 | **Tiny stitches and clumps** | A dense bought design with both repairs on | No thread nests; nothing unravels where stitches were removed |
| Phase 4 | **Locked jump** | A jump locked with Alt+Shift+T, cut by hand | Neither side pulls out |
| Phase 4 | **Density limit** | A dense bought design on a T-shirt with the T-shirt preset and the limit on | Less puckering than without; fills still cover |
| Phase 5 | **Two lines, slanted, in an envelope** | "Happy / Birthday", Arial 12 mm, slant 12°, Bulge | Even letters; no puckering where the envelope stretches them |
| Phase 5 | **True satin against satin look** | "Emma" at 10 mm and 20 mm, both ways, side by side | True satin is smoother along strokes; joins (m, a) have no gap or lump |
| Phase 5 | **Small letters without underlay** | A name at 5 mm | Thinner and more legible than with underlay; nothing unravels |
| Phase 5 | **Stitched font** | A name typed in a font made from bought letter files | Letters on one line, evenly spaced; sews like the originals |
| Phase 5 | **One letter moved and recolored** | A name with one letter raised, turned and in a second color | The color change is clean; no long thread between letters |
| Phase 5 | **Monogram in a scallop frame** | Three letters, Classic, scallop circle | Frame round and evenly scalloped; letters centered |
| Phase 5 | **Shadow and outline** | "WOW" 25 mm with a 0.8 mm shadow; the same with a 1.5 mm satin outline | Shadow shows only at the edge, no lump under letters; outline evenly spaced round the word |
| Phase 6 | **Blend** | A 50 × 30 mm rectangle, red into yellow; the same with three colors; the two-color one again at Spacing 2.5 mm | An even fade with no stripes or bare fabric; not stiffer than a plain fill; at 2.5 mm the rows as even as a plain fill at 2.5 mm, with no bare band |
| Phase 6 | **Weave** | The same square in Standard, Brick, Twill and Smooth | Each looks as named; Smooth shows no lines |
| Phase 6 | **Carved lines** | A 40 mm fill with a carved star and a carved wavy line | Grooves clear and unbroken; no loose stitches beside them |
| Phase 6 | **Feather and hand-sewn** | Two fills feathered into each other; a line, satin and fill at 60% hand-sewn | Soft join with no gap; the hand-sewn pieces look deliberately irregular, nothing loose |
| Phase 6 | **Motif fill, maze, ripple, mesh** | A 40 mm circle in each | Each lies flat; the maze has no crossing; mesh cells are even |
| Phase 6 | **Turning fill** | A leaf with two angle lines 50° apart; a rectangle with a second line turned sharply | Stitches fan smoothly; no bunching inside the turn, no gaps outside it or along the edges; the sharp turn's crease holds; note where a thin line of thread shows across finished rows, and how much it bothers (L-002) |
| Phase 7 | **Craft line styles** | A 60 mm S curve in Backstitch, Stem stitch, Candlewicking and Redwork; five French knots; blanket stitch round a felt circle with its teeth toward the felt | Each looks like its name; stem stitch looks like rope; knots stand up and don't pull out (also at the trims); every blanket tooth catches the felt; no thread nests |
| Phase 7 | **Blackwork fill** | A 40 mm square and a 40 mm star in each lattice, 5 mm cells; a 40 mm donut | Lines crisp and doubled; no thread across open cells: joins run along the edge like part of an outline (note whether they bother); the donut's few jumps snip clean |
| Phase 7 | **Lock-stitch shapes** | The same 30 mm satin on T-shirt knit with Standard, Triangle and Back-tack; a 30 mm circle fill with Triangle | Tug the tails: none unravels; the triangle doesn't show, and on the circle nothing pokes past the edge |
| Phase 7 | **Buttonhole and eyelet** | A 16 mm bar buttonhole and a rounded one on two layers of cotton; a 4 mm eyelet | Cut the slit: sides don't fray and the button passes; the eyelet holds once punched |
| Phase 7 | **Branch** | Three touching leaves in one green; two red shapes joined under a later blue patch; two shapes with a gap; three satins in an S, end to end; two later patches whose edges meet, over a join | One start and one end; nothing to snip where shapes touch, meet end to end or are covered (the two meeting patches too); the hidden run doesn't show through; where shapes only touch, the hand-over (up to about 1 mm) doesn't show; the gap is cut once |
| Phase 7 | **Imported artwork** | A simple SVG logo (fills and 2 mm strokes) imported 80 mm wide | Measures 80 mm; strokes sew as satins of the drawn width; fills meet their borders |

## Log

| Date | Milestone | Design / stitch type | Machine | Fabric + stabilizer | Result | Problems / notes |
| --- | --- | --- | --- | --- | --- | --- |
