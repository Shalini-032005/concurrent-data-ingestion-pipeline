"""
Concurrent ingestion orchestrator — THE MOST IMPORTANT MODULE.

Responsibilities:
- Run all configured sources CONCURRENTLY (asyncio.gather / tasks), never
  sequentially.
- Apply a per-source timeout.
- Apply a per-source retry policy (via app.ingestion.retry.retry_async).
- Guarantee that one source failing/timing out does NOT cancel or block
  the others (return_exceptions semantics).
- Measure real wall-clock duration per source and for the whole run using
  time.perf_counter() — never fake timings.
- Emit lifecycle events (INGESTION_STARTED, SOURCE_STARTED,
  SOURCE_COMPLETED, SOURCE_FAILED, INGESTION_COMPLETED) via an
  EventBroadcaster so the WebSocket layer can push live progress.
- Hand raw records off to a Normalizer and Deduplicator (both pluggable —
  see app/ingestion/interfaces.py) and to a Repository for persistence
  (see app/repositories/base.py). None of these are hardcoded — they are
  injected, so Members 2 and 3 can swap in their real implementations
  without touching this file.
"""

import asyncio
import itertools
import logging
import time
from typing import List, Optional

from app.ingestion.events import EventBroadcaster, NullBroadcaster
from app.ingestion.interfaces import (
    Deduplicator,
    IngestionSource,
    NoOpDeduplicator,
    Normalizer,
    PassthroughNormalizer,
)
from app.ingestion.retry import retry_async
from app.repositories.base import InMemoryRepository, Repository
from app.schemas.responses import (
    IngestionEvent,
    IngestionEventType,
    IngestionRunSummary,
    RunStatusEnum,
    SourceResult,
    SourceStatus,
    SourceStatusEnum,
    utcnow_iso,
)

logger = logging.getLogger(__name__)

_run_id_counter = itertools.count(1)


def next_run_id() -> int:
    return next(_run_id_counter)


