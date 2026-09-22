"""
Database/repository contract (Member 3).

The orchestrator and services depend ONLY on this Protocol, never on
SQLAlchemy models or session internals directly. Member 3 should implement
a concrete `PostgresRepository` (e.g. in app/repositories/postgres.py) that
satisfies this interface, backed by SQLAlchemy + asyncpg, and wire it in at
app/services/dependencies.py (see get_repository()).

Until that lands, `InMemoryRepository` (below) is used so the API is fully
testable end-to-end without a live database.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from app.schemas.responses import (
    CanonicalRecord,
    IngestionRunSummary,
    SourceStatus,
    StatsResponse,
)
from app.schemas.intelligence import (
    AlertItem,
    AlertStatusEnum,
    AnomalyRecord,
    DataQualityResponse,
    LineageStep,
    PipelineHealthResponse,
    QualityTrendPoint,
    RecordLineageResponse,
)


@runtime_checkable
class Repository(Protocol):
    """Persistence contract. All methods are async."""

    async def save_records(self, records: List[CanonicalRecord]) -> None:
        """Persist a batch of unique, normalized records."""
        ...

    async def save_ingestion_run(self, run: IngestionRunSummary) -> None:
        """Persist (or upsert) a completed/updated ingestion run summary."""
        ...

    async def update_source_status(self, status: SourceStatus) -> None:
        """Update the last-known health/stat snapshot for one source."""
        ...

    async def get_stats(self) -> StatsResponse:
        """Return aggregated statistics across all runs."""
        ...

    async def get_sources(self) -> List[SourceStatus]:
        """Return the latest known status for every source."""
        ...

    async def get_records(
        self, page: int = 1, page_size: int = 20, source: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return a paginated, optionally source-filtered list of records.

        Expected return shape:
            {"page": int, "page_size": int, "total": int, "records": [...]}
        """
        ...

    async def get_runs(self) -> List[IngestionRunSummary]:
        """Return all previous ingestion runs, most recent first."""
        ...

    async def get_run(self, run_id: int) -> Optional[IngestionRunSummary]:
        """Return a single ingestion run by id, or None if not found."""
        ...

    # Phase 1 Data Intelligence Extensions
    async def save_quality_metrics(self, metrics: DataQualityResponse, run_id: Optional[int] = None) -> None:
        ...

    async def get_latest_quality_metrics(self) -> Optional[DataQualityResponse]:
        ...

    async def get_quality_trend(self, limit: int = 20) -> List[QualityTrendPoint]:
        ...

    async def save_anomalies(self, anomalies: List[AnomalyRecord]) -> None:
        ...

    async def get_anomalies(
        self, source: Optional[str] = None, severity: Optional[str] = None
    ) -> List[AnomalyRecord]:
        ...

    async def get_anomaly(self, anomaly_id: str) -> Optional[AnomalyRecord]:
        ...

    async def save_alerts(self, alerts: List[AlertItem]) -> None:
        ...

    async def get_alerts(self, status: Optional[str] = None) -> List[AlertItem]:
        ...

    async def update_alert_status(self, alert_id: str, status: AlertStatusEnum) -> Optional[AlertItem]:
        ...

    async def save_pipeline_health(self, health: PipelineHealthResponse) -> None:
        ...

    async def get_latest_pipeline_health(self) -> Optional[PipelineHealthResponse]:
        ...

    async def save_lineage_steps(
        self, record_id: str, source: str, run_id: Optional[int], steps: List[LineageStep]
    ) -> None:
        ...

    async def get_record_lineage(self, record_id: str) -> Optional[RecordLineageResponse]:
        ...


# ---------------------------------------------------------------------------
# IN-MEMORY IMPLEMENTATION
# ---------------------------------------------------------------------------

