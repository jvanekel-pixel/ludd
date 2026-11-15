import { useStore } from "../store";
import type { EngineStatus } from "../engine/sidecar";
import { restartEngine } from "../engine/manager";

const LABELS: Record<EngineStatus["state"], string> = {
  starting: "Engine starting…",
  connected: "Engine connected",
  disconnected: "Engine disconnected",
  unavailable: "No engine",
};

export function StatusBar() {
  const status = useStore((s) => s.engineStatus);
  const loading = useStore((s) => s.loading);
  const detail =
    status.state === "connected"
      ? `v${status.version} · Python ${status.python}`
      : "reason" in status
        ? status.reason
        : "";
  return (
    <footer className="statusbar" role="status">
      <span className={`dot dot-${status.state}`} aria-hidden />
      <span>{LABELS[status.state]}</span>
      {detail && <span className="detail">{detail}</span>}
      {status.state === "disconnected" && (
        <button className="link" onClick={restartEngine}>
          Restart engine
        </button>
      )}
      {loading && <span className="loading">{loading}</span>}
    </footer>
  );
}
