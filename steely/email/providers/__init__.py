"""
Email delivery providers.

- :class:`SMTPProvider`   — stdlib only, no extra dependencies.
- :class:`ResendProvider` — Resend HTTP API (needs ``steely[http]``).
- :class:`HTTPAPIProvider`— generic HTTP API (needs ``steely[http]``).

Importing this package is always safe: the ``httpx`` dependency is imported
lazily inside the HTTP providers' constructors, so ``import`` never fails when
``httpx`` is absent — only constructing an HTTP provider does.
"""
from steely.email.providers.base import EmailProvider
from steely.email.providers.http_api import HTTPAPIProvider
from steely.email.providers.resend import ResendProvider
from steely.email.providers.smtp import SMTPProvider

__all__ = ["EmailProvider", "SMTPProvider", "ResendProvider", "HTTPAPIProvider"]
