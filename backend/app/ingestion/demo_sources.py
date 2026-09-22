"""
TEMPORARY IMPLEMENTATION — Replace with Member 2's real mock sources.

These exist only so Member 1's backend/API/concurrency layer can be
demoed and tested end-to-end before Member 2's actual source
implementations (with real validation/normalization-worthy payloads) are
ready. They satisfy the IngestionSource contract in
app/ingestion/interfaces.py, so swapping them out later is a one-line
change wherever sources are constructed (see app/services/ingestion_service.py).
"""

import asyncio
import random
from typing import Any, Dict, List


class DemoSource:
    """A fake source with a configurable artificial delay, to make
    concurrency visible/demonstrable (e.g. A=1s, B=1.5s, C=0.8s)."""

    def __init__(self, name: str, delay: float = 1.0, record_count: int = 10):
        self.name = name
        self.delay = delay
        self.record_count = record_count

    async def fetch(self) -> List[Dict[str, Any]]:
        await asyncio.sleep(self.delay)
        return [
            {
                "id": f"{self.name}-{i}",
                "name": f"Record {i} from {self.name}",
                "email": f"user{i}@{self.name.lower().replace(' ', '')}.example.com",
                "value": round(random.uniform(1, 100), 2),
                "source": self.name,
            }
            for i in range(self.record_count)
        ]


def get_demo_sources() -> List[DemoSource]:
    """Default set of 3 demo sources with staggered delays, matching the
    timings described in the project brief (A=1s, B=1.5s, C=0.8s)."""
    return [
        DemoSource(name="Source A", delay=1.0, record_count=10),
        DemoSource(name="Source B", delay=1.5, record_count=10),
        DemoSource(name="Source C", delay=0.8, record_count=10),
    ]
