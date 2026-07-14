"""
EmailMessage — provider-agnostic representation of an email to send.

This dataclass is the single input type accepted by every provider
(``SMTPProvider``, ``ResendProvider``, ``HTTPAPIProvider``) and by
``EmailClient.send``. Build one of these and hand it to a client/provider;
the provider translates it into the wire format it needs (MIME for SMTP,
JSON for the HTTP APIs).

Example
-------
>>> from steely.email import EmailMessage
>>> msg = EmailMessage(
...     to=["dest@example.com"],
...     subject="Welcome",
...     body_html="<h1>Hi</h1>",
...     body_text="Hi",            # optional plain-text fallback
...     from_email="noreply@example.com",
...     from_name="ACME",
... )
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class EmailMessage:
    """A single email, independent of how it will be delivered.

    Parameters
    ----------
    to:
        Recipient address or list of addresses. A bare ``str`` is accepted and
        normalised to a one-element list.
    subject:
        The email subject line.
    body_html:
        HTML body. At least one of ``body_html`` / ``body_text`` is required.
    body_text:
        Plain-text body / fallback. Recommended alongside ``body_html`` so
        clients that cannot render HTML still show something.
    cc, bcc:
        Optional carbon-copy / blind-carbon-copy recipients.
    reply_to:
        Optional ``Reply-To`` address.
    from_email, from_name:
        Optional sender override. When omitted the provider falls back to the
        sender configured on the provider itself. ``from_name`` produces a
        ``"Name <email>"`` header/field.
    headers:
        Optional extra headers (SMTP) / ``headers`` object (Resend).
    """

    to: List[str]
    subject: str
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    reply_to: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    headers: Optional[Dict[str, str]] = None

    def __post_init__(self) -> None:
        # Accept a bare string for any recipient field for ergonomics.
        if isinstance(self.to, str):
            self.to = [self.to]
        if isinstance(self.cc, str):
            self.cc = [self.cc]
        if isinstance(self.bcc, str):
            self.bcc = [self.bcc]

        if not self.to:
            raise ValueError("EmailMessage.to must contain at least one recipient")
        if not (self.body_html or self.body_text):
            raise ValueError("EmailMessage requires body_html or body_text")

    def recipients(self) -> List[str]:
        """Return all envelope recipients (to + cc + bcc)."""
        out: List[str] = list(self.to)
        if self.cc:
            out += self.cc
        if self.bcc:
            out += self.bcc
        return out
