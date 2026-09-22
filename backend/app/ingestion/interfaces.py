"""
Integration contracts (Protocols) for teammates plugging into the backend.

Nobody outside this file needs to import concrete implementations from
Member 2 — the orchestrator only ever depends on these Protocols. This
keeps the backend decoupled and lets Member 2 build/replace mock sources,
normalization, and deduplication without touching orchestrator code.

------------------------------------------------------------------------
SOURCE CONTRACT (Member 2)
------------------------------------------------------------------------
    class MySource:
        name: str = "Source A"

        async def fetch(self) -> list[dict]:
            ...  # return raw records as plain dicts

Requirements:
- `fetch()` must be an async function.
- `fetch()` should raise an exception on failure (the orchestrator's retry
  + timeout wrapper handles catching it) rather than returning an error
  shape itself.
- `fetch()` should return `list[dict]` of raw/unnormalized records.

------------------------------------------------------------------------
NORMALIZER CONTRACT (Member 2)
------------------------------------------------------------------------
    class MyNormalizer:
        def normalize(self, records: list[dict]) -> list[CanonicalRecord]:
            ...

See app/schemas/responses.py::CanonicalRecord for the target shape:
    record_id, name, email, value, source, created_at, ingested_at

------------------------------------------------------------------------
DEDUPLICATOR CONTRACT (Member 2)
------------------------------------------------------------------------
    class MyDeduplicator:
        def process(self, records: list[CanonicalRecord]) -> tuple[list[CanonicalRecord], int]:
            ...  # returns (unique_records, duplicate_count)

------------------------------------------------------------------------
DATABASE / REPOSITORY CONTRACT (Member 3)
------------------------------------------------------------------------
See app/repositories/base.py for the full Protocol definition
(save_records, save_ingestion_run, update_source_status, get_stats,
get_records, get_runs, get_run).
"""

from typing import Any, Dict, List, Protocol, Tuple, runtime_checkable

from app.schemas.responses import CanonicalRecord


@runtime_checkable
class IngestionSource(Protocol):
    """A single data source the orchestrator can pull from."""
    name: str

    async def fetch(self) -> List[Dict[str, Any]]:
        ...


@runtime_checkable
class Normalizer(Protocol):
    """Turns raw source records into CanonicalRecord objects."""

    def normalize(self, records: List[Dict[str, Any]]) -> List[CanonicalRecord]:
        ...


@runtime_checkable
class Deduplicator(Protocol):
    """Removes duplicate records, reporting how many were dropped."""

    def process(
        self, records: List[CanonicalRecord]
    ) -> Tuple[List[CanonicalRecord], int]:
        ...


# ---------------------------------------------------------------------------
# Default (identity) implementations
# ---------------------------------------------------------------------------
# These let the orchestrator run end-to-end *before* Member 2's real
# normalizer/deduplicator exist. They are intentionally trivial and are
# swapped out via dependency injection (see app/ingestion/orchestrator.py
# and app/api/routes.py) — nothing else needs to change when the real
# implementations land.

class PassthroughNormalizer:
    """TEMPORARY IMPLEMENTATION — Replace with Member 2's real normalizer.

    Wraps each raw dict into a CanonicalRecord doing minimal, best-effort
    field mapping so the pipeline is demonstrable end-to-end.
    """

    def normalize(self, records: List[Dict[str, Any]]) -> List[CanonicalRecord]:
        normalized = []
        for i, r in enumerate(records):
            normalized.append(
                CanonicalRecord(
                    record_id=str(r.get("id", r.get("record_id", f"unknown-{i}"))),
                    name=r.get("name"),
                    email=r.get("email"),
                    value=r.get("value"),
                    source=r.get("source", "unknown"),
                    created_at=r.get("created_at"),
                )
            )
        return normalized


class NoOpDeduplicator:
    """TEMPORARY IMPLEMENTATION — Replace with Member 2's real deduplicator.

    Does a naive dedup by record_id only, as a stand-in.
    """

    def process(
        self, records: List[CanonicalRecord]
    ) -> Tuple[List[CanonicalRecord], int]:
        seen = set()
        unique: List[CanonicalRecord] = []
        duplicates = 0
        for r in records:
            if r.record_id in seen:
                duplicates += 1
                continue
            seen.add(r.record_id)
            unique.append(r)
        return unique, duplicates
