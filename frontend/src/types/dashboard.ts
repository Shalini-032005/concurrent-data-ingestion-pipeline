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
