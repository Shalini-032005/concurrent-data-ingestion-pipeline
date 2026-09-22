import { StatusBadge } from "./StatusBadge";
import { EmptyState } from "./EmptyState";
import { formatDuration, formatNumber, formatTime } from "../utils/formatters";
import type { IngestionRunSummary } from "../types/dashboard";

interface IngestionTableProps {
  runs: IngestionRunSummary[];
}

export function IngestionTable({ runs }: IngestionTableProps) {
  if (runs.length === 0) {
    return <EmptyState message="No ingestion runs yet." />;
  }

  return (
    <div className="scroll-x">
      <table className="data-table">
        <thead>
          <tr>
            <th>Run</th>
            <th>Started</th>
            <th>Duration</th>
            <th>Status</th>
            <th>Received</th>
            <th>Processed</th>
            <th>Duplicates</th>
            <th>Failed</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.run_id}>
              <td className="mono">#{run.run_id}</td>
              <td className="mono">{formatTime(run.started_at)}</td>
              <td className="num">{formatDuration(run.duration_ms)}</td>
              <td>
                <StatusBadge status={run.status} />
              </td>
              <td className="num">{formatNumber(run.total_received)}</td>
              <td className="num">{formatNumber(run.total_processed)}</td>
              <td className="num">{formatNumber(run.total_duplicates)}</td>
              <td className="num">{formatNumber(run.total_failed)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
