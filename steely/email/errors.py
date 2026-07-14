"""Exception hierarchy for :mod:`steely.email`."""
from __future__ import annotations


class EmailError(Exception):
    """Base class for all steely.email errors."""


class ProviderNotAvailableError(EmailError):
    """A provider's optional dependency is missing (e.g. ``httpx``).

    Raised at provider construction time so failures are loud and early
    rather than at send time.
    """


class EmailSendError(EmailError):
    """Raised by helpers that opt into raising instead of returning a result."""
