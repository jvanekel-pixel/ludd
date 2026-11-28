// @vitest-environment jsdom
/** The Import artwork dialog's limits: a PDF that claims a great many pages gets a list of at most
 *  2,000, and if the engine never answers, the dialog says what to do in plain words. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { whenIdle } from "../actions";
import "../cmd";
import { newDoc } from "../design/layout";
import { DialogHost } from "../dialogs";
import { RpcClient } from "../engine/rpc";
import { letGoNewest } from "../escape";
import { importArtwork, NO_ANSWER, PREVIEW_MS, type ArtPreview } from "../feat/importArt";
import { useStore } from "../store";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.open) return;
    this.open = false;
    this.dispatchEvent(new Event("close"));
  };
});

/** The app's own JSON-RPC client, with an engine behind it that answers only when a test says so. */
let sent: { id: number; method: string }[] = [];
let client: RpcClient;
const answer = (reply: object) => client.feed(`${JSON.stringify({ jsonrpc: "2.0", id: sent.at(-1)!.id, ...reply })}\n`);

let root: Root | null = null;
let host: HTMLElement | null = null;

beforeEach(async () => {
  await whenIdle();
  while (letGoNewest());
  localStorage.clear();
  sent = [];
  client = new RpcClient(async (line) => void sent.push(JSON.parse(line)));
  const doc = newDoc();
  useStore.setState({ engine: client as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, design: null, selectedId: null, extraIds: [], dialog: null, tool: "select", pen: null, notice: null, charts: [], units: "mm", machines: [], hoopId: null });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<DialogHost />));
});

afterEach(() => {
  vi.useRealTimers();
  act(() => useStore.getState().setDialog(null));
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
});

const dialog = () => document.querySelector<HTMLDialogElement>("dialog.import-art")!;
const add = () => [...dialog().querySelectorAll("button")].find((b) => b.textContent === "Add") as HTMLButtonElement;

async function open(path: string) {
  await act(async () => {
    void importArtwork(path);
    await Promise.resolve();
  });
}

const preview = (pages: number): ArtPreview => ({ size_mm: [20, 20], scale_note: null, shapes: [{ kind: "run", geometry: { nodes: [[0, 0, "c"], [10, 0, "c"]] }, color: "#000000", name: "" }], skipped: [], warnings: [], pages });

describe("the Import artwork dialog's limits", () => {
  it("offers at most 2,000 pages, whatever a PDF claims", async () => {
    await open("C:\\art\\many.pdf");
    await act(async () => answer({ result: preview(5000) }));
    const list = dialog().querySelector("select")!;
    expect(list.options).toHaveLength(2000);
    expect(list.options[1999].textContent).toBe("2000 of 5000");
  });

  it("if the engine never answers, says what to do in plain words", async () => {
    vi.useFakeTimers();
    await open("C:\\art\\slow.pdf");
    expect(sent.map((s) => s.method)).toEqual(["art.preview"]);
    await act(() => vi.advanceTimersByTimeAsync(PREVIEW_MS - 1));
    expect(dialog().textContent).toContain("Reading the drawing");
    await act(() => vi.advanceTimersByTimeAsync(1));
    expect(dialog().querySelector('[role="alert"]')!.textContent).toBe(NO_ANSWER);
    expect(dialog().textContent).not.toContain("did not answer");
    expect(dialog().textContent).not.toContain(`${PREVIEW_MS} ms`);
    expect(add().disabled).toBe(true);
  });

  it("shows the engine's own refusals as they are", async () => {
    await open("C:\\art\\bad.svg");
    await act(async () => answer({ error: { code: -32000, message: "This SVG has far more points than LUDD imports." } }));
    expect(dialog().querySelector('[role="alert"]')!.textContent).toBe("This SVG has far more points than LUDD imports.");
  });
});
