"""
EmailResult — uniform return value for every send attempt.

Providers **never raise** on a failed send; they always return an
``EmailResult`` with ``success=False`` and a human-readable ``message``.
This keeps calling code branch-free and identical across providers.

The ``as_tuple()`` helper exists so consumers that model email sending as a
``(success, message, message_id)`` tuple (e.g. selfApi's ``EmailService``)
can adapt without reaching into fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class EmailResult:
    """Outcome of a single send attempt.

    Attributes
    ----------
    success:
        Whether the provider accepted the message.
    message:
        Human-readable status or error description. Never contains secrets.
    provider:
        The provider ``name`` that produced this result ("smtp"/"resend"/"api").
    message_id:
        Provider-assigned id when available (e.g. Resend's ``id``).
    status_code:
        HTTP status code for API providers; ``None`` for SMTP.
    raw:
        Parsed provider response body when available, for debugging.
    """

    success: bool
    message: str
    provider: str
    message_id: Optional[str] = None
    status_code: Optional[int] = None
    raw: Optional[Dict[str, Any]] = None

    def as_tuple(self) -> Tuple[bool, str, Optional[str]]:
        """Return ``(success, message, message_id)``."""
        return (self.success, self.message, self.message_id)

    def __bool__(self) -> bool:
        return self.success
