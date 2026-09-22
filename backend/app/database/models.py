"""
SQLAlchemy ORM models (Member 3 — Database + Persistence + Statistics).

Three tables, matching MEMBER3_DATABASE.md 1:1:

- records          one row per unique canonical record (record_hash UNIQUE)
- sources          one row per source, upserted after every run (health/stats)
- ingestion_runs   one row per ingestion run, upserted by run_id

Standard PostgreSQL + SQLAlchemy only — no SQLite-specific types, no
Postgres-only extensions beyond JSON — so this works unchanged against
local Postgres and Supabase Postgres.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RecordORM(Base):
    """A single unique, normalized record handed off by Member 2.

    record_hash is UNIQUE — this is the database-level duplicate guard that
    backs up Member 2's application-level deduplication (see
    app/repositories/postgres.py::save_records, which uses
    INSERT ... ON CONFLICT (record_hash) DO NOTHING).
    """

    __tablename__ = "records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        # record_hash already gets a unique index from unique=True above.
        Index("ix_records_source", "source"),
        Index("ix_records_source_record_id", "source_record_id"),
        Index("ix_records_created_at", "created_at"),
        Index("ix_records_ingested_at", "ingested_at"),
    )


class SourceORM(Base):
    """Latest known health/throughput snapshot for one source. Upserted
    after every ingestion run — one row per source, not one row per run."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="UNKNOWN", nullable=False)
    last_success: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    records_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (
        # source_name already gets a unique index from unique=True above.
    )


class IngestionRunORM(Base):
    """One row per ingestion run.

    `id` is NOT autoincrement — it is the orchestrator's own run_id
    (app/ingestion/orchestrator.py::next_run_id), passed straight through,
    so GET /api/runs/{run_id} maps 1:1 to this primary key. The orchestrator
    calls save_ingestion_run() exactly once per run with the final summary,
    so persistence is a single upsert keyed on this id rather than a
    separate create-then-update pair.
    """

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    total_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_duplicates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Names of sources that didn't fully succeed on this run (quick to scan).
    failed_sources: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    # Full per-source result list (SourceResult.model_dump() each), stored so
    # GET /api/runs/{run_id} can return the complete IngestionRunSummary
    # (including source_results) without reaching back into any other table.
    source_results: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_ingestion_runs_started_at", "started_at"),
        Index("ix_ingestion_runs_status", "status"),
    )


class QualityMetricsORM(Base):
    """Quality score snapshots computed per ingestion run."""

    __tablename__ = "quality_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    completeness: Mapped[float] = mapped_column(Float, nullable=False)
    validity: Mapped[float] = mapped_column(Float, nullable=False)
    consistency: Mapped[float] = mapped_column(Float, nullable=False)
    uniqueness: Mapped[float] = mapped_column(Float, nullable=False)
    freshness: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_quality_metrics_run_id", "run_id"),
        Index("ix_quality_metrics_timestamp", "timestamp"),
    )


class AnomalyORM(Base):
    """ML anomaly detection records."""

    __tablename__ = "anomalies"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    feature_name: Mapped[str] = mapped_column(String(100), nullable=False)
    current_value: Mapped[float] = mapped_column(Float, nullable=False)
    expected_range: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_anomalies_source", "source"),
        Index("ix_anomalies_severity", "severity"),
        Index("ix_anomalies_timestamp", "timestamp"),
    )


class AlertORM(Base):
    """Intelligent alert system items."""

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_alerts_severity", "severity"),
        Index("ix_alerts_status", "status"),
        Index("ix_alerts_timestamp", "timestamp"),
    )


class PipelineHealthORM(Base):
    """Historical snapshots of pipeline health scores."""

    __tablename__ = "pipeline_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    availability: Mapped[float] = mapped_column(Float, nullable=False)
    latency: Mapped[float] = mapped_column(Float, nullable=False)
    validation: Mapped[float] = mapped_column(Float, nullable=False)
    reliability: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_pipeline_health_updated_at", "updated_at"),
    )


class DataLineageORM(Base):
    """Record execution flow details across ingestion stages."""

    __tablename__ = "data_lineage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_data_lineage_record_id", "record_id"),
        Index("ix_data_lineage_run_id", "run_id"),
    )

