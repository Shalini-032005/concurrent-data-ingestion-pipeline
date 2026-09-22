"""
REST API routes. Kept thin — all logic lives in app/services/*.
"""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.core.config import Settings, get_settings
from app.repositories.base import Repository
from app.schemas.responses import (
    ErrorResponse,
    HealthResponse,
    IngestStartResponse,
    IngestionRunSummary,
    PaginatedRecords,
    RootResponse,
    RunStatusEnum,
    SourceStatus,
    StatsResponse,
)
from app.services.dependencies import get_repository
from app.services.ingestion_service import IngestionService
from app.services.stats_service import StatsService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_ingestion_service(
    settings: Settings = Depends(get_settings),
    repository: Repository = Depends(get_repository),
) -> IngestionService:
    return IngestionService(settings=settings, repository=repository)


def get_stats_service(repository: Repository = Depends(get_repository)) -> StatsService:
    return StatsService(repository=repository)


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

@router.get("/", response_model=RootResponse, tags=["meta"])
async def root() -> RootResponse:
    return RootResponse(message="Concurrent Data Ingestion Pipeline API", status="running")


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    return HealthResponse(status="healthy")


# ---------------------------------------------------------------------------
# POST /api/ingest
# ---------------------------------------------------------------------------

@router.post("/api/ingest", response_model=IngestStartResponse, tags=["ingestion"])
async def start_ingestion(
    background_tasks: BackgroundTasks,
    simulate_failure: Optional[str] = Query(
        default=None,
        description=(
            "DEV/DEMO ONLY: name of a source to force-fail for this run "
            "(e.g. 'Source B'), to demonstrate resilience. Never enable this "
            "in a real production deployment."
        ),
    ),
    service: IngestionService = Depends(get_ingestion_service),
) -> IngestStartResponse:
    """
    Starts an ingestion run without blocking the request. Progress is
    streamed over the /ws WebSocket; final results are available via
    GET /api/runs/{run_id} once complete.
    """
    run_id = await service.start_run(simulate_failure=simulate_failure)
    background_tasks.add_task(service.execute_run, run_id, simulate_failure)
    logger.info("Queued ingestion run %d (simulate_failure=%s)", run_id, simulate_failure)
    return IngestStartResponse(run_id=run_id, status=RunStatusEnum.RUNNING)


# ---------------------------------------------------------------------------
# GET /api/stats
# ---------------------------------------------------------------------------

@router.get("/api/stats", response_model=StatsResponse, tags=["stats"])
async def get_stats(service: StatsService = Depends(get_stats_service)) -> StatsResponse:
    return await service.get_stats()


# ---------------------------------------------------------------------------
# GET /api/sources
# ---------------------------------------------------------------------------

@router.get("/api/sources", response_model=list[SourceStatus], tags=["stats"])
async def get_sources(service: StatsService = Depends(get_stats_service)) -> list[SourceStatus]:
    return await service.get_sources()


# ---------------------------------------------------------------------------
# GET /api/records
# ---------------------------------------------------------------------------

@router.get("/api/records", response_model=PaginatedRecords, tags=["records"])
async def get_records(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    source: Optional[str] = Query(default=None, description="Filter by source name"),
    service: StatsService = Depends(get_stats_service),
) -> PaginatedRecords:
    result = await service.get_records(page=page, page_size=page_size, source=source)
    return PaginatedRecords(**result)


# ---------------------------------------------------------------------------
# GET /api/runs
# ---------------------------------------------------------------------------

@router.get("/api/runs", response_model=list[IngestionRunSummary], tags=["runs"])
async def get_runs(service: StatsService = Depends(get_stats_service)) -> list[IngestionRunSummary]:
    return await service.get_runs()


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}
# ---------------------------------------------------------------------------

@router.get(
    "/api/runs/{run_id}",
    response_model=IngestionRunSummary,
    responses={404: {"model": ErrorResponse}},
    tags=["runs"],
)
async def get_run(run_id: int, service: StatsService = Depends(get_stats_service)) -> IngestionRunSummary:
    run = await service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run
