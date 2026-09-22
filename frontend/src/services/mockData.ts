/**
 * Deterministic mock fallback data, used only when VITE_USE_MOCK_DATA=true
 * or when a live API call fails during local frontend-only development.
 * This must never be the default in a production deployment — see
 * MEMBER4_FRONTEND.md.
 */

import type {
  IngestedRecord,
  IngestionRunSummary,
  PaginatedRecords,
  SourceStatus,
  StatsResponse,
} from "../types/dashboard";

export const mockStats: StatsResponse = {
  total_received: 30,
  total_processed: 24,
  total_duplicates: 6,
  total_failed: 0,
  last_run_status: "COMPLETED",
  last_run_timestamp: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
  last_run_duration_ms: 1520,
};

export const mockSources: SourceStatus[] = [
  {
    source: "Source A",
    status: "HEALTHY",
    last_success: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
    last_failure: null,
    records_received: 10,
    records_processed: 9,
  },
  {
    source: "Source B",
    status: "HEALTHY",
    last_success: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
    last_failure: null,
    records_received: 10,
    records_processed: 8,
  },
  {
    source: "Source C",
    status: "DEGRADED",
    last_success: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    last_failure: new Date(Date.now() - 60 * 1000).toISOString(),
    records_received: 10,
    records_processed: 7,
  },
];

export const mockRuns: IngestionRunSummary[] = [
  {
    run_id: 12,
    status: "COMPLETED",
    total_received: 30,
    total_processed: 24,
    total_duplicates: 6,
    total_failed: 0,
    duration_ms: 1520,
    started_at: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
    completed_at: new Date(Date.now() - 2 * 60 * 1000 + 1520).toISOString(),
    source_results: [
      { source: "Source A", status: "SUCCESS", received: 10, duration_ms: 480, error: null },
      { source: "Source B", status: "SUCCESS", received: 10, duration_ms: 510, error: null },
      { source: "Source C", status: "SUCCESS", received: 10, duration_ms: 530, error: null },
    ],
  },
  {
    run_id: 11,
    status: "PARTIAL",
    total_received: 28,
    total_processed: 20,
    total_duplicates: 5,
    total_failed: 3,
    duration_ms: 1780,
    started_at: new Date(Date.now() - 6 * 60 * 1000).toISOString(),
    completed_at: new Date(Date.now() - 6 * 60 * 1000 + 1780).toISOString(),
    source_results: [
      { source: "Source A", status: "SUCCESS", received: 10, duration_ms: 460, error: null },
      { source: "Source B", status: "SUCCESS", received: 9, duration_ms: 495, error: null },
      { source: "Source C", status: "FAILED", received: 0, duration_ms: 5000, error: "Timeout" },
    ],
  },
  {
    run_id: 10,
    status: "COMPLETED",
    total_received: 29,
    total_processed: 23,
    total_duplicates: 6,
    total_failed: 0,
    duration_ms: 1490,
    started_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
    completed_at: new Date(Date.now() - 10 * 60 * 1000 + 1490).toISOString(),
    source_results: [
      { source: "Source A", status: "SUCCESS", received: 10, duration_ms: 470, error: null },
      { source: "Source B", status: "SUCCESS", received: 9, duration_ms: 500, error: null },
      { source: "Source C", status: "SUCCESS", received: 10, duration_ms: 520, error: null },
    ],
  },
];

function mockRecord(i: number): IngestedRecord {
  const sources = ["Source A", "Source B", "Source C"];
  return {
    record_id: `rec_${1000 + i}`,
    name: `Sample Record ${i}`,
    email: `user${i}@example.com`,
    value: Math.round((Math.random() * 500 + 10) * 100) / 100,
    source: sources[i % sources.length],
    created_at: new Date(Date.now() - i * 45000).toISOString(),
    ingested_at: new Date(Date.now() - i * 40000).toISOString(),
  };
}

export function getMockRecords(page: number, pageSize: number): PaginatedRecords {
  const total = 87;
  const start = (page - 1) * pageSize;
  const records = Array.from(
    { length: Math.min(pageSize, Math.max(0, total - start)) },
    (_, idx) => mockRecord(start + idx)
  );
  return { page, page_size: pageSize, total, records };
}
