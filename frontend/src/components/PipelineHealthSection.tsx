import { useState, useEffect } from "react";
import { HeartPulse } from "lucide-react";
import { api } from "../services/api";
import type { PipelineHealthResponse, SourceStatus } from "../types/dashboard";
import { PipelineFlow } from "./PipelineFlow";
import { LoadingState } from "./LoadingState";
import { ErrorState } from "./ErrorState";
import { EmptyState } from "./EmptyState";

export function PipelineHealthSection() {
  const [health, setHealth] = useState<PipelineHealthResponse | null>(null);
  const [sources, setSources] = useState<SourceStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [hRes, sRes] = await Promise.all([
        api.getPipelineHealth(),
        api.getSources(),
      ]);
      setHealth(hRes);
      setSources(sRes);
    } catch {
      setError("Unable to compute Pipeline Health Score.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) return <LoadingState lines={4} label="Evaluating Pipeline Health Score…" />;
  if (error) return <ErrorState message={error} onRetry={loadData} />;
  if (!health) return <EmptyState message="No pipeline health metric available." />;

  const statusColor =
    health.status === "HEALTHY"
      ? "var(--accent-green)"
      : health.status === "DEGRADED"
      ? "var(--accent-amber)"
      : "var(--accent-red)";

  return (
    <div className="dashboard-stack">
      <div className="panel">
        <div className="panel-header">
          <h2>Pipeline Health Score</h2>
          <span className="panel-sub">
            Overall operational score computed from latency, availability, validation, and reliability
          </span>
        </div>

        <div className="health-main-grid">
          <div className="score-card">
            <HeartPulse size={36} style={{ color: statusColor }} />
            <div className="score-val" style={{ color: statusColor }}>
              {health.overall_score}
            </div>
            <div className="score-denom">/ 100</div>
            <div className="score-label">
              STATUS: <strong style={{ color: statusColor }}>{health.status}</strong>
            </div>
          </div>

          <div className="pillars-grid">
            <div className="pillar-item">
              <div className="pillar-header">
                <span className="pillar-title">Availability</span>
                <span className="pillar-val">{health.availability}%</span>
              </div>
              <div className="pillar-bar-bg">
                <div
                  className="pillar-bar-fill"
                  style={{ width: `${health.availability}%`, backgroundColor: "var(--accent-green)" }}
                />
              </div>
            </div>

            <div className="pillar-item">
              <div className="pillar-header">
                <span className="pillar-title">Latency</span>
                <span className="pillar-val">{health.latency}%</span>
              </div>
              <div className="pillar-bar-bg">
                <div
                  className="pillar-bar-fill"
                  style={{ width: `${health.latency}%`, backgroundColor: "var(--accent-cyan)" }}
                />
              </div>
            </div>

            <div className="pillar-item">
              <div className="pillar-header">
                <span className="pillar-title">Validation</span>
                <span className="pillar-val">{health.validation}%</span>
              </div>
              <div className="pillar-bar-bg">
                <div
                  className="pillar-bar-fill"
                  style={{ width: `${health.validation}%`, backgroundColor: "var(--accent-amber)" }}
                />
              </div>
            </div>

            <div className="pillar-item">
              <div className="pillar-header">
                <span className="pillar-title">Reliability</span>
                <span className="pillar-val">{health.reliability}%</span>
              </div>
              <div className="pillar-bar-bg">
                <div
                  className="pillar-bar-fill"
                  style={{ width: `${health.reliability}%`, backgroundColor: "#8b5cf6" }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2>Pipeline Flow Monitor</h2>
          <span className="panel-sub">Real-time status of pipeline ingestion stages</span>
        </div>
        <PipelineFlow sources={sources} active={false} />
      </div>
    </div>
  );
}
