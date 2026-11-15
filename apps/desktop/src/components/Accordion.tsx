/**
 * The right panel's folding sections (two levels at most, never tabs inside them).
 *
 * - A Section is open or closed per kind of selection ("fill", "picture", nothing selected…), and
 *   remembered between sessions. The defaults open what you just clicked on: select a fill and its
 *   section opens; select nothing and Design and Order & colors open. Once you close a section for that
 *   kind of selection, it stays closed for it.
 * - Folded headings show a one-line summary ("Fill · Normal · 45°"), so you rarely need to open one
 *   just to see what's inside.
 * - Ctrl+click a heading to open only that section; Alt+click to open or close all its parts.
 * - A Sub is a smaller fold inside a Section (Underlay, Advanced…), remembered on its own.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { loadPrefs, savePrefs } from "../prefs";

export type SelKind = "none" | "run" | "satin" | "fill" | "applique" | "text" | "file" | "picture" | "multi";

const EVENT = "ludd:sections";
const mounted = new Set<string>();

function read(key: string, fallback: boolean): boolean {
  return loadPrefs().sections?.[key] ?? fallback;
}

function write(entries: Record<string, boolean>) {
  savePrefs({ sections: { ...(loadPrefs().sections ?? {}), ...entries } });
  window.dispatchEvent(new Event(EVENT));
}

/** Open state for `key`, kept in step when another heading changes it (Ctrl+click, Alt+click). */
function useOpen(key: string, fallback: boolean): [boolean, (v: boolean) => void] {
  const [open, setOpen] = useState(() => read(key, fallback));
  useEffect(() => setOpen(read(key, fallback)), [key, fallback]);
  useEffect(() => {
    const sync = () => setOpen(read(key, fallback));
    window.addEventListener(EVENT, sync);
    return () => window.removeEventListener(EVENT, sync);
  }, [key, fallback]);
  return [open, (v) => write({ [key]: v })];
}

export function Section({
  id,
  sel,
  title,
  summary,
  badge,
  actions,
  defaultOpen = false,
  shared = false,
  children,
}: {
  id: string;
  /** Open or closed the same whatever is selected (a list you pick things from). */
  shared?: boolean;
  /** What's selected: each section remembers being open or closed per kind of selection. */
  sel: SelKind;
  title: ReactNode;
  summary?: ReactNode;
  badge?: ReactNode;
  /** Buttons at the right of the heading (they don't fold the section). */
  actions?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const key = shared ? `${id}@all` : `${id}@${sel}`;
  const [open, setOpen] = useOpen(key, defaultOpen);
  const body = useRef<HTMLDivElement>(null);
  useEffect(() => {
    mounted.add(key);
    return () => void mounted.delete(key);
  }, [key]);
  const toggle = (e: React.MouseEvent) => {
    if (e.ctrlKey || e.metaKey) {
      // Only this one: close every other section on screen.
      const all: Record<string, boolean> = {};
      mounted.forEach((k) => (all[k] = k === key));
      write(all);
      return;
    }
    if (e.altKey) {
      // Open or close all its parts with it.
      const subs: Record<string, boolean> = {};
      body.current?.querySelectorAll<HTMLElement>("[data-sub]").forEach((el) => (subs[el.dataset.sub!] = !open));
      write({ ...subs, [key]: !open });
      return;
    }
    setOpen(!open);
  };
  // Bring a section into view when you open it (not when it appears already open: selecting
  // something shouldn't scroll the panel away from where you clicked).
  const wasOpen = useRef(open);
  useEffect(() => {
    if (open && !wasOpen.current) body.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    wasOpen.current = open;
  }, [open]);
  return (
    <section className={`acc${open ? " open" : ""}`} aria-label={typeof title === "string" ? title : undefined}>
      <div className="acc-head">
        <h3>
          <button aria-expanded={open} aria-controls={`acc-${id}`} onClick={toggle} title={open ? "Fold away (Ctrl+click: only this one)" : "Open (Ctrl+click: only this one)"}>
            <span className="caret" aria-hidden />
            <span className="acc-title">{title}</span>
            {!open && summary ? <span className="acc-summary">{summary}</span> : null}
            {badge ? <span className="acc-badge">{badge}</span> : null}
          </button>
        </h3>
        {actions && <div className="acc-actions">{actions}</div>}
      </div>
      {open && (
        <div className="acc-body" id={`acc-${id}`} ref={body}>
          {children}
        </div>
      )}
    </section>
  );
}

export function Sub({ id, title, summary, defaultOpen = false, children }: { id: string; title: ReactNode; summary?: ReactNode; defaultOpen?: boolean; children: ReactNode }) {
  const key = `sub:${id}`;
  const [open, setOpen] = useOpen(key, defaultOpen);
  return (
    <div className="acc-sub" data-sub={key}>
      <button className="acc-sub-head" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="caret" aria-hidden />
        <span>{title}</span>
        {!open && summary ? <span className="acc-summary">{summary}</span> : null}
      </button>
      {open && <div className="acc-sub-body">{children}</div>}
    </div>
  );
}

/** A label on the left, its control on the right: settings line up in one column. */
export function Row({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <div className="acc-row" title={hint}>
      <span className="acc-label">{label}</span>
      <div className="acc-control">{children}</div>
    </div>
  );
}
