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
  IngestionRunSummary,
  IngestStartResponse,
  PaginatedRecords,
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
};
