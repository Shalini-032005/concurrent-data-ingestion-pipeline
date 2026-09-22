/**
 * Centralized HTTP client for the ingestion backend (Member 1's FastAPI
 * service). No component should call fetch()/axios directly — go through
 * the functions here so the base URL, error handling, and mock fallback
 * all live in one place.
 */

import { config } from "../config";
import {
  getMockRecords,
  mockRuns,
  mockSources,
  mockStats,
} from "./mockData";
import type {
  AlertItem,
  AlertsResponse,
  AlertStatus,
  AnomaliesResponse,
  AnomalyRecord,
  DataQualityResponse,
  IngestionRunSummary,
  IngestStartResponse,
  PaginatedRecords,
  PipelineHealthResponse,
  QualityTrendResponse,
  RecordLineageResponse,
  RunComparisonResponse,
  RunReplayResponse,
  SourceStatus,
  StatsResponse,
} from "../types/dashboard";

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${config.apiUrl}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError("Could not reach the ingestion API.");
  }

  if (!response.ok) {
    throw new ApiError(
      `Request to ${path} failed (${response.status})`,
      response.status
    );
  }

  return (await response.json()) as T;
}

export const api = {
  async getStats(): Promise<StatsResponse> {
    if (config.useMockData) return mockStats;
    return request<StatsResponse>("/api/stats");
  },

  async getSources(): Promise<SourceStatus[]> {
    if (config.useMockData) return mockSources;
    return request<SourceStatus[]>("/api/sources");
  },

  async getRecords(
    page: number,
    pageSize: number,
    source?: string
  ): Promise<PaginatedRecords> {
    if (config.useMockData) return getMockRecords(page, pageSize);
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (source) params.set("source", source);
    return request<PaginatedRecords>(`/api/records?${params.toString()}`);
  },

  async getRuns(): Promise<IngestionRunSummary[]> {
    if (config.useMockData) return mockRuns;
    return request<IngestionRunSummary[]>("/api/runs");
  },

  async getRun(runId: number): Promise<IngestionRunSummary> {
    if (config.useMockData) {
      const run = mockRuns.find((r) => r.run_id === runId);
      if (!run) throw new ApiError(`Run ${runId} not found`, 404);
      return run;
    }
    return request<IngestionRunSummary>(`/api/runs/${runId}`);
  },

  async startIngestion(simulateFailure?: string): Promise<IngestStartResponse> {
    if (config.useMockData) {
      return { run_id: mockRuns[0].run_id + 1, status: "RUNNING" };
    }
    const params = simulateFailure
      ? `?simulate_failure=${encodeURIComponent(simulateFailure)}`
      : "";
    return request<IngestStartResponse>(`/api/ingest${params}`, {
      method: "POST",
    });
  },

  // Phase 1 Data Intelligence API Endpoints
  async getQuality(): Promise<DataQualityResponse> {
    return request<DataQualityResponse>("/api/quality");
  },

  async getQualityTrend(limit = 20): Promise<QualityTrendResponse> {
    return request<QualityTrendResponse>(`/api/quality/trend?limit=${limit}`);
  },

  async getAnomalies(source?: string, severity?: string): Promise<AnomaliesResponse> {
    const params = new URLSearchParams();
    if (source) params.set("source", source);
    if (severity) params.set("severity", severity);
    const query = params.toString() ? `?${params.toString()}` : "";
    return request<AnomaliesResponse>(`/api/anomalies${query}`);
  },

  async getAnomaly(anomalyId: string): Promise<AnomalyRecord> {
    return request<AnomalyRecord>(`/api/anomalies/${anomalyId}`);
  },

  async getPipelineHealth(): Promise<PipelineHealthResponse> {
    return request<PipelineHealthResponse>("/api/health/pipeline");
  },

  async getAlerts(status?: string): Promise<AlertsResponse> {
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    return request<AlertsResponse>(`/api/alerts${query}`);
  },

  async updateAlertStatus(alertId: string, status: AlertStatus): Promise<AlertItem> {
    return request<AlertItem>(`/api/alerts/${alertId}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  },

  async getLineage(recordId: string): Promise<RecordLineageResponse> {
    return request<RecordLineageResponse>(`/api/lineage/${encodeURIComponent(recordId)}`);
  },

  async replayRun(runId: number, sourceName?: string): Promise<RunReplayResponse> {
    return request<RunReplayResponse>(`/api/runs/${runId}/replay`, {
      method: "POST",
      body: JSON.stringify({ source_name: sourceName || null }),
    });
  },

  async getRunComparison(latestId?: number, previousId?: number): Promise<RunComparisonResponse> {
    if (latestId && previousId) {
      return request<RunComparisonResponse>(`/api/runs/${latestId}/compare/${previousId}`);
    }
    return request<RunComparisonResponse>("/api/runs/compare");
  },
};

