// PixiJS normally builds its drawing code with new Function, which the installed app's security
// policy (no 'unsafe-eval') blocks, leaving the design area blank. This add-on makes PixiJS work
// without it, so the policy can stay strict. It must load before PixiJS draws anything.
import "pixi.js/unsafe-eval";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "@fontsource-variable/archivo/wdth.css";
import "@fontsource/space-mono/400.css";
import "./styles.css";
import * as actions from "./actions";
import { loadPrefs } from "./prefs";
import { applyTheme } from "./theme";

applyTheme(loadPrefs().theme ?? "system");

// Dev-only handle for driving the app from the browser console and tests.
if (import.meta.env.DEV) (window as unknown as { __actions: typeof actions }).__actions = actions;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
