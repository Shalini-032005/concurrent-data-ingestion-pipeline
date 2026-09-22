import { StatusBadge } from "./StatusBadge";
import { formatRelativeTime } from "../utils/formatters";
import type { SourceStatus } from "../types/dashboard";

interface SourceCardProps {
  source: SourceStatus;
}

export function SourceCard({ source }: SourceCardProps) {
  const duplicates = Math.max(0, source.records_received - source.records_processed);

  return (
    <div className="source-card">
      <div className="source-card-head">
        <span className="source-name">{source.source}</span>
        <StatusBadge status={source.status} />
      </div>

      <div className="source-card-metrics">
        <div className="source-metric">
          <div className="m-label">Received</div>
          <div className="m-value mono">{source.records_received}</div>
        </div>
        <div className="source-metric">
          <div className="m-label">Processed</div>
          <div className="m-value mono">{source.records_processed}</div>
        </div>
        <div className="source-metric">
          <div className="m-label">Duplicates</div>
          <div className="m-value mono">{duplicates}</div>
        </div>
      </div>

      <div className={`source-card-foot${source.status === "DOWN" ? " is-error" : ""}`}>
        {source.status === "DOWN" && source.last_failure
          ? `Last failure ${formatRelativeTime(source.last_failure)}`
          : `Last success ${formatRelativeTime(source.last_success)}`}
      </div>
    </div>
  );
}
