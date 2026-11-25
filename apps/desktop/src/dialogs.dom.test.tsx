// @vitest-environment jsdom
import { act, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";
import { DialogHost, registerDialog } from "./dialogs";
import { useStore } from "./store";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("the dialog registry", () => {
  it("a registered dialog mounts only while open", () => {
    let mounted = 0;
    let unmounted = 0;
    function Probe() {
      useEffect(() => {
        mounted++;
        return () => void unmounted++;
      }, []);
      return <p>probe dialog</p>;
    }
    registerDialog("test.probe", Probe);
    const host = document.createElement("div");
    document.body.append(host);
    const root = createRoot(host);
    act(() => root.render(<DialogHost />));
    expect([host.textContent, mounted]).toEqual(["", 0]);
    act(() => useStore.getState().setDialog("test.probe"));
    expect([host.textContent, mounted, unmounted]).toEqual(["probe dialog", 1, 0]);
    act(() => useStore.getState().setDialog(null));
    expect([host.textContent, mounted, unmounted]).toEqual(["", 1, 1]);
    // A dialog nothing registered (the built-in ones show themselves): nothing from the host.
    act(() => useStore.getState().setDialog("offset"));
    expect([host.textContent, mounted]).toEqual(["", 1]);
    act(() => useStore.getState().setDialog(null));
    act(() => root.unmount());
    host.remove();
  });
});
