import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { EmptyState } from "./EmptyState";
import { formatDuration } from "../utils/formatters";
import type { IngestionRunSummary } from "../types/dashboard";

interface IngestionChartProps {
  runs: IngestionRunSummary[];
}

interface ChartPoint {
  label: string;
  duration_ms: number;
  status: string;
}

const STATUS_COLOR: Record<string, string> = {
  COMPLETED: "var(--accent-green)",
  RUNNING: "var(--accent-cyan)",
  PARTIAL: "var(--accent-orange)",
  FAILED: "var(--accent-red)",
};

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: ChartPoint }[];
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="ct-title">{point.label}</div>
      <div className="ct-row">
        <span>Duration</span>
        <span className="mono">{formatDuration(point.duration_ms)}</span>
      </div>
      <div className="ct-row">
        <span>Status</span>
        <span className="mono">{point.status}</span>
      </div>
    </div>
  );
}

export function IngestionChart({ runs }: IngestionChartProps) {
  if (runs.length === 0) {
    return <EmptyState message="No ingestion runs yet." />;
  }

  // Runs arrive newest-first; plot chronologically so the trend reads left-to-right.
  const data: ChartPoint[] = [...runs]
    .slice(0, 10)
    .reverse()
    .map((run) => ({
      label: `Run ${run.run_id}`,
      duration_ms: Math.round(run.duration_ms),
      status: run.status,
    }));

  return (
    <div style={{ width: "100%", height: 220 }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--border-soft)" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "var(--text-faint)", fontSize: 11 }}
            axisLine={{ stroke: "var(--border-soft)" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "var(--text-faint)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={44}
            tickFormatter={(v: number) => `${v}ms`}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--panel-raised)" }} />
          <Bar dataKey="duration_ms" radius={[3, 3, 0, 0]} maxBarSize={34}>
            {data.map((entry, i) => (
              <Cell key={i} fill={STATUS_COLOR[entry.status] ?? "var(--accent-cyan)"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
