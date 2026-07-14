"""
Provider abstraction for :mod:`steely.email`.

Every concrete provider implements this interface, so ``EmailClient`` and
consumers can treat SMTP and HTTP-API delivery identically. Adding a new
provider is: subclass :class:`EmailProvider`, implement the three members,
and (optionally) register it in ``steely.email.client._FACTORY``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from steely.email.message import EmailMessage
from steely.email.result import EmailResult


def redact(secret: Any) -> str:
    """Return a log-safe representation of a secret (``***`` + last 4 chars)."""
    if not secret:
        return "***"
    s = str(secret)
    return "***" + s[-4:] if len(s) > 4 else "***"


class EmailProvider(ABC):
    """Contract implemented by every delivery backend.

    Implementations must be safe to reuse across threads. Stateful transports
    (SMTP) should open a fresh connection per :meth:`send`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short provider identifier, e.g. ``"smtp"``, ``"resend"``, ``"api"``."""

    @abstractmethod
    def send(self, message: EmailMessage, **kwargs: Any) -> EmailResult:
        """Send ``message``. Must return an :class:`EmailResult`, never raise
        for a rejected/failed send (only for programmer errors)."""

    @abstractmethod
    def validate(self) -> bool:
        """Return ``True`` if the provider's configuration/credentials look
        usable. Must not raise; return ``False`` on any failure."""
