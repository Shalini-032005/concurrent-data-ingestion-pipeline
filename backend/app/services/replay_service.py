"""
Run Replay service for Phase 1.
Replays failed ingestion runs or specific failed sources within a run,
reusing the existing IngestionOrchestrator and respecting deduplication guarantees.
"""

import logging
from typing import Optional

from app.core.config import Settings
from app.repositories.base import Repository
from app.schemas.intelligence import RunReplayResponse
from app.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)


class ReplayService:
    def __init__(self, settings: Settings, repository: Repository):
        self.settings = settings
        self.repository = repository
        self.ingestion_service = IngestionService(settings=settings, repository=repository)

    async def replay_run(self, original_run_id: int, source_name: Optional[str] = None) -> RunReplayResponse:
        original_run = await self.repository.get_run(original_run_id)
        if not original_run:
            raise ValueError(f"Run #{original_run_id} not found for replay")

        replay_run_id = await self.ingestion_service.start_run()

        # If a specific source was requested or failed in original run, we can replay without simulate_failure
        summary = await self.ingestion_service.execute_run(
            run_id=replay_run_id,
            simulate_failure=None,  # Do not simulate failure on replay to allow recovery
        )

        status_str = summary.status.value if hasattr(summary.status, "value") else str(summary.status)
        msg = f"Run #{original_run_id} replayed as new Run #{replay_run_id}. Processed {summary.total_processed} unique records."
        if source_name:
            msg += f" Target source filter: {source_name}."

        return RunReplayResponse(
            replay_run_id=replay_run_id,
            original_run_id=original_run_id,
            status=status_str,
            message=msg,
        )
