"""
Unit tests for Source A / Source B / Source C (Phase 23).

Verifies: fetch is async, records come back, each source's schema is
correct, the expected record counts hold, cross-source duplicates exist
where intended, and controlled failure simulation works cleanly.
"""

import asyncio
import inspect

import pytest

from app.sources.exceptions import SourceFetchError
from app.sources.source_a import SourceA
from app.sources.source_b import SourceB
from app.sources.source_c import SourceC


def test_fetch_is_async():
    assert inspect.iscoroutinefunction(SourceA().fetch)
    assert inspect.iscoroutinefunction(SourceB().fetch)
    assert inspect.iscoroutinefunction(SourceC().fetch)


async def test_source_a_schema_and_count():
    records = await SourceA(delay=0).fetch()
    assert len(records) == 11  # 10 valid + 1 intentionally invalid
    for r in records:
        assert set(r.keys()) == {"id", "name", "email", "amount", "created"}


async def test_source_b_schema_and_count():
    records = await SourceB(delay=0).fetch()
    assert len(records) == 10
    for r in records:
        assert set(r.keys()) == {"customer_id", "full_name", "email_address", "value", "timestamp"}


async def test_source_c_schema_and_count():
    records = await SourceC(delay=0).fetch()
    assert len(records) == 10
    for r in records:
        assert set(r.keys()) == {"userId", "username", "mail", "transaction_value", "createdAt"}


async def test_cross_source_duplicates_exist_by_design():
    a = {r["id"] for r in await SourceA(delay=0).fetch()}
    b = {r["customer_id"] for r in await SourceB(delay=0).fetch()}
    c = {r["userId"] for r in await SourceC(delay=0).fetch()}

    assert a & b, "Source A and Source B should share at least one logical id"
    assert a & c, "Source A and Source C should share at least one logical id"
    assert b & c, "Source B and Source C should share at least one logical id"


async def test_sources_run_concurrently_not_sequentially():
    sources = [SourceA(delay=0.3), SourceB(delay=0.4), SourceC(delay=0.2)]
    start = asyncio.get_event_loop().time()
    await asyncio.gather(*(s.fetch() for s in sources))
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 0.4 + 0.2  # well under the sequential sum (~0.9s)


@pytest.mark.parametrize("source_cls", [SourceA, SourceB, SourceC])
async def test_simulate_failure_raises_cleanly(source_cls):
    source = source_cls(delay=0)
    with pytest.raises(SourceFetchError):
        await source.fetch(simulate_failure=True)


async def test_no_failure_by_default():
    # Default call (no args) must still work, matching the IngestionSource
    # contract the orchestrator relies on: `await source.fetch()`.
    records = await SourceA(delay=0).fetch()
    assert records
