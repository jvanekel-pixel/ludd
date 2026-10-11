import { useStore } from "../store";
import type { EngineStatus } from "../engine/sidecar";

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
      {loading && <span className="loading">{loading}</span>}
    </footer>
  );
}
