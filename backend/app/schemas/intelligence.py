"""
Pydantic models for Phase 1 Data Intelligence Platform endpoints.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Data Quality
# ---------------------------------------------------------------------------

class DataQualityResponse(BaseModel):
    overall_score: float = Field(..., description="Overall Data Quality Score (0-100)")
    completeness: float = Field(..., description="Completeness percentage (0-100)")
    validity: float = Field(..., description="Validity percentage (0-100)")
    consistency: float = Field(..., description="Consistency percentage (0-100)")
    uniqueness: float = Field(..., description="Uniqueness percentage (0-100)")
    freshness: float = Field(..., description="Freshness percentage (0-100)")
    timestamp: str = Field(..., description="ISO timestamp of computation")
    quality_by_source: Dict[str, float] = Field(default_factory=dict)
    details: Dict[str, Any] = Field(default_factory=dict)


class QualityTrendPoint(BaseModel):
    run_id: int
    timestamp: str
    overall_score: float
    completeness: float
    validity: float
    consistency: float
    uniqueness: float
    freshness: float


class QualityTrendResponse(BaseModel):
    trend: List[QualityTrendPoint] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Anomaly Detection
# ---------------------------------------------------------------------------

class AnomalySeverityEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AnomalyStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class AnomalyRecord(BaseModel):
    id: str
    run_id: Optional[int] = None
    record_id: Optional[str] = None
    source: str
    feature_name: str
    current_value: float
    expected_range: str
    severity: AnomalySeverityEnum
    reason: str
    status: AnomalyStatusEnum = AnomalyStatusEnum.ACTIVE
    timestamp: str


class AnomaliesSummary(BaseModel):
    total_anomalies: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0


class AnomaliesResponse(BaseModel):
    anomalies: List[AnomalyRecord] = Field(default_factory=list)
    summary: AnomaliesSummary = Field(default_factory=AnomaliesSummary)


# ---------------------------------------------------------------------------
# Pipeline Health
# ---------------------------------------------------------------------------

class PipelineHealthResponse(BaseModel):
    overall_score: float = Field(..., description="Pipeline Health Score (0-100)")
    availability: float = Field(..., description="Availability percentage (0-100)")
    latency: float = Field(..., description="Latency score (0-100)")
    validation: float = Field(..., description="Validation success score (0-100)")
    reliability: float = Field(..., description="Reliability score (0-100)")
    status: str = Field("HEALTHY", description="HEALTHY, DEGRADED, or CRITICAL")
    updated_at: str


# ---------------------------------------------------------------------------
# Intelligent Alerts
# ---------------------------------------------------------------------------

class AlertSeverityEnum(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class AlertItem(BaseModel):
    id: str
    severity: AlertSeverityEnum
    title: str
    description: str
    source: str
    timestamp: str
    status: AlertStatusEnum = AlertStatusEnum.ACTIVE
    run_id: Optional[int] = None
    record_id: Optional[str] = None


class AlertsResponse(BaseModel):
    alerts: List[AlertItem] = Field(default_factory=list)
    active_count: int = 0


class AlertUpdateRequest(BaseModel):
    status: AlertStatusEnum


# ---------------------------------------------------------------------------
# Data Lineage
# ---------------------------------------------------------------------------

class LineageStep(BaseModel):
    stage: str  # SOURCE, RAW_INGESTION, VALIDATION, NORMALIZATION, DEDUPLICATION, STORAGE
    status: str  # SUCCESS, FAILED, SKIPPED, DUPLICATE
    timestamp: str
    details: Dict[str, Any] = Field(default_factory=dict)


class RecordLineageResponse(BaseModel):
    record_id: str
    source: str
    run_id: Optional[int] = None
    received_at: Optional[str] = None
    final_status: str
    steps: List[LineageStep] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Run Replay
# ---------------------------------------------------------------------------

class RunReplayRequest(BaseModel):
    source_name: Optional[str] = None


class RunReplayResponse(BaseModel):
    replay_run_id: int
    original_run_id: int
    status: str
    message: str


# ---------------------------------------------------------------------------
# Run Comparison ("What Changed?")
# ---------------------------------------------------------------------------

class MetricChange(BaseModel):
    name: str
    latest_value: float
    previous_value: float
    absolute_change: float
    percent_change: float
    status: str  # IMPROVED, DEGRADED, NEUTRAL


class RunComparisonResponse(BaseModel):
    latest_run_id: int
    previous_run_id: int
    records_change: MetricChange
    duplicates_change: MetricChange
    validation_errors_change: MetricChange
    latency_change: MetricChange
    quality_change: MetricChange
    anomalies_change: MetricChange
