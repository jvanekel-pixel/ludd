/**
 * Light and dark mode. "system" follows the computer's setting (and changes with it);
 * "light" and "dark" stick. The choice is kept in preferences and set in Settings.
 */
import { getCurrentWindow } from "@tauri-apps/api/window";
import { isTauri } from "./engine/sidecar";

export type ThemeChoice = "system" | "light" | "dark";

const darkQuery = () => (typeof matchMedia === "function" ? matchMedia("(prefers-color-scheme: dark)") : null);

/** What the screen actually shows for a choice. */
export function resolveTheme(choice: ThemeChoice, systemDark = darkQuery()?.matches ?? false): "light" | "dark" {
  return choice === "system" ? (systemDark ? "dark" : "light") : choice;
}

export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
  // The window frame (title bar) follows too; null means "follow the system".
  if (isTauri()) void getCurrentWindow().setTheme(choice === "system" ? null : choice).catch(() => {});
  window.dispatchEvent(new Event("ludd:theme"));
}
