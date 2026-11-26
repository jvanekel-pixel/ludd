import { useEffect, useMemo, useRef, useState } from "react";
import { command, info, loadFonts, saveStitchFont, setText, takeTextToEdit } from "../actions";
import { formatShortcut } from "../commands";
import { heldCount, holdEscape } from "../escape";
import { MM_PER_IN } from "../design/grid";
import type { FontInfo, LayoutItemInfo, TextItem, TextShape, Thread } from "../design/types";
import { useStore } from "../store";
import { Section, Sub, type SelKind } from "./Accordion";
import { ExtrasControls, ExtrasMore } from "./text/ExtrasControls";
import { LayoutControls, LayoutMore } from "./text/LayoutControls";
import { isStitchFont } from "./text/slots";
import { StyleControls, styleLabel } from "./text/StyleControls";
import { ThreadPicker } from "./ThreadDialogs";

const SHAPES: { type: TextShape["type"]; label: string; title: string }[] = [
  { type: "line", label: "Straight", title: "Letters on a straight line" },
  { type: "arc_up", label: "Arch", title: "Letters curve over the top of a circle" },
  { type: "arc_down", label: "Smile", title: "Letters curve under the bottom of a circle" },
  { type: "circle", label: "Circle", title: "Letters all the way round a circle" },
];

const TYPE_DELAY_MS = 450;
/** The text box's look, as the one-line box it replaces. */
const TEXT_AREA: React.CSSProperties = { font: "inherit", fontSize: 16, padding: "0.35rem 0.5rem", border: "1px solid var(--line)", borderRadius: 6, background: "var(--panel)", color: "var(--fg)", resize: "vertical" };
const FONT_LIST_MAX = 200;
const MIN_SIZE_MM = 2;
const MAX_SIZE_MM = 200;

/** Searchable font list: type part of a name ("script", "arial"). */
function FontPicker({ value, onPick }: { value: TextItem["font"]; onPick: (f: FontInfo) => void }) {
  const fonts = useStore((s) => s.fonts);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (open && !fonts) void loadFonts();
  }, [open, fonts]);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (root.current?.contains(e.target as Node)) return;
      setOpen(false);
      // A click on the design that closes the list only closes it: it doesn't also draw or select.
      if (e.target instanceof Element && e.target.closest(".stitch-canvas")) e.stopPropagation();
    };
    const release = holdEscape(() => setOpen(false));
    // Capture: heard before the canvas gets the click.
    window.addEventListener("pointerdown", onDown, true);
    return () => {
      window.removeEventListener("pointerdown", onDown, true);
      release();
    };
  }, [open]);
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const all = fonts ?? [];
    return q ? all.filter((f) => `${f.family} ${f.style}`.toLowerCase().includes(q)) : all;
  }, [fonts, query]);
  const list = matches.slice(0, FONT_LIST_MAX);
  return (
    <div className="font-picker" ref={root}>
      <button className="font-current" onClick={() => setOpen(!open)} aria-expanded={open} title="Choose a font">
        <span>{value.family}</span>
        <small>{value.style}</small>
      </button>
      {open && (
        <div className="font-list">
          <input autoFocus placeholder="Search fonts, e.g. script" value={query} onChange={(e) => setQuery(e.target.value)} />
          {!fonts && <p className="hint">Looking for fonts…</p>}
          {matches.length > list.length && <p className="hint">Showing {list.length} of {matches.length} fonts: type part of a name to find the others.</p>}
          <ul>
            {list.map((f) => (
              <li key={`${f.path}#${f.index}`}>
                <button
                  className={f.path === value.path && f.index === value.index ? "on" : undefined}
                  onClick={() => {
                    onPick(f);
                    setOpen(false);
                  }}
                >
                  {f.family} <small>{f.kind === "stitch" ? "stitch font" : f.style}</small>
                </button>
              </li>
            ))}
          </ul>
          <button
            className="wide"
            title="Make a stitch font from a folder of single-letter stitch files"
            onClick={() => {
              setOpen(false);
              command("text.fontFromFiles").run();
            }}
          >
            Make a stitch font from letter files…
          </button>
        </div>
      )}
    </div>
  );
}

