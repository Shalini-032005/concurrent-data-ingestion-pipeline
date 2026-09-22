"""
REST API routes for Phase 1 Data Intelligence features:
- Data Quality Engine
- ML Anomaly Detection & Explanations
- Pipeline Health Score
- Intelligent Alert Center
- Data Lineage
- Run Replay
- "What Changed?" Run Comparison
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import Settings, get_settings
from app.repositories.base import Repository
from app.schemas.intelligence import (
    AlertItem,
    AlertsResponse,
    AlertStatusEnum,
    AlertUpdateRequest,
    AnomaliesResponse,
    AnomalyRecord,
    DataQualityResponse,
    PipelineHealthResponse,
    QualityTrendResponse,
    RecordLineageResponse,
    RunComparisonResponse,
    RunReplayRequest,
    RunReplayResponse,
)
from app.services.alert_service import AlertService
from app.services.anomaly_service import AnomalyService
from app.services.comparison_service import ComparisonService
from app.services.data_quality_service import DataQualityService
from app.services.dependencies import get_repository
from app.services.lineage_service import LineageService
from app.services.pipeline_health_service import PipelineHealthService
from app.services.replay_service import ReplayService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["intelligence"])


# Dependencies
def get_quality_service(repo: Repository = Depends(get_repository)) -> DataQualityService:
    return DataQualityService(repository=repo)


def get_anomaly_service(repo: Repository = Depends(get_repository)) -> AnomalyService:
    return AnomalyService(repository=repo)


def get_health_service(repo: Repository = Depends(get_repository)) -> PipelineHealthService:
    return PipelineHealthService(repository=repo)


def get_alert_service(repo: Repository = Depends(get_repository)) -> AlertService:
    return AlertService(repository=repo)


def get_lineage_service(repo: Repository = Depends(get_repository)) -> LineageService:
    return LineageService(repository=repo)


def get_replay_service(
    settings: Settings = Depends(get_settings),
    repo: Repository = Depends(get_repository),
) -> ReplayService:
    return ReplayService(settings=settings, repository=repo)


def get_comparison_service(repo: Repository = Depends(get_repository)) -> ComparisonService:
    return ComparisonService(repository=repo)


# ---------------------------------------------------------------------------
# Feature 1 — Data Quality Engine
# ---------------------------------------------------------------------------

@router.get("/api/quality", response_model=DataQualityResponse)
async def get_quality(service: DataQualityService = Depends(get_quality_service)) -> DataQualityResponse:
    return await service.get_summary()


@router.get("/api/quality/summary", response_model=DataQualityResponse)
async def get_quality_summary(service: DataQualityService = Depends(get_quality_service)) -> DataQualityResponse:
    return await service.get_summary()


@router.get("/api/quality/trend", response_model=QualityTrendResponse)
async def get_quality_trend(
    limit: int = Query(default=20, ge=1, le=100),
    service: DataQualityService = Depends(get_quality_service),
) -> QualityTrendResponse:
    return await service.get_trend(limit=limit)


# ---------------------------------------------------------------------------
# Feature 2 — ML Anomaly Detection
# ---------------------------------------------------------------------------

@router.get("/api/anomalies", response_model=AnomaliesResponse)
async def get_anomalies(
    source: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    service: AnomalyService = Depends(get_anomaly_service),
) -> AnomaliesResponse:
    return await service.get_anomalies(source=source, severity=severity)


@router.get("/api/anomalies/summary", response_model=AnomaliesResponse)
async def get_anomalies_summary(service: AnomalyService = Depends(get_anomaly_service)) -> AnomaliesResponse:
    return await service.get_anomalies()


@router.get("/api/anomalies/{anomaly_id}", response_model=AnomalyRecord)
async def get_anomaly(
    anomaly_id: str, service: AnomalyService = Depends(get_anomaly_service)
) -> AnomalyRecord:
    anomaly = await service.get_anomaly_by_id(anomaly_id)
    if not anomaly:
        raise HTTPException(status_code=404, detail=f"Anomaly '{anomaly_id}' not found")
    return anomaly


# ---------------------------------------------------------------------------
# Feature 3 — Pipeline Health Score
# ---------------------------------------------------------------------------

@router.get("/api/health/pipeline", response_model=PipelineHealthResponse)
async def get_pipeline_health(
    service: PipelineHealthService = Depends(get_health_service),
) -> PipelineHealthResponse:
    return await service.get_health()


# ---------------------------------------------------------------------------
# Feature 4 — Intelligent Alert Center
# ---------------------------------------------------------------------------

@router.get("/api/alerts", response_model=AlertsResponse)
async def get_alerts(
    status: Optional[str] = Query(default=None),
    service: AlertService = Depends(get_alert_service),
) -> AlertsResponse:
    return await service.get_alerts(status=status)


@router.get("/api/alerts/{alert_id}", response_model=AlertItem)
async def get_alert(
    alert_id: str, service: AlertService = Depends(get_alert_service)
) -> AlertItem:
    res = await service.get_alerts()
    for a in res.alerts:
        if a.id == alert_id:
            return a
    raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")


@router.patch("/api/alerts/{alert_id}", response_model=AlertItem)
async def update_alert(
    alert_id: str,
    payload: AlertUpdateRequest,
    service: AlertService = Depends(get_alert_service),
) -> AlertItem:
    updated = await service.update_alert_status(alert_id, payload.status)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# Feature 5 — Data Lineage
# ---------------------------------------------------------------------------

@router.get("/api/lineage/{record_id}", response_model=RecordLineageResponse)
async def get_lineage(
    record_id: str, service: LineageService = Depends(get_lineage_service)
) -> RecordLineageResponse:
    lineage = await service.get_lineage(record_id)
    if not lineage:
        raise HTTPException(status_code=404, detail=f"Data lineage for record '{record_id}' not found")
    return lineage


# ---------------------------------------------------------------------------
# Feature 6 — Run Replay
# ---------------------------------------------------------------------------

@router.post("/api/runs/{run_id}/replay", response_model=RunReplayResponse)
async def replay_run(
    run_id: int,
    payload: Optional[RunReplayRequest] = None,
    service: ReplayService = Depends(get_replay_service),
) -> RunReplayResponse:
    source_filter = payload.source_name if payload else None
    try:
        return await service.replay_run(original_run_id=run_id, source_name=source_filter)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))


# ---------------------------------------------------------------------------
# Feature 7 — "What Changed?" Run Comparison
# ---------------------------------------------------------------------------

@router.get("/api/runs/compare", response_model=RunComparisonResponse)
async def compare_latest_runs(
    service: ComparisonService = Depends(get_comparison_service),
) -> RunComparisonResponse:
    try:
        return await service.compare_runs()
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get("/api/runs/{latest_id}/compare/{previous_id}", response_model=RunComparisonResponse)
async def compare_specific_runs(
    latest_id: int,
    previous_id: int,
    service: ComparisonService = Depends(get_comparison_service),
) -> RunComparisonResponse:
    try:
        return await service.compare_runs(latest_run_id=latest_id, previous_run_id=previous_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
