"""
Simple async retry helper.

Wraps an async callable with a bounded number of attempts and a delay
between them. Kept intentionally simple for the hackathon — no
exponential backoff/jitter complexity, just linear backoff by attempt
number, which is more than enough to demonstrate retry behavior.
"""

import asyncio
import logging
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    max_retries: int = 3,
    retry_delay: float = 0.5,
    label: str = "operation",
) -> T:
    """
    Call `func()` up to `max_retries` times (first call counts as attempt 1).

    Re-raises the last exception if all attempts fail. Does NOT retry
    forever — `max_retries` is a hard ceiling.
    """
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return await func()
        except Exception as exc:  # noqa: BLE001 - intentionally broad, this is a generic retry wrapper
            last_exc = exc
            if attempt < max_retries:
                logger.warning(
                    "%s failed on attempt %d/%d: %s — retrying in %.2fs",
                    label, attempt, max_retries, exc, retry_delay,
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.warning(
                    "%s failed on final attempt %d/%d: %s — giving up",
                    label, attempt, max_retries, exc,
                )

    # If we get here, every attempt failed.
    assert last_exc is not None
    raise last_exc
