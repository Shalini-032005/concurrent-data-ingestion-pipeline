import { ChevronLeft, ChevronRight } from "lucide-react";
import { EmptyState } from "./EmptyState";
import { formatTime, formatValue } from "../utils/formatters";
import type { PaginatedRecords } from "../types/dashboard";

interface RecordsTableProps {
  data: PaginatedRecords | null;
  onPageChange: (page: number) => void;
}

export function RecordsTable({ data, onPageChange }: RecordsTableProps) {
  if (!data || data.records.length === 0) {
    return <EmptyState message="No records available yet." />;
  }

  const { page, page_size, total, records } = data;
  const totalPages = Math.max(1, Math.ceil(total / page_size));
  const rangeStart = (page - 1) * page_size + 1;
  const rangeEnd = Math.min(total, page * page_size);

  return (
    <>
      <div className="scroll-x">
        <table className="data-table">
          <thead>
            <tr>
              <th>Record ID</th>
              <th>Name</th>
              <th>Email</th>
              <th>Value</th>
              <th>Source</th>
              <th>Created</th>
              <th>Ingested</th>
            </tr>
          </thead>
          <tbody>
            {records.map((record) => (
              <tr key={record.record_id}>
                <td className="mono">{record.record_id}</td>
                <td>{record.name ?? "—"}</td>
                <td>{record.email ?? "—"}</td>
                <td className="num">{formatValue(record.value)}</td>
                <td>{record.source}</td>
                <td className="mono">{formatTime(record.created_at)}</td>
                <td className="mono">{formatTime(record.ingested_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="pagination">
        <span>
          {rangeStart}–{rangeEnd} of {total}
        </span>
        <div className="pagination-controls">
          <button
            type="button"
            className="pagination-btn"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            aria-label="Previous page"
          >
            <ChevronLeft size={14} />
          </button>
          <span className="mono">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            className="pagination-btn"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            aria-label="Next page"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </>
  );
}
