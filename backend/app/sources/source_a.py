"""
Source A — mock ingestion source.

Schema (intentionally different from Source B / Source C, and from the
canonical model):

    {
        "id": "A-001",
        "name": "Alice",
        "email": "ALICE@EXAMPLE.COM",
        "amount": "1500",
        "created": "22-09-2026",
    }

Field mapping to the canonical model lives in app/ingestion/normalizer.py,
not here — this module's only job is to hand back raw, source-shaped
dicts (Phase 8: "keep raw source records as dictionaries initially").

Contains 11 records: 10 well-formed records (some of which intentionally
overlap, by logical identity, with records in Source B / Source C — see
MEMBER2_DATA_PIPELINE.md for the full duplicate map) plus one
intentionally invalid record (A-011) so the validation layer has
something real to reject during a live demo, rather than only in tests.
"""

import asyncio
from typing import Any, Dict, List

from app.sources.exceptions import SourceFetchError

# Deterministic — no randomness, so unit tests and demo runs are
# reproducible (Phase 22: "avoid random data for core tests").
_RECORDS: List[Dict[str, Any]] = [
    {"id": "A-001", "name": "Alice Johnson", "email": "alice.johnson@example.com", "amount": "1500", "created": "22-09-2026"},
    {"id": "A-002", "name": "Bob Smith", "email": "bob.smith@example.com", "amount": "2200.50", "created": "20-09-2026"},
    {"id": "A-003", "name": "Carol Davis", "email": "carol.davis@example.com", "amount": "875", "created": "18-09-2026"},
    {"id": "A-004", "name": "David Lee", "email": "david.lee@example.com", "amount": "3000", "created": "15-09-2026"},
    {"id": "A-005", "name": "Eve Turner", "email": "eve.turner@example.com", "amount": "450.25", "created": "10-09-2026"},
    {"id": "A-006", "name": "Frank Wright", "email": "frank.wright@example.com", "amount": "1200", "created": "05-09-2026"},
    {"id": "A-007", "name": "Grace Kim", "email": "grace.kim@example.com", "amount": "990.75", "created": "01-09-2026"},
    {"id": "A-008", "name": "Heidi Brown", "email": "heidi.brown@example.com", "amount": "1675", "created": "28-08-2026"},
    {"id": "A-009", "name": "Ivan Chen", "email": "ivan.chen@example.com", "amount": "2500", "created": "25-08-2026"},
    {"id": "A-010", "name": "Judy Patel", "email": "judy.patel@example.com", "amount": "610", "created": "20-08-2026"},
    # Intentionally invalid: bad email format AND a negative amount, so
    # the validator has two distinct problems to report on one record.
    {"id": "A-011", "name": "Invalid Record", "email": "not-an-email", "amount": "-50", "created": "19-08-2026"},
]


class SourceA:
    """Mock source with the "id/name/email/amount/created" schema."""

    name = "Source A"

    def __init__(self, delay: float = 1.0):
        # Matches the timing described in the project brief so Member 1's
        # concurrency demo (sequential ~3.3s vs concurrent ~1.5s) holds.
        self.delay = delay

    async def fetch(self, simulate_failure: bool = False) -> List[Dict[str, Any]]:
        """Return Source A's raw records.

        `simulate_failure` is for direct unit testing / manual demos of
        this source in isolation. Member 1's orchestrator has its own,
        separate simulate_failure mechanism at the run level (see
        app/ingestion/orchestrator.py) — sources don't need to know about
        that one at all; this parameter is purely an extra, optional
        convenience that keeps `await source.fetch()` (no args) working
        exactly per the IngestionSource contract.
        """
        await asyncio.sleep(self.delay)  # simulated network latency — never blocking
        if simulate_failure:
            raise SourceFetchError(self.name, "simulated upstream outage")
        return [dict(record) for record in _RECORDS]  # defensive copy
