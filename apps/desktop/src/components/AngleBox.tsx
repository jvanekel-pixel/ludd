/** A fill's stitch direction: its angle, or the lines its rows turn to follow. */
import type { ObjectItem } from "../design/types";
import { Row } from "./Accordion";
import { Cmd, Stepper } from "./controls";

export function AngleBox({ item, set }: { item: ObjectItem; set: (patch: Record<string, unknown>) => void }) {
  const angle = (item.params as { angle_deg?: number }).angle_deg ?? 45;
  return (
    <>
      <Stepper label="Angle" value={Math.round(angle)} step={5} min={0} max={179} digits={0} suffix="°" onCommit={(v) => set({ angle_deg: v })} title="Direction of the rows" />
      <Row label="">
        <Cmd id="object.angle" label="Draw the angle (I)" />
      </Row>
    </>
  );
}
