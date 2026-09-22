import type { WsStatus } from "../services/websocket";

interface LiveIndicatorProps {
  status: WsStatus;
}

const COPY: Record<WsStatus, string> = {
  open: "LIVE",
  connecting: "CONNECTING",
  closed: "DISCONNECTED",
};

export function LiveIndicator({ status }: LiveIndicatorProps) {
  return (
    <span
      className={`live-indicator is-${status === "open" ? "open" : status === "connecting" ? "connecting" : "closed"}`}
      role="status"
      aria-live="polite"
    >
      <span className="dot" aria-hidden="true" />
      {COPY[status]}
    </span>
  );
}
