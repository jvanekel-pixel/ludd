import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { command, currentLayout, selectionIds, setItemsThread, setObjectThread, setText } from "../actions";
import { formatShortcut } from "../commands";
import { closeContextMenu, isLocal, useContextMenu } from "../contextMenu";
import { isObject, isText, type Thread } from "../design/types";
import { holdEscape } from "../escape";
import { useStore } from "../store";
import { ThreadPicker } from "./ThreadDialogs";

/** The right-click menu, at the mouse (kept inside the window). Arrow keys move, Enter picks,
 *  Esc, a click elsewhere, scrolling or leaving the window closes it. */
export function ContextMenu() {
  const menu = useContextMenu((s) => s.menu);
  const list = useRef<HTMLUListElement>(null);
  const [at, setAt] = useState<{ left: number; top: number } | null>(null);
  // Re-render when what the commands depend on changes.
  useStore((s) => s.history);
  useStore((s) => s.selectedId);
  useStore((s) => s.extraIds);

  useLayoutEffect(() => {
    if (!menu || !list.current) return setAt(null);
    const r = list.current.getBoundingClientRect();
    setAt({
      left: Math.max(4, Math.min(menu.x, window.innerWidth - r.width - 4)),
      top: Math.max(4, Math.min(menu.y, window.innerHeight - r.height - 4)),
    });
    list.current.querySelector<HTMLButtonElement>("button:not(:disabled)")?.focus({ preventScroll: true });
  }, [menu]);

  useEffect(() => {
    if (!menu) return;
    const onDown = (e: PointerEvent) => {
      if (list.current?.contains(e.target as Node)) return;
      closeContextMenu();
      // A click on the design that closes the menu only closes it (a right-click opens the next one).
      if (e.button === 0 && e.target instanceof Element && e.target.closest(".stitch-canvas")) e.stopPropagation();
    };
    const release = holdEscape(closeContextMenu);
    const close = () => closeContextMenu();
    // Scrolling the menu itself (a long one in a short window) doesn't close it.
    const onWheel = (e: WheelEvent) => {
      if (!list.current?.contains(e.target as Node)) closeContextMenu();
    };
    window.addEventListener("pointerdown", onDown, true);
    window.addEventListener("blur", close);
    window.addEventListener("resize", close);
    window.addEventListener("wheel", onWheel, { passive: true });
    return () => {
      window.removeEventListener("pointerdown", onDown, true);
      window.removeEventListener("blur", close);
      window.removeEventListener("resize", close);
      window.removeEventListener("wheel", onWheel);
      release();
    };
  }, [menu]);

  const onKey = (e: React.KeyboardEvent) => {
    if (!menu) return;
    const buttons = [...(list.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? [])];
    const i = buttons.indexOf(document.activeElement as HTMLButtonElement);
    const go = (k: number) => buttons[(k + buttons.length) % buttons.length]?.focus();
    if (e.key === "ArrowDown") go(i + 1);
    else if (e.key === "ArrowUp") go(i < 0 ? -1 : i - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(-1);
    else if (e.key === "Tab") closeContextMenu();
    else return;
    e.preventDefault();
    e.stopPropagation();
  };

  // The thread picker stays in the same place in the tree whether a menu is open or not, so
  // opening or closing a menu never resets a picker that's open.
  return (
    <>
      {menu && (
      <ul
        ref={list}
        role="menu"
        aria-label={menu.title ?? "Menu"}
        className="menu-list context-menu"
        style={{ position: "fixed", left: at?.left ?? menu.x, top: at?.top ?? menu.y, right: "auto", visibility: at ? "visible" : "hidden" }}
        onKeyDown={onKey}
        onContextMenu={(e) => e.preventDefault()}
      >
        {menu.title && (
          <li role="presentation" className="context-title">
            {menu.title}
          </li>
        )}
        {menu.items.map((item, i) => {
          if (item === "separator") return <li key={i} role="separator" />;
          if (isLocal(item)) {
            return (
              <li key={i} role="none">
                <button
                  role="menuitem"
                  disabled={item.enabled === false}
                  title={item.hint}
                  onClick={() => {
                    closeContextMenu();
                    item.run();
                  }}
                >
                  <span className="check-mark" aria-hidden />
                  <span className="label">{item.label}</span>
                  <kbd />
                </button>
              </li>
            );
          }
          const cmd = command(item.id);
          const enabled = cmd.enabled ? cmd.enabled() : true;
          return (
            <li key={i} role="none">
              <button
                role={item.checked === undefined ? "menuitem" : "menuitemcheckbox"}
                aria-checked={item.checked}
                disabled={!enabled}
                onClick={() => {
                  closeContextMenu();
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
      <ThreadFor />
    </>
  );
}

/** "Change thread…" from a right-click or Alt+T, for a drawn shape or text. */
function ThreadFor() {
  const id = useContextMenu((s) => s.threadFor);
  const design = useStore((s) => s.design);
  const layout = currentLayout();
  const i = layout && id ? layout.items.findIndex((it) => it.id === id) : -1;
  const item = i >= 0 ? layout!.items[i] : undefined;
  // The thread it's sewn in, as Order & colors shows it (a color changed there wins).
  const block = design?.blocks.find((b) => b.sources?.some((src) => src.item === i));
  const current: Thread | undefined = block && design ? design.threads[block.thread] : item && (isObject(item) || isText(item)) ? (item.threads?.[0] ?? item.thread) : undefined;
  const close = () => useContextMenu.setState({ threadFor: null });
  return (
    <ThreadPicker
      index={item && current ? -1 : null}
      onClose={close}
      current={current}
      onPick={(t) => {
        if (!item) return;
        // Several selected: the same thread for all of them.
        const ids = selectionIds();
        if (ids.length > 1 && ids.includes(item.id)) setItemsThread(ids, t);
        else if (isObject(item)) setObjectThread(item.id, t);
        else if (isText(item)) setText(item.id, { thread: t, threads: [] });
      }}
    />
  );
}
