"""
Shared application-level singletons and FastAPI dependency providers.

Member 3's real PostgreSQL repository is wired in here, and ONLY here:
`get_repository()` returns a `PostgresRepository` when DATABASE_URL is
configured, and transparently falls back to the original
`InMemoryRepository` when it isn't (e.g. a contributor running the API
locally without Postgres set up yet). Nothing in routes.py,
orchestrator.py, or ingestion_service.py needs to change either way,
because they all depend on the `Repository` Protocol, not a concrete
class.
"""

from functools import lru_cache

from app.core.config import get_settings
from app.database.database import get_session_factory
from app.repositories.base import InMemoryRepository, Repository
from app.repositories.postgres import PostgresRepository

_settings = get_settings()

if _settings.DATABASE_URL:
    _repository: Repository = PostgresRepository(get_session_factory(_settings.DATABASE_URL))
else:
    # No DATABASE_URL configured — keep the API fully runnable without a
    # database (e.g. local frontend/API development before Postgres is
    # set up). See MEMBER3_DATABASE.md for how to configure DATABASE_URL.
    _repository = InMemoryRepository()


def get_repository() -> Repository:
    """FastAPI dependency: returns the shared repository instance."""
    return _repository


@lru_cache
def get_settings_dependency():
    """FastAPI dependency wrapper around get_settings() for consistency."""
    return get_settings()
