/** A fill's stitch direction: its angle, or the lines its rows turn to follow. */
import type { ObjectItem } from "../design/types";
import { angleLines, canTurn, oneAngleAgain, startAddAngle } from "../feat/angleLines";
import { Row } from "./Accordion";
import { Cmd, Stepper } from "./controls";

/** Shift+I's button (object.addAngle): draw another line for the rows to follow. */
function AddLine() {
  return (
    <button onClick={() => startAddAngle()} title="Draw another line: the rows turn to follow each line where it lies (Shift+I)">
      Add another line (Shift+I)
    </button>
  );
}

export function AngleBox({ item, set }: { item: ObjectItem; set: (patch: Record<string, unknown>) => void }) {
  const angle = (item.params as { angle_deg?: number }).angle_deg ?? 45;
  const lines = angleLines(item);
  const turns = canTurn(item);
  if (lines.length >= 2) {
    return (
      <>
        <Row label="Angle" hint="The rows turn to follow each line where it lies. Drag a line's purple dots to move it; right-click a line to remove it.">
          <span className="angle-lines">Follows {lines.length} lines</span>
        </Row>
        <Row label="">
          <button onClick={() => oneAngleAgain(item.id)} title="Keep the first line's angle and remove the others">
            Back to one angle
          </button>
          {turns && <AddLine />}
        </Row>
      </>
    );
  }
  return (
    <>
      <Stepper label="Angle" value={Math.round(angle)} step={5} min={0} max={179} digits={0} suffix="°" onCommit={(v) => set({ angle_deg: v })} title="Direction of the rows" />
      <Row label="">
        <Cmd id="object.angle" label="Draw the angle (I)" />
        {turns && <AddLine />}
      </Row>
    </>
  );
}
