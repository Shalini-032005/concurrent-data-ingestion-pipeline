"""
Validation tests (Phase 25): one valid record, plus one rejection case
per rule — missing id, missing email, invalid email, invalid numeric
value, negative value, invalid timestamp.
"""

from app.ingestion.validator import validate_records
from app.schemas.responses import CanonicalRecord


def _record(**overrides):
    base = dict(
        record_id="A-001",
        name="Alice",
        email="alice@example.com",
        value=100.0,
        source="Source A",
        created_at="2026-09-22T10:30:00+00:00",
    )
    base.update(overrides)
    return CanonicalRecord(**base)


def test_valid_record_passes():
    result = validate_records([_record()])
    assert result.valid_count == 1
    assert result.invalid_count == 0


def test_missing_record_id_rejected():
    result = validate_records([_record(record_id="")])
    assert result.invalid_count == 1
    assert "Missing record_id" in result.invalid_records[0].errors


def test_missing_email_rejected():
    result = validate_records([_record(email=None)])
    assert result.invalid_count == 1
    assert "Invalid email" in result.invalid_records[0].errors


def test_invalid_email_format_rejected():
    result = validate_records([_record(email="not-an-email")])
    assert result.invalid_count == 1
    assert "Invalid email" in result.invalid_records[0].errors


def test_non_numeric_value_rejected():
    result = validate_records([_record(value=None)])
    assert result.invalid_count == 1
    assert "Value must be numeric" in result.invalid_records[0].errors


def test_negative_value_rejected():
    result = validate_records([_record(value=-5.0)])
    assert result.invalid_count == 1
    assert "Value must not be negative" in result.invalid_records[0].errors


def test_invalid_timestamp_rejected():
    result = validate_records([_record(created_at="not-a-date")])
    assert result.invalid_count == 1
    assert "Invalid or missing created_at" in result.invalid_records[0].errors


def test_no_stack_trace_leaks_into_error_strings():
    result = validate_records([_record(value=-5.0)])
    for err in result.invalid_records[0].errors:
        assert "Traceback" not in err
