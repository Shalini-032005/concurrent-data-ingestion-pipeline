"""
Anomaly Detection service.
Connects MLAnomalyDetector to repository records and runs, exposing querying & breakdown APIs.
"""

import logging
from typing import List, Optional

from app.ml.anomaly_detector import MLAnomalyDetector
from app.repositories.base import Repository
from app.schemas.intelligence import (
    AnomaliesResponse,
    AnomaliesSummary,
    AnomalyRecord,
    AnomalySeverityEnum,
)

logger = logging.getLogger(__name__)


class AnomalyService:
    def __init__(self, repository: Repository):
        self.repository = repository
        self.detector = MLAnomalyDetector()

    async def scan_and_save_anomalies(self, run_id: Optional[int] = None) -> List[AnomalyRecord]:
        records_data = await self.repository.get_records(page=1, page_size=1000)
        records_raw = records_data.get("records", [])

        runs_raw = [r.model_dump() for r in await self.repository.get_runs()]

        anomalies: List[AnomalyRecord] = []

        # Record level scanning
        record_anomalies = self.detector.detect_anomalies_for_records(
            records=records_raw[-100:] if len(records_raw) > 100 else records_raw,
            historical_records=records_raw[:-100] if len(records_raw) > 100 else records_raw,
            run_id=run_id,
        )
        anomalies.extend(record_anomalies)

        # Run level scanning
        if runs_raw:
            latest_run = runs_raw[0]
            run_anomalies = self.detector.detect_anomalies_for_runs(
                latest_run=latest_run,
                historical_runs=runs_raw[1:],
            )
            anomalies.extend(run_anomalies)

        if anomalies:
            await self.repository.save_anomalies(anomalies)

        return anomalies

    async def get_anomalies(
        self, source: Optional[str] = None, severity: Optional[str] = None
    ) -> AnomaliesResponse:
        records = await self.repository.get_anomalies(source=source, severity=severity)

        high = sum(1 for a in records if (a.severity.value if hasattr(a.severity, "value") else str(a.severity)) == "HIGH")
        med = sum(1 for a in records if (a.severity.value if hasattr(a.severity, "value") else str(a.severity)) == "MEDIUM")
        low = sum(1 for a in records if (a.severity.value if hasattr(a.severity, "value") else str(a.severity)) == "LOW")

        summary = AnomaliesSummary(
            total_anomalies=len(records),
            high_count=high,
            medium_count=med,
            low_count=low,
        )

        return AnomaliesResponse(anomalies=records, summary=summary)

    async def get_anomaly_by_id(self, anomaly_id: str) -> Optional[AnomalyRecord]:
        return await self.repository.get_anomaly(anomaly_id)
