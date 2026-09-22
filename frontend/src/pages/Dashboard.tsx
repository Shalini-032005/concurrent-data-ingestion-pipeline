import { useCallback, useEffect, useRef, useState } from "react";
import { WifiOff } from "lucide-react";
import { DashboardHeader } from "../components/DashboardHeader";
import { StatsPanel } from "../components/StatsPanel";
import { PipelineFlow } from "../components/PipelineFlow";
import { SourceGrid } from "../components/SourceGrid";
import { IngestionChart } from "../components/IngestionChart";
import { IngestionTable } from "../components/IngestionTable";
import { RecordsTable } from "../components/RecordsTable";
import { ActivityFeed } from "../components/ActivityFeed";
import { LoadingState } from "../components/LoadingState";
import { ErrorState } from "../components/ErrorState";
import { useWebSocket } from "../hooks/useWebSocket";
import { api, ApiError } from "../services/api";
import type {
  IngestionRunSummary,
  PaginatedRecords,
  SourceStatus,
  StatsResponse,
} from "../types/dashboard";

const RECORDS_PAGE_SIZE = 20;

export function Dashboard() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [sources, setSources] = useState<SourceStatus[]>([]);
  const [runs, setRuns] = useState<IngestionRunSummary[]>([]);
  const [records, setRecords] = useState<PaginatedRecords | null>(null);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ingestionRunning, setIngestionRunning] = useState(false);
  const [recordsPage, setRecordsPage] = useState(1);

  const recordsPageRef = useRef(recordsPage);
  recordsPageRef.current = recordsPage;

  const loadAll = useCallback(async (page: number) => {
    const [statsRes, sourcesRes, runsRes, recordsRes] = await Promise.all([
      api.getStats(),
      api.getSources(),
      api.getRuns(),
      api.getRecords(page, RECORDS_PAGE_SIZE),
    ]);
    setStats(statsRes);
    setSources(sourcesRes);
    setRuns(runsRes);
    setRecords(recordsRes);
  }, []);

  const initialLoad = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await loadAll(1);
      setRecordsPage(1);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? "Unable to load dashboard data."
          : "Unexpected error while loading the dashboard."
      );
    } finally {
      setLoading(false);
    }
  }, [loadAll]);

  useEffect(() => {
    initialLoad();
  }, [initialLoad]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await loadAll(recordsPageRef.current);
      setError(null);
    } catch {
      // Keep whatever data is already on screen; the user can retry manually.
    } finally {
      setRefreshing(false);
    }
  }, [loadAll]);

  const handlePageChange = useCallback(
    async (page: number) => {
      try {
        const res = await api.getRecords(page, RECORDS_PAGE_SIZE);
        setRecords(res);
        setRecordsPage(page);
      } catch {
        // Leave the current page visible on failure.
      }
    },
    []
  );

  const handleRunIngestion = useCallback(async () => {
    setIngestionRunning(true);
    try {
      await api.startIngestion();
    } catch {
      setIngestionRunning(false);
    }
  }, []);

  const { status: wsStatus, activity } = useWebSocket(
    useCallback((event) => {
      if (event.event === "INGESTION_STARTED") {
        setIngestionRunning(true);
      }
      if (event.event === "INGESTION_COMPLETED") {
        setIngestionRunning(false);
        // The event carries only a summary; pull the authoritative totals
        // and refreshed record/source state over REST.
        loadAll(recordsPageRef.current).catch(() => undefined);
      }
    }, [loadAll])
  );

  if (loading) {
    return (
      <div className="app-shell">
        <DashboardHeader
          wsStatus={wsStatus}
          onRefresh={handleRefresh}
          refreshing={refreshing}
          onRunIngestion={handleRunIngestion}
          ingestionRunning={ingestionRunning}
          ingestionAvailable={false}
        />
        <div className="dashboard-stack">
          <div className="panel">
            <LoadingState lines={2} label="Loading pipeline stats…" />
          </div>
          <div className="panel">
            <LoadingState lines={4} label="Loading sources…" />
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app-shell">
        <DashboardHeader
          wsStatus={wsStatus}
          onRefresh={handleRefresh}
          refreshing={refreshing}
          onRunIngestion={handleRunIngestion}
          ingestionRunning={ingestionRunning}
          ingestionAvailable={false}
        />
        <div className="panel">
          <ErrorState message={error} onRetry={initialLoad} />
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <DashboardHeader
        wsStatus={wsStatus}
        onRefresh={handleRefresh}
        refreshing={refreshing}
        onRunIngestion={handleRunIngestion}
        ingestionRunning={ingestionRunning}
        ingestionAvailable
      />

      {wsStatus === "closed" && (
        <div className="banner" role="status">
          <WifiOff size={14} />
          Live updates unavailable — showing the last data loaded over REST. Use Refresh to
          check for updates.
        </div>
      )}

      <div className="dashboard-stack" style={{ marginTop: 14 }}>
        <StatsPanel stats={stats} />

        <div className="panel">
          <div className="panel-header">
            <h2>Concurrent Ingestion</h2>
            <span className="panel-sub">
              Three sources ingested in parallel by the backend orchestrator
            </span>
          </div>
          <PipelineFlow sources={sources} active={ingestionRunning} />
        </div>

        <div className="dashboard-columns">
          <div className="dashboard-stack">
            <div className="panel">
              <div className="panel-header">
                <h2>Ingestion Performance</h2>
                <span className="panel-sub">Run duration, most recent 10 runs</span>
              </div>
              <div className="panel-body">
                <IngestionChart runs={runs} />
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <h2>Recent Ingestion Runs</h2>
              </div>
              <IngestionTable runs={runs} />
            </div>
          </div>

          <div className="dashboard-stack">
            <div className="panel">
              <div className="panel-header">
                <h2>Source Monitoring</h2>
              </div>
              <div className="panel-body">
                <SourceGrid sources={sources} />
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <h2>Live Activity</h2>
              </div>
              <ActivityFeed items={activity} />
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Processed Records</h2>
            <span className="panel-sub">Page {recordsPage}</span>
          </div>
          <RecordsTable data={records} onPageChange={handlePageChange} />
        </div>
      </div>

      <footer className="app-footer">
        <span>Concurrent Data Ingestion Pipeline — Member 4 dashboard</span>
        <span>Backend: REST + WebSocket, contract owned by Member 1</span>
      </footer>
    </div>
  );
}
