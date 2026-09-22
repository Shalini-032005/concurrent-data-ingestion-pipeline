"""
Data Quality Engine service for Phase 1.
Computes real Data Quality metrics (Completeness, Validity, Consistency, Uniqueness, Freshness)
and Overall Quality Score (0-100) from actual application data.
"""

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional

import pandas as pd

from app.repositories.base import Repository
from app.schemas.responses import CanonicalRecord
from app.schemas.intelligence import (
    DataQualityResponse,
    QualityTrendPoint,
    QualityTrendResponse,
)

logger = logging.getLogger(__name__)


class DataQualityService:
    def __init__(self, repository: Repository):
        self.repository = repository

    async def calculate_quality(self, run_id: Optional[int] = None) -> DataQualityResponse:
        records_data = await self.repository.get_records(page=1, page_size=1000)
        records_raw: List[Dict] = records_data.get("records", [])

        if not records_raw:
            # Baseline response when no records exist yet
            now_iso = datetime.now(timezone.utc).isoformat()
            res = DataQualityResponse(
                overall_score=100.0,
                completeness=100.0,
                validity=100.0,
                consistency=100.0,
                uniqueness=100.0,
                freshness=100.0,
                timestamp=now_iso,
                quality_by_source={},
                details={"message": "No records in repository yet"},
            )
            await self.repository.save_quality_metrics(res, run_id=run_id)
            return res

        df = pd.DataFrame(records_raw)

        # 1. Completeness: % of non-null/non-empty values across key fields (name, email, value, created_at)
        total_cells = len(df) * 4
        missing_count = 0
        for col in ["name", "email", "value", "created_at"]:
            if col in df.columns:
                missing_count += df[col].isna().sum() + (df[col] == "").sum()
            else:
                missing_count += len(df)

        completeness = max(0.0, min(100.0, ((total_cells - missing_count) / total_cells) * 100.0))

        # 2. Validity: % of records with valid non-negative numeric value & non-empty id & valid email format
        valid_records = 0
        for _, row in df.iterrows():
            is_valid = True
            email = str(row.get("email") or "")
            if not email or "@" not in email or "." not in email:
                is_valid = False
            val = row.get("value")
            if val is None or not isinstance(val, (int, float)) or val < 0:
                is_valid = False
            if is_valid:
                valid_records += 1

        validity = (valid_records / len(df)) * 100.0 if len(df) > 0 else 100.0

        # 3. Consistency: % of records matching ISO format timestamps & clean lowercase email formats
        consistent_records = 0
        for _, row in df.iterrows():
            email = str(row.get("email") or "")
            created_at = str(row.get("created_at") or "")
            is_consistent = (email == email.lower()) and bool(created_at)
            if is_consistent:
                consistent_records += 1
        consistency = (consistent_records / len(df)) * 100.0 if len(df) > 0 else 100.0

        # 4. Uniqueness: % of records with unique record_hash
        if "record_hash" in df.columns:
            unique_hashes = df["record_hash"].nunique()
            uniqueness = (unique_hashes / len(df)) * 100.0 if len(df) > 0 else 100.0
        else:
            uniqueness = 100.0

        # 5. Freshness: recency of ingested_at timestamps (decay score based on hours old)
        freshness = 95.0
        if "ingested_at" in df.columns:
            try:
                latest_ts = pd.to_datetime(df["ingested_at"], utc=True).max()
                if pd.notnull(latest_ts):
                    hours_diff = (datetime.now(timezone.utc) - latest_ts).total_seconds() / 3600.0
                    freshness = max(50.0, min(100.0, 100.0 - min(hours_diff * 2.0, 50.0)))
            except Exception:
                freshness = 90.0

        # Overall Score: weighted formula
        overall_score = round(
            (completeness * 0.25)
            + (validity * 0.25)
            + (consistency * 0.20)
            + (uniqueness * 0.15)
            + (freshness * 0.15),
            1,
        )

        # Quality by source
        quality_by_source: Dict[str, float] = {}
        if "source" in df.columns:
            for source_name, group in df.groupby("source"):
                src_total = len(group) * 3
                src_missing = 0
                for col in ["name", "email", "value"]:
                    if col in group.columns:
                        src_missing += group[col].isna().sum() + (group[col] == "").sum()
                src_comp = ((src_total - src_missing) / src_total) * 100.0 if src_total > 0 else 100.0
                quality_by_source[str(source_name)] = round(src_comp, 1)

        now_iso = datetime.now(timezone.utc).isoformat()
        res = DataQualityResponse(
            overall_score=overall_score,
            completeness=round(completeness, 1),
            validity=round(validity, 1),
            consistency=round(consistency, 1),
            uniqueness=round(uniqueness, 1),
            freshness=round(freshness, 1),
            timestamp=now_iso,
            quality_by_source=quality_by_source,
            details={
                "total_records_evaluated": len(df),
                "valid_records_count": valid_records,
                "consistent_records_count": consistent_records,
            },
        )

        await self.repository.save_quality_metrics(res, run_id=run_id)
        return res

    async def get_summary(self) -> DataQualityResponse:
        latest = await self.repository.get_latest_quality_metrics()
        if latest is None:
            return await self.calculate_quality()
        return latest

    async def get_trend(self, limit: int = 20) -> QualityTrendResponse:
        points = await self.repository.get_quality_trend(limit=limit)
        return QualityTrendResponse(trend=points)