class InMemoryRepository:
    """InMemoryRepository with Phase 1 Data Intelligence support."""

    def __init__(self) -> None:
        self._records: List[CanonicalRecord] = []
        self._runs: Dict[int, IngestionRunSummary] = {}
        self._sources: Dict[str, SourceStatus] = {}

        # Phase 1 storage structures
        self._quality_history: List[Dict[str, Any]] = []
        self._anomalies: Dict[str, AnomalyRecord] = {}
        self._alerts: Dict[str, AlertItem] = {}
        self._pipeline_health: Optional[PipelineHealthResponse] = None
        self._lineage: Dict[str, RecordLineageResponse] = {}

    async def save_records(self, records: List[CanonicalRecord]) -> None:
        self._records.extend(records)

    async def save_ingestion_run(self, run: IngestionRunSummary) -> None:
        self._runs[run.run_id] = run

    async def update_source_status(self, status: SourceStatus) -> None:
        self._sources[status.source] = status

    async def get_stats(self) -> StatsResponse:
        if not self._runs:
            return StatsResponse()

        last_run = max(self._runs.values(), key=lambda r: r.run_id)
        return StatsResponse(
            total_received=sum(r.total_received for r in self._runs.values()),
            total_processed=sum(r.total_processed for r in self._runs.values()),
            total_duplicates=sum(r.total_duplicates for r in self._runs.values()),
            total_failed=sum(r.total_failed for r in self._runs.values()),
            last_run_status=last_run.status.value if hasattr(last_run.status, "value") else str(last_run.status),
            last_run_timestamp=last_run.completed_at or last_run.started_at,
            last_run_duration_ms=last_run.duration_ms,
        )

    async def get_sources(self) -> List[SourceStatus]:
        return list(self._sources.values())

    async def get_records(
        self, page: int = 1, page_size: int = 20, source: Optional[str] = None
    ) -> Dict[str, Any]:
        filtered = [
            r.model_dump() for r in self._records if source is None or r.source == source
        ]
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "page": page,
            "page_size": page_size,
            "total": len(filtered),
            "records": filtered[start:end],
        }

    async def get_runs(self) -> List[IngestionRunSummary]:
        return sorted(self._runs.values(), key=lambda r: r.run_id, reverse=True)

    async def get_run(self, run_id: int) -> Optional[IngestionRunSummary]:
        return self._runs.get(run_id)

    # Phase 1 Data Intelligence Implementation
    async def save_quality_metrics(self, metrics: DataQualityResponse, run_id: Optional[int] = None) -> None:
        self._quality_history.append({"run_id": run_id, "metrics": metrics})

    async def get_latest_quality_metrics(self) -> Optional[DataQualityResponse]:
        if not self._quality_history:
            return None
        return self._quality_history[-1]["metrics"]

    async def get_quality_trend(self, limit: int = 20) -> List[QualityTrendPoint]:
        points: List[QualityTrendPoint] = []
        for idx, item in enumerate(self._quality_history[-limit:]):
            m: DataQualityResponse = item["metrics"]
            points.append(
                QualityTrendPoint(
                    run_id=item["run_id"] or (idx + 1),
                    timestamp=m.timestamp,
                    overall_score=m.overall_score,
                    completeness=m.completeness,
                    validity=m.validity,
                    consistency=m.consistency,
                    uniqueness=m.uniqueness,
                    freshness=m.freshness,
                )
            )
        return points

    async def save_anomalies(self, anomalies: List[AnomalyRecord]) -> None:
        for anomaly in anomalies:
            self._anomalies[anomaly.id] = anomaly

    async def get_anomalies(
        self, source: Optional[str] = None, severity: Optional[str] = None
    ) -> List[AnomalyRecord]:
        result = list(self._anomalies.values())
        if source:
            result = [a for a in result if a.source == source]
        if severity:
            result = [a for a in result if (a.severity.value if hasattr(a.severity, "value") else str(a.severity)) == severity]
        return sorted(result, key=lambda a: a.timestamp, reverse=True)

    async def get_anomaly(self, anomaly_id: str) -> Optional[AnomalyRecord]:
        return self._anomalies.get(anomaly_id)

    async def save_alerts(self, alerts: List[AlertItem]) -> None:
        for alert in alerts:
            self._alerts[alert.id] = alert

    async def get_alerts(self, status: Optional[str] = None) -> List[AlertItem]:
        result = list(self._alerts.values())
        if status:
            result = [a for a in result if (a.status.value if hasattr(a.status, "value") else str(a.status)) == status]
        return sorted(result, key=lambda a: a.timestamp, reverse=True)

    async def update_alert_status(self, alert_id: str, status: AlertStatusEnum) -> Optional[AlertItem]:
        if alert_id in self._alerts:
            alert = self._alerts[alert_id]
            updated = alert.model_copy(update={"status": status})
            self._alerts[alert_id] = updated
            return updated
        return None

    async def save_pipeline_health(self, health: PipelineHealthResponse) -> None:
        self._pipeline_health = health

    async def get_latest_pipeline_health(self) -> Optional[PipelineHealthResponse]:
        return self._pipeline_health

    async def save_lineage_steps(
        self, record_id: str, source: str, run_id: Optional[int], steps: List[LineageStep]
    ) -> None:
        received_at = steps[0].timestamp if steps else ""
        final_status = steps[-1].status if steps else "UNKNOWN"
        self._lineage[record_id] = RecordLineageResponse(
            record_id=record_id,
            source=source,
            run_id=run_id,
            received_at=received_at,
            final_status=final_status,
            steps=steps,
        )

    async def get_record_lineage(self, record_id: str) -> Optional[RecordLineageResponse]:
        return self._lineage.get(record_id)

