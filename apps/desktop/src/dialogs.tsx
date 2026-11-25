/**
 * Feature dialogs: register a component under an id, open it with setDialog(id). <DialogHost />
 * mounts it only while it's open, so it starts fresh each time (it shows itself as a modal, for
 * example with useModal(true), and closes with setDialog(null)).
 */
import type { ComponentType } from "react";
import { useStore } from "./store";

const dialogs = new Map<string, ComponentType>();

export function registerDialog(id: string, C: ComponentType): void {
  dialogs.set(id, C);
}

export function DialogHost() {
  const id = useStore((s) => s.dialog);
  const C = id === null ? undefined : dialogs.get(id);
  return C ? <C key={id} /> : null;
}
