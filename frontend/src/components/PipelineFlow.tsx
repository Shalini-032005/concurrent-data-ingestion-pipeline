import type { SourceHealth, SourceStatus } from "../types/dashboard";

interface PipelineFlowProps {
  sources: SourceStatus[];
  active: boolean;
}

const HEALTH_COLOR: Record<SourceHealth, string> = {
  HEALTHY: "var(--accent-green)",
  DEGRADED: "var(--accent-orange)",
  DOWN: "var(--accent-red)",
  UNKNOWN: "var(--text-faint)",
};

const SOURCE_Y = [34, 92, 150];

export function PipelineFlow({ sources, active }: PipelineFlowProps) {
  // Always render three source lanes (A/B/C), falling back to UNKNOWN
  // until /api/sources has loaded, so the diagram never collapses.
  const lanes = ["Source A", "Source B", "Source C"].map((name) => {
    const found = sources.find((s) => s.source === name);
    return {
      name,
      health: (found?.status ?? "UNKNOWN") as SourceHealth,
    };
  });

  return (
    <div className="pipeline">
      <svg viewBox="0 0 700 184" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Pipeline flow: three sources are ingested concurrently, processed, stored, then served to this dashboard.">
        {/* Convergence lines from each source into the processing node */}
        {lanes.map((lane, i) => (
          <path
            key={lane.name}
            d={`M 106 ${SOURCE_Y[i]} H 150 L 236 92 H 268`}
            fill="none"
            stroke={HEALTH_COLOR[lane.health]}
            strokeWidth="1.6"
            strokeLinecap="round"
            opacity={lane.health === "DOWN" ? 0.35 : 0.85}
            strokeDasharray={active ? "5 4" : undefined}
            className={active ? "flow-line" : undefined}
          />
        ))}

        {/* Processing -> Database -> Dashboard */}
        <path d="M 402 92 H 452" fill="none" stroke="var(--border)" strokeWidth="1.6" strokeDasharray={active ? "5 4" : undefined} className={active ? "flow-line" : undefined} />
        <path d="M 586 92 H 636" fill="none" stroke="var(--border)" strokeWidth="1.6" strokeDasharray={active ? "5 4" : undefined} className={active ? "flow-line" : undefined} />

        {/* Source nodes */}
        {lanes.map((lane, i) => (
          <g key={lane.name} transform={`translate(0, ${SOURCE_Y[i] - 18})`}>
            <rect x="4" y="0" width="102" height="36" rx="4" fill="var(--panel-raised)" stroke="var(--border)" />
            <circle cx="18" cy="18" r="4" fill={HEALTH_COLOR[lane.health]} />
            <text x="30" y="22" fontSize="11" fontFamily="var(--font-ui)" fill="var(--text-primary)" fontWeight={600}>
              {lane.name}
            </text>
          </g>
        ))}

        {/* Processing node */}
        <g transform="translate(268, 62)">
          <rect width="134" height="60" rx="4" fill="var(--panel-raised)" stroke="var(--border)" />
          <text x="67" y="24" fontSize="11" fontWeight={600} textAnchor="middle" fill="var(--text-primary)">
            Concurrent
          </text>
          <text x="67" y="39" fontSize="10" textAnchor="middle" fill="var(--text-secondary)">
            Validate · Normalize
          </text>
          <text x="67" y="52" fontSize="10" textAnchor="middle" fill="var(--text-secondary)">
            Deduplicate
          </text>
        </g>

        {/* Database node */}
        <g transform="translate(452, 62)">
          <rect width="134" height="60" rx="4" fill="var(--panel-raised)" stroke="var(--border)" />
          <text x="67" y="30" fontSize="11" fontWeight={600} textAnchor="middle" fill="var(--text-primary)">
            PostgreSQL
          </text>
          <text x="67" y="45" fontSize="10" textAnchor="middle" fill="var(--text-secondary)">
            REST + WebSocket
          </text>
        </g>

        {/* Dashboard node (you are here) */}
        <g transform="translate(636, 56)">
          <rect width="60" height="72" rx="4" fill="var(--accent-amber-dim)" stroke="var(--accent-amber)" />
          <text x="30" y="30" fontSize="10" fontWeight={600} textAnchor="middle" fill="var(--accent-amber)">
            This
          </text>
          <text x="30" y="43" fontSize="10" fontWeight={600} textAnchor="middle" fill="var(--accent-amber)">
            dashboard
          </text>
        </g>
      </svg>
    </div>
  );
}
