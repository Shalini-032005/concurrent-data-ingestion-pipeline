"""
Logging configuration.

Call `configure_logging()` once at application startup. Everywhere else,
just do `logger = logging.getLogger(__name__)` and log normally.

NEVER log secrets (DATABASE_URL, API keys, tokens). If you need to log a
connection string for debugging, mask it first.
"""

import logging
import sys

LOG_FORMAT = "[%(levelname)s] %(asctime)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers if configure_logging() is called more than once
    # (e.g. under --reload).
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root.addHandler(handler)

    # Quiet down noisy third-party loggers a little, but keep uvicorn's own
    # access/error logs since they're useful during the demo.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def mask_secret(value: str, keep: int = 4) -> str:
    """Utility for safely logging something that might contain a secret,
    e.g. a DATABASE_URL. Never log the raw value."""
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "*" * (len(value) - keep)
