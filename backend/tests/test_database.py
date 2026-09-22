"""
Database + repository tests (Member 3 — Phases 25-30).

These exercise the real PostgreSQL layer end-to-end (engine, tables,
constraints, repository methods) rather than mocking SQLAlchemy, so they
need an actual reachable Postgres instance — never SQLite, since the whole
point is verifying real Postgres behavior (ON CONFLICT, unique
constraints) that a SQLite substitute wouldn't faithfully reproduce.

Configure with:

    TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/ingestion_test

Point this at a disposable local/dev database — NEVER at production
Supabase (Phase 25 is explicit about this). If TEST_DATABASE_URL isn't
set, or the database isn't reachable, every test in this module is
skipped rather than failed, so `pytest` stays green in environments
without Postgres available (e.g. a fresh clone before `docker compose up`).
"""

import os
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from app.database.database import (
    check_database_connection,
    dispose_engine,
    get_engine,
    get_session_factory,
    init_db,
)
from app.database.models import Base
from app.repositories.postgres import DatabaseError, PostgresRepository
from app.schemas.responses import (
    CanonicalRecord,
    IngestionRunSummary,
    RunStatusEnum,
    SourceHealthEnum,
    SourceStatus,
)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


def _canonical(record_id: str, source: str, record_hash: str, email: str = None) -> CanonicalRecord:
    rec = CanonicalRecord(
        record_id=record_id,
        name=f"Name {record_id}",
        email=email or f"{record_id.lower()}@example.com",
        value=100.0,
        source=source,
        created_at=datetime.now(timezone.utc).isoformat(),
        ingested_at=datetime.now(timezone.utc).isoformat(),
    )
    rec.record_hash = record_hash  # type: ignore[attr-defined]
    return rec


async def _db_reachable() -> bool:
    if not TEST_DATABASE_URL:
        return False
    return await check_database_connection(TEST_DATABASE_URL)


requires_db = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL not set — skipping live Postgres tests",
)


@pytest_asyncio.fixture(scope="module")
async def db_available():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    if not await _db_reachable():
        pytest.skip(f"Could not connect to TEST_DATABASE_URL ({TEST_DATABASE_URL})")
    yield True
    await dispose_engine(TEST_DATABASE_URL)


@pytest_asyncio.fixture
async def repository(db_available):
    """Fresh, empty tables for every test."""
    engine = get_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_factory = get_session_factory(TEST_DATABASE_URL)
    repo = PostgresRepository(session_factory)
    yield repo

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# Connection + table creation
# ---------------------------------------------------------------------------

@requires_db
@pytest.mark.asyncio
async def test_database_connection(db_available):
    assert await check_database_connection(TEST_DATABASE_URL) is True


@requires_db
@pytest.mark.asyncio
async def test_init_db_creates_tables(db_available):
    await init_db(TEST_DATABASE_URL)
    engine = get_engine(TEST_DATABASE_URL)

    from sqlalchemy import inspect

    async with engine.connect() as conn:
        table_names = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())

    for expected in ("records", "sources", "ingestion_runs"):
        assert expected in table_names


# ---------------------------------------------------------------------------
# Records: insert, unique record_hash, duplicate handling (Phase 26-27)
# ---------------------------------------------------------------------------

@requires_db
@pytest.mark.asyncio
async def test_insert_record(repository):
    record = _canonical("A-001", "Source A", "hash-001")
    await repository.save_records([record])

    result = await repository.get_records()
    assert result["total"] == 1
    assert result["records"][0]["record_id"] == "A-001"
    assert result["records"][0]["record_hash"] == "hash-001"


@requires_db
@pytest.mark.asyncio
async def test_duplicate_record_hash_is_ignored_not_crashed(repository):
    """Phase 27: inserting the same record_hash twice must not crash the
    application, and must result in exactly ONE stored row."""
    first = _canonical("A-001", "Source A", "ABC123")
    duplicate = _canonical("A-001", "Source B", "ABC123")  # same hash, different source

    await repository.save_records([first])
    await repository.save_records([duplicate])  # must not raise

    result = await repository.get_records()
    assert result["total"] == 1


@requires_db
@pytest.mark.asyncio
async def test_duplicate_within_same_batch_is_ignored(repository):
    """Same guarantee, but both copies arrive in a single save_records() call."""
    batch = [
        _canonical("A-001", "Source A", "SAME-HASH"),
        _canonical("A-002", "Source A", "SAME-HASH"),
    ]
    await repository.save_records(batch)

    result = await repository.get_records()
    assert result["total"] == 1


@requires_db
@pytest.mark.asyncio
async def test_save_records_empty_list_is_a_noop(repository):
    await repository.save_records([])
    result = await repository.get_records()
    assert result["total"] == 0


@requires_db
@pytest.mark.asyncio
async def test_record_missing_hash_raises_database_error(repository):
    bad = CanonicalRecord(record_id="X-1", source="Source A")
    with pytest.raises(DatabaseError):
        await repository.save_records([bad])


# ---------------------------------------------------------------------------
# Ingestion runs: create + update (upsert), retrieval (Phase 15, 20-21)
# ---------------------------------------------------------------------------

