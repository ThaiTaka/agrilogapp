"""Domain errors.

Services raise these; routers translate them to HTTP. Keeping `HTTPException`
out of the service layer is what lets the same functions be called from the
seed script, the sync engine, and tests without dragging FastAPI along.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class. The message is safe to show a user."""


class NotFound(DomainError):
    """The record does not exist, or belongs to another household.

    Deliberately one error for both. Distinguishing them would confirm that a
    given ID exists somewhere in the system, which is an information leak
    across the tenant boundary — returning 404 rather than 403 is the point.
    """


class Conflict(DomainError):
    """The request contradicts existing data (duplicate, stale write)."""


class ValidationFailed(DomainError):
    """The request is well-formed but violates a business rule."""