class IngestionOrchestrator:
    """
    Orchestrates one concurrent ingestion run across many sources.

    Usage:
        orchestrator = IngestionOrchestrator(
            timeout=settings.INGESTION_TIMEOUT,
            max_retries=settings.MAX_RETRIES,
            retry_delay=settings.RETRY_DELAY,
            broadcaster=websocket_manager,   # optional
            repository=repository,           # optional, defaults to in-memory
            normalizer=normalizer,           # optional, defaults to passthrough
            deduplicator=deduplicator,       # optional, defaults to no-op
        )
        summary = await orchestrator.run(sources, simulate_failure="Source B")
    """

    def __init__(
        self,
        timeout: float = 5.0,
        max_retries: int = 3,
        retry_delay: float = 0.5,
        broadcaster: Optional[EventBroadcaster] = None,
        repository: Optional[Repository] = None,
        normalizer: Optional[Normalizer] = None,
        deduplicator: Optional[Deduplicator] = None,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.broadcaster: EventBroadcaster = broadcaster or NullBroadcaster()
        self.repository: Repository = repository or InMemoryRepository()
        self.normalizer: Normalizer = normalizer or PassthroughNormalizer()
        self.deduplicator: Deduplicator = deduplicator or NoOpDeduplicator()

    async def _emit(self, event: IngestionEvent) -> None:
        try:
            await self.broadcaster.broadcast(event)
        except Exception:  # noqa: BLE001
            # A broken WebSocket client must never break the ingestion run.
            logger.exception("Failed to broadcast event %s", event.event)

    async def _run_source(
        self, source: IngestionSource, run_id: int, simulate_failure: Optional[str]
    ) -> SourceResult:
        """Run a single source with timeout + retry, always returning a
        SourceResult (never raising) so asyncio.gather never has to deal
        with a raw exception from this coroutine."""
        start = time.perf_counter()
        await self._emit(
            IngestionEvent(
                event=IngestionEventType.SOURCE_STARTED,
                run_id=run_id,
                source=source.name,
            )
        )

        async def attempt() -> List[dict]:
            if simulate_failure and source.name == simulate_failure:
                raise RuntimeError(f"Simulated failure for {source.name}")
            async with asyncio.timeout(self.timeout):
                return await source.fetch()

        try:
            records = await retry_async(
                attempt,
                max_retries=self.max_retries,
                retry_delay=self.retry_delay,
                label=f"source:{source.name}",
            )
            duration_ms = (time.perf_counter() - start) * 1000
            result = SourceResult(
                source=source.name,
                status=SourceStatusEnum.SUCCESS,
                records=records,
                received=len(records),
                duration_ms=duration_ms,
                error=None,
            )
            logger.info(
                "Source %s completed: %d records in %.1fms",
                source.name, result.received, duration_ms,
            )
            await self._emit(
                IngestionEvent(
                    event=IngestionEventType.SOURCE_COMPLETED,
                    run_id=run_id,
                    source=source.name,
                    records=result.received,
                    duration_ms=duration_ms,
                )
            )
            return result

        except (TimeoutError, asyncio.TimeoutError):
            duration_ms = (time.perf_counter() - start) * 1000
            logger.warning("Source %s timed out after %.1fms", source.name, duration_ms)
            result = SourceResult(
                source=source.name,
                status=SourceStatusEnum.TIMEOUT,
                records=[],
                received=0,
                duration_ms=duration_ms,
                error=f"Timed out after {self.timeout}s",
            )
            await self._emit(
                IngestionEvent(
                    event=IngestionEventType.SOURCE_FAILED,
                    run_id=run_id,
                    source=source.name,
                    error=result.error,
                    duration_ms=duration_ms,
                )
            )
            return result

        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.perf_counter() - start) * 1000
            logger.warning("Source %s failed after %.1fms: %s", source.name, duration_ms, exc)
            result = SourceResult(
                source=source.name,
                status=SourceStatusEnum.FAILED,
                records=[],
                received=0,
                duration_ms=duration_ms,
                error=str(exc),
            )
            await self._emit(
                IngestionEvent(
                    event=IngestionEventType.SOURCE_FAILED,
                    run_id=run_id,
                    source=source.name,
                    error=result.error,
                    duration_ms=duration_ms,
                )
            )
            return result

    async def run(
        self,
        sources: List[IngestionSource],
        run_id: Optional[int] = None,
        simulate_failure: Optional[str] = None,
    ) -> IngestionRunSummary:
        """
        Execute all sources CONCURRENTLY and return a run summary.

        `simulate_failure` (demo-only): pass a source name to force that
        one source to fail, to demonstrate resilience. Never wired to
        anything sensitive — see app/api/routes.py for how it's exposed.
        """
        run_id = run_id if run_id is not None else next_run_id()
        started_at = utcnow_iso()
        overall_start = time.perf_counter()

        logger.info("Ingestion run %d started with %d sources", run_id, len(sources))
        await self._emit(IngestionEvent(event=IngestionEventType.INGESTION_STARTED, run_id=run_id))

        # --- THE IMPORTANT PART: concurrent execution, not sequential ---
        tasks = [
            asyncio.create_task(self._run_source(source, run_id, simulate_failure))
            for source in sources
        ]
        source_results: List[SourceResult] = await asyncio.gather(*tasks, return_exceptions=False)
        # Note: _run_source never raises, so return_exceptions=False is safe
        # and lets type checkers know we always get SourceResult back.

        overall_duration_ms = (time.perf_counter() - overall_start) * 1000

        total_received = sum(r.received for r in source_results)
        total_failed = sum(1 for r in source_results if r.status != SourceStatusEnum.SUCCESS)

        # --- Hand off to normalization + deduplication (Member 2's contracts) ---
        all_raw_records = [rec for r in source_results for rec in r.records]
        normalized = self.normalizer.normalize(all_raw_records)
        unique_records, duplicate_count = self.deduplicator.process(normalized)

        # --- Persist (Member 3's contract) ---
        if unique_records:
            await self.repository.save_records(unique_records)

        for r in source_results:
            status_health = "HEALTHY" if r.status == SourceStatusEnum.SUCCESS else "DEGRADED"
            await self.repository.update_source_status(
                SourceStatus(
                    source=r.source,
                    status=status_health,  # type: ignore[arg-type]
                    last_success=utcnow_iso() if r.status == SourceStatusEnum.SUCCESS else None,
                    last_failure=utcnow_iso() if r.status != SourceStatusEnum.SUCCESS else None,
                    records_received=r.received,
                    records_processed=r.received,
                )
            )

        if total_failed == 0:
            run_status = RunStatusEnum.COMPLETED
        elif total_failed == len(sources):
            run_status = RunStatusEnum.FAILED
        else:
            run_status = RunStatusEnum.PARTIAL

        summary = IngestionRunSummary(
            run_id=run_id,
            status=run_status,
            total_received=total_received,
            total_processed=len(unique_records),
            total_duplicates=duplicate_count,
            total_failed=total_failed,
            duration_ms=overall_duration_ms,
            started_at=started_at,
            completed_at=utcnow_iso(),
            source_results=source_results,
        )

        await self.repository.save_ingestion_run(summary)

        # Trigger Phase 1 Data Intelligence computations automatically
        try:
            from app.services.data_quality_service import DataQualityService
            from app.services.anomaly_service import AnomalyService
            from app.services.pipeline_health_service import PipelineHealthService
            from app.services.alert_service import AlertService

            dq_service = DataQualityService(self.repository)
            await dq_service.calculate_quality(run_id=run_id)

            anom_service = AnomalyService(self.repository)
            await anom_service.scan_and_save_anomalies(run_id=run_id)

            health_service = PipelineHealthService(self.repository)
            await health_service.calculate_health()

            alert_service = AlertService(self.repository)
            await alert_service.scan_and_generate_alerts(run_summary=summary)
        except Exception:  # noqa: BLE001
            logger.exception("Data intelligence background computation failed for run %d", run_id)

        logger.info(
            "Ingestion run %d completed with status=%s in %.1fms "
            "(received=%d processed=%d duplicates=%d failed=%d)",
            run_id, run_status.value, overall_duration_ms,
            total_received, len(unique_records), duplicate_count, total_failed,
        )
        await self._emit(
            IngestionEvent(
                event=IngestionEventType.INGESTION_COMPLETED,
                run_id=run_id,
                status=run_status.value,
                duration_ms=overall_duration_ms,
            )
        )

        return summary

