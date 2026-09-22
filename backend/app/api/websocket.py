"""
WebSocket connection manager + /ws endpoint.

Member 4 (frontend) should connect to `ws://<host>/ws` and expect JSON
messages shaped like app.schemas.responses.IngestionEvent (see
to_ws_message()). No auth is required for this hackathon build.

Broadcast contract (used by the orchestrator via EventBroadcaster):
    await manager.broadcast(event: IngestionEvent) -> None
"""

import logging
from typing import List

from fastapi import WebSocket, WebSocketDisconnect

from app.schemas.responses import IngestionEvent

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Tracks active WebSocket clients and broadcasts events to all of them.

    Disconnected/broken clients are dropped silently rather than raising —
    a bad frontend connection must never crash an ingestion run.
    """

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected (total=%d)", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WebSocket client disconnected (total=%d)", len(self.active_connections))

    async def broadcast(self, event: IngestionEvent) -> None:
        """Send an event to every connected client. Satisfies the
        EventBroadcaster protocol used by the orchestrator."""
        message = event.to_ws_message()
        stale: List[WebSocket] = []

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:  # noqa: BLE001
                logger.warning("Dropping unresponsive WebSocket client")
                stale.append(connection)

        for connection in stale:
            self.disconnect(connection)


# Single shared instance for the whole application.
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket) -> None:
    """Handler for the /ws route. Registered in app.api.routes / main.py."""
    await manager.connect(websocket)
    try:
        while True:
            # We don't require clients to send anything, but we still need
            # to await something so we notice disconnects promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected WebSocket error")
        manager.disconnect(websocket)
