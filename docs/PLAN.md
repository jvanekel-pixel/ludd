# Embroidery Studio: Research & Build Plan

|  |  |  |
| --- | --- | --- |
|  |  |  |
|  |  |  |

Oct 11, 2026 · @Copper

## Summary

Build a free, open-source desktop digitizer for Windows, Mac and Linux that covers what hobbyists actually use from Embrilliance and Hatch, with AI as a switchable add-on that assists but never takes over. Name: **LUDD** (Oct 11, 2026; the working name was Threadline).

The core bet: digitizing stays a human job, but the software handles the tedious parts. It proposes the next point along the line you are tracing (Tab to accept), suggests stitch angles and order, and flags density problems before you stitch. That matches the industry's own view: Embrilliance says outright that image-to-stitch conversion does not produce good embroidery, and digitizing guides treat auto-digitize as a rough starting point at best.

The Tab-to-accept tracing feature does not need a language model at all. It is classic computer vision that runs instantly on any PC, so it belongs in the free core, not the AI add-on.

**How to use this plan with Claude Code**

1. Create an empty repo. Export this doc as Markdown to `docs/PLAN.md` and save the CLAUDE.md block near the end as `CLAUDE.md`.
2. Run one milestone per session. Open each with: "Read CLAUDE.md and docs/PLAN.md. Implement milestone M\<n>. Stop at its acceptance criteria and tell me how to verify."
3. From M4 on, stitch out the test sheet on your machine after each milestone and log results in `docs/stitchout-log.md`.
4. Pull from the backlog only when the current milestone is green.

## What the competition charges

A hobbyist who wants full digitizing pays about $1,000 to $1,200 once, or $790 to $1,490 a year for Wilcom's commercial line. Hatch is not a subscription, but its top level costs $1,199 and runs only on Windows 11.

