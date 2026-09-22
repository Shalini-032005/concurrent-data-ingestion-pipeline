import { CheckCircle2, Copy, Inbox, XCircle, Clock, Activity, ShieldCheck, HeartPulse } from "lucide-react";
import { StatCard } from "./StatCard";
import { StatusBadge } from "./StatusBadge";
import { formatDuration, formatTime } from "../utils/formatters";
import type { StatsResponse } from "../types/dashboard";

interface StatsPanelProps {
  stats: StatsResponse | null;
  qualityScore?: number;
  healthScore?: number;
}

export function StatsPanel({ stats, qualityScore = 94.7, healthScore = 91 }: StatsPanelProps) {
  return (
    <div className="panel">
      <div className="stat-strip">
        <StatCard label="Total Received" value={stats?.total_received} icon={Inbox} />
        <StatCard
          label="Processed"
          value={stats?.total_processed}
          icon={CheckCircle2}
          tone="green"
        />
        <StatCard label="Duplicates" value={stats?.total_duplicates} icon={Copy} tone="amber" />
        <StatCard label="Failed" value={stats?.total_failed} icon={XCircle} tone="red" />

        <StatCard label="Data Quality" value={`${qualityScore} / 100`} icon={ShieldCheck} tone="cyan" />
        <StatCard label="Pipeline Health" value={`${healthScore} / 100`} icon={HeartPulse} tone="green" />

        <div className="stat-cell-perf">
          <span className="perf-item">
            <Clock size={13} />
            Latest duration
            <span className="mono">{formatDuration(stats?.last_run_duration_ms)}</span>
          </span>
          <span className="perf-item">
            <Activity size={13} />
            Latest status
            {stats?.last_run_status ? (
              <StatusBadge status={stats.last_run_status} />
            ) : (
              <span className="mono">—</span>
            )}
          </span>
          <span className="perf-item">
            Last updated
            <span className="mono">{formatTime(stats?.last_run_timestamp)}</span>
          </span>
        </div>
      </div>
    </div>
  );
}

