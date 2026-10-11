import { useState } from "react";
import { loadPrefs, savePrefs } from "../prefs";

/** A panel section that folds away when you click its heading; remembered between sessions. */
export function useFold(id: string, openByDefault = true): [boolean, () => void] {
  const [open, setOpen] = useState(() => loadPrefs().folds?.[id] ?? openByDefault);
  const toggle = () => {
    const next = !open;
    setOpen(next);
    savePrefs({ folds: { ...(loadPrefs().folds ?? {}), [id]: next } });
  };
  return [open, toggle];
}

/** The clickable heading of a folding section. */
export function FoldTitle({ open, onToggle, children }: { open: boolean; onToggle: () => void; children: React.ReactNode }) {
  return (
    <h3 className="fold-title">
      <button className="fold-button" aria-expanded={open} onClick={onToggle} title={open ? "Fold away" : "Show"}>
        <span className="caret" aria-hidden>
          {open ? "▾" : "▸"}
        </span>
        {children}
      </button>
    </h3>
  );
}
