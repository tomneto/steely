"""
steely.email — provider-agnostic email sending.

Send email over SMTP or an HTTP API (Resend, or any REST API via the generic
provider) behind one small interface.

Quick start
-----------
>>> from steely.email import EmailClient, EmailMessage
>>>
>>> # SMTP (stdlib only, no extra install)
>>> client = EmailClient(
...     "smtp",
...     server="smtp.example.com", port=587,
...     username="user@example.com", password="secret",
... )
>>>
>>> # Resend / generic HTTP API need the optional dependency:
>>> #   pip install "steely[http]"
>>> # client = EmailClient("resend", api_key="re_xxx", from_email="noreply@acme.com")
>>>
>>> msg = EmailMessage(
...     to=["dest@example.com"],
...     subject="Hello",
...     body_html="<h1>Hello</h1>",
...     body_text="Hello",
... )
>>> result = client.send(msg)          # doctest: +SKIP
>>> result.success, result.message_id  # doctest: +SKIP

See ``EMAIL_PROVIDERS.md`` for the full integration guide (intended for both
humans and coding agents consuming this library).
"""
from steely.email.client import EmailClient
from steely.email.errors import (
    EmailError,
    EmailSendError,
    ProviderNotAvailableError,
)
from steely.email.message import EmailMessage
from steely.email.providers import (
    EmailProvider,
    HTTPAPIProvider,
    ResendProvider,
    SMTPProvider,
)
from steely.email.result import EmailResult

__all__ = [
    "EmailClient",
    "EmailMessage",
    "EmailResult",
    "EmailProvider",
    "SMTPProvider",
    "ResendProvider",
    "HTTPAPIProvider",
    "EmailError",
    "ProviderNotAvailableError",
    "EmailSendError",
]
