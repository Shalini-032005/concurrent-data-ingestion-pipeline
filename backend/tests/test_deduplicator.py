"""
Deduplication tests (Phase 26): A-001/A-001/A-002/A-003/A-003 in ->
3 unique / 2 duplicates out, plus the fingerprint determinism checks.
"""

from app.ingestion.deduplicator import RecordDeduplicator, compute_fingerprint
from app.schemas.responses import CanonicalRecord


def _record(record_id, email="person@example.com", source="Source A"):
    return CanonicalRecord(record_id=record_id, name="Someone", email=email, value=10.0, source=source)


def test_deduplication_counts():
    records = [
        _record("A-001"),
        _record("A-001"),
        _record("A-002"),
        _record("A-003"),
        _record("A-003"),
    ]
    unique, duplicate_count = RecordDeduplicator().process(records)

    assert len(unique) == 3
    assert duplicate_count == 2
    assert {r.record_id for r in unique} == {"A-001", "A-002", "A-003"}


def test_same_logical_record_same_hash_different_records_different_hash():
    same_a = _record("A-001", email="alice@example.com")
    same_b = _record(" a-001 ", email="ALICE@EXAMPLE.COM")  # different case/whitespace, same logical record
    different = _record("A-002", email="alice@example.com")

    assert compute_fingerprint(same_a) == compute_fingerprint(same_b)
    assert compute_fingerprint(same_a) != compute_fingerprint(different)


def test_cross_source_duplicate_metadata_recorded():
    records = [
        _record("A-001", source="Source A"),
        _record("A-001", source="Source B"),
    ]
    dedup = RecordDeduplicator()
    unique, duplicate_count = dedup.process(records)

    assert duplicate_count == 1
    assert len(dedup.last_duplicates) == 1
    info = dedup.last_duplicates[0].to_dict()
    assert info["original_source"] == "Source A"
    assert info["duplicate_source"] == "Source B"


def test_record_hash_attached_to_output_records():
    unique, _ = RecordDeduplicator().process([_record("A-001")])
    assert hasattr(unique[0], "record_hash")
    assert unique[0].record_hash == compute_fingerprint(_record("A-001"))
