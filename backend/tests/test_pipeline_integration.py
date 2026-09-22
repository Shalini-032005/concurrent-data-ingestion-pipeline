"""
Integration test (Phase 27): Source A + Source B + Source C ->
normalization -> validation -> deduplication, end to end, using the
real (not mocked-out) mock sources.

Expected math for this fixed dataset (documented in
MEMBER2_DATA_PIPELINE.md):
    raw records fetched   = 31  (11 + 10 + 10; Source A includes 1
                                  intentionally invalid record)
    invalid (rejected)    = 1
    valid (post-validate) = 30
    unique (post-dedupe)  = 22
    duplicates removed    = 8
"""

import asyncio

from app.ingestion.deduplicator import RecordDeduplicator
from app.ingestion.normalizer import RecordNormalizer
from app.sources.source_a import SourceA
from app.sources.source_b import SourceB
from app.sources.source_c import SourceC


async def test_full_pipeline_end_to_end():
    sources = [SourceA(delay=0), SourceB(delay=0), SourceC(delay=0)]

    # Concurrent fetch, same as the orchestrator would do.
    results = await asyncio.gather(*(s.fetch() for s in sources))
    raw_records = [rec for batch in results for rec in batch]
    assert len(raw_records) == 31

    normalizer = RecordNormalizer()
    valid_records, validation_result = normalizer.normalize_with_validation(raw_records)

    assert validation_result.invalid_count == 1
    assert len(valid_records) == 30
    # Source metadata must survive normalization.
    assert {r.source for r in valid_records} == {"Source A", "Source B", "Source C"}

    unique_records, duplicate_count = RecordDeduplicator().process(valid_records)

    assert duplicate_count == 8
    assert len(unique_records) == 22
    # No record_id collisions remain among the unique set.
    assert len({r.record_id for r in unique_records}) == len(unique_records)
