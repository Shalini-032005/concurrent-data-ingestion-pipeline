"""
PostgresRepository — the real implementation of the `Repository` Protocol
(see app/repositories/base.py) backed by SQLAlchemy 2.x async + asyncpg.

Wired in at app/services/dependencies.py::get_repository(). Nothing in
routes.py, orchestrator.py, or ingestion_service.py needs to change to use
this instead of InMemoryRepository — they all depend on the Protocol.

Design notes:
- Every method opens its own short-lived AsyncSession from an injected
  async_sessionmaker (rather than holding one session open across calls),
  since a single Repository instance is shared across concurrent requests.
- save_records() and update_source_status()/save_ingestion_run() use
  PostgreSQL's INSERT ... ON CONFLICT (upsert) so duplicate record_hash
  values and repeat calls for the same source/run never raise or crash the
  ingestion run (Phase 13/16 of the database brief).
- Database errors are logged with full detail server-side and re-raised as
  a small set of typed exceptions so callers (and Member 1's error
  handlers) never see raw SQLAlchemy/asyncpg internals.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models import (
    AlertORM,
    AnomalyORM,
    DataLineageORM,
    IngestionRunORM,
    PipelineHealthORM,
    QualityMetricsORM,
    RecordORM,
    SourceORM,
)
from app.schemas.responses import (
    CanonicalRecord,
    IngestionRunSummary,
    RunStatusEnum,
    SourceHealthEnum,
    SourceResult,
    SourceStatus,
    StatsResponse,
)
from app.schemas.intelligence import (
    AlertItem,
    AlertSeverityEnum,
    AlertStatusEnum,
    AnomalyRecord,
    AnomalySeverityEnum,
    AnomalyStatusEnum,
    DataQualityResponse,
    LineageStep,
    PipelineHealthResponse,
    QualityTrendPoint,
    RecordLineageResponse,
)


logger = logging.getLogger(__name__)


class DatabaseError(RuntimeError):
    """Raised for any persistence failure. Callers should treat this as a
    500-class error; the original exception is always logged, never
    swallowed."""


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse the ISO-8601 strings used throughout app/schemas/responses.py
    into timezone-aware datetimes. Never raises — an unparsable timestamp
    becomes None rather than crashing persistence."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Could not parse timestamp %r; storing as NULL", value)
        return None


def _record_to_row(record: CanonicalRecord) -> Dict[str, Any]:
    record_hash = getattr(record, "record_hash", None)
    if not record_hash:
        # Should never happen once the deduplicator has run (it always sets
        # record_hash — see app/ingestion/deduplicator.py), but persistence
        # must not silently accept a record it can't dedupe against later.
        raise DatabaseError(
            f"Record {record.record_id!r} from {record.source!r} is missing "
            "record_hash; refusing to persist it without a dedup key."
        )
    return {
        "record_hash": record_hash,
        "source": record.source,
        "source_record_id": record.record_id,
        "name": record.name,
        "email": record.email,
        "value": record.value,
        "created_at": _parse_dt(record.created_at),
        "ingested_at": _parse_dt(record.ingested_at) or datetime.now(tz=None),
    }


def _row_to_record_dict(row: RecordORM) -> Dict[str, Any]:
    return {
        "record_id": row.source_record_id,
        "name": row.name,
        "email": row.email,
        "value": row.value,
        "source": row.source,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "ingested_at": row.ingested_at.isoformat() if row.ingested_at else None,
        "record_hash": row.record_hash,
    }


def _source_status_to_row(status: SourceStatus) -> Dict[str, Any]:
    status_value = status.status.value if hasattr(status.status, "value") else str(status.status)
    return {
        "source_name": status.source,
        "status": status_value,
        "last_success": _parse_dt(status.last_success),
        "last_failure": _parse_dt(status.last_failure),
        "records_received": status.records_received,
        "records_processed": status.records_processed,
        # duplicates/error_message aren't part of Member 1's current
        # SourceStatus schema; default them rather than guessing. If the
        # schema grows those fields later, getattr picks them up for free.
        "duplicates": getattr(status, "duplicates", 0) or 0,
        "error_message": getattr(status, "error_message", None),
    }


def _row_to_source_status(row: SourceORM) -> SourceStatus:
    try:
        health = SourceHealthEnum(row.status)
    except ValueError:
        health = SourceHealthEnum.UNKNOWN
    return SourceStatus(
        source=row.source_name,
        status=health,
        last_success=row.last_success.isoformat() if row.last_success else None,
        last_failure=row.last_failure.isoformat() if row.last_failure else None,
        records_received=row.records_received,
        records_processed=row.records_processed,
    )


def _run_to_row(run: IngestionRunSummary) -> Dict[str, Any]:
    source_results = [sr.model_dump(mode="json") for sr in run.source_results]
    failed_sources = [
        sr.source
        for sr in run.source_results
        if (sr.status.value if hasattr(sr.status, "value") else str(sr.status)) != "SUCCESS"
    ]
    status_value = run.status.value if hasattr(run.status, "value") else str(run.status)
    return {
        "id": run.run_id,
        "started_at": _parse_dt(run.started_at) or datetime.now(tz=None),
        "completed_at": _parse_dt(run.completed_at),
        "duration_ms": run.duration_ms,
        "status": status_value,
        "total_received": run.total_received,
        "total_processed": run.total_processed,
        "total_duplicates": run.total_duplicates,
        "total_failed": run.total_failed,
        "failed_sources": failed_sources,
        "source_results": source_results,
    }


def _row_to_run_summary(row: IngestionRunORM) -> IngestionRunSummary:
    source_results = [SourceResult(**sr) for sr in (row.source_results or [])]
    return IngestionRunSummary(
        run_id=row.id,
        status=RunStatusEnum(row.status),
        total_received=row.total_received,
        total_processed=row.total_processed,
        total_duplicates=row.total_duplicates,
        total_failed=row.total_failed,
        duration_ms=row.duration_ms or 0.0,
        started_at=row.started_at.isoformat() if row.started_at else "",
        completed_at=row.completed_at.isoformat() if row.completed_at else None,
        source_results=source_results,
    )


class PostgresRepository:
    """Satisfies app/repositories/base.py::Repository, backed by Postgres."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    # -- writes ------------------------------------------------------

    async def save_records(self, records: List[CanonicalRecord]) -> None:
        if not records:
            return
        rows = [_record_to_row(r) for r in records]
        stmt = pg_insert(RecordORM).values(rows)
        # Second layer of duplicate protection: even if a duplicate
        # record_hash slips past Member 2's deduplicator, Postgres ignores
        # the repeat insert instead of raising (Phase 13).
        stmt = stmt.on_conflict_do_nothing(index_elements=["record_hash"])
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    await session.execute(stmt)
        except SQLAlchemyError:
            logger.exception("save_records failed for %d record(s)", len(rows))
            raise DatabaseError("Failed to save records") from None

    async def save_ingestion_run(self, run: IngestionRunSummary) -> None:
        row = _run_to_row(run)
        stmt = pg_insert(IngestionRunORM).values(**row)
        update_cols = {k: v for k, v in row.items() if k != "id"}
        stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    await session.execute(stmt)
        except SQLAlchemyError:
            logger.exception("save_ingestion_run failed for run_id=%s", run.run_id)
            raise DatabaseError(f"Failed to save ingestion run {run.run_id}") from None

    async def update_source_status(self, status: SourceStatus) -> None:
        row = _source_status_to_row(status)
        stmt = pg_insert(SourceORM).values(**row)
        update_cols = {k: v for k, v in row.items() if k != "source_name"}
        stmt = stmt.on_conflict_do_update(index_elements=["source_name"], set_=update_cols)
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    await session.execute(stmt)
        except SQLAlchemyError:
            logger.exception("update_source_status failed for source=%s", status.source)
            raise DatabaseError(f"Failed to update status for source {status.source}") from None

    # -- reads ---------------------------------------------------------

    async def get_stats(self) -> StatsResponse:
        try:
            async with self._session_factory() as session:
                totals_row = (
                    await session.execute(
                        select(
                            func.coalesce(func.sum(IngestionRunORM.total_received), 0),
                            func.coalesce(func.sum(IngestionRunORM.total_processed), 0),
                            func.coalesce(func.sum(IngestionRunORM.total_duplicates), 0),
                            func.coalesce(func.sum(IngestionRunORM.total_failed), 0),
                        )
                    )
                ).one()
                last_run = (
                    await session.execute(
                        select(IngestionRunORM).order_by(IngestionRunORM.id.desc()).limit(1)
                    )
                ).scalar_one_or_none()
        except SQLAlchemyError:
            logger.exception("get_stats failed")
            raise DatabaseError("Failed to compute statistics") from None

        total_received, total_processed, total_duplicates, total_failed = totals_row
        if last_run is None:
            return StatsResponse(
                total_received=total_received,
                total_processed=total_processed,
                total_duplicates=total_duplicates,
                total_failed=total_failed,
            )

        last_ts = last_run.completed_at or last_run.started_at
        return StatsResponse(
            total_received=total_received,
            total_processed=total_processed,
            total_duplicates=total_duplicates,
            total_failed=total_failed,
            last_run_status=last_run.status,
            last_run_timestamp=last_ts.isoformat() if last_ts else None,
            last_run_duration_ms=last_run.duration_ms,
        )

    async def get_sources(self) -> List[SourceStatus]:
        try:
            async with self._session_factory() as session:
                rows = (await session.execute(select(SourceORM))).scalars().all()
        except SQLAlchemyError:
            logger.exception("get_sources failed")
            raise DatabaseError("Failed to fetch sources") from None
        return [_row_to_source_status(r) for r in rows]

    async def get_records(
        self, page: int = 1, page_size: int = 20, source: Optional[str] = None
    ) -> Dict[str, Any]:
        page = max(page, 1)
        page_size = max(page_size, 1)
        try:
            async with self._session_factory() as session:
                count_stmt = select(func.count()).select_from(RecordORM)
                query_stmt = select(RecordORM)
                if source is not None:
                    count_stmt = count_stmt.where(RecordORM.source == source)
                    query_stmt = query_stmt.where(RecordORM.source == source)

                total = (await session.execute(count_stmt)).scalar_one()

                query_stmt = (
                    query_stmt.order_by(RecordORM.ingested_at.desc(), RecordORM.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
                rows = (await session.execute(query_stmt)).scalars().all()
        except SQLAlchemyError:
            logger.exception("get_records failed (page=%s, page_size=%s, source=%s)", page, page_size, source)
            raise DatabaseError("Failed to fetch records") from None

        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "records": [_row_to_record_dict(r) for r in rows],
        }

    async def get_runs(self) -> List[IngestionRunSummary]:
        try:
            async with self._session_factory() as session:
                rows = (
                    await session.execute(
                        select(IngestionRunORM).order_by(IngestionRunORM.id.desc()).limit(20)
                    )
                ).scalars().all()
        except SQLAlchemyError:
            logger.exception("get_runs failed")
            raise DatabaseError("Failed to fetch ingestion runs") from None
        return [_row_to_run_summary(r) for r in rows]

    async def get_run(self, run_id: int) -> Optional[IngestionRunSummary]:
        try:
            async with self._session_factory() as session:
                row = await session.get(IngestionRunORM, run_id)
        except SQLAlchemyError:
            logger.exception("get_run failed for run_id=%s", run_id)
            raise DatabaseError(f"Failed to fetch ingestion run {run_id}") from None
        return _row_to_run_summary(row) if row else None

    # Phase 1 Data Intelligence Extensions
    async def save_quality_metrics(self, metrics: DataQualityResponse, run_id: Optional[int] = None) -> None:
        row = QualityMetricsORM(
            run_id=run_id,
            overall_score=metrics.overall_score,
            completeness=metrics.completeness,
            validity=metrics.validity,
            consistency=metrics.consistency,
            uniqueness=metrics.uniqueness,
            freshness=metrics.freshness,
            details=metrics.details,
            timestamp=_parse_dt(metrics.timestamp) or datetime.now(tz=None),
        )
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add(row)
        except SQLAlchemyError:
            logger.exception("save_quality_metrics failed")
            raise DatabaseError("Failed to save quality metrics") from None

    async def get_latest_quality_metrics(self) -> Optional[DataQualityResponse]:
        try:
            async with self._session_factory() as session:
                row = (
                    await session.execute(
                        select(QualityMetricsORM).order_by(QualityMetricsORM.timestamp.desc()).limit(1)
                    )
                ).scalar_one_or_none()
        except SQLAlchemyError:
            logger.exception("get_latest_quality_metrics failed")
            raise DatabaseError("Failed to fetch quality metrics") from None
        if not row:
            return None
        return DataQualityResponse(
            overall_score=row.overall_score,
            completeness=row.completeness,
            validity=row.validity,
            consistency=row.consistency,
            uniqueness=row.uniqueness,
            freshness=row.freshness,
            timestamp=row.timestamp.isoformat(),
            details=row.details or {},
        )

    async def get_quality_trend(self, limit: int = 20) -> List[QualityTrendPoint]:
        try:
            async with self._session_factory() as session:
                rows = (
                    await session.execute(
                        select(QualityMetricsORM).order_by(QualityMetricsORM.timestamp.asc()).limit(limit)
                    )
                ).scalars().all()
        except SQLAlchemyError:
            logger.exception("get_quality_trend failed")
            raise DatabaseError("Failed to fetch quality trend") from None
        points: List[QualityTrendPoint] = []
        for idx, r in enumerate(rows):
            points.append(
                QualityTrendPoint(
                    run_id=r.run_id or (idx + 1),
                    timestamp=r.timestamp.isoformat(),
                    overall_score=r.overall_score,
                    completeness=r.completeness,
                    validity=r.validity,
                    consistency=r.consistency,
                    uniqueness=r.uniqueness,
                    freshness=r.freshness,
                )
            )
        return points

    async def save_anomalies(self, anomalies: List[AnomalyRecord]) -> None:
        if not anomalies:
            return
        rows = []
        for a in anomalies:
            severity_str = a.severity.value if hasattr(a.severity, "value") else str(a.severity)
            status_str = a.status.value if hasattr(a.status, "value") else str(a.status)
            rows.append(
                {
                    "id": a.id,
                    "run_id": a.run_id,
                    "record_id": a.record_id,
                    "source": a.source,
                    "feature_name": a.feature_name,
                    "current_value": a.current_value,
                    "expected_range": a.expected_range,
                    "severity": severity_str,
                    "reason": a.reason,
                    "status": status_str,
                    "timestamp": _parse_dt(a.timestamp) or datetime.now(tz=None),
                }
            )
        stmt = pg_insert(AnomalyORM).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    await session.execute(stmt)
        except SQLAlchemyError:
            logger.exception("save_anomalies failed")
            raise DatabaseError("Failed to save anomalies") from None

    async def get_anomalies(
        self, source: Optional[str] = None, severity: Optional[str] = None
    ) -> List[AnomalyRecord]:
        try:
            async with self._session_factory() as session:
                stmt = select(AnomalyORM)
                if source:
                    stmt = stmt.where(AnomalyORM.source == source)
                if severity:
                    stmt = stmt.where(AnomalyORM.severity == severity)
                stmt = stmt.order_by(AnomalyORM.timestamp.desc())
                rows = (await session.execute(stmt)).scalars().all()
        except SQLAlchemyError:
            logger.exception("get_anomalies failed")
            raise DatabaseError("Failed to fetch anomalies") from None
        return [
            AnomalyRecord(
                id=r.id,
                run_id=r.run_id,
                record_id=r.record_id,
                source=r.source,
                feature_name=r.feature_name,
                current_value=r.current_value,
                expected_range=r.expected_range,
                severity=AnomalySeverityEnum(r.severity),
                reason=r.reason,
                status=AnomalyStatusEnum(r.status),
                timestamp=r.timestamp.isoformat(),
            )
            for r in rows
        ]

    async def get_anomaly(self, anomaly_id: str) -> Optional[AnomalyRecord]:
        try:
            async with self._session_factory() as session:
                row = await session.get(AnomalyORM, anomaly_id)
        except SQLAlchemyError:
            logger.exception("get_anomaly failed for id=%s", anomaly_id)
            raise DatabaseError("Failed to fetch anomaly") from None
        if not row:
            return None
        return AnomalyRecord(
            id=row.id,
            run_id=row.run_id,
            record_id=row.record_id,
            source=row.source,
            feature_name=row.feature_name,
            current_value=row.current_value,
            expected_range=row.expected_range,
            severity=AnomalySeverityEnum(row.severity),
            reason=row.reason,
            status=AnomalyStatusEnum(row.status),
            timestamp=row.timestamp.isoformat(),
        )

    async def save_alerts(self, alerts: List[AlertItem]) -> None:
        if not alerts:
            return
        rows = []
        for a in alerts:
            sev = a.severity.value if hasattr(a.severity, "value") else str(a.severity)
            st = a.status.value if hasattr(a.status, "value") else str(a.status)
            rows.append(
                {
                    "id": a.id,
                    "severity": sev,
                    "title": a.title,
                    "description": a.description,
                    "source": a.source,
                    "status": st,
                    "run_id": a.run_id,
                    "record_id": a.record_id,
                    "timestamp": _parse_dt(a.timestamp) or datetime.now(tz=None),
                }
            )
        stmt = pg_insert(AlertORM).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    await session.execute(stmt)
        except SQLAlchemyError:
            logger.exception("save_alerts failed")
            raise DatabaseError("Failed to save alerts") from None

    async def get_alerts(self, status: Optional[str] = None) -> List[AlertItem]:
        try:
            async with self._session_factory() as session:
                stmt = select(AlertORM)
                if status:
                    stmt = stmt.where(AlertORM.status == status)
                stmt = stmt.order_by(AlertORM.timestamp.desc())
                rows = (await session.execute(stmt)).scalars().all()
        except SQLAlchemyError:
            logger.exception("get_alerts failed")
            raise DatabaseError("Failed to fetch alerts") from None
        return [
            AlertItem(
                id=r.id,
                severity=AlertSeverityEnum(r.severity),
                title=r.title,
                description=r.description,
                source=r.source,
                timestamp=r.timestamp.isoformat(),
                status=AlertStatusEnum(r.status),
                run_id=r.run_id,
                record_id=r.record_id,
            )
            for r in rows
        ]

    async def update_alert_status(self, alert_id: str, status: AlertStatusEnum) -> Optional[AlertItem]:
        st_val = status.value if hasattr(status, "value") else str(status)
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    row = await session.get(AlertORM, alert_id)
                    if row:
                        row.status = st_val
                        await session.flush()
                        return AlertItem(
                            id=row.id,
                            severity=AlertSeverityEnum(row.severity),
                            title=row.title,
                            description=row.description,
                            source=row.source,
                            timestamp=row.timestamp.isoformat(),
                            status=AlertStatusEnum(row.status),
                            run_id=row.run_id,
                            record_id=row.record_id,
                        )
        except SQLAlchemyError:
            logger.exception("update_alert_status failed for alert_id=%s", alert_id)
            raise DatabaseError("Failed to update alert status") from None
        return None

    async def save_pipeline_health(self, health: PipelineHealthResponse) -> None:
        row = PipelineHealthORM(
            overall_score=health.overall_score,
            availability=health.availability,
            latency=health.latency,
            validation=health.validation,
            reliability=health.reliability,
            status=health.status,
            updated_at=_parse_dt(health.updated_at) or datetime.now(tz=None),
        )
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add(row)
        except SQLAlchemyError:
            logger.exception("save_pipeline_health failed")
            raise DatabaseError("Failed to save pipeline health") from None

    async def get_latest_pipeline_health(self) -> Optional[PipelineHealthResponse]:
        try:
            async with self._session_factory() as session:
                row = (
                    await session.execute(
                        select(PipelineHealthORM).order_by(PipelineHealthORM.updated_at.desc()).limit(1)
                    )
                ).scalar_one_or_none()
        except SQLAlchemyError:
            logger.exception("get_latest_pipeline_health failed")
            raise DatabaseError("Failed to fetch pipeline health") from None
        if not row:
            return None
        return PipelineHealthResponse(
            overall_score=row.overall_score,
            availability=row.availability,
            latency=row.latency,
            validation=row.validation,
            reliability=row.reliability,
            status=row.status,
            updated_at=row.updated_at.isoformat(),
        )

    async def save_lineage_steps(
        self, record_id: str, source: str, run_id: Optional[int], steps: List[LineageStep]
    ) -> None:
        if not steps:
            return
        rows = [
            DataLineageORM(
                record_id=record_id,
                source=source,
                run_id=run_id,
                stage=step.stage,
                status=step.status,
                details=step.details,
                timestamp=_parse_dt(step.timestamp) or datetime.now(tz=None),
            )
            for step in steps
        ]
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add_all(rows)
        except SQLAlchemyError:
            logger.exception("save_lineage_steps failed")
            raise DatabaseError("Failed to save data lineage") from None

    async def get_record_lineage(self, record_id: str) -> Optional[RecordLineageResponse]:
        try:
            async with self._session_factory() as session:
                rows = (
                    await session.execute(
                        select(DataLineageORM)
                        .where(DataLineageORM.record_id == record_id)
                        .order_by(DataLineageORM.timestamp.asc())
                    )
                ).scalars().all()
        except SQLAlchemyError:
            logger.exception("get_record_lineage failed for record_id=%s", record_id)
            raise DatabaseError("Failed to fetch record lineage") from None
        if not rows:
            return None
        first = rows[0]
        steps = [
            LineageStep(
                stage=r.stage,
                status=r.status,
                timestamp=r.timestamp.isoformat(),
                details=r.details or {},
            )
            for r in rows
        ]
        return RecordLineageResponse(
            record_id=record_id,
            source=first.source,
            run_id=first.run_id,
            received_at=first.timestamp.isoformat(),
            final_status=rows[-1].status,
            steps=steps,
        )

