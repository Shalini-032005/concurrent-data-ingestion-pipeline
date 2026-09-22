"""
Tests for the WebSocket connection manager and /ws endpoint.
"""

import pytest
from starlette.testclient import TestClient

from app.api.websocket import ConnectionManager
from app.schemas.responses import IngestionEvent, IngestionEventType
from main import app


def test_websocket_connect_and_disconnect():
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        # Connection should be accepted without raising.
        assert websocket is not None
    # After the context exits, the client has disconnected cleanly.


@pytest.mark.asyncio
async def test_connection_manager_broadcasts_to_all_clients():
    manager = ConnectionManager()

    sent_messages = []

    class FakeWebSocket:
        async def send_json(self, data):
            sent_messages.append(data)

    fake_1 = FakeWebSocket()
    fake_2 = FakeWebSocket()
    manager.active_connections = [fake_1, fake_2]

    event = IngestionEvent(event=IngestionEventType.INGESTION_STARTED, run_id=1)
    await manager.broadcast(event)

    assert len(sent_messages) == 2
    assert sent_messages[0]["event"] == "INGESTION_STARTED"


@pytest.mark.asyncio
async def test_connection_manager_drops_broken_clients_without_raising():
    manager = ConnectionManager()

    class BrokenWebSocket:
        async def send_json(self, data):
            raise ConnectionError("client gone")

    broken = BrokenWebSocket()
    manager.active_connections = [broken]

    event = IngestionEvent(event=IngestionEventType.INGESTION_STARTED, run_id=1)
    # Must not raise even though the only client is broken.
    await manager.broadcast(event)

    assert broken not in manager.active_connections
