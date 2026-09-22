import { useState, useEffect } from "react";
import { AlertTriangle, Info, X } from "lucide-react";
import { api } from "../services/api";
import type { AnomaliesResponse, AnomalyRecord } from "../types/dashboard";
import { LoadingState } from "./LoadingState";
import { ErrorState } from "./ErrorState";
import { EmptyState } from "./EmptyState";

export function AnomaliesSection() {
  const [data, setData] = useState<AnomaliesResponse | null>(null);
  const [selectedAnomaly, setSelectedAnomaly] = useState<AnomalyRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getAnomalies();
      setData(res);
    } catch {
      setError("Unable to load ML Anomaly records.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) return <LoadingState lines={4} label="Running IsolationForest anomaly scan…" />;
  if (error) return <ErrorState message={error} onRetry={loadData} />;
  if (!data || data.anomalies.length === 0) {
    return (
      <div className="panel">
        <div className="panel-header">
          <h2>ML Anomaly Detection</h2>
          <span className="panel-sub">scikit-learn IsolationForest scan</span>
        </div>
        <EmptyState message="No anomalies detected in pipeline runs or records." />
      </div>
    );
  }

  const { summary, anomalies } = data;

  return (
    <div className="dashboard-stack">
      <div className="panel">
        <div className="panel-header">
          <h2>ML Anomaly Detection</h2>
          <span className="panel-sub">
            Powered by scikit-learn IsolationForest & Statistical Explanation Engine
          </span>
        </div>

        <div className="anomaly-summary-cards">
          <div className="anom-summary-card high">
            <span className="count">{summary.high_count}</span>
            <span className="lbl">HIGH SEVERITY</span>
          </div>
          <div className="anom-summary-card medium">
            <span className="count">{summary.medium_count}</span>
            <span className="lbl">MEDIUM SEVERITY</span>
          </div>
          <div className="anom-summary-card low">
            <span className="count">{summary.low_count}</span>
            <span className="lbl">LOW SEVERITY</span>
          </div>
          <div className="anom-summary-card total">
            <span className="count">{summary.total_anomalies}</span>
            <span className="lbl">TOTAL DETECTED</span>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2>Detected Anomalies</h2>
          <span className="panel-sub">Select a row to view full statistical reason</span>
        </div>

        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Record ID</th>
                <th>Source</th>
                <th>Feature</th>
                <th>Value</th>
                <th>Severity</th>
                <th>Time</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {anomalies.map((anom) => (
                <tr key={anom.id} className="interactive-row" onClick={() => setSelectedAnomaly(anom)}>
                  <td>
                    <code>{anom.record_id || `Run #${anom.run_id}`}</code>
                  </td>
                  <td>{anom.source}</td>
                  <td>{anom.feature_name}</td>
                  <td>
                    <strong>{anom.current_value.toFixed(2)}</strong>
                  </td>
                  <td>
                    <span className={`badge badge-${anom.severity.toLowerCase()}`}>
                      {anom.severity}
                    </span>
                  </td>
                  <td>{new Date(anom.timestamp).toLocaleTimeString()}</td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedAnomaly(anom);
                      }}
                    >
                      Inspect
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Modal */}
      {selectedAnomaly && (
        <div className="modal-backdrop" onClick={() => setSelectedAnomaly(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                <AlertTriangle
                  size={20}
                  className={`text-${selectedAnomaly.severity.toLowerCase()}`}
                />
                <h3>Anomaly Detail: {selectedAnomaly.id}</h3>
              </div>
              <button
                type="button"
                className="btn-icon"
                onClick={() => setSelectedAnomaly(null)}
                aria-label="Close detail modal"
              >
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <div className="detail-grid">
                <div>
                  <span className="detail-lbl">Target Record/Run</span>
                  <span className="detail-val">
                    {selectedAnomaly.record_id || `Run #${selectedAnomaly.run_id}`}
                  </span>
                </div>
                <div>
                  <span className="detail-lbl">Source</span>
                  <span className="detail-val">{selectedAnomaly.source}</span>
                </div>
                <div>
                  <span className="detail-lbl">Observed Value</span>
                  <span className="detail-val">{selectedAnomaly.current_value}</span>
                </div>
                <div>
                  <span className="detail-lbl">Expected Historical Range</span>
                  <span className="detail-val">{selectedAnomaly.expected_range}</span>
                </div>
              </div>

              <div className="reason-box">
                <Info size={18} style={{ color: "var(--accent-cyan)", flexShrink: 0 }} />
                <div>
                  <strong>Statistical Reason:</strong>
                  <p>{selectedAnomaly.reason}</p>
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button type="button" className="btn" onClick={() => setSelectedAnomaly(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
