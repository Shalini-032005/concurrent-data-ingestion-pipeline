"""
Source B — mock ingestion source.

Schema (deliberately different field names from Source A / Source C):

    {
        "customer_id": "A-001",
        "full_name": " Alice ",
        "email_address": "alice@example.com",
        "value": 1500,
        "timestamp": "2026-09-22T10:30:00",
    }

Four of these ten records share a logical identity with Source A records
(customer_id "A-001".."A-004") to demonstrate cross-source deduplication;
the other six ("B-001".."B-006") are unique to Source B. Two of those six
("B-001", "B-002") are, in turn, duplicated again in Source C — see
MEMBER2_DATA_PIPELINE.md for the full map and the resulting math.

`full_name` and `email_address` intentionally carry stray whitespace /
mixed case on a couple of records so the normalizer's cleaning rules
(Phase 11) have something real to clean.
"""

import asyncio
from typing import Any, Dict, List

from app.sources.exceptions import SourceFetchError

_RECORDS: List[Dict[str, Any]] = [
    # --- overlap with Source A (same logical record, same person) ---
    {"customer_id": "A-001", "full_name": " Alice Johnson ", "email_address": "alice.johnson@example.com", "value": 1500, "timestamp": "2026-09-22T10:30:00"},
    {"customer_id": "A-002", "full_name": "Bob Smith", "email_address": "BOB.SMITH@EXAMPLE.COM", "value": 2200.5, "timestamp": "2026-09-20T09:15:00"},
    {"customer_id": "A-003", "full_name": "Carol Davis", "email_address": "carol.davis@example.com", "value": 875, "timestamp": "2026-09-18T14:00:00"},
    {"customer_id": "A-004", "full_name": "David Lee", "email_address": "david.lee@example.com", "value": 3000, "timestamp": "2026-09-15T11:45:00"},
    # --- unique to Source B ---
    {"customer_id": "B-001", "full_name": "Karen White", "email_address": "karen.white@example.com", "value": 1100, "timestamp": "2026-09-14T08:00:00"},
    {"customer_id": "B-002", "full_name": "Leo Martins", "email_address": "leo.martins@example.com", "value": 1800, "timestamp": "2026-09-13T16:20:00"},
    {"customer_id": "B-003", "full_name": "Mona Iyer", "email_address": "mona.iyer@example.com", "value": 950, "timestamp": "2026-09-12T12:00:00"},
    {"customer_id": "B-004", "full_name": "Nate Cole", "email_address": "nate.cole@example.com", "value": 2100, "timestamp": "2026-09-11T09:00:00"},
    {"customer_id": "B-005", "full_name": "Olivia Shah", "email_address": "olivia.shah@example.com", "value": 700, "timestamp": "2026-09-10T13:30:00"},
    {"customer_id": "B-006", "full_name": "Peter Nolan", "email_address": "peter.nolan@example.com", "value": 3300, "timestamp": "2026-09-09T07:45:00"},
]


class SourceB:
    """Mock source with the "customer_id/full_name/email_address/value/timestamp" schema."""

    name = "Source B"

    def __init__(self, delay: float = 1.5):
        self.delay = delay

    async def fetch(self, simulate_failure: bool = False) -> List[Dict[str, Any]]:
        """Return Source B's raw records. See SourceA.fetch for the note
        on `simulate_failure`."""
        await asyncio.sleep(self.delay)
        if simulate_failure:
            raise SourceFetchError(self.name, "simulated upstream outage")
        return [dict(record) for record in _RECORDS]
