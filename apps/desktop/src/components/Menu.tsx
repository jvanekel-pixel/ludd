import { useEffect, useRef, useState, type ReactNode } from "react";
import { command } from "../actions";
import { formatShortcut } from "../commands";
import { holdEscape } from "../escape";
import { useStore } from "../store";

export type MenuItem = { id: string; label?: string; checked?: boolean } | "separator";

/** A "⋯" button with a dropdown of commands, each showing its shortcut. */
/** A menu button and its list. `side`: the list pops out to the right of the button (for the
 *  tool rail), placed against the window so a narrow, scrolling bar can't cut it off. */
export function Menu({ items, label = "More", trigger, className, side }: { items: MenuItem[]; label?: string; trigger?: ReactNode; className?: string; side?: "right" }) {
  const [open, setOpen] = useState(false);
  const [at, setAt] = useState<{ left: number; top: number } | null>(null);
  const root = useRef<HTMLDivElement>(null);
  // Re-render when state that commands depend on changes.
  useStore((s) => s.engine);
  useStore((s) => s.design);
  useStore((s) => s.history);
  useStore((s) => s.selectedId);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (root.current?.contains(e.target as Node)) return;
      setOpen(false);
      // A click on the design that closes the menu only closes it: it doesn't also draw or select.
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

  return (
    <div className="menu" ref={root}>
      <button
        className={className}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={(e) => {
          if (side === "right") {
            const r = e.currentTarget.getBoundingClientRect();
            // Beside the button (past the bar it sits in), kept on screen at the bottom.
            const bar = e.currentTarget.closest(".tool-rail")?.getBoundingClientRect();
            setAt({ left: (bar?.right ?? r.right) + 6, top: Math.max(8, Math.min(r.top, window.innerHeight - 40 - items.length * 38)) });
          }
          setOpen(!open);
        }}
        title={label}
        aria-label={label}
      >
        {trigger ?? "⋯"}
      </button>
      {open && (
        <ul role="menu" className={`menu-list${side === "right" ? " pop-right" : ""}`} style={side === "right" && at ? { position: "fixed", left: at.left, top: at.top, right: "auto" } : undefined}>
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
