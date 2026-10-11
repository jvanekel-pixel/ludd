import { useEffect, useRef, useState } from "react";
import { command } from "../actions";
import { formatShortcut } from "../commands";
import { holdEscape } from "../escape";
import { useStore } from "../store";

export type MenuItem = { id: string; label?: string; checked?: boolean } | "separator";

/** A "⋯" button with a dropdown of commands, each showing its shortcut. */
export function Menu({ items, label = "More" }: { items: MenuItem[]; label?: string }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  // Re-render when state that commands depend on changes.
  useStore((s) => s.engine);
  useStore((s) => s.design);
  useStore((s) => s.history);
  useStore((s) => s.selectedId);

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

  return (
    <div className="menu" ref={root}>
      <button aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)} title={label} aria-label={label}>
        ⋯
      </button>
      {open && (
        <ul role="menu" className="menu-list">
          {items.map((item, i) => {
            if (item === "separator") return <li key={i} role="separator" />;
            const cmd = command(item.id);
            const enabled = cmd.enabled ? cmd.enabled() : true;
            return (
              <li key={item.id} role="none">
                <button
                  role={item.checked === undefined ? "menuitem" : "menuitemcheckbox"}
                  aria-checked={item.checked}
                  disabled={!enabled}
                  onClick={() => {
                    setOpen(false);
                    cmd.run();
                  }}
                >
                  <span className="check-mark" aria-hidden>
                    {item.checked ? "✓" : ""}
                  </span>
                  <span className="label">{item.label ?? cmd.title}</span>
                  <kbd>{formatShortcut(cmd.shortcut)}</kbd>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
