"""
Pipeline Health Score service for Phase 1.
Computes an overall 0-100 Pipeline Health score from actual application metrics
(ingestion success rate, latency, retry count, validation failure rate, duplicate rate, anomaly rate).
"""

from datetime import datetime, timezone
import logging
from typing import Optional

from app.repositories.base import Repository
from app.schemas.intelligence import PipelineHealthResponse

logger = logging.getLogger(__name__)


class PipelineHealthService:
    def __init__(self, repository: Repository):
        self.repository = repository

    async def calculate_health(self) -> PipelineHealthResponse:
        runs = await self.repository.get_runs()
        sources = await self.repository.get_sources()
        anomalies = await self.repository.get_anomalies()

        if not runs:
            now_iso = datetime.now(timezone.utc).isoformat()
            res = PipelineHealthResponse(
                overall_score=100.0,
                availability=100.0,
                latency=100.0,
                validation=100.0,
                reliability=100.0,
                status="HEALTHY",
                updated_at=now_iso,
            )
            await self.repository.save_pipeline_health(res)
            return res

        # 1. Availability: % of sources currently HEALTHY or ratio of completed runs
        if sources:
            healthy_sources = sum(1 for s in sources if (s.status.value if hasattr(s.status, "value") else str(s.status)) in ("HEALTHY", "SUCCESS"))
            availability = (healthy_sources / len(sources)) * 100.0
        else:
            successful_runs = sum(1 for r in runs if (r.status.value if hasattr(r.status, "value") else str(r.status)) == "COMPLETED")
            availability = (successful_runs / len(runs)) * 100.0

        # 2. Latency: compare average duration against threshold (target 1000ms)
        recent_durations = [r.duration_ms for r in runs[:10] if r.duration_ms is not None]
        avg_dur = sum(recent_durations) / len(recent_durations) if recent_durations else 500.0
        # Target 1000ms = 100 score; 5000ms = 50 score
        latency = max(20.0, min(100.0, 100.0 - max(0.0, (avg_dur - 1000.0) / 100.0)))

        # 3. Validation Pass Rate
        total_rec = sum(r.total_received for r in runs[:5])
        total_proc = sum(r.total_processed for r in runs[:5])
        total_dups = sum(r.total_duplicates for r in runs[:5])
        total_fail = sum(r.total_failed for r in runs[:5])

        if total_rec > 0:
            val_failures = max(0, total_rec - (total_proc + total_dups))
            validation = max(0.0, min(100.0, 100.0 - (val_failures / total_rec) * 100.0))
        else:
            validation = 100.0

        # 4. Reliability: penalized by duplicate rate and active anomaly count
        dup_rate = (total_dups / total_rec) if total_rec > 0 else 0.0
        anomaly_count = len(anomalies)
        reliability = max(10.0, min(100.0, 100.0 - (dup_rate * 40.0) - (anomaly_count * 5.0)))

        overall_score = round(
            (availability * 0.30)
            + (latency * 0.25)
            + (validation * 0.25)
            + (reliability * 0.20),
            1,
        )

        status = "HEALTHY"
        if overall_score < 50:
            status = "CRITICAL"
        elif overall_score < 80:
            status = "DEGRADED"

        now_iso = datetime.now(timezone.utc).isoformat()
        res = PipelineHealthResponse(
            overall_score=overall_score,
            availability=round(availability, 1),
            latency=round(latency, 1),
            validation=round(validation, 1),
            reliability=round(reliability, 1),
            status=status,
            updated_at=now_iso,
        )

        await self.repository.save_pipeline_health(res)
        return res

    async def get_health(self) -> PipelineHealthResponse:
        latest = await self.repository.get_latest_pipeline_health()
        if latest is None:
            return await self.calculate_health()
        return latest
