/**
 * Remove stitches of a placed stitch file hidden under what is sewn on top of it (P4-A1).
 *
 * Held until the owner has had the patent checked (the Phase 4 spec's owner decision 1), so it
 * isn't built: the dialog leaves its step out and the command says it isn't built yet.
 */
import { info } from "../../actions";
import { registerRepairStep } from "./steps";

registerRepairStep({
  id: "remove_hidden",
  op: "remove_hidden",
  label: "Remove stitches hidden under what's on top",
  hint: "Not built yet.",
  visible: () => false,
  preset: () => false,
  make: () => ({ op: "remove_hidden" }),
  fields: [],
  summary: () => "",
});

export const removeHidden = (): void => info("Not built yet");
