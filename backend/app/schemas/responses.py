"""
Shared Pydantic models used across the API, orchestrator, and event system.

These are the "shapes" that other teammates should treat as the contract:
- Member 2 (sources/normalization/dedup) produces/consumes CanonicalRecord,
  SourceResult.
- Member 3 (database) persists CanonicalRecord / IngestionRun and returns
  StatsResponse / SourceStatus / IngestionRunSummary shaped data.
- Member 4 (frontend) consumes IngestionEvent over the WebSocket and the
  REST response models below over HTTP.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Status enums
# ---------------------------------------------------------------------------

class SourceStatusEnum(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class RunStatusEnum(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Source-level result (Phase 7)
# ---------------------------------------------------------------------------

class SourceResult(BaseModel):
    """Standard result object returned by the orchestrator for one source."""
    source: str
    status: SourceStatusEnum
    records: List[Dict[str, Any]] = Field(default_factory=list)
    received: int = 0
    duration_ms: float = 0.0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Canonical record (Phase 17 — Normalizer contract)
# ---------------------------------------------------------------------------

class CanonicalRecord(BaseModel):
    """
    The normalized shape every record should be in after Member 2's
    normalizer has processed it, and before it reaches the deduplicator /
    database layer.
    """
    record_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    value: Optional[float] = None
    source: str
    created_at: Optional[str] = None
    ingested_at: str = Field(default_factory=utcnow_iso)

    model_config = ConfigDict(extra="allow")  # tolerate extra source-specific fields


# ---------------------------------------------------------------------------
# Ingestion run summary (Phase 10)
# ---------------------------------------------------------------------------

class IngestionRunSummary(BaseModel):
    run_id: int
    status: RunStatusEnum
    total_received: int = 0
    total_processed: int = 0
    total_duplicates: int = 0
    total_failed: int = 0
    duration_ms: float = 0.0
    started_at: str
    completed_at: Optional[str] = None
    source_results: List[SourceResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Events (Phase 12)
# ---------------------------------------------------------------------------

class IngestionEventType(str, Enum):
    INGESTION_STARTED = "INGESTION_STARTED"
    SOURCE_STARTED = "SOURCE_STARTED"
    SOURCE_COMPLETED = "SOURCE_COMPLETED"
    SOURCE_FAILED = "SOURCE_FAILED"
    INGESTION_COMPLETED = "INGESTION_COMPLETED"


class IngestionEvent(BaseModel):
    event: IngestionEventType
    run_id: int
    timestamp: str = Field(default_factory=utcnow_iso)
    source: Optional[str] = None
    records: Optional[int] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    status: Optional[str] = None

    def to_ws_message(self) -> Dict[str, Any]:
        """Drop None fields before sending over the wire."""
        return self.model_dump(exclude_none=True)


# ---------------------------------------------------------------------------
# REST response shapes
# ---------------------------------------------------------------------------

class RootResponse(BaseModel):
    message: str
    status: str


class HealthResponse(BaseModel):
    status: str


class IngestStartResponse(BaseModel):
    run_id: int
    status: RunStatusEnum


class StatsResponse(BaseModel):
    total_received: int = 0
    total_processed: int = 0
    total_duplicates: int = 0
    total_failed: int = 0
    last_run_status: Optional[str] = None
    last_run_timestamp: Optional[str] = None
    last_run_duration_ms: Optional[float] = None


class SourceHealthEnum(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


class SourceStatus(BaseModel):
    source: str
    status: SourceHealthEnum = SourceHealthEnum.UNKNOWN
    last_success: Optional[str] = None
    last_failure: Optional[str] = None
    records_received: int = 0
    records_processed: int = 0


class PaginatedRecords(BaseModel):
    page: int
    page_size: int
    total: int
    records: List[Dict[str, Any]]


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
