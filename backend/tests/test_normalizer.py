"""
Normalization tests (Phase 24) — one record per source schema, checking
whitespace stripping, email lower-casing, numeric coercion, and
timestamp parsing all land in the canonical shape correctly.
"""

from app.ingestion.normalizer import RecordNormalizer


def test_normalizes_source_a_record():
    raw = [{"id": " A-001 ", "name": " Alice ", "email": "ALICE@EXAMPLE.COM", "amount": "1500", "created": "22-09-2026"}]
    [record] = RecordNormalizer().normalize(raw)

    assert record.record_id == "A-001"
    assert record.name == "Alice"
    assert record.email == "alice@example.com"
    assert record.value == 1500.0
    assert record.source == "Source A"
    assert record.created_at is not None


def test_normalizes_source_b_record():
    raw = [{"customer_id": "B-010", "full_name": " Bob ", "email_address": "BOB@EXAMPLE.COM", "value": 250, "timestamp": "2026-09-22T10:30:00"}]
    [record] = RecordNormalizer().normalize(raw)

    assert record.record_id == "B-010"
    assert record.name == "Bob"
    assert record.email == "bob@example.com"
    assert record.value == 250.0
    assert record.source == "Source B"
    assert record.created_at.startswith("2026-09-22T10:30:00")


def test_normalizes_source_c_record():
    raw = [{"userId": "C-010", "username": "Carla", "mail": "carla@example.com", "transaction_value": "99.99", "createdAt": "2026-09-01T00:00:00"}]
    [record] = RecordNormalizer().normalize(raw)

    assert record.record_id == "C-010"
    assert record.name == "Carla"
    assert record.email == "carla@example.com"
    assert record.value == 99.99
    assert record.source == "Source C"


def test_unparseable_value_becomes_none_not_a_crash():
    raw = [{"id": "A-999", "name": "Bad Value", "email": "x@example.com", "amount": "not-a-number", "created": "22-09-2026"}]
    # normalize() itself never raises; an unconvertible value just makes
    # the record fail *validation* (checked in test_validator.py), so it
    # is filtered out of normalize()'s returned list rather than crashing.
    valid, result = RecordNormalizer().normalize_with_validation(raw)
    assert valid == []
    assert result.invalid_count == 1
    assert "Value must be numeric" in result.invalid_records[0].errors


def test_source_metadata_preserved_across_batch():
    raw = [
        {"id": "A-001", "name": "Alice", "email": "alice@example.com", "amount": "10", "created": "01-01-2026"},
        {"customer_id": "B-001", "full_name": "Bob", "email_address": "bob@example.com", "value": 10, "timestamp": "2026-01-01T00:00:00"},
        {"userId": "C-001", "username": "Carl", "mail": "carl@example.com", "transaction_value": 10, "createdAt": "2026-01-01T00:00:00"},
    ]
    records = RecordNormalizer().normalize(raw)
    sources = {r.source for r in records}
    assert sources == {"Source A", "Source B", "Source C"}
