import { useEffect, useMemo, useRef, useState } from "react";
import { command, loadFonts, saveStitchFont, setText } from "../actions";
import { formatShortcut } from "../commands";
import { holdEscape } from "../escape";
import { MM_PER_IN } from "../design/grid";
import type { FontInfo, LayoutItemInfo, TextItem, TextShape, Thread } from "../design/types";
import { useStore } from "../store";
import { ThreadPicker } from "./ThreadDialogs";

const SHAPES: { type: TextShape["type"]; label: string; title: string }[] = [
  { type: "line", label: "Straight", title: "Letters on a straight line" },
  { type: "arc_up", label: "Arch", title: "Letters curve over the top of a circle" },
  { type: "arc_down", label: "Smile", title: "Letters curve under the bottom of a circle" },
  { type: "circle", label: "Circle", title: "Letters all the way round a circle" },
];

const TYPE_DELAY_MS = 450;

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
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    const release = holdEscape(() => setOpen(false));
    window.addEventListener("pointerdown", onDown);
    return () => {
      window.removeEventListener("pointerdown", onDown);
      release();
    };
  }, [open]);
  const list = useMemo(() => {
    const q = query.trim().toLowerCase();
    const all = fonts ?? [];
    return (q ? all.filter((f) => `${f.family} ${f.style}`.toLowerCase().includes(q)) : all).slice(0, 200);
  }, [fonts, query]);
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
        </div>
      )}
    </div>
  );
}

/** Lettering: what it says, its font and size, satin look or fill, and the shape it follows. */
export function SelectedText({ item, info }: { item: TextItem; info: LayoutItemInfo }) {
  const units = useStore((s) => s.units);
  const [draft, setDraft] = useState(item.text);
  const [picking, setPicking] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const reverting = useRef(false);

  useEffect(() => setDraft(item.text), [item.text]);
  useEffect(() => {
    const onEdit = (e: Event) => {
      if ((e as CustomEvent).detail === item.id) {
        input.current?.focus();
        input.current?.select();
      }
    };
    window.addEventListener("ludd:edit-text", onEdit);
    return () => window.removeEventListener("ludd:edit-text", onEdit);
  }, [item.id]);

  const commitText = (t: string) => {
    clearTimeout(timer.current);
    if (t.trim() && t !== item.text) setText(item.id, { text: t });
  };
  const toUnits = (mm: number) => (units === "in" ? mm / MM_PER_IN : mm);
  const fromUnits = (v: number) => (units === "in" ? v * MM_PER_IN : v);
  const curved = item.shape.type !== "line";

  return (
    <section className="selected">
      <h3>{info.name}</h3>
      <label className="text-field">
        <span>{item.monogram ? "Three initials" : "Text"}</span>
        <input
          ref={input}
          value={draft}
          maxLength={item.monogram ? 3 : 200}
          onChange={(e) => {
            setDraft(e.target.value);
            clearTimeout(timer.current);
            const v = e.target.value;
            // Typing updates the stitches after a short pause, not on every key.
            timer.current = setTimeout(() => commitText(v), TYPE_DELAY_MS);
          }}
          onBlur={() => {
            if (reverting.current) reverting.current = false;
            else commitText(draft);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
            if (e.key === "Escape") {
              // Esc lets go of the edit: the text goes back to what it was.
              clearTimeout(timer.current);
              reverting.current = true;
              setDraft(item.text);
            }
          }}
        />
      </label>
      <FontPicker value={item.font} onPick={(f) => setText(item.id, { font: { path: f.path, index: f.index, family: f.family, style: f.style } })} />

      <div className="size-row">
        <label className="num-field">
          <span>Letter height</span>
          <input
            type="number"
            step={units === "in" ? 0.05 : 1}
            defaultValue={toUnits(item.size_mm).toFixed(2)}
            key={`${item.id}-${item.size_mm}-${units}`}
            onBlur={(e) => {
              if (e.target.value === e.target.defaultValue) return; // unchanged: clicking in and out does nothing
              const v = fromUnits(Number(e.target.value));
              if (Number.isFinite(v) && v > 0) setText(item.id, { size_mm: v });
            }}
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
          />
          <small>{units} (capitals)</small>
        </label>
      </div>

      <button className="thread-button" onClick={() => setPicking(true)} title="Change thread">
        <span className="swatch" style={{ background: item.thread.color }} />
        <span className="tname">
          {item.thread.name || item.thread.color}
          <small>{[item.thread.brand, item.thread.catalog].filter(Boolean).join(" ") || "Click to choose a thread"}</small>
        </span>
      </button>

      <div className="seg" role="group" aria-label="Stitch look">
        <button aria-pressed={item.style === "satin"} onClick={() => setText(item.id, { style: "satin" })} title="Smooth, shiny stitches across each stroke: best for names and small text">
          Satin look
        </button>
        <button aria-pressed={item.style === "fill"} onClick={() => setText(item.id, { style: "fill" })} title="Woven fill: best for big, bold letters">
          Fill
        </button>
      </div>

      {!item.monogram && (
        <div className="seg" role="group" aria-label="Shape">
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
      <label className="check">
        <input type="checkbox" checked={item.monogram} onChange={(e) => setText(item.id, { monogram: e.target.checked, text: e.target.checked ? (item.text.replace(/\s/g, "").slice(0, 3).padEnd(3, "A")) : item.text })} />
        Monogram (three letters, big middle initial)
      </label>

      <div className="btn-row">
        <Cmd id="arrange.rotateCcw" label="⟲ 90°" />
        <Cmd id="arrange.rotateCw" label="⟳ 90°" />
        <Cmd id="arrange.duplicate" label="Duplicate" />
        <Cmd id="arrange.repeat" label="Repeat…" />
      </div>

      <details className="more">
        <summary>More options</summary>
        <div className="size-row">
          <label className="num-field">
            <span>Extra letter spacing</span>
            <input
              type="number"
              step={0.1}
              defaultValue={item.spacing_mm.toFixed(1)}
              key={`${item.id}-sp-${item.spacing_mm}`}
              onBlur={(e) => {
                if (e.target.value === e.target.defaultValue) return;
                const v = Number(e.target.value);
                if (Number.isFinite(v) && v !== item.spacing_mm) setText(item.id, { spacing_mm: v });
              }}
              onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
            />
            <small>mm</small>
          </label>
        </div>
        <button className="wide" onClick={() => void saveStitchFont(item.font, item.style)} title="Turn this font into an editable LUDD stitch font (.luddfont)">
          Save this font as a stitch font…
        </button>
        <div className="btn-row">
          <Cmd id="arrange.delete" label="Remove" />
        </div>
      </details>
      <ThreadPicker index={picking ? -1 : null} onClose={() => setPicking(false)} onPick={(t: Thread) => setText(item.id, { thread: t })} current={item.thread} />
    </section>
  );
}

function Cmd({ id, label }: { id: string; label: string }) {
  const c = command(id);
  return (
    <button onClick={c.run} title={`${c.title} (${formatShortcut(c.shortcut)})`} aria-label={c.title}>
      {label}
    </button>
  );
}
