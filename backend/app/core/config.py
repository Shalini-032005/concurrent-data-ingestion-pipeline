"""
Application configuration.

Loads settings from environment variables (and a local .env file during
development). All values have sensible development defaults so the backend
can be started immediately without any setup.

Other teammates:
- DATABASE_URL is consumed by the database layer (Member 3). This module
  does not open a database connection itself.
- CORS_ORIGINS should be updated by whoever deploys the frontend, so the
  deployed dashboard origin is allowed in production.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- General ---
    ENVIRONMENT: str = "development"
    APP_NAME: str = "Concurrent Data Ingestion Pipeline API"

    # --- Database (owned/implemented by Member 3) ---
    DATABASE_URL: str = ""

    # --- CORS ---
    # Comma-separated string in the environment, exposed as a list via the
    # `cors_origins_list` property below.
    CORS_ORIGINS: str = "http://localhost:5173"

    # --- Ingestion tuning ---
    INGESTION_TIMEOUT: float = 5.0     # seconds, per-source timeout
    MAX_RETRIES: int = 3               # attempts per source (including first)
    RETRY_DELAY: float = 0.5           # base seconds between retries

    # --- Server ---
    PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS into a clean list of origins."""
        if not self.CORS_ORIGINS:
            return []
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — import and call this, don't instantiate Settings() directly."""
    return Settings()
