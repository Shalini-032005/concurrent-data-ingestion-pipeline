"""
Normalization layer (Phases 9-11 of the Member 2 brief).

Converts the three different raw source schemas into the single
canonical shape the rest of the backend already speaks:
app.schemas.responses.CanonicalRecord (Member 1 defined this — see
MEMBER2_DATA_PIPELINE.md for why we reuse it instead of adding a second,
competing canonical model).

IMPORTANT — why schema detection instead of a `source` tag:
Member 1's orchestrator flattens every source's raw records into one
list before calling `normalizer.normalize(all_raw_records)` (see
IngestionOrchestrator.run in app/ingestion/orchestrator.py), and none of
Source A/B/C's raw dicts carry a `source` field themselves (that would
defeat the point of the exercise — see Phase 8). So each raw record is
matched to a schema, and therefore a source name, purely by which field
names are present on it. This is deterministic and safe because the
three schemas share no field names at all.

Runs validation (app/ingestion/validator.py) as its last internal step,
per the brief's required pipeline order (normalize -> validate ->
dedupe) and because Member 1's `Normalizer` Protocol only has room for
one method (`normalize`). `normalize()` therefore returns only the
*valid* canonical records, matching the Normalizer contract exactly;
`normalize_with_validation()` is available for callers (tests, demos)
that also want the rejected records and reasons.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.ingestion.validator import ValidationResult, validate_records
from app.schemas.responses import CanonicalRecord

# Field sets that uniquely identify each source's schema. No two sources
# share a field name, so checking for one distinguishing key is enough.
_SOURCE_A_KEY = "id"
_SOURCE_B_KEY = "customer_id"
_SOURCE_C_KEY = "userId"


def _detect_source(record: Dict[str, Any]) -> str:
    if _SOURCE_A_KEY in record:
        return "Source A"
    if _SOURCE_B_KEY in record:
        return "Source B"
    if _SOURCE_C_KEY in record:
        return "Source C"
    return "Unknown"


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_email(value: Any) -> Optional[str]:
    text = _clean_str(value)
    return text.lower() if text else None


def _clean_value(value: Any) -> Optional[float]:
    """Rule 3: "1500", 1500, "1500.50" all become a float. Anything that
    can't be converted becomes None (and is caught by the validator)."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_timestamp(value: Any) -> Optional[str]:
    """Rule 5: normalize supported source timestamp formats into one
    consistent, timezone-aware ISO-8601 representation (UTC).

    Supports:
    - Source A: "22-09-2026" (DD-MM-YYYY, date only)
    - Source B / Source C: "2026-09-22T10:30:00" (ISO 8601, naive)

    Anything else returns None rather than raising — an unparsable
    timestamp is a validation problem, not a normalizer crash.
    """
    if not value:
        return None
    text = str(value).strip()

    for fmt in ("%d-%m-%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue

    # Fall back to Python's general ISO-8601 parser (handles offsets etc.)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    except ValueError:
        return None


def _map_source_a(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "record_id": _clean_str(record.get("id")),
        "name": _clean_str(record.get("name")),
        "email": _clean_email(record.get("email")),
        "value": _clean_value(record.get("amount")),
        "created_at": _parse_timestamp(record.get("created")),
    }


def _map_source_b(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "record_id": _clean_str(record.get("customer_id")),
        "name": _clean_str(record.get("full_name")),
        "email": _clean_email(record.get("email_address")),
        "value": _clean_value(record.get("value")),
        "created_at": _parse_timestamp(record.get("timestamp")),
    }


def _map_source_c(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "record_id": _clean_str(record.get("userId")),
        "name": _clean_str(record.get("username")),
        "email": _clean_email(record.get("mail")),
        "value": _clean_value(record.get("transaction_value")),
        "created_at": _parse_timestamp(record.get("createdAt")),
    }


_MAPPERS = {
    "Source A": _map_source_a,
    "Source B": _map_source_b,
    "Source C": _map_source_c,
}


class RecordNormalizer:
    """Satisfies Member 1's Normalizer Protocol
    (app/ingestion/interfaces.py::Normalizer)."""

    def __init__(self) -> None:
        # Populated by the most recent normalize() call, for
        # introspection/demo purposes (e.g. an admin endpoint could
        # surface invalid_records without re-running anything).
        self.last_validation_result: Optional[ValidationResult] = None

    def _map_all(self, records: List[Dict[str, Any]]) -> List[CanonicalRecord]:
        canonical: List[CanonicalRecord] = []
        for raw in records:
            source = _detect_source(raw)
            mapper = _MAPPERS.get(source)
            if mapper is None:
                # Unrecognized schema — still produce a record so the
                # validator (not the normalizer) is the single place that
                # decides what's rejected, and so one weird record can
                # never silently disappear.
                mapped = {
                    "record_id": _clean_str(raw.get("id") or raw.get("record_id")),
                    "name": None,
                    "email": None,
                    "value": None,
                    "created_at": None,
                }
            else:
                mapped = mapper(raw)
            canonical.append(
                CanonicalRecord(
                    record_id=mapped["record_id"] or "",
                    name=mapped["name"],
                    email=mapped["email"],
                    value=mapped["value"],
                    source=source,
                    created_at=mapped["created_at"],
                )
            )
        return canonical

    def normalize_with_validation(
        self, records: List[Dict[str, Any]]
    ) -> Tuple[List[CanonicalRecord], ValidationResult]:
        """Map every raw record to the canonical shape, then validate.
        Returns (valid_records, full ValidationResult)."""
        canonical = self._map_all(records)
        result = validate_records(canonical)
        self.last_validation_result = result
        return result.valid_records, result

    def normalize(self, records: List[Dict[str, Any]]) -> List[CanonicalRecord]:
        """Normalizer Protocol entry point — returns only valid records.
        Invalid records are dropped here but remain inspectable via
        `self.last_validation_result` right after the call."""
        valid_records, _ = self.normalize_with_validation(records)
        return valid_records