def _run_summary(run_id: int, status: RunStatusEnum = RunStatusEnum.COMPLETED, **overrides) -> IngestionRunSummary:
    base = dict(
        run_id=run_id,
        status=status,
        total_received=10,
        total_processed=8,
        total_duplicates=2,
        total_failed=0,
        duration_ms=123.4,
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=datetime.now(timezone.utc).isoformat(),
        source_results=[],
    )
    base.update(overrides)
    return IngestionRunSummary(**base)


@requires_db
@pytest.mark.asyncio
async def test_create_ingestion_run(repository):
    await repository.save_ingestion_run(_run_summary(1))
    run = await repository.get_run(1)
    assert run is not None
    assert run.run_id == 1
    assert run.status == RunStatusEnum.COMPLETED


@requires_db
@pytest.mark.asyncio
async def test_update_ingestion_run_upserts_same_id(repository):
    """save_ingestion_run() is called once per run with the final summary —
    calling it again for the same run_id must UPDATE, not duplicate."""
    await repository.save_ingestion_run(_run_summary(2, status=RunStatusEnum.RUNNING, total_received=0))
    await repository.save_ingestion_run(_run_summary(2, status=RunStatusEnum.COMPLETED, total_received=50))

    run = await repository.get_run(2)
    assert run.status == RunStatusEnum.COMPLETED
    assert run.total_received == 50

    all_runs = await repository.get_runs()
    assert len([r for r in all_runs if r.run_id == 2]) == 1


@requires_db
@pytest.mark.asyncio
async def test_get_run_not_found_returns_none(repository):
    assert await repository.get_run(999) is None


@requires_db
@pytest.mark.asyncio
async def test_get_runs_most_recent_first(repository):
    for run_id in (1, 2, 3):
        await repository.save_ingestion_run(_run_summary(run_id))

    runs = await repository.get_runs()
    assert [r.run_id for r in runs] == [3, 2, 1]


# ---------------------------------------------------------------------------
# Sources: upsert + retrieval (Phase 16, 18)
# ---------------------------------------------------------------------------

@requires_db
@pytest.mark.asyncio
async def test_source_upsert_creates_then_updates(repository):
    await repository.update_source_status(
        SourceStatus(source="Source A", status=SourceHealthEnum.HEALTHY, records_received=10, records_processed=9)
    )
    await repository.update_source_status(
        SourceStatus(source="Source A", status=SourceHealthEnum.DOWN, records_received=0, records_processed=0)
    )

    sources = await repository.get_sources()
    matching = [s for s in sources if s.source == "Source A"]
    assert len(matching) == 1
    assert matching[0].status == SourceHealthEnum.DOWN


@requires_db
@pytest.mark.asyncio
async def test_get_sources_returns_all(repository):
    for name in ("Source A", "Source B", "Source C"):
        await repository.update_source_status(SourceStatus(source=name, status=SourceHealthEnum.HEALTHY))

    sources = await repository.get_sources()
    assert {s.source for s in sources} == {"Source A", "Source B", "Source C"}


# ---------------------------------------------------------------------------
# Statistics (Phase 17, 28)
# ---------------------------------------------------------------------------

@requires_db
@pytest.mark.asyncio
async def test_get_stats_computes_real_values(repository):
    """Phase 28: verify actual aggregated values, not merely the response
    shape."""
    await repository.save_ingestion_run(
        _run_summary(1, total_received=10, total_processed=7, total_duplicates=3, total_failed=0)
    )
    await repository.save_ingestion_run(
        _run_summary(2, total_received=20, total_processed=15, total_duplicates=4, total_failed=1)
    )

    stats = await repository.get_stats()
    assert stats.total_received == 30
    assert stats.total_processed == 22
    assert stats.total_duplicates == 7
    assert stats.total_failed == 1
    assert stats.last_run_status == "COMPLETED"


@requires_db
@pytest.mark.asyncio
async def test_get_stats_with_no_runs(repository):
    stats = await repository.get_stats()
    assert stats.total_received == 0
    assert stats.last_run_status is None


# ---------------------------------------------------------------------------
# Pagination (Phase 19, 29)
# ---------------------------------------------------------------------------

@requires_db
@pytest.mark.asyncio
async def test_record_pagination(repository):
    records = [_canonical(f"R-{i:03d}", "Source A", f"hash-{i:03d}") for i in range(25)]
    await repository.save_records(records)

    page1 = await repository.get_records(page=1, page_size=10)
    page2 = await repository.get_records(page=2, page_size=10)
    page3 = await repository.get_records(page=3, page_size=10)

    assert page1["total"] == 25
    assert len(page1["records"]) == 10
    assert len(page2["records"]) == 10
    assert len(page3["records"]) == 5


# ---------------------------------------------------------------------------
# Source filtering (Phase 30)
# ---------------------------------------------------------------------------

@requires_db
@pytest.mark.asyncio
async def test_record_source_filter(repository):
    a = [_canonical(f"A-{i}", "Source A", f"a-hash-{i}") for i in range(10)]
    b = [_canonical(f"B-{i}", "Source B", f"b-hash-{i}") for i in range(8)]
    c = [_canonical(f"C-{i}", "Source C", f"c-hash-{i}") for i in range(7)]
    await repository.save_records(a + b + c)

    result = await repository.get_records(source="Source B", page_size=100)
    assert result["total"] == 8
    assert all(r["source"] == "Source B" for r in result["records"])
