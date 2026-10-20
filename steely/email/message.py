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

Attachments
-----------
>>> from steely.email import Attachment, EmailMessage
>>> msg = EmailMessage(
...     to=["dest@example.com"],
...     subject="Report",
...     body_html='<p>See the attached report. <img src="cid:logo"></p>',
...     attachments=[
...         Attachment(filename="report.xlsx", content=b"...",
...                    content_type="text/csv"),
...         Attachment(filename="logo.png", content=b"...", content_type="image/png",
...                    inline=True, content_id="logo"),
...     ],
... )
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Attachment:
    """A single file to attach to an :class:`EmailMessage`.

    Parameters
    ----------
    filename:
        Name shown to the recipient.
    content:
        Raw bytes of the file. Providers encode it as needed (base64 for the
        HTTP APIs, a base64 MIME part for SMTP).
    content_type:
        MIME type such as ``"application/pdf"``. Defaults to
        ``"application/octet-stream"`` when the type is unknown.
    inline:
        When ``True`` the part is marked ``Content-Disposition: inline`` so it
        can be referenced from the HTML body instead of being listed as a
        separate download.
    content_id:
        The ``Content-ID`` used by ``<img src="cid:...">`` for inline parts.
        Ignored when ``inline`` is ``False``.
    """

    filename: str
    content: bytes
    content_type: str = "application/octet-stream"
    inline: bool = False
    content_id: str | None = None

    def mime_parts(self) -> tuple:
        """Return ``(maintype, subtype)`` derived from ``content_type``."""
        ctype = (self.content_type or "application/octet-stream").split(";")[0].strip()
        if "/" in ctype:
            maintype, _, subtype = ctype.partition("/")
        else:
            maintype, subtype = "application", "octet-stream"
        return maintype or "application", subtype or "octet-stream"


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
    attachments:
        Optional list of :class:`Attachment`. Supported by ``SMTPProvider`` and
        ``ResendProvider``; the generic HTTP provider ignores it.
    """

    to: list[str]
    subject: str
    body_html: str | None = None
    body_text: str | None = None
    cc: list[str] | None = None
    bcc: list[str] | None = None
    reply_to: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    headers: dict[str, str] | None = None
    attachments: list[Attachment] | None = None

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

    def recipients(self) -> list[str]:
        """Return all envelope recipients (to + cc + bcc)."""
        out: list[str] = list(self.to)
        if self.cc:
            out += self.cc
        if self.bcc:
            out += self.bcc
        return out
