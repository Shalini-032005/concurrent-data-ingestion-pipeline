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


# ---------------------------------------------------------------------------
# TEMPORARY IMPLEMENTATION
# Replace with a real PostgreSQL repository (SQLAlchemy + asyncpg).
# This in-memory version exists purely so Member 1's API is independently
# testable/demoable before Member 3's database layer is wired in.
# ---------------------------------------------------------------------------

class InMemoryRepository:
    """TEMPORARY IMPLEMENTATION — Replace with PostgreSQL repository."""

    def __init__(self) -> None:
        self._records: List[CanonicalRecord] = []
        self._runs: Dict[int, IngestionRunSummary] = {}
        self._sources: Dict[str, SourceStatus] = {}

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
