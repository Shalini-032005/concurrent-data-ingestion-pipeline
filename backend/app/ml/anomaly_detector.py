"""
ML Anomaly Detector module.
Uses IsolationForest from scikit-learn for anomaly detection and
builds an empirical statistical explanation layer over historical feature distributions.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.ensemble import IsolationForest

from app.schemas.intelligence import (
    AnomalyRecord,
    AnomalySeverityEnum,
    AnomalyStatusEnum,
)

logger = logging.getLogger(__name__)


class MLAnomalyDetector:
    def __init__(self, contamination: float = 0.1):
        self.contamination = contamination
        self.model = IsolationForest(n_estimators=100, contamination=self.contamination, random_state=42)
        self.is_fitted = False

    def detect_anomalies_for_records(
        self,
        records: List[Dict[str, Any]],
        historical_records: List[Dict[str, Any]],
        run_id: Optional[int] = None,
    ) -> List[AnomalyRecord]:
        """Scans records for numerical value anomalies using Isolation Forest & historical range stats."""
        if not records:
            return []

        # Gather numeric values for fitting
        all_vals = []
        for r in historical_records + records:
            v = r.get("value")
            if v is not None and isinstance(v, (int, float)):
                all_vals.append(v)

        if len(all_vals) < 5:
            logger.info("Not enough numeric data points (%d) to fit IsolationForest", len(all_vals))
            return []

        X_train = np.array(all_vals).reshape(-1, 1)
        self.model.fit(X_train)
        self.is_fitted = True

        mean_val = float(np.mean(all_vals))
        std_val = float(np.std(all_vals))
        if std_val == 0:
            std_val = 1.0

        low_bound = max(0.0, mean_val - 2.5 * std_val)
        high_bound = mean_val + 2.5 * std_val

        detected: List[AnomalyRecord] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for rec in records:
            val = rec.get("value")
            if val is None or not isinstance(val, (int, float)):
                continue

            # IsolationForest prediction (-1 = anomaly, 1 = normal)
            pred = self.model.predict([[val]])[0]

            # Explanation layer using z-score & range boundaries
            z_score = abs(val - mean_val) / std_val if std_val > 0 else 0
            is_range_outlier = val < low_bound or val > high_bound

            if pred == -1 or z_score > 2.5 or is_range_outlier:
                source = str(rec.get("source") or "Unknown")
                rec_id = str(rec.get("record_id") or rec.get("id") or "N/A")

                severity = AnomalySeverityEnum.MEDIUM
                if z_score > 4.0 or val > mean_val + 4 * std_val:
                    severity = AnomalySeverityEnum.HIGH
                elif z_score < 2.0:
                    severity = AnomalySeverityEnum.LOW

                reason = (
                    f"Record value ({val:.2f}) is significantly outside historical normal range "
                    f"[{low_bound:.2f} – {high_bound:.2f}]. Historical mean: {mean_val:.2f}, "
                    f"Std dev: {std_val:.2f}."
                )

                anomaly_id = f"anom-{run_id or '0'}-{rec_id}-{int(datetime.now().timestamp() * 1000)}"

                detected.append(
                    AnomalyRecord(
                        id=anomaly_id,
                        run_id=run_id,
                        record_id=rec_id,
                        source=source,
                        feature_name="value",
                        current_value=float(val),
                        expected_range=f"{low_bound:.1f} – {high_bound:.1f}",
                        severity=severity,
                        reason=reason,
                        status=AnomalyStatusEnum.ACTIVE,
                        timestamp=now_iso,
                    )
                )

        return detected

    def detect_anomalies_for_runs(
        self,
        latest_run: Dict[str, Any],
        historical_runs: List[Dict[str, Any]],
    ) -> List[AnomalyRecord]:
        """Detects run-level performance anomalies (duration, failure rate, duplicate count)."""
        if len(historical_runs) < 3:
            return []

        durations = [r.get("duration_ms", 0.0) for r in historical_runs if r.get("duration_ms")]
        if not durations:
            return []

        mean_dur = float(np.mean(durations))
        std_dur = float(np.std(durations)) if len(durations) > 1 else 100.0
        if std_dur == 0:
            std_dur = 50.0

        current_dur = latest_run.get("duration_ms", 0.0)
        run_id = latest_run.get("run_id")
        now_iso = datetime.now(timezone.utc).isoformat()
        detected: List[AnomalyRecord] = []

        if current_dur > mean_dur + 2.5 * std_dur:
            anomaly_id = f"anom-run-{run_id}-{int(datetime.now().timestamp() * 1000)}"
            reason = (
                f"Ingestion run duration ({current_dur:.1f} ms) exceeded historical baseline "
                f"[{mean_dur - std_dur:.1f} ms – {mean_dur + std_dur * 2:.1f} ms]."
            )
            detected.append(
                AnomalyRecord(
                    id=anomaly_id,
                    run_id=run_id,
                    record_id=None,
                    source="Pipeline Orchestrator",
                    feature_name="duration_ms",
                    current_value=float(current_dur),
                    expected_range=f"<{mean_dur + std_dur * 2:.1f} ms",
                    severity=AnomalySeverityEnum.HIGH,
                    reason=reason,
                    status=AnomalyStatusEnum.ACTIVE,
                    timestamp=now_iso,
                )
            )

        return detected
