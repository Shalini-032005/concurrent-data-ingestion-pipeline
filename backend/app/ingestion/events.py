"""
Event broadcaster contract.

The orchestrator emits IngestionEvent objects through anything satisfying
this Protocol. In production that's the WebSocket ConnectionManager
(app/api/websocket.py). In tests, a simple list-collecting fake works fine.

EVENT CONTRACT:
    async def broadcast(event: IngestionEvent) -> None
"""

from typing import Protocol, runtime_checkable

from app.schemas.responses import IngestionEvent


@runtime_checkable
class EventBroadcaster(Protocol):
    async def broadcast(self, event: IngestionEvent) -> None:
        ...


class NullBroadcaster:
    """No-op broadcaster — used when no WebSocket clients / manager is wired in
    (e.g. in orchestrator unit tests)."""

    async def broadcast(self, event: IngestionEvent) -> None:
        return None
