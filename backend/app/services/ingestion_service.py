"""
Ingestion service — sits between the HTTP route and the orchestrator.

Keeps routes.py thin: routes just call into this service, which owns
constructing the orchestrator with the right sources/config and running it
as a background task so POST /api/ingest returns immediately.
"""

import logging
from typing import Optional

from app.api.websocket import manager as websocket_manager
from app.core.config import Settings
from app.ingestion.deduplicator import RecordDeduplicator
from app.ingestion.normalizer import RecordNormalizer
from app.ingestion.orchestrator import IngestionOrchestrator, next_run_id
from app.repositories.base import Repository
from app.schemas.responses import IngestionRunSummary
from app.sources import get_real_sources

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, settings: Settings, repository: Repository):
        self.settings = settings
        self.repository = repository

    def build_orchestrator(self) -> IngestionOrchestrator:
        return IngestionOrchestrator(
            timeout=self.settings.INGESTION_TIMEOUT,
            max_retries=self.settings.MAX_RETRIES,
            retry_delay=self.settings.RETRY_DELAY,
            broadcaster=websocket_manager,
            repository=self.repository,
            normalizer=RecordNormalizer(),
            deduplicator=RecordDeduplicator(),
        )

    async def start_run(self, simulate_failure: Optional[str] = None) -> int:
        """Reserve a run_id synchronously and kick off the actual ingestion
        as a background task, so the HTTP call returns immediately."""
        run_id = next_run_id()
        return run_id

    async def execute_run(self, run_id: int, simulate_failure: Optional[str] = None) -> IngestionRunSummary:
        """The actual long-running ingestion work. Called from a
        BackgroundTask (see app/api/routes.py) — NOT awaited directly by
        the HTTP handler."""
        orchestrator = self.build_orchestrator()
        sources = get_real_sources()
        try:
            return await orchestrator.run(sources, run_id=run_id, simulate_failure=simulate_failure)
        except Exception:  # noqa: BLE001
            logger.exception("Ingestion run %d crashed unexpectedly", run_id)
            raise