/** Lettering: what it says, its font and size, how it's stitched, and the shape it follows. */
export function SelectedText({ item, info: itemInfo, sel }: { item: TextItem; info: LayoutItemInfo; sel: SelKind }) {
  // The thread it's sewn in: a color changed in Order & colors wins over its own.
  const sewn = item.threads?.[0] ?? item.thread;
  const units = useStore((s) => s.units);
  const [draft, setDraft] = useState(item.text);
  const [picking, setPicking] = useState(false);
  const input = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const reverting = useRef(false);
  const before = useRef(item.text); // the text when the box was clicked into: Esc brings it back

  // The saved text comes back into the box, but never while you're typing in it: a slow update
  // landing mid-word would wipe the letters typed since.
  useEffect(() => {
    if (document.activeElement !== input.current) setDraft(item.text);
  }, [item.text]);
  useEffect(() => setDraft(item.text), [item.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const focus = () => {
      takeTextToEdit(item.id);
      input.current?.focus();
      input.current?.select();
    };
    // Just placed: the request came before this panel was here.
    if (takeTextToEdit(item.id)) focus();
    const onEdit = (e: Event) => {
      if ((e as CustomEvent).detail === item.id) focus();
    };
    window.addEventListener("ludd:edit-text", onEdit);
    return () => window.removeEventListener("ludd:edit-text", onEdit);
  }, [item.id]);

  const commitText = (t: string) => {
    clearTimeout(timer.current);
    if (t.trim() && t !== item.text) setText(item.id, { text: t });
  };
  /** The words: several lines, but a monogram's three initials on one. */
  const textField = {
    ref: (el: HTMLInputElement | HTMLTextAreaElement | null) => {
      input.current = el;
    },
    value: draft,
    maxLength: item.monogram ? 3 : 200,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setDraft(e.target.value);
      clearTimeout(timer.current);
      const v = e.target.value;
      // Typing updates the stitches after a short pause, not on every key.
      timer.current = setTimeout(() => commitText(v), TYPE_DELAY_MS);
    },
    onFocus: () => {
      before.current = item.text;
    },
    onBlur: () => {
      if (reverting.current) reverting.current = false;
      else if (!draft.trim()) {
        // An empty box can't be stitched: the text it had comes back.
        clearTimeout(timer.current);
        setDraft(item.text);
      } else commitText(draft);
    },
    onKeyDown: (e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      // Several lines: Enter starts a new one and Ctrl+Enter (Cmd+Enter on a Mac) is done.
      // Initials: Enter is done. (Not while an input method is still composing a character.)
      if (e.key === "Enter" && (item.monogram || e.ctrlKey || e.metaKey) && !e.nativeEvent.isComposing) {
        e.preventDefault();
        e.currentTarget.blur();
      }
      // (While something is held, such as a drag, Esc lets go of that first.)
      if (e.key === "Escape" && !heldCount()) {
        // Esc lets go of the edit: the text goes back to what it was before you typed,
        // even if a pause in typing already updated the design.
        clearTimeout(timer.current);
        reverting.current = true;
        setDraft(before.current);
        if (before.current !== item.text) setText(item.id, { text: before.current });
        e.currentTarget.blur();
      }
    },
  };
  const toUnits = (mm: number) => (units === "in" ? mm / MM_PER_IN : mm);
  const fromUnits = (v: number) => (units === "in" ? v * MM_PER_IN : v);
  const curved = item.shape.type !== "line" && item.shape.type !== "path";
  const stitchFont = isStitchFont(item.font.path);

  return (
    <Section id="lettering" sel={sel} defaultOpen title="Lettering" summary={`${item.font.family} · ${styleLabel(item)}`}>
      <label className="text-field">
        <span>{item.monogram ? "Three initials" : "Text"}</span>
        {item.monogram ? (
          <input {...textField} />
        ) : (
          <textarea {...textField} rows={3} title={`Enter starts a new line; ${formatShortcut("Mod+Enter")} is done`} style={TEXT_AREA} />
        )}
      </label>
      <FontPicker value={item.font} onPick={(f) => setText(item.id, { font: { path: f.path, index: f.index, family: f.family, style: f.style, ...(f.made_of ? { made_of: f.made_of } : {}) } })} />

      <div className="size-row">
        <label className="num-field">
          <span>Letter height</span>
          <input
            type="number"
            step={units === "in" ? 0.05 : 1}
            min={toUnits(MIN_SIZE_MM).toFixed(2)}
            max={toUnits(MAX_SIZE_MM).toFixed(2)}
            defaultValue={toUnits(item.size_mm).toFixed(2)}
            key={`${item.id}-${item.size_mm}-${units}`}
            onBlur={(e) => {
              if (e.target.value === e.target.defaultValue) return; // unchanged: clicking in and out does nothing
              const v = fromUnits(Number(e.target.value));
              if (e.target.value.trim() && Number.isFinite(v) && v >= MIN_SIZE_MM - 1e-6 && v <= MAX_SIZE_MM + 1e-6) {
                setText(item.id, { size_mm: v });
                return;
              }
              e.target.value = e.target.defaultValue; // the old height comes back
              const range = units === "in" ? `${toUnits(MIN_SIZE_MM).toFixed(2)} and ${toUnits(MAX_SIZE_MM).toFixed(1)} in` : `${MIN_SIZE_MM} and ${MAX_SIZE_MM} mm`;
              info(`Letter height must be between ${range}.`);
            }}
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
          />
          <small>{units} (capitals)</small>
        </label>
      </div>

      <button className="thread-button" onClick={() => setPicking(true)} title="Change thread">
        <span className="swatch" style={{ background: sewn.color }} />
        <span className="tname">
          {sewn.name || sewn.color}
          <small>{[sewn.brand, sewn.catalog].filter(Boolean).join(" ") || "Click to choose a thread"}</small>
        </span>
      </button>

      <LayoutControls item={item} info={itemInfo} />
      <StyleControls item={item} info={itemInfo} />
      <ExtrasControls item={item} info={itemInfo} />

      {!item.monogram && (
        <Sub id="text-shape" title="Shape" summary={SHAPES.find((sh) => sh.type === item.shape.type)?.label}>
      {!item.monogram && (
        <div className="seg" role="group" aria-label="Shape">
          {item.shape.type === "path" && (
            <button aria-pressed title="Following a line you drew (pick another shape to put it back)">
              On your line
            </button>
          )}
          {SHAPES.map((sh) => (
            <button
              key={sh.type}
              aria-pressed={item.shape.type === sh.type}
              title={sh.title}
              onClick={() => setText(item.id, { shape: { type: sh.type, radius_mm: item.shape.radius_mm ?? 40 } })}
            >
              {sh.label}
            </button>
          ))}
        </div>
      )}
      {curved && !item.monogram && (
        <div className="size-row">
          <label className="num-field">
            <span>Curve size (radius)</span>
            <input
              type="number"
              step={units === "in" ? 0.1 : 1}
              defaultValue={toUnits(item.shape.radius_mm ?? 40).toFixed(2)}
              key={`${item.id}-r-${item.shape.radius_mm}-${units}`}
              onBlur={(e) => {
                if (e.target.value === e.target.defaultValue) return;
                const v = fromUnits(Number(e.target.value));
                if (Number.isFinite(v) && v > 2) setText(item.id, { shape: { ...item.shape, radius_mm: v } });
              }}
              onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
            />
            <small>{units}</small>
          </label>
        </div>
      )}
        </Sub>
      )}

      <Sub id="text-advanced" title="More options">
        <LayoutMore item={item} info={itemInfo} />
        <ExtrasMore item={item} info={itemInfo} />
        <div className="size-row">
          <label className="num-field">
            <span>Extra letter spacing</span>
            <input
              type="number"
              step={units === "in" ? 0.01 : 0.1}
              defaultValue={toUnits(item.spacing_mm).toFixed(units === "in" ? 3 : 1)}
              key={`${item.id}-sp-${item.spacing_mm}-${units}`}
              onBlur={(e) => {
                if (e.target.value === e.target.defaultValue) return;
                const v = fromUnits(Number(e.target.value));
                if (!e.target.value.trim() || !Number.isFinite(v)) e.target.value = e.target.defaultValue;
                else if (v !== item.spacing_mm) setText(item.id, { spacing_mm: v });
              }}
              onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
            />
            <small>{units}</small>
          </label>
        </div>
        <button className="wide" onClick={() => useStore.getState().setDialog("names")} title="Save one machine file per name, from a list">
          One file per name…
        </button>
        <p className="hint">To put the text on a line of your own: draw a Line, select it and the text (Shift+click), then ⋯ → Put the text on the line.</p>
        {!stitchFont && (
          <button className="wide" onClick={() => void saveStitchFont(item.font, item.style)} title="Turn this font into a LUDD stitch font (.luddfont) you can fine-tune; it's added to your font list">
            Save this font as a stitch font
          </button>
        )}
      </Sub>
      <ThreadPicker index={picking ? -1 : null} onClose={() => setPicking(false)} onPick={(t: Thread) => setText(item.id, { thread: t, threads: [] })} current={sewn} />
    </Section>
  );
}
