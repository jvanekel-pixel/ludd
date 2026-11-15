import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mayCheckOnStart, updateCheckError } from "./updates";

const store = new Map<string, string>();
beforeEach(() => {
  store.clear();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  });
});
afterEach(() => vi.unstubAllGlobals());

describe("update check (QA tauri)", () => {
  it("waits for the first-run question, and never runs once the user said no", () => {
    expect(mayCheckOnStart()).toBe("later"); // first run: Welcome card not answered yet
    store.set("ludd.prefs", JSON.stringify({ welcomed: true, checkUpdates: false }));
    expect(mayCheckOnStart()).toBe("no");
    store.set("ludd.prefs", JSON.stringify({ welcomed: true, checkUpdates: true }));
    expect(mayCheckOnStart()).toBe("yes");
    store.set("ludd.prefs", JSON.stringify({ welcomed: true })); // on unless turned off
    expect(mayCheckOnStart()).toBe("yes");
  });

  it("says 'check your connection' in plain words when offline", () => {
    const offline = new Error("error sending request for url (https://github.com/jvanekel-pixel/ludd/releases/latest/download/latest.json)");
    expect(updateCheckError(offline)).toBe("Couldn't reach the update server. Check your internet connection and try again.");
    expect(updateCheckError("signature mismatch")).toBe("Couldn't check for updates: signature mismatch");
  });
});