| Product | What it adds | Price (USD, list) | Model | Platforms |
| --- | --- | --- | --- | --- |
| [Embrilliance Essentials](https://embrilliance.com/product/essentials) | Edit, combine, resize, lettering | $159 | Perpetual | Windows + Mac |
| [Embrilliance Enthusiast](https://embrilliance.com/product/enthusiast) | Stitch editing, multi-hoop splitting, knockdown | $179 | Perpetual | Windows + Mac |
| [Embrilliance StitchArtist L3](https://embrilliance.com/product/stitchartist-level-3) | Full manual digitizing, font publishing | $699 | Perpetual | Windows + Mac |
| [Hatch 4 Composer](https://hatchembroidery.com/pricing) | Auto-digitize, layout, multi-hooping | $699 | Perpetual or $45/mo FlexPay | Windows 11 only |
| [Hatch 4 Digitizer](https://hatchembroidery.com/pricing) | Manual digitizing, Multi Blend, PhotoStitch | $1,199 | Perpetual or $99/mo FlexPay | Windows 11 only |
| [Wilcom ES 2026 Decorating](https://www.swingdesign.com/collections/all/products/wilcom-embroiderystudio-decorating-digitizing-software-2026-annual-subscription) | Commercial editing and decorating | $790/yr | Annual subscription | Windows |
| [Wilcom ES 2026 Designing](https://www.swingdesign.com/collections/all/products/wilcom-embroiderystudio-designing-digitizing-software-annual-subscription) | Commercial top tier, all Elements | $1,490/yr | Annual subscription | Windows |
| [Ink/Stitch 3.3](https://inkstitch.org/) | Open-source digitizing inside Inkscape | $0 | GPL-3.0 | Windows, Mac, Linux |

The full Embrilliance stack (Essentials + Enthusiast + StitchArtist L3) is $1,037 at list before fonts and add-ons; Embrilliance prices were on sale through Oct 15, 2026. Wilcom also sells EmbroideryStudio as a one-time purchase alongside the subscription.

## Feature landscape

Most of the value hobbyists pay for sits in five areas: opening and editing existing designs, lettering, manual digitizing with good satin and fill control, multi-hooping, and fabric-aware settings. Those land in v1. Photo stitch, sequins and wireless transfer come later.

| Feature area | Embrilliance | Hatch 4 | Wilcom ES | LUDD phase |
| --- | --- | --- | --- | --- |
| Open, convert, resize, recolor designs | Essentials | All levels | All levels | v1 (M1–M3) |
| Print 1:1 templates and run sheets | Essentials | Yes | Yes | v1 (M3) |
| Stop without a color change | Not listed | New in Hatch 4 | Yes | v1 (M1) |
| Stitch-level editing, jumps to trims | Enthusiast | Composer+ | Yes | v1 (M3) |
| Manual digitizing: run, satin, tatami, underlay, pull comp | StitchArtist L1–3 | Digitizer | Yes | v1 (M4) |
| Assisted tracing of reference art | Magic wand for line areas (L3) | Not listed | Not listed | v1 (M5), our differentiator |
| Lettering with digitized fonts | Essentials (12 fonts) | 66–130 fonts by level | 226+ fonts | v1 (M6) |
| TrueType/OpenType to embroidery | No | Personalizer+ | Yes | v1 (M6) |
| Fabric presets, stabilizer advice | Not listed | Auto-Fabrics (all levels) | Yes | v1 (M7) |
| Knockdown / laydown for napped fabric | Enthusiast | Laydown, Personalizer+ | Yes | v1 (M8) |
| Applique with cut-file export | Essentials + StitchArtist | Advanced Applique (Digitizer) | Yes | v1 (M8) |
| Multi-hoop design splitting | Enthusiast (patented) | Composer+ | Yes | v1 (M8) |
| Repeat, carousel, mirror x4, scatter | Enthusiast | Some layout tools | Yes | v1 (M8) |
| Advanced stitch types: motif, stipple, gradient, emboss, carving, eyelets, 3D foam, fringe, patch edge | StitchArtist L1–3 | Digitizer | Yes plus Elements | v1.x–v2 (backlog) |
| Color blending in one object | Gradient fill (L2) | Multi Blend (Digitizer) | Color Blending | v2 |
| Design library with thumbnails | Thumbnailer add-on | Design Explorer | Yes | v1.x |
| In-app AI help assistant | No | AI Answers (all levels) | Wilcom Answers | v2 (AI add-on) |
| Auto-digitize and photo stitch | No, by design | Composer / Digitizer | Yes, incl. Reef PhotoStitch | Later, assistive only |
| Wireless send to machine | No | Brother Wi-Fi (PR680W, PR1055X, PR1060W) | EmbroideryConnect | Later |
| Sequins and beading | No | No | Elements | Later (commercial) |
| Runs natively on Mac | Yes | No (VM only) | No | Yes, plus Linux |

"Not listed" means the vendor page I read didn't mention it, not that it's definitely absent.

## Gaps and pain points

The clearest openings are cost, platform lock-in, weak fabric handling in free tools, and auto-digitizing that disappoints. Each maps to a design decision below.

| Pain point | Evidence | What LUDD does |
| --- | --- | --- |
| Cost stacks up module by module | Full Embrilliance stack $1,037 list; Hatch Digitizer $1,199; Wilcom $790–1,490/yr; fonts sold separately | Free core; fonts from TrueType plus an open font format |
| Platform lock-in | Hatch 4 needs Windows 11; Wilcom's trial won't run on Mac or VMs; Ink/Stitch needs Inkscape and reviewers flag stability and learning-curve issues | Native Windows, Mac and Linux builds |
| Auto-digitize disappoints | Guides say it fails on complex designs and needs manual refinement; Embrilliance refuses to ship it | Assist tools that propose, human accepts every object |
| Steep learning curve | Hatch 4's headline AI feature is an in-app assistant pitched at shortening the learning curve | Explain-why warnings, guided first design, optional AI help |
| Fabric handling is per-object and manual in free tools | Ink/Stitch maintainers said there's no global fabric-based pull compensation and the fill expand option isn't true pull comp | Fabric profiles applied globally with per-object overrides; directional compensation |
| Push compensation, continuous underlay, custom tie-ins | Patent background describes these as missing from mainstream software | Backlog, after a patent check |
| Basic machine functions arrive late | Hatch only added stop-without-color-change in v4 | Full stop, trim, needle-set support from M1 |
| Machine quirks | A Pfaff creative 1.5 owner had to script color splitting because files over \~100 KB were rejected | Machine profiles with size and stitch-count limits and auto-split |
| No auto-digitize or TrueType in Embrilliance | Reviewer comparison | TrueType lettering in M6 |

One caveat: Reddit and Facebook groups weren't readable with my tools, so this table leans on vendor pages, reviews, the Inkscape forum and patent text. Spend 30 minutes in r/MachineEmbroidery and the StitchArtist Addicts group to confirm or add to it.

## Competitive research: Wilcom and Hatch (added Oct 11, 2026)

Source: the user's research report on Wilcom EmbroideryStudio 2026 and Hatch Embroidery 4 (`compass_artifact_…_text_markdown.md` in the repo root). They are one engine sold as a hobby line and a commercial line; the paywall, not the technology, is the product.

What it changes here:

- **Manual digitizing is the biggest paywall in the industry** (Hatch Digitizer US$1,199; Wilcom Designing US$4,000). M4 is the most valuable milestone; it gets node editing with visible entry and exit points, "continue digitizing" (add to an existing object), snap to objects, and the two-level grid (done in M3).
- **Visible machine functions.** Hatch users praise seeing where trims are; Embrilliance inserts them "totally invisibly". Trims, stops and color changes are shown on the canvas (done after M3).
- **Realistic stitch preview** is table stakes (TrueView and Stitch Player). A shaded thread view ships with the viewer (done after M3); a fabric-distortion and density heat-map is M7.
- **Onboarding is Hatch's moat** (in-app hint videos, F1 help, Academy). LUDD answers with contextual hints and a guided first design (backlog), on top of "Don't make me think".
- **Fabric-aware compensation is still preset-based everywhere.** M7 goes further: geometry-aware pull compensation and automatic widening of satins that are too narrow.
- **Auto-digitizing is the weakest premium promise** ("unlikely to give good results and likely to crash"). Any auto-digitize here produces editable objects with warnings ("too small for satin"), never one-click blobs.
- **Licensing friction moved from dongles to accounts** (sign-ins, 20 to 30 day offline limits, one active session). LUDD promise: **no account, no sign-in, no licence check, works offline forever.**
- **Platform pain:** both are Windows-only; Hatch 4 needs Windows 11 and 16 to 32 GB RAM under Parallels on a Mac. Native Windows, Mac and Linux stays a v1 requirement; a browser build is in the backlog.

## Product principles

These are the rules Claude Code should check every feature against.

- **Human decides, software assists.** Nothing silently changes stitches. Every suggestion is previewed and accepted or dismissed.
- **Objects are the source of truth.** Shapes plus parameters are saved; stitches are regenerated from them, so resizing never wrecks density.
- **Works fully offline with zero AI.** AI features are add-ons with a toggle each, off by default. No account, sign-in or licence check, ever.
- **Machine-agnostic.** Design in millimetres; export through machine profiles, so moving from your domestic machine to a multi-needle is a profile, not a rewrite.
- **Open project format.** Zipped JSON with a published schema from day one, so designs outlive the app.
- **Keyboard-first.** Every tool has a shortcut and appears in a command palette.
- **Every milestone ships something usable.** You can use M1 for real before M4 exists.

## Architecture and tech stack

Use a Tauri desktop shell with a React UI, and a Python engine running beside it. You already know React, and the embroidery ecosystem (file formats, geometry, the best open-source stitch algorithms) lives in Python.

&#91;embedded content: architecture · app, engine, files, optional AI\]

The UI only draws and sends commands; all stitch math, file I/O and Trace Assist run in the engine. AI can only hand the engine proposals, and the whole AI box can be switched off. Trace Assist is highlighted because it's the differentiator, and it lives in the engine, not the AI box.

| Layer | Choice | Why |
| --- | --- | --- |
| App shell | Tauri 2 (Rust) | Small installers for Windows, Mac and Linux, built-in auto-updater, runs a bundled sidecar process |
| UI | React + TypeScript + Vite | Your existing skills |
| Canvas | PixiJS (WebGL) for stitches; SVG overlay for paths and handles | Smooth pan and zoom on 100k+ stitch designs |
| State and undo | Zustand + Immer, command pattern | Every edit is an undoable command |
| Engine | Python 3.12 sidecar, JSON-RPC over stdio | Stitch generation, file I/O, vision |
| File I/O | [pyembroidery](https://github.com/EmbroidePy/pyembroidery) (MIT) | Reads 40+ formats; writes PES, DST, EXP, JEF, VP3, U01, PEC, XXX, TBF; handles stop, trim, needle set and sequins |
| Geometry | Shapely 2, numpy, networkx | Offsets, clipping, fill routing |
| Vision | OpenCV ([Intelligent Scissors](https://docs.opencv.org/4.x/df/d6b/classcv_1_1segmentation_1_1IntelligentScissorsMB.html), edges, color reduction), [vtracer](https://github.com/visioncortex/vtracer) (MIT) | Trace Assist, magic wand, vector tracing |
| ML runtime (optional download) | ONNX Runtime with CUDA, DirectML or CPU; SAM 2.1 tiny (Apache-2.0) | Click-to-region on photos |
| AI providers (optional) | Ollama on localhost; Anthropic or any OpenAI-compatible API with the user's own key | Stitch Advisor, help assistant |
| Packaging and CI | PyInstaller-frozen engine bundled as a Tauri sidecar; GitHub Actions matrix builds | One installer per OS on every release |

**Data model**

- **Project file** (`.ludd`, a zip; `.thl` from before the rename opens too): `design.json`, reference images, thumbnails. **Reference images are embedded** (the original file bytes, not a path), together with their placement: position, scale, rotation, opacity, lock and crop. Save and Save As both write them. Reopening a project on another day, after a reboot, or on another PC shows the image exactly where it was. (User requirement, Oct 11, 2026: Embrilliance lost the source image after a reboot.)
- **Design** holds ordered **objects**. Each object has an id, geometry in mm, stitch type and parameters, thread, optional fabric override, sequence index, locked and hidden flags.
- **Generated stitches** are cached per object by a hash of its inputs. The **pattern** is the ordered blocks plus connectors, trims and tie-ins.
- **Export** runs the pattern through a machine profile into a pyembroidery pattern, then to a file.

**Profiles** are user-editable, shareable JSON:

- **Machine profile:** formats, hoops (including multi-position), needle count, max stitch and jump length, trim support, color change vs needle set, file-size and stitch-count limits.
- **Fabric profile:** density factor, pull and push compensation, underlay recipe, stabilizer suggestion, knockdown default.
- **Thread chart:** brand, code, name, RGB. Color matching uses CIEDE2000 distance.

## Trace Assist: Tab to accept the next point

While you place points over a reference image, a ghost point appears where the line goes next. Tab accepts it, keep tapping Tab to run along the line, and a click anywhere overrides it.

**Why no language model:** a local vision model takes seconds per image; this has to answer in under 30 ms per keystroke. It's built from classic computer vision, needs no download, and works on every PC, so it ships in the free core.

**How it picks the point**

1. **On image load**, precompute three maps: an edge map (gradient magnitude), a centerline map (binarize, then skeletonize, for line art), and an OpenCV Intelligent Scissors cost map.
2. **After each point**, estimate heading and curvature from the last 3 to 5 points with a spline fit.
3. **Generate candidates** on a fan of rays within ±35° of the predicted heading, at a step distance that shrinks on tight curves and grows on straight runs (start at 1.5–6 mm, tune by testing).
4. **Score each candidate** on line strength under it, heading continuity, curvature smoothness, and distance from existing points (no backtracking). For satin rails, also score width consistency between the two rails.
5. **Refine** the winner by snapping to the strongest edge or ridge within 2 px, then check that an Intelligent Scissors path from the last point stays on the line. A costly path lowers confidence.
6. **Show** the ghost point and segment with opacity set by confidence. Below a threshold, show nothing.

**Controls**

- Tab: accept one point. Shift+Tab: keep accepting until a corner or junction.
- `[` and `]`: shorten or lengthen the step. C: toggle corner or curve point.
- At a T or X junction, show up to two ghosts; press 1 or 2 to choose.
- Esc dismisses; Backspace removes the last point.

**Modes**

- **Edge follow** for outlines of fill regions, with a toggle for which side of the edge to sit on.
- **Centerline follow** for run and bean stitches.
- **Satin rails** proposes left and right rail points from the stroke width at that spot and builds a satin column with rungs.

**Later upgrades:** magic wand (flood fill on color-reduced image) to turn a region into a shape; SAM 2.1 tiny click-to-region for photos. SAM runs its image encoder once per image, then each click decodes in milliseconds. An opt-in local log of accepted and rejected ghosts can tune the scoring weights; it never leaves the machine.

**Acceptance targets (proposed):** on five test images (line art, cartoon, logo, scanned sketch, photo), at least 70% of outline points accepted with Tab; ghost latency under 30 ms at p95 on your PC; zero network calls.

## AI add-on: off, local or cloud

AI is a settings switch with three positions, off by default. Users who want it bring their own local model or API key, so there's no account, billing or server for you to run.

| Setting | What runs | Hardware | Features |
| --- | --- | --- | --- |
| Off (default) | Classic algorithms only | Any PC | Trace Assist, magic wand, color reduction, sequence optimizer, density and quality checks |
| Local | ONNX models plus Ollama | 8 GB VRAM is enough | Everything above, plus SAM click-to-region, Stitch Advisor and Help via a local vision model (`qwen2.5vl:7b` or `qwen3-vl:8b`; `gemma3:4b` on smaller cards) |
| Cloud | Anthropic or any OpenAI-compatible API, user's own key | Any PC | Same features as Local, usually better quality; pay-as-you-go on the user's account |

**Features that use a model**

- **Stitch Advisor.** Select regions; the model gets a rendered crop plus a geometry summary and returns JSON: stitch type, angle, underlay and sequence order, each with a one-line reason. Shown as a checklist you accept per object.
- **Design Review.** The quality checks are rule-based; the model explains the findings in plain language and suggests fixes.
- **Help assistant.** Answers questions grounded in the app's own docs, like Hatch's AI Answers.
- **Palette suggestions.** Nearest-thread matching is plain math; the model only suggests a palette that suits a photo.

**Rules for the AI layer**

- One `AIProvider` interface (`chat`, `vision`, `embed`) with Off, Ollama and cloud implementations; features check capabilities and hide when unsupported.
- Per-feature toggles; a "what gets sent" preview and a cost estimate before any cloud call.
- Structured JSON output validated against a schema; invalid output is discarded, never applied.
- Nothing auto-applies. Every suggestion is a proposal you accept.
- Unload local models after use (Ollama `keep_alive`) so the VLM, SAM and the canvas aren't fighting over 8 GB.

## Build milestones for Claude Code

Eleven milestones take you from an empty repo to a v1.0 installer. Each one ends with something you can use and a check you can run yourself; hand Claude Code one at a time.

&#91;embedded content: roadmap · 4 phases, 11 milestones, a gate after each phase\]

Phases are in order, not to scale. Each diamond is the check that must pass before the next phase starts.

1. **M0 Scaffold.** Tauri + React app, Python engine sidecar answering a ping, CI building a Windows installer.
   - Done when: the installer runs on your PC and the status bar shows "Engine connected".
2. **M1 Viewer and converter.** Open any format pyembroidery reads; render stitches in thread colors; info panel (size in mm, stitch count, colors, trims, stops); stitch player with scrubbing; export to other formats; batch-convert a folder.
   - Done when: 20 files from your own library open correctly, and a converted file stitches on your machine.
3. **M2 Machines, hoops, threads.** Machine profile for your machine first; hoop overlay with out-of-hoop warning; thread chart import from CSV; recolor and match to a brand. **Cut-stops** (added Oct 11, 2026): for machines that only cut at color changes (the PE550D), export can turn trims and long jumps into same-color stops so the machine ties off and cuts; tie-in stitches on resume; the export screen shows how many stops it adds.
   - Done when: picking your machine shows its hoops, exports respect its limits, and a cut-stop export stitches on the PE550D with the jump threads cut.
4. **M3 Edit existing designs.** Move, rotate, mirror, scale (warn past ±20%); merge designs; color sort and merge; delete a color block; insert stop or trim; jumps to trims; basting box; print 1:1 template and run sheet. Also (added Oct 11, 2026): a zoom-adaptive grid centred on the hoop, inches by default, covering the whole canvas.
   - Done when: you can do your usual Embrilliance Essentials jobs here.
5. **M4 Digitizing core.** Reference image with opacity, lock and scale-by-measurement; pen tool with corner and curve points; node editing with visible entry and exit points; continue digitizing (extend an existing object); snap to objects and grid; shape tools; run (single, triple, bean), satin column (two rails plus rungs), tatami fill (angle, density, length); underlay (edge run, zigzag, tatami); pull compensation; tie-in and tie-off; live regeneration; sequence panel; save and load projects with embedded reference images; autosave and crash recovery.
   - Done when: you digitize a three-object test design and it stitches cleanly, and after saving, rebooting, and deleting or moving the original image file, the reopened project still shows the reference image in exactly the same place.
6. **M5 Trace Assist.** As specified above.
   - Done when: the acceptance targets in the Trace Assist section are met.
7. **M6 Lettering.** TrueType/OpenType to satin or fill; an open stitch-font format; text on a line, arc and circle; three-letter monograms.
   - Done when: a 10 mm name in a script font stitches legibly.
8. **M7 Fabric profiles and quality checks.** Fabric presets driving density, compensation and underlay; checks for density hotspots, too-short and too-long stitches, over-wide satins, tiny text, gaps; every warning explains why it matters. A density heat-map over the design; geometry-aware pull compensation and automatic widening of satins that are too narrow to stitch.
   - Done when: switching from cotton to towel visibly changes the stitches and the checks catch a deliberately bad design.
9. **M8 Applique and layout.** Applique (placement, tack-down, cover) with SVG cut-file export; multi-hoop splitting with alignment marks; repeat, carousel, mirror x4; knockdown stitches.
   - Done when: a design bigger than your hoop stitches in two hoopings and lines up.
10. **M9 AI add-on.** Provider layer, settings, Stitch Advisor, Help assistant, as specified above.
    - Done when: everything still works with AI off, and Advisor suggestions arrive as accept-or-dismiss proposals.
11. **M10 Release 1.0.** Code signing, auto-update, user guide, sample files, GitHub Releases page.
    - Done when: a friend installs it from the Releases page without your help.

## Prioritized backlog

These are the features beyond M0–M10, sorted by phase and then value. Change the Phase dropdown as you learn what you actually reach for. Effort: S is a session or two, M a few sessions, L a milestone of its own.

| Feature | Seen in | Value | Effort | Phase |
| --- | --- | --- | --- | --- |
| Motif run and motif fill, with custom motifs | StitchArtist, Hatch Digitizer | High | M | v1.x |
| Stipple fill | StitchArtist L1 | High | S | v1.x |
| Push compensation along the stitch direction | Described as missing in patent background | High | M | v1.x |
| Auto sequence optimizer (fewer trims, jumps, color changes) | All three | High | M | v1.x |
| Design library with thumbnails, search and OS thumbnails | Embrilliance Thumbnailer, Hatch Design Explorer | High | M | v1.x |
| Thread inventory and shopping list | Not in the three | High | S | v1.x |
| SVG, DXF and PDF import | StitchArtist L2, Hatch 4 DXF | High | M | v1.x |
| Guided first-design tutorial | Hatch Academy | High | M | v1.x |
| Contextual hints panel and F1 help for the tool in use | Hatch Hints Docker | High | M | v1.x |
| Gradient and feathered fills | StitchArtist L2 | Medium | M | v1.x |
| Monogram templates and ornaments | Hatch Personalizer | Medium | M | v1.x |
| Stitch time and thread usage estimate | Wilcom Estimator | Medium | S | v1.x |
| Command palette and custom shortcuts | Hatch 4 added shortcuts | Medium | S | v1.x |
| Multi-color blending in one object | Hatch Multi Blend, Wilcom | Medium | L | v2 |
| Contour, spiral and maze fills | StitchArtist L2, Wilcom Elements | Medium | M | v2 |
| Fill embossing and carving lines | StitchArtist L2–3, Hatch Digitizer | Medium | M | v2 |
| 3D foam satin with auto underlay and caps | StitchArtist L2, Hatch Digitizer | Medium | M | v2 |
| Patch edge (faux merrow) and patch workflow | StitchArtist L3, PatchArtist | Medium | M | v2 |
| Freestanding lace background | StitchArtist L1 | Medium | M | v2 |
| Cap frame center-out sequencing | Embrilliance lettering | Medium | S | v2 |
| Multi-needle color-to-needle assignment | Commercial software | Medium | M | v2 |
| Realistic preview and garment mock-up export | Embrilliance Enthusiast PNG export | Medium | M | v2 |
| Python plugin and scripting API | Not in the three | Medium | M | v2 |
| Translations | All three | Medium | M | v2 |
| Eyelets, candlewicking, French knots | StitchArtist L2–3 | Low | S | v2 |
| Cross stitch fill | StitchArtist, Hatch add-on, Ink/Stitch 3.3 | Low | S | v2 |
| Hand-stitch randomized effect | Hatch Digitizer, Wilcom | Low | S | v2 |
| Custom tie-in and tie-off shapes | Described as missing in patent background | Low | S | v2 |
| Keyboard design collections (alphabet mapping) | Hatch, Embrilliance AlphaTricks | Low | M | v2 |
| Photo stitch with an editable result | Hatch Digitizer, Wilcom | Medium | L | Later |
| Auto-digitize to editable draft objects | Hatch Composer | Medium | L | Later |
| Continuous underlay across neighboring objects | Described as missing in patent background | Medium | L | Later |
| Sequins and beading | Wilcom Elements | Low | L | Later |
| Wireless send to Brother Wi-Fi machines | Hatch 4 | Low | L | Later |
| Hosted AI tier, if you ever want to charge | Not applicable | Low | L | Later |
| Browser/PWA build (engine via Pyodide) for Chromebooks and tablets | WilcomWorkspace is view-only | Medium | L | Later |
| Pen and touch digitizing, high-DPI and screen-reader pass | Neither vendor commits to it | Medium | M | v2 |

## Testing and quality

The real acceptance test is thread on fabric; automated tests keep Claude Code from breaking what already stitched well.

- **Golden files.** A `fixtures/` folder of real designs in every format you use. Tests read, write and re-read, then compare stitch coordinates, command counts and bounds.
- **Stitch snapshots.** Fixed shapes plus parameters produce stored stitch lists; any change shows up as a diff to review.
- **Property tests.** No stitch longer than the machine's maximum or shorter than the minimum; every stitch inside its shape plus compensation.
- **Visual regression.** Render each fixture to PNG and diff against the last approved image.
- **Performance budgets.** Open a 100k-stitch file in under 2 s; pan and zoom at 60 fps; regenerate one object in under 100 ms; Trace Assist under 30 ms at p95.
- **Stitch-out sheet.** One test design per stitch type on one standard fabric and stabilizer. Photograph each run and note problems in `docs/stitchout-log.md`.
- **AI checks.** A small set of images with expected Stitch Advisor answers; 100% of model output must pass schema validation.

## Risks and open decisions

The one decision to make before M4 is the license, because it decides whether Claude Code may learn from Ink/Stitch's code.

**Decide now**

- [x] **License: GPL-3.0-or-later.** Decided Oct 11, 2026. Ink/Stitch's code (GPL) can be adapted, with credit. I'd pick GPL-3.0. It lets you port Ink/Stitch's proven satin, fill-routing and lettering code (also GPL-3.0), and you can still share freely and charge for a hosted AI service later. Choose MIT only if you may sell a closed desktop app someday; then every stitch algorithm must be written from scratch.
- [x] **First target machine and format.** Decided Oct 11, 2026: a Brother machine (model to confirm before M2). PES is the primary format and JEF (Janome) is a required second export target; M1 golden tests cover both.
- [x] **Name: LUDD.** Decided Oct 11, 2026, with a logo (hammer and needle in a hoop) and light/dark themes. Still check the name is free before the first public release.

**Risks**

- **Patents.** Embrilliance describes its multi-hoop splitting as patented, and [US8851001](https://patents.google.com/patent/US8851001) covers methods for push compensation and continuous underlay. Keep those implementations simple and well documented, and check before shipping them. This isn't legal advice.
- **Format gaps.** pyembroidery reads 40+ formats but writes about ten. Husqvarna and Pfaff owners get VP3; HUS and some others are read-only.
- **Machine quirks.** Brands treat trims, jumps and file sizes differently. Machine profiles plus the stitch-out log are the defense.
- **Install size and signing.** The bundled Python engine with OpenCV adds real size, so keep ONNX models as optional downloads. Unsigned builds trigger Windows and macOS warnings; signing needs paid developer certificates.
- **Font licenses.** Only bundle fonts whose license allows it (OFL and similar).
- **Scope creep.** The backlog is long; v1.0 is M0 through M10 and nothing else.
- **VRAM on 8 GB.** A local vision model, SAM and the canvas compete for memory; load models on demand and unload after use.

## Starter CLAUDE.md

Save this as `CLAUDE.md` in the repo root and fill in the license line once you've decided.

```markdown
# LUDD: notes for Claude Code

## What this is
Cross-platform desktop embroidery digitizer. Full plan: docs/PLAN.md.
Work one milestone at a time. Stop at its acceptance criteria and explain how to verify.

## Layout
- apps/desktop: Tauri 2 + React + TypeScript + Vite; PixiJS canvas, SVG overlay for handles
- engine/: Python 3.12 sidecar, JSON-RPC 2.0 over stdio
  - deps: pyembroidery, shapely, numpy, networkx, opencv-python-headless; onnxruntime optional
- schemas/: JSON Schemas for project, machine, fabric, thread chart (source of truth; generate TS and Python types)
- fixtures/: real design files for golden tests
- docs/: PLAN.md, CHANGELOG.md, stitchout-log.md

## Rules
- Model units are millimetres. Convert to 0.1 mm only at export.
- Objects are the source of truth. Stitches are derived and cached by object hash.
- Imported stitch files are edited in a separate stitch-edit mode.
- Core makes no network calls. AI lives behind engine/ai/providers and is off by default.
- Never auto-apply AI or Trace Assist output. Always preview, then accept or dismiss.
- Every command goes in the command registry with a keyboard shortcut.
- Every engine function gets a pytest; every stitch type gets snapshot tests.
- License: [GPL-3.0 or MIT]. If MIT, do not copy or port code from GPL projects such as Ink/Stitch.

## Commands
- pnpm tauri dev: run the app
- cd engine && uv run pytest: engine tests
- pnpm test: UI tests

## Definition of done for a milestone
- Acceptance criteria in docs/PLAN.md met and demonstrated
- CI green on Windows and macOS
- docs/CHANGELOG.md updated; stitchout-log.md updated if stitch output changed
```

## Sources

- [Embrilliance StitchArtist Level 3](https://embrilliance.com/product/stitchartist-level-3): stitch types by level, tools, formats, prices
- [Embrilliance Enthusiast](https://embrilliance.com/product/enthusiast): stitch editing, patented splitting, knockdown, price
- [Hatch software levels FAQ](https://hatchembroidery.com/faq/software-levels): features per level, Hatch 4 additions
- [What's new in Hatch Embroidery 4](https://hatchembroidery.com/whats-new): Multi Blend, Stop, AI Answers, Wi-Fi transfer
- [Hatch 4 pricing and comparison](https://hatchembroidery.com/pricing): $699 and $1,199, FlexPay, Windows 11 only
- [Wilcom: EmbroideryStudio 2025 top features](https://wilcom.com/resources/blog/top-10-new-features-of-wilcom-embroiderystudio-2025): one-time or subscription
- [Wilcom ES 2026 Designing subscription](https://www.swingdesign.com/collections/all/products/wilcom-embroiderystudio-designing-digitizing-software-annual-subscription) and [Decorating subscription](https://www.swingdesign.com/collections/all/products/wilcom-embroiderystudio-decorating-digitizing-software-2026-annual-subscription)
- [Wilcom EmbroideryStudio trial](https://wilcom.com/embroiderystudio/trial): not available on Mac or VMs
- [Wilcom e4.5 What's New](https://legacy.wilcom.com/e4/download/pdf/ReleaseNotes/Whats_New_e4.5.1_DS_WORLD.pdf): Elements such as Hand Stitch, Maze Fill, Reef PhotoStitch, beading
- [pyembroidery on GitHub](https://github.com/EmbroidePy/pyembroidery): MIT, read and write formats, commands
- [Ink/Stitch](https://inkstitch.org/) and [v3.3.0 release news](https://alternativeto.net/news/2026/7/ink-stitch-v3-3-0-cross-stitch-fill-improved-lettering-and-satin-column-simplification/); [license on AlternativeTo](https://alternativeto.net/software/ink-stitch/about)
- [Inkscape forum: global pull compensation in Ink/Stitch](https://inkscape.org/forums/embroidery/global-parameters-for-shrink-compensation)
- [US8851001: Method for improved stitch generation](https://patents.google.com/patent/US8851001)
- [Embroidery software comparison (Sewing Machine Fun)](https://www.sewingmachinefun.com/best-embroidery-software/): Embrilliance lacks auto-digitize and TrueType conversion
- [Ink/Stitch vs Hatch vs Embrilliance (MaggieFrame)](https://maggieframestore.com/blogs/maggieframe-news/best-embroidery-digitizing-programs-2025-expert-reviews-feature-comparisons): Ink/Stitch stability and learning curve
- [Beginner digitizing mistakes](https://www.patreon.com/posts/top-mistakes-157798745): auto-digitize as a starting point only
- [embroiderySplit script](https://github.com/hisermann/embroiderySplit): Pfaff creative 1.5 file-size limit
- [OpenCV IntelligentScissorsMB](https://docs.opencv.org/4.x/df/d6b/classcv_1_1segmentation_1_1IntelligentScissorsMB.html)
- [SAM 2.1 tiny split ONNX](https://huggingface.co/AbrahamPJ/sam2-tiny-split-onnx): encoder once per image, fast per-click decoder
- [vtracer license (FreshPorts)](https://www.freshports.org/graphics/vtracer/)
- [Local vision models by VRAM tier](https://insiderllm.com/guides/vision-models-locally/): 8 GB picks
