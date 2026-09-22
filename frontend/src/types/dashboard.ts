/**
 * Types mirror app/schemas/responses.py on the backend (Member 1) exactly.
 * If Member 1 changes a field name or enum, update it here first — every
 * other file in the frontend depends on these.
 */

export type RunStatus = "RUNNING" | "COMPLETED" | "PARTIAL" | "FAILED";

export type SourceHealth = "HEALTHY" | "DEGRADED" | "DOWN" | "UNKNOWN";

export type SourceResultStatus = "SUCCESS" | "FAILED" | "TIMEOUT";

export interface SourceResult {
  source: string;
  status: SourceResultStatus;
  received: number;
  duration_ms: number;
  error: string | null;
}

export interface IngestionRunSummary {
  run_id: number;
  status: RunStatus;
  total_received: number;
  total_processed: number;
  total_duplicates: number;
  total_failed: number;
  duration_ms: number;
  started_at: string;
  completed_at: string | null;
  source_results: SourceResult[];
}

export interface StatsResponse {
  total_received: number;
  total_processed: number;
  total_duplicates: number;
  total_failed: number;
  last_run_status: string | null;
  last_run_timestamp: string | null;
  last_run_duration_ms: number | null;
}

export interface SourceStatus {
  source: string;
  status: SourceHealth;
  last_success: string | null;
  last_failure: string | null;
  records_received: number;
  records_processed: number;
}

/** Records come back as loosely-typed dicts (`extra="allow"` on the backend). */
export interface IngestedRecord {
  record_id: string;
  name?: string | null;
  email?: string | null;
  value?: number | null;
  source: string;
  created_at?: string | null;
  ingested_at: string;
  [key: string]: unknown;
}

export interface PaginatedRecords {
  page: number;
  page_size: number;
  total: number;
  records: IngestedRecord[];
}

export interface IngestStartResponse {
  run_id: number;
  status: RunStatus;
}

export type IngestionEventType =
  | "INGESTION_STARTED"
  | "SOURCE_STARTED"
  | "SOURCE_COMPLETED"
  | "SOURCE_FAILED"
  | "INGESTION_COMPLETED";

/** Message shape broadcast over /ws. Fields are omitted (not null) when unset. */
export interface IngestionEvent {
  event: IngestionEventType;
  run_id: number;
  timestamp: string;
  source?: string;
  records?: number;
  duration_ms?: number;
  error?: string;
  status?: string;
}

export type ConnectionState = "connecting" | "open" | "closed";

/** One line in the live activity feed, derived from IngestionEvent as it arrives. */
export interface ActivityItem {
  id: string;
  timestamp: string;
  message: string;
  tone: "success" | "warning" | "error" | "info";
}

// ---------------------------------------------------------------------------
// Phase 1 Intelligence Types
// ---------------------------------------------------------------------------

export interface DataQualityResponse {
  overall_score: number;
  completeness: number;
  validity: number;
  consistency: number;
  uniqueness: number;
  freshness: number;
  timestamp: string;
  quality_by_source: Record<string, number>;
  details: Record<string, unknown>;
}

export interface QualityTrendPoint {
  run_id: number;
  timestamp: string;
  overall_score: number;
  completeness: number;
  validity: number;
  consistency: number;
  uniqueness: number;
  freshness: number;
}

export interface QualityTrendResponse {
  trend: QualityTrendPoint[];
}

export type AnomalySeverity = "LOW" | "MEDIUM" | "HIGH";
export type AnomalyStatus = "ACTIVE" | "ACKNOWLEDGED" | "RESOLVED";

export interface AnomalyRecord {
  id: string;
  run_id?: number | null;
  record_id?: string | null;
  source: string;
  feature_name: string;
  current_value: number;
  expected_range: string;
  severity: AnomalySeverity;
  reason: string;
  status: AnomalyStatus;
  timestamp: string;
}

export interface AnomaliesSummary {
  total_anomalies: number;
  high_count: number;
  medium_count: number;
  low_count: number;
}

export interface AnomaliesResponse {
  anomalies: AnomalyRecord[];
  summary: AnomaliesSummary;
}

export interface PipelineHealthResponse {
  overall_score: number;
  availability: number;
  latency: number;
  validation: number;
  reliability: number;
  status: "HEALTHY" | "DEGRADED" | "CRITICAL";
  updated_at: string;
}

export type AlertSeverity = "INFO" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type AlertStatus = "ACTIVE" | "ACKNOWLEDGED" | "RESOLVED";

export interface AlertItem {
  id: string;
  severity: AlertSeverity;
  title: string;
  description: string;
  source: string;
  timestamp: string;
  status: AlertStatus;
  run_id?: number | null;
  record_id?: string | null;
}

export interface AlertsResponse {
  alerts: AlertItem[];
  active_count: number;
}

export interface LineageStep {
  stage: string;
  status: string;
  timestamp: string;
  details: Record<string, unknown>;
}

export interface RecordLineageResponse {
  record_id: string;
  source: string;
  run_id?: number | null;
  received_at?: string | null;
  final_status: string;
  steps: LineageStep[];
}

export interface MetricChange {
  name: string;
  latest_value: number;
  previous_value: number;
  absolute_change: number;
  percent_change: number;
  status: "IMPROVED" | "DEGRADED" | "NEUTRAL";
}

export interface RunComparisonResponse {
  latest_run_id: number;
  previous_run_id: number;
  records_change: MetricChange;
  duplicates_change: MetricChange;
  validation_errors_change: MetricChange;
  latency_change: MetricChange;
  quality_change: MetricChange;
  anomalies_change: MetricChange;
}

export interface RunReplayResponse {
  replay_run_id: number;
  original_run_id: number;
  status: string;
  message: string;
}

