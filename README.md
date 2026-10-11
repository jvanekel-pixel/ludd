# LUDD

*Break the machine. Free the stitch.*

**Free, open-source embroidery software** for Windows, Mac and Linux. Open designs and change them,
draw your own, add lettering, and save them for your machine (PES, JEF and 40+ formats). No
account, no sign-in, no subscription, and it works offline.

![The sample designs that come with LUDD](docs/images/samples.png)

**[Download LUDD](https://github.com/jvanekel-pixel/ludd/releases/latest)** · [User guide](docs/USER-GUIDE.md) · [What's new](docs/CHANGELOG.md)

- Open, recolor, resize and combine designs; print a real-size template.
- Draw running stitch, satin and fill; trace pictures with **Trace Assist** (press Tab for the next point).
- Lettering from any installed font, on lines, arches and circles; monograms.
- Save for your machine with checks first; have machines that only cut at color changes (like the
  Brother PE550D) cut jump threads too.
- Fabric presets with stabilizer advice, quality checks that explain themselves, a density map.
- Applique with SVG cut files, splitting big designs across hoopings, repeats, knockdown stitches.
- Light and dark mode, built-in Help (F1), and an optional AI add-on that's off by default.

(Its working name was Threadline; projects saved as `.thl` still open.)

## Building from source

The plan behind it: [docs/PLAN.md](docs/PLAN.md). Releasing: [docs/RELEASING.md](docs/RELEASING.md).

### Prerequisites

- Node 20+ with corepack (`corepack enable` once, to get `pnpm`)
- [uv](https://docs.astral.sh/uv/) (fetches Python 3.12 for the engine)
- Rust via [rustup](https://rustup.rs/), plus the [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/) for your OS (on Windows: Microsoft C++ Build Tools and WebView2)

### Run

```bash
pnpm install
pnpm build:engine   # freeze the Python engine into the Tauri sidecar (re-run after engine changes)
pnpm tauri dev      # desktop app; status bar should read "Engine connected"
```

`pnpm dev` alone serves the UI in a browser at http://localhost:1420. In development the dev server starts the
Python engine itself (see `apps/desktop/vite-engine-bridge.ts`), so the browser preview works too, except native file
dialogs.

### Test

```bash
cd engine && uv run pytest
pnpm test
```

### Build an installer

```bash
pnpm build:engine
pnpm tauri build --config '{"bundle":{"createUpdaterArtifacts":false}}'
```

Output lands in `apps/desktop/src-tauri/target/release/bundle/`. Official releases are built by GitHub Actions; see [docs/RELEASING.md](docs/RELEASING.md).

## Everyday shortcuts

LUDD uses Embrilliance's keys where they exist. The full list is in [docs/USER-MANUAL.md](docs/USER-MANUAL.md#keyboard-shortcuts).

| Do this | Press |
| --- | --- |
| New / Open / Save project | Ctrl+N (or Shift+D) / Ctrl+O / Ctrl+S |
| Save for machine (PES, JEF…) | Ctrl+E |
| Select / Line / Satin / Fill / Text | V / L / C / F / Shift+T |
| Switch between drawing and Select | D |
| Place a curve point / straight point / sharp corner | click / Ctrl+click / Shift+click |
| Finish a shape / undo a point / cancel | Enter or right-click / Backspace / Esc |
| Trace Assist: take the suggested point / keep going | Tab / Shift+Tab |
| Select several / select all / group / ungroup | Shift+click / Ctrl+A / Ctrl+G / Ctrl+U |
| Copy / cut / paste | Ctrl+C / Ctrl+X / Ctrl+V |
| Turn 90° / mirror | R / Alt+H, Alt+V |
| Nudge 1 mm (Shift 1 cm, Ctrl 0.1 mm) | arrow keys |
| Zoom to all / selection / hoop / 1–9× real size | A / S / 0 / 1–9 |
| Realistic thread / stitch points / measure | T / P / M |
| Stitch-out: play / slower / faster | Space / , / . |
| Density map | Alt+D |
| Help (works offline) / Settings | F1 / Ctrl+, |
| Undo / Redo | Ctrl+Z / Ctrl+Y |

Esc lets go of whatever you're doing, one thing per press.

## License

LUDD is free software under the GNU General Public License, version 3 or (at your option) any later version.
See [LICENSE](LICENSE). Anyone may use, share and change it; versions they distribute must stay open under the same terms.
