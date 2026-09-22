type Tone = "green" | "red" | "orange" | "cyan" | "neutral";

const TONE_BY_STATUS: Record<string, Tone> = {
  HEALTHY: "green",
  SUCCESS: "green",
  COMPLETED: "green",
  DEGRADED: "orange",
  PARTIAL: "orange",
  DOWN: "red",
  FAILED: "red",
  TIMEOUT: "red",
  RUNNING: "cyan",
  UNKNOWN: "neutral",
};

interface StatusBadgeProps {
  status: string;
  label?: string;
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const tone = TONE_BY_STATUS[status] ?? "neutral";
  return (
    <span className={`status-badge tone-${tone}`}>
      <span className="dot" aria-hidden="true" />
      {label ?? status}
    </span>
  );
}
