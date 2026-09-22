"""
Tests for the concurrent ingestion orchestrator — the most important
module in the backend.

Covers:
- Actual concurrent execution (timing-based proof, not just mocking).
- Per-source timeout handling.
- Retry behavior (bounded, not infinite).
- One source failing does not stop or cancel the others.
- Event generation (INGESTION_STARTED ... INGESTION_COMPLETED).
"""

import asyncio
import time

import pytest

from app.ingestion.events import EventBroadcaster
from app.ingestion.orchestrator import IngestionOrchestrator
from app.repositories.base import InMemoryRepository
from app.schemas.responses import (
    IngestionEvent,
    IngestionEventType,
    RunStatusEnum,
    SourceStatusEnum,
)


class FakeSource:
    """A controllable fake source for tests."""

    def __init__(self, name, delay=0.0, should_fail=False, fail_times=0, hang=False):
        self.name = name
        self.delay = delay
        self.should_fail = should_fail
        self.fail_times = fail_times  # number of times to fail before succeeding
        self.hang = hang
        self.call_count = 0

    async def fetch(self):
        self.call_count += 1
        if self.hang:
            await asyncio.sleep(9999)  # will be cut off by timeout
        if self.should_fail:
            raise RuntimeError(f"{self.name} always fails")
        if self.call_count <= self.fail_times:
            raise RuntimeError(f"{self.name} transient failure #{self.call_count}")
        await asyncio.sleep(self.delay)
        return [{"id": f"{self.name}-1", "source": self.name}]


class CollectingBroadcaster:
    """Collects every event broadcast during a run, for assertions."""

    def __init__(self):
        self.events: list[IngestionEvent] = []

    async def broadcast(self, event: IngestionEvent) -> None:
        self.events.append(event)


@pytest.mark.asyncio
async def test_sources_run_concurrently_not_sequentially():
    """THE MOST IMPORTANT TEST: prove sources run concurrently.

    A=1.0s, B=1.5s, C=0.8s. Sequential would take ~3.3s.
    Concurrent should take close to max(delays) ~= 1.5s.
    """
    sources = [
        FakeSource("A", delay=1.0),
        FakeSource("B", delay=1.5),
        FakeSource("C", delay=0.8),
    ]
    orchestrator = IngestionOrchestrator(timeout=5, max_retries=1, retry_delay=0.1)

    start = time.perf_counter()
    summary = await orchestrator.run(sources)
    elapsed = time.perf_counter() - start

    # Concurrent execution: should be well under the sequential sum (3.3s),
    # and close to the slowest single source (1.5s). Generous tolerance for
    # CI/sandbox scheduling jitter.
    assert elapsed < 2.2, f"Expected concurrent execution (~1.5s), took {elapsed:.2f}s"
    assert summary.status == RunStatusEnum.COMPLETED
    assert summary.total_received == 3


@pytest.mark.asyncio
async def test_source_timeout_does_not_crash_pipeline():
    sources = [
        FakeSource("A", delay=0.1),
        FakeSource("B", hang=True),  # will exceed the timeout
        FakeSource("C", delay=0.1),
    ]
    orchestrator = IngestionOrchestrator(timeout=0.5, max_retries=1, retry_delay=0.1)

    summary = await orchestrator.run(sources)

    results_by_source = {r.source: r for r in summary.source_results}
    assert results_by_source["A"].status == SourceStatusEnum.SUCCESS
    assert results_by_source["C"].status == SourceStatusEnum.SUCCESS
    assert results_by_source["B"].status == SourceStatusEnum.TIMEOUT
    assert summary.status == RunStatusEnum.PARTIAL


@pytest.mark.asyncio
async def test_retry_recovers_from_transient_failure():
    # Fails twice, succeeds on the 3rd attempt.
    source = FakeSource("Flaky", delay=0.0, fail_times=2)
    orchestrator = IngestionOrchestrator(timeout=2, max_retries=3, retry_delay=0.05)

    summary = await orchestrator.run([source])

    assert source.call_count == 3
    assert summary.source_results[0].status == SourceStatusEnum.SUCCESS


@pytest.mark.asyncio
async def test_retry_is_bounded_not_infinite():
    source = FakeSource("AlwaysFails", should_fail=True)
    orchestrator = IngestionOrchestrator(timeout=2, max_retries=3, retry_delay=0.01)

    summary = await orchestrator.run([source])

    assert source.call_count == 3  # exactly max_retries, not more
    assert summary.source_results[0].status == SourceStatusEnum.FAILED


@pytest.mark.asyncio
async def test_one_source_failure_does_not_stop_others():
    sources = [
        FakeSource("A", delay=0.1),
        FakeSource("B", should_fail=True),
        FakeSource("C", delay=0.1),
    ]
    orchestrator = IngestionOrchestrator(timeout=2, max_retries=1, retry_delay=0.01)

    summary = await orchestrator.run(sources)
    statuses = {r.source: r.status for r in summary.source_results}

    assert statuses["A"] == SourceStatusEnum.SUCCESS
    assert statuses["B"] == SourceStatusEnum.FAILED
    assert statuses["C"] == SourceStatusEnum.SUCCESS
    assert summary.status == RunStatusEnum.PARTIAL


@pytest.mark.asyncio
async def test_simulate_failure_query_param_forces_a_source_to_fail():
    sources = [FakeSource("A", delay=0.05), FakeSource("B", delay=0.05)]
    orchestrator = IngestionOrchestrator(timeout=2, max_retries=1, retry_delay=0.01)

    summary = await orchestrator.run(sources, simulate_failure="B")
    statuses = {r.source: r.status for r in summary.source_results}

    assert statuses["A"] == SourceStatusEnum.SUCCESS
    assert statuses["B"] == SourceStatusEnum.FAILED


@pytest.mark.asyncio
async def test_ingestion_events_are_emitted_in_order():
    broadcaster = CollectingBroadcaster()
    sources = [FakeSource("A", delay=0.05), FakeSource("B", delay=0.05)]
    orchestrator = IngestionOrchestrator(
        timeout=2, max_retries=1, retry_delay=0.01, broadcaster=broadcaster
    )

    await orchestrator.run(sources)
    event_types = [e.event for e in broadcaster.events]

    assert event_types[0] == IngestionEventType.INGESTION_STARTED
    assert event_types[-1] == IngestionEventType.INGESTION_COMPLETED
    assert event_types.count(IngestionEventType.SOURCE_STARTED) == 2
    assert event_types.count(IngestionEventType.SOURCE_COMPLETED) == 2


@pytest.mark.asyncio
async def test_run_persists_summary_via_repository():
    repo = InMemoryRepository()
    sources = [FakeSource("A", delay=0.01)]
    orchestrator = IngestionOrchestrator(
        timeout=2, max_retries=1, retry_delay=0.01, repository=repo
    )

    summary = await orchestrator.run(sources)
    stored = await repo.get_run(summary.run_id)

    assert stored is not None
    assert stored.run_id == summary.run_id
    assert stored.status == RunStatusEnum.COMPLETED


@pytest.mark.asyncio
async def test_duration_is_measured_not_hardcoded():
    source = FakeSource("A", delay=0.3)
    orchestrator = IngestionOrchestrator(timeout=2, max_retries=1, retry_delay=0.01)

    summary = await orchestrator.run([source])

    # duration should reflect the ~0.3s sleep, not a fixed/fake number.
    assert 250 <= summary.duration_ms <= 900
