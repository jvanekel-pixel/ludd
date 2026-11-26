/** "Make a stitch font from letter files…" (text.fontFromFiles): a folder (or files) with one
 *  design for each letter. Each file is shown with the character guessed from its name, to check;
 *  then the font gets a name and a letter gap, a line of its letters stands on a baseline (any of
 *  them can be nudged up or down), and it's saved in LUDD's fonts folder, where the font list
 *  finds it. */
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { useRef, useState, type CSSProperties, type FocusEvent, type KeyboardEvent } from "react";
import { basename, engine, info, loadFonts, PREFERRED_FORMATS } from "../actions";
import { isTauri } from "../engine/sidecar";
import { pickFolder } from "../features";
import { useStore } from "../store";
import { useModal } from "./ThreadDialogs";

/** A letter file as the engine reads it (fonts.scan_letter_files). */
export type LetterFile = {
  path: string;
  name: string;
  guess: string;
  thumb: string;
  width_mm: number;
  height_mm: number;
  stitches: number;
  colors: number;
  error?: string;
};
type Scan = { files: LetterFile[]; common: { prefix: string; suffix: string } };
type Built = { path: string; glyphs: number; cap_height_mm: number; folder: string };

const LONG_MS = 300_000;
const GAP_RANGE = [-50, 100];
const BASELINE_COLOR = "#2f8fd8"; // as the guides on the design

const close = () => useStore.getState().setDialog(null);
const round3 = (v: number) => Math.round(v * 1000) / 1000;

// ---------------------------------------------------------------- lining the letters up
// The same rules as the engine (lettering/fontbuild.py: _cap_height and _drop), so the preview
// shows the font as it will be saved.

const CAPITALS_AND_DIGITS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
const TALL = "bdfhkl";
const SMALL = "acemnorsuvwxz";
const SMALL_SHARE = 0.68;

const isCapital = (c: string) => c !== c.toLowerCase() && c === c.toUpperCase();

