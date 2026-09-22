"""
Tests: FastAPI app starts, GET /, GET /health, response shapes, error handling.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_app_starts_and_root_works():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "running"
        assert "message" in body


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_stats_endpoint_shape():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/stats")
        assert resp.status_code == 200
        body = resp.json()
        for key in [
            "total_received", "total_processed", "total_duplicates",
            "total_failed", "last_run_status", "last_run_timestamp",
            "last_run_duration_ms",
        ]:
            assert key in body


@pytest.mark.asyncio
async def test_sources_endpoint_shape():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/sources")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_records_endpoint_pagination_params():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/records?page=1&page_size=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 1
        assert body["page_size"] == 5
        assert "records" in body
        assert "total" in body


@pytest.mark.asyncio
async def test_run_not_found_returns_clean_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/runs/999999")
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        # must not leak a raw traceback
        assert "Traceback" not in str(body)


@pytest.mark.asyncio
async def test_ingest_returns_running_status_and_run_id():
    """POST /api/ingest must respond with RUNNING + a run_id, using
    FastAPI's BackgroundTasks so the HTTP layer never blocks on the
    ingestion itself.

    NOTE: httpx's ASGITransport test harness awaits background tasks as
    part of the same call before returning control to the test (unlike a
    real uvicorn server socket, which returns to the client immediately
    and finishes the background task afterwards). So this test asserts on
    response shape, not on wall-clock timing. The "doesn't block the HTTP
    response" behavior is verified live against a running uvicorn server
    in the phase-25 manual verification (see MEMBER1_BACKEND.md) where
    POST /api/ingest returns in milliseconds while the run finishes
    ~1.5s later in the background.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/ingest")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "RUNNING"
        assert "run_id" in body
