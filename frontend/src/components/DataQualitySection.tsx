import { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { ShieldCheck, CheckCircle2 } from "lucide-react";
import { api } from "../services/api";
import type { DataQualityResponse, QualityTrendPoint } from "../types/dashboard";
import { LoadingState } from "./LoadingState";
import { ErrorState } from "./ErrorState";
import { EmptyState } from "./EmptyState";

export function DataQualitySection() {
  const [data, setData] = useState<DataQualityResponse | null>(null);
  const [trend, setTrend] = useState<QualityTrendPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [qualityRes, trendRes] = await Promise.all([
        api.getQuality(),
        api.getQualityTrend(15),
      ]);
      setData(qualityRes);
      setTrend(trendRes.trend);
    } catch {
      setError("Unable to load Data Quality metrics.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) return <LoadingState lines={4} label="Calculating Data Quality Score…" />;
  if (error) return <ErrorState message={error} onRetry={loadData} />;
  if (!data) return <EmptyState message="No quality data available yet." />;

  const pillars = [
    { label: "Completeness", value: data.completeness, color: "var(--accent-cyan)" },
    { label: "Validity", value: data.validity, color: "var(--accent-green)" },
    { label: "Consistency", value: data.consistency, color: "var(--accent-amber)" },
    { label: "Uniqueness", value: data.uniqueness, color: "#8b5cf6" },
    { label: "Freshness", value: data.freshness, color: "#ec4899" },
  ];

  return (
    <div className="dashboard-stack">
      <div className="panel">
        <div className="panel-header">
          <h2>Data Quality Engine</h2>
          <span className="panel-sub">
            Real-time deterministic score computed from real project records
          </span>
        </div>

        <div className="quality-main-grid">
          {/* Main Score Gauge */}
          <div className="score-card">
            <ShieldCheck size={36} style={{ color: "var(--accent-cyan)" }} />
            <div className="score-val">{data.overall_score}</div>
            <div className="score-denom">/ 100</div>
            <div className="score-label">Overall Quality Score</div>
          </div>

          {/* 5 Pillars Breakdown */}
          <div className="pillars-grid">
            {pillars.map((p) => (
              <div key={p.label} className="pillar-item">
                <div className="pillar-header">
                  <span className="pillar-title">{p.label}</span>
                  <span className="pillar-val">{p.value}%</span>
                </div>
                <div className="pillar-bar-bg">
                  <div
                    className="pillar-bar-fill"
                    style={{ width: `${Math.max(0, Math.min(100, p.value))}%`, backgroundColor: p.color }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Trend & Source Quality */}
      <div className="dashboard-columns">
        <div className="panel">
          <div className="panel-header">
            <h2>Quality Score Trend</h2>
            <span className="panel-sub">Recent ingestion runs</span>
          </div>
          <div style={{ width: "100%", height: 260 }}>
            {trend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trend} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.5} />
                  <XAxis dataKey="run_id" stroke="var(--text-sub)" tickFormatter={(v) => `Run #${v}`} />
                  <YAxis domain={[0, 100]} stroke="var(--text-sub)" />
                  <Tooltip
                    contentStyle={{ backgroundColor: "var(--bg-panel)", borderColor: "var(--border)" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="overall_score"
                    name="Quality Score"
                    stroke="var(--accent-cyan)"
                    strokeWidth={2}
                    dot={{ fill: "var(--accent-cyan)", r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState message="No trend history recorded yet." />
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Quality by Source</h2>
          </div>
          <div className="source-quality-list">
            {Object.keys(data.quality_by_source).length > 0 ? (
              Object.entries(data.quality_by_source).map(([src, score]) => (
                <div key={src} className="src-qual-row">
                  <div className="src-qual-name">
                    <CheckCircle2 size={16} style={{ color: "var(--accent-green)" }} />
                    <span>{src}</span>
                  </div>
                  <span className="src-qual-score">{score}%</span>
                </div>
              ))
            ) : (
              <EmptyState message="No source quality breakdown available." />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
