"""
Deduplication layer (Phases 14-17 of the Member 2 brief).

Runs AFTER normalization and validation, on CanonicalRecord instances —
never on raw, source-specific dicts (Phase 14 is explicit about this:
"Do NOT deduplicate raw records using source-specific field names").

Fingerprint strategy (Phase 15): SHA-256 of
`record_id.strip().lower() + "|" + email.strip().lower()`. Using both
fields (rather than record_id alone) means two different logical people
who happened to reuse an id string still wouldn't collide, while the
same logical person reported by two different sources under the same id
and email always will.
"""

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.schemas.responses import CanonicalRecord


def compute_fingerprint(record: CanonicalRecord) -> str:
    """Deterministic, reproducible SHA-256 hex digest for one canonical
    record. Identical for logically identical records, different
    otherwise (Phase 15)."""
    record_id = (record.record_id or "").strip().lower()
    email = (record.email or "").strip().lower()
    fingerprint_input = f"{record_id}|{email}"
    return hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()


@dataclass
class DuplicateInfo:
    """Debugging/demo metadata for one detected duplicate (Phase 17)."""
    record_hash: str
    original_source: str
    duplicate_source: str
    record_id: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "record_hash": self.record_hash,
            "original_source": self.original_source,
            "duplicate_source": self.duplicate_source,
            "record_id": self.record_id,
        }


class RecordDeduplicator:
    """Satisfies Member 1's Deduplicator Protocol
    (app/ingestion/interfaces.py::Deduplicator)."""

    def __init__(self) -> None:
        # Populated by the most recent process() call, for
        # introspection/demo purposes only.
        self.last_duplicates: List[DuplicateInfo] = []

    def process(self, records: List[CanonicalRecord]) -> Tuple[List[CanonicalRecord], int]:
        """Keep the first occurrence of each logical record (by
        fingerprint) in input order; every later occurrence is counted as
        a duplicate and dropped."""
        seen: Dict[str, CanonicalRecord] = {}
        unique: List[CanonicalRecord] = []
        duplicates: List[DuplicateInfo] = []

        for record in records:
            fingerprint = compute_fingerprint(record)
            # Attach the fingerprint to the record itself (CanonicalRecord
            # allows extra fields) so Member 3 can persist it directly as
            # `record_hash` per the documented database contract.
            record.record_hash = fingerprint  # type: ignore[attr-defined]

            if fingerprint in seen:
                original = seen[fingerprint]
                duplicates.append(
                    DuplicateInfo(
                        record_hash=fingerprint,
                        original_source=original.source,
                        duplicate_source=record.source,
                        record_id=record.record_id,
                    )
                )
                continue

            seen[fingerprint] = record
            unique.append(record)

        self.last_duplicates = duplicates
        return unique, len(duplicates)
