"""
Source C — mock ingestion source.

Schema (deliberately different field names from Source A / Source B):

    {
        "userId": "A-001",
        "username": "Alice",
        "mail": "alice@example.com",
        "transaction_value": 1500,
        "createdAt": "2026-09-22T10:30:00",
    }

Ten records: two share a logical identity with Source A ("A-001",
"A-005"), two share a logical identity with Source B ("B-001", "B-002"),
and six ("C-001".."C-006") are unique to Source C. See
MEMBER2_DATA_PIPELINE.md for the full cross-source duplicate map.
"""

import asyncio
from typing import Any, Dict, List

from app.sources.exceptions import SourceFetchError

_RECORDS: List[Dict[str, Any]] = [
    # --- overlap with Source A ---
    {"userId": "A-001", "username": "Alice Johnson", "mail": "ALICE.JOHNSON@EXAMPLE.COM", "transaction_value": 1500, "createdAt": "2026-09-22T10:30:00"},
    {"userId": "A-005", "username": "Eve Turner", "mail": "eve.turner@example.com", "transaction_value": 450.25, "createdAt": "2026-09-10T18:00:00"},
    # --- overlap with Source B ---
    {"userId": "B-001", "username": "Karen White", "mail": "karen.white@example.com", "transaction_value": 1100, "createdAt": "2026-09-14T08:00:00"},
    {"userId": "B-002", "username": "Leo Martins", "mail": "leo.martins@example.com", "transaction_value": 1800, "createdAt": "2026-09-13T16:20:00"},
    # --- unique to Source C ---
    {"userId": "C-001", "username": "Wendy Ross", "mail": "wendy.ross@example.com", "transaction_value": 1250, "createdAt": "2026-09-08T10:00:00"},
    {"userId": "C-002", "username": "Xavier Cruz", "mail": "xavier.cruz@example.com", "transaction_value": 875.5, "createdAt": "2026-09-07T09:30:00"},
    {"userId": "C-003", "username": "Yara Ahmed", "mail": "yara.ahmed@example.com", "transaction_value": 1990, "createdAt": "2026-09-06T11:15:00"},
    {"userId": "C-004", "username": "Zane Foster", "mail": "zane.foster@example.com", "transaction_value": 620, "createdAt": "2026-09-05T14:45:00"},
    {"userId": "C-005", "username": "Amara Singh", "mail": "amara.singh@example.com", "transaction_value": 1430, "createdAt": "2026-09-04T16:00:00"},
    {"userId": "C-006", "username": "Ben Okafor", "mail": "ben.okafor@example.com", "transaction_value": 2050, "createdAt": "2026-09-03T08:20:00"},
]


class SourceC:
    """Mock source with the "userId/username/mail/transaction_value/createdAt" schema."""

    name = "Source C"

    def __init__(self, delay: float = 0.8):
        self.delay = delay

    async def fetch(self, simulate_failure: bool = False) -> List[Dict[str, Any]]:
        """Return Source C's raw records. See SourceA.fetch for the note
        on `simulate_failure`."""
        await asyncio.sleep(self.delay)
        if simulate_failure:
            raise SourceFetchError(self.name, "simulated upstream outage")
        return [dict(record) for record in _RECORDS]
