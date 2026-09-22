"""
Stats/read service — thin wrapper around the Repository for GET endpoints.

Exists mainly so routes.py doesn't call repository methods directly,
keeping a consistent "route -> service -> repository" layering even
though today this is a near pass-through onto InMemoryRepository (and
later PostgresRepository).
"""

from typing import Any, Dict, List, Optional

from app.repositories.base import Repository
from app.schemas.responses import IngestionRunSummary, SourceStatus, StatsResponse


class StatsService:
    def __init__(self, repository: Repository):
        self.repository = repository

    async def get_stats(self) -> StatsResponse:
        return await self.repository.get_stats()

    async def get_sources(self) -> List[SourceStatus]:
        return await self.repository.get_sources()

    async def get_records(
        self, page: int = 1, page_size: int = 20, source: Optional[str] = None
    ) -> Dict[str, Any]:
        return await self.repository.get_records(page=page, page_size=page_size, source=source)

    async def get_runs(self) -> List[IngestionRunSummary]:
        return await self.repository.get_runs()

    async def get_run(self, run_id: int) -> Optional[IngestionRunSummary]:
        return await self.repository.get_run(run_id)
