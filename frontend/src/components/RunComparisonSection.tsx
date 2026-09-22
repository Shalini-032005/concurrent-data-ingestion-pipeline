import { useState, useEffect } from "react";
import { ArrowDownRight, ArrowUpRight, RotateCcw } from "lucide-react";
import { api } from "../services/api";
import type { IngestionRunSummary, RunComparisonResponse } from "../types/dashboard";
import { LoadingState } from "./LoadingState";
import { ErrorState } from "./ErrorState";
import { EmptyState } from "./EmptyState";

export function RunComparisonSection() {
  const [comparison, setComparison] = useState<RunComparisonResponse | null>(null);
  const [runs, setRuns] = useState<IngestionRunSummary[]>([]);
  const [replaying, setReplaying] = useState<boolean>(false);
  const [replayMessage, setReplayMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [compRes, runsRes] = await Promise.all([
        api.getRunComparison(),
        api.getRuns(),
      ]);
      setComparison(compRes);
      setRuns(runsRes);
    } catch {
      setError("Unable to compare ingestion runs.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleReplay = async (runId: number, sourceName?: string) => {
    setReplaying(true);
    setReplayMessage(null);
    try {
      const res = await api.replayRun(runId, sourceName);
      setReplayMessage(res.message);
      await loadData();
    } catch (err) {
      setReplayMessage(err instanceof Error ? err.message : "Replay failed");
    } finally {
      setReplaying(false);
    }
  };

  if (loading) return <LoadingState lines={4} label="Calculating run comparisons & deltas…" />;
  if (error) return <ErrorState message={error} onRetry={loadData} />;
  if (!comparison) return <EmptyState message="Not enough ingestion runs to generate comparison." />;

  const changes = [
    comparison.records_change,
    comparison.duplicates_change,
    comparison.validation_errors_change,
    comparison.latency_change,
    comparison.quality_change,
    comparison.anomalies_change,
  ];

  return (
    <div className="dashboard-stack">
      {/* What Changed Matrix */}
      <div className="panel">
        <div className="panel-header">
          <h2>WHAT CHANGED?</h2>
          <span className="panel-sub">
            Comparing Latest Run #{comparison.latest_run_id} vs Previous Run #{comparison.previous_run_id}
          </span>
        </div>

        <div className="comparison-grid">
          {changes.map((item) => {
            const isPos = item.percent_change >= 0;
            const isDeg = item.status === "DEGRADED";
            const chipClass = isDeg ? "chip-degraded" : "chip-improved";

            return (
              <div key={item.name} className="comp-card">
                <div className="comp-title">{item.name}</div>
                <div className="comp-values">
                  <span className="comp-latest">{item.latest_value}</span>
                  <span className="comp-prev">vs {item.previous_value}</span>
                </div>
                <div className={`comp-pct ${chipClass}`}>
                  {isPos ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                  <span>
                    {isPos ? "+" : ""}
                    {item.percent_change}% ({isPos ? "+" : ""}
                    {item.absolute_change})
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Run Replay Section */}
      <div className="panel">
        <div className="panel-header">
          <h2>Run Replay Center</h2>
          <span className="panel-sub">
            Re-execute failed runs or failed sources with duplicate prevention guarantees
          </span>
        </div>

        {replayMessage && (
          <div className="banner banner-info" style={{ marginBottom: 12 }}>
            <RotateCcw size={14} /> {replayMessage}
          </div>
        )}

        <div className="runs-replay-list">
          {runs.map((r) => {
            const isFailed = r.status !== "COMPLETED";
            return (
              <div key={r.run_id} className={`replay-row ${isFailed ? "failed-row" : ""}`}>
                <div className="replay-run-info">
                  <strong>Run #{r.run_id}</strong>
                  <span className={`badge badge-${r.status.toLowerCase()}`}>
                    {r.status}
                  </span>
                  <span className="text-sub">
                    Received: {r.total_received} • Processed: {r.total_processed} • Duplicates: {r.total_duplicates} • Failed: {r.total_failed}
                  </span>
                </div>
                <div className="replay-actions">
                  <button
                    type="button"
                    className="btn btn-sm btn-primary"
                    onClick={() => handleReplay(r.run_id)}
                    disabled={replaying}
                  >
                    <RotateCcw size={12} className={replaying ? "spin" : ""} />
                    {replaying ? "Replaying…" : "Replay Run"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
