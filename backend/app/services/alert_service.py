"""
Intelligent Alert Center service for Phase 1.
Generates alerts based on real conditions (latency spikes, duplicate rates, validation failures, source failures).
"""

from datetime import datetime, timezone
import logging
from typing import Any, List, Optional

from app.repositories.base import Repository
from app.schemas.intelligence import (
    AlertItem,
    AlertsResponse,
    AlertSeverityEnum,
    AlertStatusEnum,
)

logger = logging.getLogger(__name__)


class AlertService:
    def __init__(self, repository: Repository):
        self.repository = repository

    async def scan_and_generate_alerts(self, run_summary: Optional[Any] = None) -> List[AlertItem]:
        sources = await self.repository.get_sources()
        runs = await self.repository.get_runs()
        anomalies = await self.repository.get_anomalies()

        generated_alerts: List[AlertItem] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        # Check source statuses
        for s in sources:
            st = s.status.value if hasattr(s.status, "value") else str(s.status)
            if st in ("FAILED", "DEGRADED", "UNHEALTHY"):
                alert_id = f"alert-src-{s.source}-{int(datetime.now().timestamp() * 1000)}"
                generated_alerts.append(
                    AlertItem(
                        id=alert_id,
                        severity=AlertSeverityEnum.HIGH,
                        title=f"Source Degradation: {s.source}",
                        description=f"Source {s.source} is currently reporting {st} status. Error: {s.error_message or 'Unknown error'}",
                        source=s.source,
                        timestamp=now_iso,
                        status=AlertStatusEnum.ACTIVE,
                    )
                )

        # Check recent run stats
        if runs:
            latest_run = runs[0]
            r_id = latest_run.run_id
            if latest_run.duration_ms and latest_run.duration_ms > 3000.0:
                alert_id = f"alert-lat-{r_id}-{int(datetime.now().timestamp() * 1000)}"
                generated_alerts.append(
                    AlertItem(
                        id=alert_id,
                        severity=AlertSeverityEnum.MEDIUM,
                        title=f"High Run Latency in Run #{r_id}",
                        description=f"Ingestion run #{r_id} took {latest_run.duration_ms:.1f}ms, exceeding 3000ms threshold.",
                        source="Pipeline Orchestrator",
                        timestamp=now_iso,
                        status=AlertStatusEnum.ACTIVE,
                        run_id=r_id,
                    )
                )

            if latest_run.total_duplicates > 0 and latest_run.total_received > 0:
                dup_rate = (latest_run.total_duplicates / latest_run.total_received) * 100.0
                if dup_rate > 15.0:
                    alert_id = f"alert-dup-{r_id}-{int(datetime.now().timestamp() * 1000)}"
                    generated_alerts.append(
                        AlertItem(
                            id=alert_id,
                            severity=AlertSeverityEnum.MEDIUM,
                            title=f"High Duplicate Rate ({dup_rate:.1f}%) in Run #{r_id}",
                            description=f"Detected {latest_run.total_duplicates} duplicates out of {latest_run.total_received} records.",
                            source="Deduplicator",
                            timestamp=now_iso,
                            status=AlertStatusEnum.ACTIVE,
                            run_id=r_id,
                        )
                    )

            if latest_run.total_failed > 0:
                alert_id = f"alert-fail-{r_id}-{int(datetime.now().timestamp() * 1000)}"
                generated_alerts.append(
                    AlertItem(
                        id=alert_id,
                        severity=AlertSeverityEnum.HIGH,
                        title=f"Failed Sources in Run #{r_id}",
                        description=f"{latest_run.total_failed} source(s) failed during concurrent ingestion run #{r_id}.",
                        source="Pipeline Orchestrator",
                        timestamp=now_iso,
                        status=AlertStatusEnum.ACTIVE,
                        run_id=r_id,
                    )
                )

        # Check anomalies
        active_anomalies = [a for a in anomalies if (a.status.value if hasattr(a.status, "value") else str(a.status)) == "ACTIVE"]
        if len(active_anomalies) >= 3:
            alert_id = f"alert-anom-cluster-{int(datetime.now().timestamp() * 1000)}"
            generated_alerts.append(
                AlertItem(
                    id=alert_id,
                    severity=AlertSeverityEnum.HIGH if len(active_anomalies) > 5 else AlertSeverityEnum.MEDIUM,
                    title=f"Multiple Active Anomalies ({len(active_anomalies)} detected)",
                    description=f"{len(active_anomalies)} active records/runs flagged as anomalies by IsolationForest.",
                    source="ML Anomaly Engine",
                    timestamp=now_iso,
                    status=AlertStatusEnum.ACTIVE,
                )
            )

        if generated_alerts:
            await self.repository.save_alerts(generated_alerts)

        return generated_alerts

    async def get_alerts(self, status: Optional[str] = None) -> AlertsResponse:
        alerts = await self.repository.get_alerts(status=status)
        active_count = sum(1 for a in alerts if (a.status.value if hasattr(a.status, "value") else str(a.status)) == "ACTIVE")
        return AlertsResponse(alerts=alerts, active_count=active_count)

    async def update_alert_status(self, alert_id: str, status: AlertStatusEnum) -> Optional[AlertItem]:
        return await self.repository.update_alert_status(alert_id, status)
