"""
Unit & Integration tests for Phase 1 Data Intelligence features:
1. Data Quality Engine
2. ML Anomaly Detection & Explanations
3. Pipeline Health Score
4. Intelligent Alert Center
5. Data Lineage
6. Run Replay
7. "What Changed?" Run Comparison
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from app.schemas.responses import CanonicalRecord
from app.schemas.intelligence import AlertStatusEnum
from app.services.data_quality_service import DataQualityService
from app.services.anomaly_service import AnomalyService
from app.services.pipeline_health_service import PipelineHealthService
from app.services.alert_service import AlertService
from app.services.lineage_service import LineageService
from app.services.replay_service import ReplayService
from app.services.comparison_service import ComparisonService
from app.repositories.base import InMemoryRepository


@pytest.fixture
def memory_repo():
    return InMemoryRepository()


@pytest.mark.asyncio
async def test_data_quality_service(memory_repo):
    # Save test canonical records
    records = [
        CanonicalRecord(record_id="REC1", name="Alice", email="alice@example.com", value=100.0, source="Source A", created_at="2026-09-22T10:00:00Z"),
        CanonicalRecord(record_id="REC2", name="Bob", email="bob@example.com", value=200.0, source="Source B", created_at="2026-09-22T10:00:00Z"),
    ]
    await memory_repo.save_records(records)

    service = DataQualityService(memory_repo)
    res = await service.calculate_quality(run_id=1)

    assert res.overall_score > 0.0
    assert res.completeness == 100.0
    assert res.validity == 100.0
    assert res.uniqueness == 100.0

    trend = await service.get_trend()
    assert len(trend.trend) >= 1


@pytest.mark.asyncio
async def test_anomaly_service(memory_repo):
    records = [
        CanonicalRecord(record_id=f"R{i}", name=f"User {i}", email=f"user{i}@test.com", value=10.0 + i, source="Source A", created_at="2026-09-22T10:00:00Z")
        for i in range(10)
    ]
    # Add extreme outlier
    records.append(CanonicalRecord(record_id="R_OUTLIER", name="Outlier", email="out@test.com", value=9999.0, source="Source A", created_at="2026-09-22T10:00:00Z"))

    await memory_repo.save_records(records)

    service = AnomalyService(memory_repo)
    anomalies = await service.scan_and_save_anomalies(run_id=1)

    assert len(anomalies) > 0
    outlier_anom = [a for a in anomalies if a.record_id == "R_OUTLIER"]
    assert len(outlier_anom) == 1
    assert "historical" in outlier_anom[0].reason.lower()


@pytest.mark.asyncio
async def test_pipeline_health_service(memory_repo):
    service = PipelineHealthService(memory_repo)
    health = await service.calculate_health()
    assert health.overall_score >= 0.0
    assert health.status in ("HEALTHY", "DEGRADED", "CRITICAL")


@pytest.mark.asyncio
async def test_alert_service(memory_repo):
    service = AlertService(memory_repo)
    alerts_res = await service.scan_and_generate_alerts()
    assert isinstance(alerts_res, list)

    # Test update alert
    if alerts_res:
        a_id = alerts_res[0].id
        updated = await service.update_alert_status(a_id, AlertStatusEnum.ACKNOWLEDGED)
        assert updated.status == AlertStatusEnum.ACKNOWLEDGED


@pytest.mark.asyncio
async def test_lineage_service(memory_repo):
    records = [
        CanonicalRecord(record_id="LINEAGE_1", name="Test Lineage", email="lineage@test.com", value=50.0, source="Source A", created_at="2026-09-22T10:00:00Z")
    ]
    await memory_repo.save_records(records)

    service = LineageService(memory_repo)
    lineage = await service.get_lineage("LINEAGE_1")

    assert lineage is not None
    assert lineage.record_id == "LINEAGE_1"
    assert len(lineage.steps) == 6
    assert lineage.steps[0].stage == "SOURCE"
    assert lineage.steps[-1].stage == "STORAGE"


def test_api_intelligence_endpoints():
    client = TestClient(app)

    # Trigger run first
    resp_ingest = client.post("/api/ingest")
    assert resp_ingest.status_code == 200

    # 1. Quality
    res = client.get("/api/quality")
    assert res.status_code == 200
    assert "overall_score" in res.json()

    # 2. Anomalies
    res = client.get("/api/anomalies")
    assert res.status_code == 200
    assert "anomalies" in res.json()

    # 3. Health
    res = client.get("/api/health/pipeline")
    assert res.status_code == 200
    assert "overall_score" in res.json()

    # 4. Alerts
    res = client.get("/api/alerts")
    assert res.status_code == 200
    assert "alerts" in res.json()

    # 5. Compare
    res = client.get("/api/runs/compare")
    assert res.status_code in (200, 400)
