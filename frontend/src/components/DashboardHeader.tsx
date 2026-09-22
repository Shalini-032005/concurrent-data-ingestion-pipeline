import { Play, RefreshCw } from "lucide-react";
import type { WsStatus } from "../services/websocket";
import { LiveIndicator } from "./LiveIndicator";

interface DashboardHeaderProps {
  wsStatus: WsStatus;
  onRefresh: () => void;
  refreshing: boolean;
  onRunIngestion: () => void;
  ingestionRunning: boolean;
  ingestionAvailable: boolean;
}

function BrandMark() {
  return (
    <svg
      className="header-mark"
      viewBox="0 0 34 34"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <rect x="0.5" y="0.5" width="33" height="33" rx="6.5" stroke="var(--border)" />
      <circle cx="8" cy="9" r="2" fill="var(--accent-amber)" />
      <circle cx="8" cy="17" r="2" fill="var(--accent-cyan)" />
      <circle cx="8" cy="25" r="2" fill="var(--accent-green)" />
      <path
        d="M10 9 H16 L24 17 H27"
        stroke="var(--accent-amber)"
        strokeWidth="1.4"
        strokeLinecap="round"
        fill="none"
        opacity="0.85"
      />
      <path
        d="M10 17 H24"
        stroke="var(--accent-cyan)"
        strokeWidth="1.4"
        strokeLinecap="round"
        fill="none"
        opacity="0.85"
      />
      <path
        d="M10 25 H16 L24 17 H27"
        stroke="var(--accent-green)"
        strokeWidth="1.4"
        strokeLinecap="round"
        fill="none"
        opacity="0.85"
      />
      <circle cx="27" cy="17" r="2.2" fill="var(--text-primary)" />
    </svg>
  );
}

export function DashboardHeader({
  wsStatus,
  onRefresh,
  refreshing,
  onRunIngestion,
  ingestionRunning,
  ingestionAvailable,
}: DashboardHeaderProps) {
  return (
    <header className="header">
      <div className="header-brand">
        <BrandMark />
        <div className="header-titles">
          <h1>Concurrent Data Ingestion</h1>
          <p>Real-time monitoring of multi-source data pipelines</p>
        </div>
      </div>

      <div className="header-actions">
        <LiveIndicator status={wsStatus} />
        <button
          type="button"
          className="btn"
          onClick={onRefresh}
          disabled={refreshing}
          aria-label="Refresh dashboard data"
        >
          <RefreshCw size={14} className={refreshing ? "spin" : undefined} />
          Refresh
        </button>
        {ingestionAvailable && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={onRunIngestion}
            disabled={ingestionRunning}
            aria-label="Run a new ingestion"
          >
            <Play size={14} />
            {ingestionRunning ? "Running…" : "Run Ingestion"}
          </button>
        )}
      </div>
    </header>
  );
}
