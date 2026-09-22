"""
Validation layer (Phases 12-13 of the Member 2 brief).

Validates already-*normalized* CanonicalRecord instances (see
app/ingestion/normalizer.py — normalization always runs before
validation, and validation always runs before deduplication, per the
brief's required pipeline order). Never raises on a bad record: invalid
records are collected and reported, not thrown as exceptions, so one bad
record can never crash an ingestion run.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from app.schemas.responses import CanonicalRecord

# Simple, intentionally permissive email shape check — good enough to
# catch obviously-malformed addresses without pulling in a full RFC 5322
# validator, which would be overkill for a hackathon data-quality gate.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class InvalidRecord:
    """One rejected record plus the reasons it was rejected."""
    record_id: str
    source: str
    errors: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {"record_id": self.record_id, "source": self.source, "errors": self.errors}


@dataclass
class ValidationResult:
    """Everything a caller needs to know about one validation pass."""
    valid_records: List[CanonicalRecord] = field(default_factory=list)
    invalid_records: List[InvalidRecord] = field(default_factory=list)

    @property
    def invalid_count(self) -> int:
        return len(self.invalid_records)

    @property
    def valid_count(self) -> int:
        return len(self.valid_records)

    def to_dict(self) -> Dict[str, object]:
        """Matches the shape sketched in the brief:
        {"valid_records": [...], "invalid_records": [...], "invalid_count": N}
        Never includes a Python stack trace (Phase 13) — just the plain
        string reasons collected in `errors`.
        """
        return {
            "valid_records": [r.model_dump() for r in self.valid_records],
            "invalid_records": [ir.to_dict() for ir in self.invalid_records],
            "invalid_count": self.invalid_count,
        }


def _validate_one(record: CanonicalRecord) -> List[str]:
    """Return a list of human-readable error strings; empty list means valid."""
    errors: List[str] = []

    if not record.record_id or not record.record_id.strip():
        errors.append("Missing record_id")

    if not record.name or not record.name.strip():
        errors.append("Missing name")

    if not record.email or not _EMAIL_RE.match(record.email):
        errors.append("Invalid email")

    if record.value is None:
        errors.append("Value must be numeric")
    elif not isinstance(record.value, (int, float)):
        errors.append("Value must be numeric")
    elif record.value < 0:
        errors.append("Value must not be negative")

    if not record.created_at:
        errors.append("Invalid or missing created_at")
    else:
        try:
            # created_at is normalized to ISO-8601 by the normalizer, so a
            # successful parse here also confirms the normalizer did its job.
            datetime.fromisoformat(record.created_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            errors.append("Invalid or missing created_at")

    return errors


def validate_records(records: List[CanonicalRecord]) -> ValidationResult:
    """Validate a batch of canonical records, rejecting bad ones cleanly."""
    result = ValidationResult()
    for record in records:
        errors = _validate_one(record)
        if errors:
            result.invalid_records.append(
                InvalidRecord(record_id=record.record_id, source=record.source, errors=errors)
            )
        else:
            result.valid_records.append(record)
    return result
