import React, { useEffect, useState } from "react";
import { ArrowDown, Search } from "lucide-react";
import { api } from "../services/api";
import type { IngestedRecord, RecordLineageResponse } from "../types/dashboard";
import { LoadingState } from "./LoadingState";
import { ErrorState } from "./ErrorState";
import { EmptyState } from "./EmptyState";

export function DataLineageSection() {
  const [records, setRecords] = useState<IngestedRecord[]>([]);
  const [selectedRecordId, setSelectedRecordId] = useState<string>("");
  const [lineage, setLineage] = useState<RecordLineageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [lineageLoading, setLineageLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadInitialRecords = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getRecords(1, 20);
      setRecords(res.records);
      if (res.records.length > 0) {
        const firstId = res.records[0].record_id || String(res.records[0].id || "");
        setSelectedRecordId(firstId);
        fetchLineage(firstId);
      }
    } catch {
      setError("Unable to load records for lineage tracing.");
    } finally {
      setLoading(false);
    }
  };

  const fetchLineage = async (id: string) => {
    if (!id) return;
    setLineageLoading(true);
    try {
      const res = await api.getLineage(id);
      setLineage(res);
    } catch {
      setLineage(null);
    } finally {
      setLineageLoading(false);
    }
  };

  useEffect(() => {
    loadInitialRecords();
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedRecordId) {
      fetchLineage(selectedRecordId);
    }
  };

  if (loading) return <LoadingState lines={4} label="Loading record lineage explorer…" />;
  if (error) return <ErrorState message={error} onRetry={loadInitialRecords} />;

  return (
    <div className="dashboard-stack">
      <div className="panel">
        <div className="panel-header">
          <h2>Record Data Lineage</h2>
          <span className="panel-sub">
            End-to-end execution flow from raw ingestion to final storage
          </span>
        </div>

        {/* Record selector form */}
        <form onSubmit={handleSearchSubmit} className="lineage-search-bar">
          <div className="search-input-group">
            <Search size={16} />
            <input
              type="text"
              className="input"
              placeholder="Enter Record ID (e.g. REC-101)..."
              value={selectedRecordId}
              onChange={(e) => setSelectedRecordId(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary">
            Trace Lineage
          </button>
        </form>

        {/* Quick select list */}
        {records.length > 0 && (
          <div className="quick-records-chips">
            <span className="chip-label">Quick Select:</span>
            {records.slice(0, 5).map((r) => {
              const rId = r.record_id || String(r.id || "");
              return (
                <button
                  key={rId}
                  type="button"
                  className={`chip ${selectedRecordId === rId ? "active" : ""}`}
                  onClick={() => {
                    setSelectedRecordId(rId);
                    fetchLineage(rId);
                  }}
                >
                  {rId} ({r.source})
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Visual Lineage Flow */}
      <div className="panel">
        <div className="panel-header">
          <h2>Visual Execution Path</h2>
          {lineage && (
            <span className="panel-sub">
              Tracing Record: <strong>{lineage.record_id}</strong> ({lineage.source})
            </span>
          )}
        </div>

        {lineageLoading ? (
          <LoadingState lines={3} label="Fetching lineage steps..." />
        ) : !lineage ? (
          <EmptyState message="No lineage data found for the specified Record ID. Enter or select a valid ID above." />
        ) : (
          <div className="lineage-flow-container">
            {lineage.steps.map((step, idx) => (
              <React.Fragment key={step.stage}>
                <div className="lineage-step-card">
                  <div className="step-num">{idx + 1}</div>
                  <div className="step-content">
                    <div className="step-header">
                      <h4>{step.stage}</h4>
                      <span className="badge badge-success">{step.status}</span>
                    </div>
                    <span className="step-time">
                      {new Date(step.timestamp).toLocaleTimeString()}
                    </span>
                    <div className="step-details">
                      {Object.entries(step.details).map(([k, v]) => (
                        <div key={k} className="detail-item">
                          <span>{k}:</span> <strong>{String(v)}</strong>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                {idx < lineage.steps.length - 1 && (
                  <div className="lineage-connector">
                    <ArrowDown size={18} />
                  </div>
                )}
              </React.Fragment>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
