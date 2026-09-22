"""
Exceptions raised by mock data sources.

Kept deliberately small (Phase 29 in the brief): sources raise a single,
clearly-named exception on failure and let the caller (Member 1's
orchestrator, or a test) decide what to do about it. Sources never catch
and hide their own failures.
"""


class SourceFetchError(Exception):
    """Raised by an IngestionSource when fetch() cannot return data.

    This is intentionally a plain Exception subclass (not a hierarchy of
    error types) — the orchestrator's retry/timeout wrapper only needs to
    know "this attempt failed", not the reason, and callers that do want
    the reason can read str(exc).
    """

    def __init__(self, source_name: str, reason: str = "simulated failure"):
        self.source_name = source_name
        self.reason = reason
        super().__init__(f"{source_name}: {reason}")
