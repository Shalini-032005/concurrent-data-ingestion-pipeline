"""
Async PostgreSQL connection layer (Member 3 — Database + Persistence).

Owns the SQLAlchemy async engine, the session factory, table creation, and
a lightweight connection health check. Nothing in here talks about
records/sources/runs directly — that's app/database/models.py (ORM shapes)
and app/repositories/postgres.py (the Repository implementation).

Works against both:
- a local PostgreSQL instance, and
- Supabase PostgreSQL (including Supabase's connection pooler),

using nothing but a single DATABASE_URL — see MEMBER3_DATABASE.md.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database.models import Base

logger = logging.getLogger(__name__)

# Module-level singletons. A hackathon backend has exactly one database, so
# a per-DATABASE_URL cache (rather than a single unconditional global) keeps
# this safe if tests point at a different URL than the running app without
# needing a class wrapper around every call site.
_engines: dict[str, AsyncEngine] = {}
_session_factories: dict[str, async_sessionmaker[AsyncSession]] = {}


def _normalize_database_url(url: str) -> str:
    """Accept the URL forms people actually copy-paste (Heroku/Supabase-style
    `postgres://...` or plain `postgresql://...`) and coerce them to the
    asyncpg driver SQLAlchemy needs: `postgresql+asyncpg://...`.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _connect_args_for(url: str) -> dict:
    """asyncpg-specific connection tweaks needed for Supabase's pooler.

    Supabase's transaction-mode pooler (pgbouncer, typically port 6543)
    does not support asyncpg's server-side prepared statement cache — reused
    prepared statement names collide across pooled connections. Disabling
    the cache (statement_cache_size=0) is the documented workaround and is
    harmless against a direct Postgres connection (port 5432) too, so it's
    always applied rather than sniffed for conditionally.
    """
    parsed = urlparse(url)
    connect_args: dict = {"statement_cache_size": 0}
    if parsed.hostname and "supabase" in parsed.hostname:
        connect_args["ssl"] = True
    return connect_args


def get_engine(database_url: str) -> AsyncEngine:
    """Return the shared async engine for this DATABASE_URL, creating it on
    first use. Safe to call repeatedly (e.g. from a FastAPI dependency)."""
    normalized = _normalize_database_url(database_url)
    engine = _engines.get(normalized)
    if engine is None:
        engine = create_async_engine(
            normalized,
            echo=False,
            pool_pre_ping=True,  # avoid handing out dead pooled connections
            pool_size=5,
            max_overflow=5,
            connect_args=_connect_args_for(normalized),
        )
        _engines[normalized] = engine
    return engine


def get_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Return the shared session factory for this DATABASE_URL."""
    normalized = _normalize_database_url(database_url)
    factory = _session_factories.get(normalized)
    if factory is None:
        factory = async_sessionmaker(
            bind=get_engine(database_url),
            class_=AsyncSession,
            expire_on_commit=False,
        )
        _session_factories[normalized] = factory
    return factory


async def init_db(database_url: str) -> None:
    """Create any tables that don't exist yet.

    Hackathon-appropriate: no Alembic, just Base.metadata.create_all() run
    through an async connection. Safe to call on every startup — existing
    tables are left untouched.
    """
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")


async def check_database_connection(database_url: Optional[str]) -> bool:
    """Lightweight health check: SELECT 1. Returns True/False, never raises."""
    if not database_url:
        return False
    try:
        engine = get_engine(database_url)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Database connection check failed")
        return False


async def get_db(database_url: str) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI-style dependency: yields a session, closes it afterwards.

    Not currently wired into any route (Member 3's repository opens its own
    sessions internally — see app/repositories/postgres.py), but available
    for any endpoint or script that wants a raw session directly.
    """
    factory = get_session_factory(database_url)
    async with factory() as session:
        yield session


async def dispose_engine(database_url: Optional[str] = None) -> None:
    """Dispose engine(s) and drop cached session factories. Call on app
    shutdown, and between tests that each want a clean engine."""
    global _engines, _session_factories
    if database_url is None:
        for engine in _engines.values():
            await engine.dispose()
        _engines = {}
        _session_factories = {}
        return

    normalized = _normalize_database_url(database_url)
    engine = _engines.pop(normalized, None)
    _session_factories.pop(normalized, None)
    if engine is not None:
        await engine.dispose()
