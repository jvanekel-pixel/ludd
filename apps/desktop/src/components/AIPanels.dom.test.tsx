// @vitest-environment jsdom
/**
 * The first panel test that runs in a browser-like page (jsdom; QA decision 19). Name files
 * `*.dom.test.tsx` and keep that first line to get one: every other test stays in plain Node.
 */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import type { AIEstimate } from "../ai";
import { useStore } from "../store";
import { SendPreview } from "./AIPanels";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const estimate: AIEstimate = {
  provider: "anthropic",
  model: "a-model",
  cloud: true,
  host: "api.anthropic.com",
  instructions: "You are an expert machine-embroidery digitizer.",
  text: "One satin column, 4 mm wide.",
  images: [],
  tokens_in: 1200,
  tokens_out_max: 1500,
  cost_usd_max: null,
};

let root: Root | null = null;
let host: HTMLElement | null = null;

beforeAll(() => {
  // jsdom has no <dialog> opening yet; give it the two calls LUDD makes.
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) {
    this.removeAttribute("open");
  };
});

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
  useStore.setState({ aiPreview: null });
});

function show() {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<SendPreview />));
}

describe("AI send preview (a panel, in jsdom)", () => {
  it("shows where it goes, the text, and LUDD's fixed instructions", () => {
    show();
    act(() => useStore.getState().setAIPreview({ estimate, resolve: () => undefined }));
    const d = host!.querySelector("dialog")!;
    expect(d.open).toBe(true);
    expect(d.querySelector("h2")!.textContent).toContain("api.anthropic.com");
    const texts = [...d.querySelectorAll("pre.send-text")].map((p) => p.textContent);
    expect(texts).toEqual(["One satin column, 4 mm wide.", "You are an expert machine-embroidery digitizer."]);
  });

  it("answers Send or Cancel and closes", () => {
    show();
    const answers: boolean[] = [];
    act(() => useStore.getState().setAIPreview({ estimate, resolve: (send) => answers.push(send) }));
    const send = [...host!.querySelectorAll("button")].find((b) => b.textContent === "Send")!;
    act(() => send.click());
    expect(answers).toEqual([true]);
    expect(useStore.getState().aiPreview).toBeNull();
  });
});
