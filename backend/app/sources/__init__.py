"""
Member 2's real mock data sources.

Mirrors the shape of app/ingestion/demo_sources.py::get_demo_sources() so
swapping one for the other in app/services/ingestion_service.py is a
one-line change — see MEMBER2_DATA_PIPELINE.md, section "Integration
instructions for Member 1".
"""

from typing import List

from app.sources.source_a import SourceA
from app.sources.source_b import SourceB
from app.sources.source_c import SourceC

__all__ = ["SourceA", "SourceB", "SourceC", "get_real_sources"]


def get_real_sources() -> List[object]:
    """Default set of the three real mock sources, with the staggered
    delays described in the project brief (A=1s, B=1.5s, C=0.8s) so the
    concurrency demo (sequential ~3.3s vs concurrent ~1.5s) still holds."""
    return [
        SourceA(delay=1.0),
        SourceB(delay=1.5),
        SourceC(delay=0.8),
    ]