function median(values: number[]) {
  const s = [...values].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/** The capital height and the height of small letters like x, from one height per character. */
export function fontMetrics(letters: { char: string; height: number }[]): { cap: number; small: number } {
  const of = (want: (c: string) => boolean) => letters.filter((l) => want(l.char)).map((l) => l.height);
  const smalls = of((c) => SMALL.includes(c));
  const capitals = [of((c) => CAPITALS_AND_DIGITS.includes(c)), of(isCapital), of((c) => TALL.includes(c))].find((v) => v.length);
  const measured = capitals ? median(capitals) : smalls.length ? median(smalls) / SMALL_SHARE : letters.length ? median(of(() => true)) : 1;
  const cap = round3(Math.max(measured, 1));
  return { cap, small: smalls.length ? median(smalls) : SMALL_SHARE * cap };
}

/** How far below the baseline a letter's bottom goes (mm; above it when negative). */
export function autoDrop(char: string, height: number, cap: number, small: number): number {
  if ("gjpqy".includes(char)) return height - small; // its top level with the small letters'
  if (",;".includes(char)) return 0.15 * cap;
  if ("'\"^*".includes(char)) return height - cap; // at the top
  if ("-+=~".includes(char)) return (height - cap) / 2; // in the middle
  return 0;
}

const otherCase = (c: string) => (c === c.toLowerCase() ? c.toUpperCase() : c.toLowerCase());

/** "Hamburg 123" from the characters there are (the other case will do, as when typing), else the
 *  first few; the picked letter is added if it isn't in it. */
export function previewText(have: Set<string>, picked: string): string {
  const use = (c: string) => (have.has(c) ? c : have.has(otherCase(c)) ? otherCase(c) : "");
  let text = Array.from("Hamburg 123", (c) => (c === " " ? c : use(c))).join("").replace(/ +/g, " ").trim();
  if (!text) text = [...have].slice(0, 12).join("");
  if (picked && !text.includes(picked)) text = text ? `${text} ${picked}` : picked;
  return text;
}

/** The preview's letters in mm, the baseline at y = 0, and the box that holds them. */
function layOutLine(text: string, gapMm: number, cap: number, letter: (ch: string) => { file: LetterFile; bottom: number } | null) {
  const letters: { key: number; file: LetterFile; char: string; x: number; y: number }[] = [];
  let x = 0;
  Array.from(text).forEach((ch, key) => {
    if (ch === " ") {
      x += 0.35 * cap;
      return;
    }
    const found = letter(ch);
    if (!found) return;
    letters.push({ key, file: found.file, char: ch, x: x + gapMm / 2, y: found.bottom - found.file.height_mm });
    x += Math.max(found.file.width_mm + gapMm, 0.1);
  });
  const pad = 0.15 * cap;
  const top = Math.min(-cap, ...letters.map((l) => l.y)) - pad;
  const bottom = Math.max(0.35 * cap, ...letters.map((l) => l.y + l.file.height_mm)) + pad;
  return { letters, width: Math.max(x, cap), top, height: bottom - top };
}

/** What the character box holds after typing: one character (one typed next to the old one replaces it). */
function typedChar(value: string, before: string): string {
  const chars = Array.from(value.normalize("NFC").replace(/[\uFE0E\uFE0F]/g, "")).filter((c) => c.trim());
  if (chars.length > 1) {
    const old = chars.indexOf(before);
    if (old >= 0) chars.splice(old, 1);
  }
  return chars[chars.length - 1] ?? "";
}

// ---------------------------------------------------------------- the dialog

const cellStyle = (color?: string): CSSProperties => ({
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: 4,
  padding: 6,
  border: `1px solid ${color ?? "var(--line)"}`,
  borderRadius: 8,
  textAlign: "center",
});

export function FontFromFilesDialog() {
  const ref = useModal(true);
  const formats = useStore((s) => s.formats);
  const [files, setFiles] = useState<LetterFile[] | null>(null);
  const [source, setSource] = useState("");
  const [chars, setChars] = useState<Record<string, string>>({});
  const [nudges, setNudges] = useState<Record<string, number>>({});
  const [picked, setPicked] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [gap, setGap] = useState("8");
  const [busy, setBusy] = useState<"reading" | "saving" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const saving = useRef(false);
  const scanSeq = useRef(0);
  const fieldUndo = useRef<(() => void) | null>(null); // Esc in a box: what it said comes back
  const preview = useRef<HTMLDivElement>(null);

  const listed = files ?? [];
  const assigned = listed.filter((f) => !f.error && chars[f.path]);
  const uses = new Map<string, number>();
  for (const f of assigned) uses.set(chars[f.path], (uses.get(chars[f.path]) ?? 0) + 1);
  const twice = [...uses].filter(([, n]) => n > 1).map(([c]) => c);
  const unnamed = listed.filter((f) => !f.error && !chars[f.path]).length;
  const broken = listed.filter((f) => f.error).length;
  const gapValue = Number(gap);
  const gapOk = gap.trim() !== "" && Number.isFinite(gapValue) && gapValue >= GAP_RANGE[0] && gapValue <= GAP_RANGE[1];
  const whyNot = busy
    ? "Just a moment…"
    : !files
      ? "Choose the letter files first"
      : twice.length
        ? `${twice.join(", ")} ${twice.length > 1 ? "are" : "is"} used twice`
        : !assigned.length
          ? "No file has a character yet"
          : !name.trim()
            ? "Give the font a name"
            : !gapOk
              ? `The letter gap is a number from ${GAP_RANGE[0]} to ${GAP_RANGE[1]}`
              : "";

  // The font as it will be built: the first file for each character.
  const byChar = new Map<string, LetterFile>();
  for (const f of assigned) if (!byChar.has(chars[f.path])) byChar.set(chars[f.path], f);
  const { cap, small } = fontMetrics([...byChar].map(([char, f]) => ({ char, height: f.height_mm })));
  const dropOf = (f: LetterFile) => autoDrop(chars[f.path], f.height_mm, cap, small);
  const step = Math.max(0.1, Math.round(cap * 0.2) / 10);
  const pickedFile = assigned.find((f) => f.path === picked) ?? null;
  const sample = previewText(new Set(byChar.keys()), pickedFile ? chars[pickedFile.path] : "");

  const line = layOutLine(sample, ((gapOk ? gapValue : 8) / 100) * cap, cap, (ch) => {
    // The picked file stands for its character, even when another file has the same one.
    const f = pickedFile && chars[pickedFile.path] === ch ? pickedFile : byChar.get(ch);
    return f ? { file: f, bottom: dropOf(f) + (nudges[f.path] ?? 0) } : null;
  });

  const read = async (what: { folder: string } | { files: string[] }, label: string) => {
    const mine = ++scanSeq.current;
    setBusy("reading");
    setError(null);
    try {
      const r = await engine().call<Scan>("fonts.scan_letter_files", what, LONG_MS);
      if (mine !== scanSeq.current) return;
      setFiles(r.files);
      setSource(label);
      setChars(Object.fromEntries(r.files.map((f) => [f.path, f.guess])));
      setNudges({});
      setPicked(null);
    } catch (e) {
      if (mine === scanSeq.current) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (mine === scanSeq.current) setBusy(null);
    }
  };

  const chooseFolder = async () => {
    const folder = await pickFolder("Folder with one design file for each letter");
    if (folder) await read({ folder }, folder);
  };

  const chooseFiles = async () => {
    const exts = formats?.read.map((f) => f.ext) ?? PREFERRED_FORMATS;
    const chosen = isTauri()
      ? await openDialog({ title: "Choose the letter files", multiple: true, directory: false, filters: [{ name: "Embroidery designs", extensions: exts.flatMap((e) => [e, e.toUpperCase()]) }] })
      : window.prompt("Letter files (full paths, separated by ;)")?.split(";").map((p) => p.trim()).filter(Boolean);
    const list = Array.isArray(chosen) ? chosen : chosen ? [chosen] : [];
    if (list.length) await read({ files: list }, list.length === 1 ? basename(list[0]) : `${list.length} files`);
  };

  const save = async () => {
    if (whyNot) return;
    const letters = assigned.map((f) => {
      const nudge = nudges[f.path] ?? 0;
      return { path: f.path, char: chars[f.path], ...(nudge ? { dy_mm: round3(dropOf(f) + nudge) } : {}) };
    });
    const fontName = name.trim();
    saving.current = true;
    setBusy("saving");
    setError(null);
    try {
      const r = await engine().call<Built>("fonts.build_from_files", { letters, name: fontName, gap_pct: gapValue, dest: "" }, LONG_MS);
      saving.current = false;
      useStore.setState({ fonts: null }); // listed again, with the new font in it
      void loadFonts().catch(() => {});
      close();
      info(`Saved the font “${fontName}” with ${r.glyphs} letter${r.glyphs === 1 ? "" : "s"}. It's in the font list now, as a stitch font.`);
    } catch (e) {
      saving.current = false;
      setError(e instanceof Error ? e.message : String(e));
      setBusy(null);
    }
  };

  const nudge = (mm: number) => {
    if (!pickedFile) return;
    const path = pickedFile.path;
    setNudges((n) => ({ ...n, [path]: round3((n[path] ?? 0) + mm) }));
  };
  const putBack = () => {
    if (pickedFile) setNudges(({ [pickedFile.path]: _, ...rest }) => rest);
  };

  /** Focus handlers for a box: what it says is selected, ready to type over, and kept so Esc can
   *  put it back. */
  const undoable = (value: string, set: (v: string) => void) => ({
    onFocus: (e: FocusEvent<HTMLInputElement>) => {
      fieldUndo.current = () => set(value);
      e.currentTarget.select();
    },
    onBlur: () => {
      fieldUndo.current = null;
    },
  });

  // Esc lets go of one thing per press: a box you're typing in (what it said comes back), then the
  // dialog. While saving it stays open.
  const onKeyDown = (e: KeyboardEvent<HTMLDialogElement>) => {
    if (e.key !== "Escape") return;
    e.preventDefault();
    e.stopPropagation();
    if (e.repeat || saving.current) return;
    const undo = fieldUndo.current;
    if (undo && e.target instanceof HTMLInputElement) {
      fieldUndo.current = null;
      undo();
      e.target.blur();
      return;
    }
    close();
  };

  const onPreviewKey = (e: KeyboardEvent) => {
    if (!pickedFile || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
    e.preventDefault();
    nudge(e.key === "ArrowUp" ? -step : step);
  };

  const pickedNudge = pickedFile ? (nudges[pickedFile.path] ?? 0) : 0;

  return (
    <dialog
      ref={ref}
      className="modal browse"
      aria-labelledby="font-files-title"
      onKeyDown={onKeyDown}
      onCancel={(e) => saving.current && e.preventDefault()}
      onClose={() => (saving.current ? ref.current?.showModal() : close())}
    >
      <h2 id="font-files-title">Make a stitch font from letter files</h2>
      <p className="hint">
        One embroidery file for each letter, in any format LUDD opens. LUDD guesses each character from the file's name: check them and fix any that are wrong.
      </p>
      <div className="browse-bar">
        <button disabled={!!busy} onClick={() => void chooseFolder()}>
          Choose folder…
        </button>
        <button disabled={!!busy} onClick={() => void chooseFiles()}>
          Choose files…
        </button>
        <span className="browse-folder" title={source}>
          {source}
        </span>
      </div>
      {busy === "reading" && <p className="hint">Reading the letter files…</p>}

      {files && (
        <>
          <p className="hint">
            {twice.length
              ? `${twice.join(", ")} ${twice.length > 1 ? "are" : "is"} used twice: change one, or clear its box to leave it out.`
              : `${assigned.length} of ${files.length} file${files.length === 1 ? "" : "s"} will be in the font.`}
            {unnamed > 0 && ` ${unnamed} ${unnamed === 1 ? "has" : "have"} no character.`}
            {broken > 0 && ` ${broken} can't be read.`}
          </p>
          <ul className="browse-grid" style={{ maxHeight: "30vh" }}>
            {files.map((f) => {
              const ch = chars[f.path] ?? "";
              const n = ch ? (uses.get(ch) ?? 0) : 0;
              const flag = f.error ? null : !ch ? "No character: left out" : n > 1 ? `${ch} is used ${n === 2 ? "twice" : `${n} times`}` : null;
              return (
                <li key={f.path} style={cellStyle(f.error || n > 1 ? "var(--bad)" : !ch ? "var(--warn)" : undefined)}>
                  <button
                    type="button"
                    disabled={!!f.error || !ch}
                    title={ch ? `Show ${f.name} on the preview` : f.name}
                    onClick={() => setPicked(f.path)}
                    style={{ width: 76, height: 76, padding: 5, background: "var(--fabric)", outline: picked === f.path ? "2px solid var(--mark)" : undefined }}
                  >
                    {f.thumb ? <img src={f.thumb} alt="" style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }} /> : "?"}
                  </button>
                  <small className="browse-name" title={f.path}>
                    {f.name}
                  </small>
                  {f.error ? (
                    <small style={{ color: "var(--bad)" }}>{f.error}</small>
                  ) : (
                    <input
                      aria-label={`Character for ${f.name}`}
                      value={ch}
                      style={{ width: "3rem", textAlign: "center", fontSize: 18 }}
                      {...undoable(ch, (v) => setChars((c) => ({ ...c, [f.path]: v })))}
                      onClick={(e) => e.currentTarget.select()}
                      onChange={(e) => {
                        const next = typedChar(e.target.value, ch);
                        setChars((c) => ({ ...c, [f.path]: next }));
                      }}
                    />
                  )}
                  {flag && <small style={{ color: n > 1 ? "var(--bad)" : "var(--warn)" }}>{flag}</small>}
                </li>
              );
            })}
          </ul>

          <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap", gap: "1rem", margin: "0.75rem 0" }}>
            <label className="field" style={{ flex: "1 1 14rem", margin: 0 }}>
              Font name
              <input aria-label="Font name" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} {...undoable(name, setName)} />
            </label>
            <label className="field" style={{ margin: 0 }}>
              Letter gap
              <span className="row">
                <input aria-label="Letter gap" type="number" step={1} min={GAP_RANGE[0]} max={GAP_RANGE[1]} value={gap} style={{ width: "5rem" }} onChange={(e) => setGap(e.target.value)} {...undoable(gap, setGap)} />
                <small>% of the capital height</small>
              </span>
            </label>
          </div>

          <div ref={preview} tabIndex={0} aria-label="Preview on the baseline" onKeyDown={onPreviewKey}>
            <svg viewBox={`0 ${line.top} ${line.width} ${line.height}`} preserveAspectRatio="xMidYMid meet" style={{ display: "block", width: "100%", height: 120, background: "var(--fabric)", borderRadius: 6 }}>
              <line className="baseline" x1={0} x2={line.width} y1={0} y2={0} stroke={BASELINE_COLOR} strokeWidth={1} vectorEffect="non-scaling-stroke" />
              {line.letters.map((l) => (
                <g key={l.key}>
                  <image
                    data-char={l.char}
                    href={l.file.thumb}
                    x={round3(l.x)}
                    y={round3(l.y)}
                    width={l.file.width_mm}
                    height={l.file.height_mm}
                    preserveAspectRatio="none"
                    style={{ cursor: "pointer" }}
                    onClick={() => {
                      setPicked(l.file.path);
                      preview.current?.focus();
                    }}
                  />
                  {l.file.path === picked && (
                    <rect x={l.x} y={l.y} width={l.file.width_mm} height={l.file.height_mm} fill="none" stroke={BASELINE_COLOR} strokeDasharray="4 3" vectorEffect="non-scaling-stroke" pointerEvents="none" />
                  )}
                </g>
              ))}
            </svg>
          </div>
          <div className="row" style={{ margin: "0.4rem 0 0.75rem", flexWrap: "wrap" }}>
            {pickedFile ? (
              <>
                <small style={{ flex: "1 1 12rem" }}>
                  “{chars[pickedFile.path]}” {pickedNudge ? `nudged ${Math.abs(pickedNudge).toFixed(1)} mm ${pickedNudge > 0 ? "down" : "up"}` : "is where LUDD puts it"}.
                </small>
                <button onClick={() => nudge(-step)} title="Arrow up">
                  Nudge up
                </button>
                <button onClick={() => nudge(step)} title="Arrow down">
                  Nudge down
                </button>
                <button disabled={!pickedNudge} onClick={putBack}>
                  Put back
                </button>
              </>
            ) : (
              <small className="hint" style={{ margin: 0 }}>
                A letter not sitting right? Click it, then nudge it up or down.
              </small>
            )}
          </div>
        </>
      )}

      <p className="hint">Only make fonts from designs you're allowed to use this way.</p>
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button onClick={close} disabled={busy === "saving"}>
          Cancel
        </button>
        <button className="primary" disabled={!!whyNot} title={whyNot || undefined} onClick={() => void save()}>
          Save font
        </button>
      </div>
    </dialog>
  );
}
