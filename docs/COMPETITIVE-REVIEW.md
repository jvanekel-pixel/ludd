# Competitive review (2026-11-24)

The full review lives in two Claude Docs (owner's account):

- **LUDD Competitive Feature Compendium**: https://claude.ai/artifact/R3yVfvAnM8ntwoQbshosZe
  154 features from eight competitor manuals (Wilcom EmbroideryStudio e4, BERNINA Editor/DesignerPlus, Brother PE-DESIGN 11, Floriani Total Control U, Embrilliance 1.180, Melco OS v11, Embird Studio, Pulse Autograph), best-in-class pick per feature, user complaints and paywalled features, and LUDD's status per feature.
- **LUDD User Manual - Outline**: https://claude.ai/artifact/4R7YFU9hcx2wTr3Luw2tsd
  Chapter plan for the public manual; each item tagged [now] or with the PLAN.md phase that ships it.

Both documents use the phase numbers the plan had when they were written. The plan was renumbered the same day; `docs/phases/README.md` ("Old plan → new plan") translates them.

## Result in one paragraph

LUDD has 72 of the 154 features, partly has 21, lacks 58; 3 are out of scope. The gaps cluster in lettering (11 of 17 missing) and decorative stitch types (10 of 21). LUDD already wins on what users complain about most: paid levels and upgrades, activation, Windows-only builds, lost work.

## Highest-value gaps, and the phase that closes each

| # | Gap (users pay extra for these or complain about them) | Phase now |
| --- | --- | --- |
| 1 | Merge-safe stitch files: hidden stitches, de-clump, tiny stitches, density-aware resize (Embrilliance Density Repair Kit is a separate purchase) | 4 |
| 2 | Lettering: multi-line, slant, envelopes, single-letter edits, true satin, font from single-letter files (AlphaTricks, $119) | 5 |
| 3 | Two-color blend (Hatch 4 Digitizer only) and push compensation | 6 |
| 4 | Branching (StitchArtist Level 3, $699), freehand drawing, SVG and DXF import | 7 |
| 5 | Freestanding lace, 3D puff, patch edge, open-shape applique, multi-position hoops | 8 |
| 6 | Magic wand and photo stitch | 9 |
| 7 | Organizer and OS thumbnails (Embrilliance Thumbnailer, $44.95); thread inventory | 10 |
| 8 | Learning aids: Simple / Expert switch, hints, F1 help, guided first design, start screen | 11 |
| 9 | Machine list, more thread charts, translations | 12 |
| 10 | The review's "Later" rows: stitches to shapes, chain and string stitch, cutwork, word art | 13 |

Specs: one file per phase in `docs/phases/`. Three items wait on the owner before they are built: remove hidden stitches in merged designs (the review notes Embrilliance's version is patented; Phase 4, decision 1), push compensation (the patent check `PLAN.md` has always asked for; Phase 6, decision 1) and photo stitch (`SPEC.md` lists it as out of scope; Phase 9). BX font import is answered by "make a stitch font from letter files" (Phase 5) unless the owner wants the format looked into.
