/**
 * The installed app runs in a web view, which keeps a browser's own keys and right-click menu:
 * F5 reloads (losing the open design without asking), Ctrl+F opens find-in-page, Ctrl+P a print
 * preview, Alt+Left goes "back". A desktop app has none of these, so they're switched off here.
 * The keys still reach LUDD's own shortcuts (only the browser's action is cancelled).
 */
import { stopEngine } from "./engine/manager";
import { isTauri } from "./engine/sidecar";

type KeyLike = Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey" | "shiftKey">;

/** Whether the web view would do something browser-like with this key. */
export function isBrowserKey(e: KeyLike): boolean {
  const mod = e.ctrlKey || e.metaKey;
  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  if (k === "F5" || k === "F3" || k === "F7" || k === "BrowserRefresh" || k === "BrowserBack" || k === "BrowserForward") return true;
  // Reload, find, find next, print, view source, downloads, history.
  if (mod && !e.altKey && ["r", "f", "g", "p", "u", "j", "h"].includes(k)) return true;
  // Back and forward.
  if (e.altKey && !mod && (k === "ArrowLeft" || k === "ArrowRight")) return true;
  return false;
}

/** Text you can type in keeps its own right-click menu (copy, paste). */
function isTextField(t: EventTarget | null): boolean {
  const el = t as Element | null;
  return !!el && typeof el.closest === "function" && !!el.closest("input, textarea, [contenteditable=true]");
}

/** Switch the browser's keys and menu off (installed app only; the browser preview keeps them). */
export function blockBrowserKeys(): () => void {
  if (!isTauri()) return () => {};
  const onKey = (e: KeyboardEvent) => {
    if (isBrowserKey(e)) e.preventDefault();
  };
  const onMenu = (e: MouseEvent) => {
    if (!isTextField(e.target)) e.preventDefault();
  };
  // If the page goes away anyway, don't leave its engine running.
  const onHide = () => stopEngine();
  window.addEventListener("keydown", onKey, true);
  window.addEventListener("contextmenu", onMenu, true);
  window.addEventListener("pagehide", onHide);
  return () => {
    window.removeEventListener("keydown", onKey, true);
    window.removeEventListener("contextmenu", onMenu, true);
    window.removeEventListener("pagehide", onHide);
  };
}
